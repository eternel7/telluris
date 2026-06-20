import os
import random
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from db.config import get_doc, save_doc, find_docs
from utils.auth import get_current_user
from utils.characters import get_selected_character
from utils.zones import load_zone_defs_for_lieu, compute_zone_intensity
from utils.combat import (
    BATTLE_MAPS, instantiate_monsters, create_combat_doc,
    resolve_first_turns, resolve_action, finalize_combat, select_battle_map,
)

combat_router = APIRouter()

TOWNS_IMAGES_PATH = "templates/resources/towns"
TOWN_PROFIL_NIVEAU_MAX = 2  # Dans une ville, monstres de profil 1 à 2 max.


def _is_town_lieu(lieu: dict | None) -> bool:
    """Le lieu est-il associé à une image du dossier TOWNS ?"""
    img = (lieu or {}).get("image")
    return bool(img) and os.path.exists(os.path.join(TOWNS_IMAGES_PATH, img))


def _active_zone_ids(lieu: dict, character: dict) -> set:
    """Ids des zones-defs actives à la position du personnage dans le lieu."""
    placements = lieu.get("zone_influences", [])
    if not placements:
        return set()
    pos = character.get("position", {})
    px, py = pos.get("x", 0), pos.get("y", 0)
    zone_defs = load_zone_defs_for_lieu(lieu, get_doc)
    actives = set()
    for placement in placements:
        zone_def = zone_defs.get(placement.get("zone"))
        if zone_def and compute_zone_intensity(px, py, placement, zone_def) > 0.0:
            actives.add(placement.get("zone"))
    return actives


class StartCombatRequest(BaseModel):
    tags: list[str] = []
    intensite: float = 0.5
    modificateurs: dict = {}


class ActionRequest(BaseModel):
    type: str
    cible_id: str | None = None
    dx: int | None = None
    dy: int | None = None
    sens: int | None = None


@combat_router.post("/combat/start")
async def start_combat(
    body: StartCombatRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Non authentifié")

    character = get_selected_character(current_user)
    if not character:
        raise HTTPException(status_code=404, detail="Personnage introuvable")

    # Anti-doublon : si un combat est déjà actif pour ce personnage, le reprendre.
    existing = find_docs({"type": "combat", "user_id": current_user["_id"]}) or []
    for c in existing:
        if c.get("character_id") == character["_id"] and c.get("status") == "active":
            return {"combat_id": c["_id"]}

    especes_all = find_docs({"type": "espece"}) or []
    profils_all = find_docs({"type": "profil"}) or []
    if not especes_all:
        raise HTTPException(status_code=500, detail="Aucune espèce en base")

    depart_lieu = get_doc(character.get("lieu")) if character.get("lieu") else None

    # Espèces rencontrables = celles du lieu dont une zone concernée est active à la
    # position du personnage (rencontres: [{espece, zones:[zone_def_id]}]).
    actives = _active_zone_ids(depart_lieu, character) if depart_lieu else set()
    rencontres = (depart_lieu or {}).get("rencontres", [])
    espece_ids = {
        r["espece"] for r in rencontres
        if r.get("espece") and (set(r.get("zones", [])) & actives)
    }
    pool_especes = [e for e in especes_all if e["_id"] in espece_ids]

    # Aucune espèce associée aux zones actives → pas de combat.
    if not pool_especes:
        return {"combat_id": None}

    # Dans une ville (image TOWNS) : profils de niveau 1 à 2 max.
    profils = profils_all
    if _is_town_lieu(depart_lieu):
        profils = [p for p in profils_all if p.get("niveau", 1) <= TOWN_PROFIL_NIVEAU_MAX]

    nb_monstres = max(1, round(body.intensite * 3))
    # Espèces déjà filtrées par zone → pas de re-filtrage par tags (zone_tags vide).
    monstres = instantiate_monsters(pool_especes, profils, nb_monstres, [])
    if not monstres:
        return {"combat_id": None}

    # Sélection pondérée d'une battle map (lieu) selon les tags de la zone + lieu de départ.
    battle_map = select_battle_map(body.tags, depart_lieu)
    map_image = battle_map.get("image") if battle_map else random.choice(BATTLE_MAPS)
    # Le combat référence le lieu battle map (cells non dupliqué) ; repli grille ouverte.
    combat_doc = create_combat_doc(character, monstres, body.tags, map_image, battle_map=battle_map)
    resolve_first_turns(combat_doc)  # no-op if player goes first
    # Cas limite : les monstres terminent déjà le combat au 1er tour.
    if combat_doc["status"] != "active":
        finalize_combat(combat_doc)
    save_doc(combat_doc)

    return {"combat_id": combat_doc["_id"]}


@combat_router.get("/combat/{combat_id}")
async def get_combat(
    combat_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Non authentifié")

    combat_doc = get_doc(combat_id)
    if not combat_doc or combat_doc.get("type") != "combat":
        raise HTTPException(status_code=404, detail="Combat introuvable")

    if combat_doc["user_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="Accès refusé")

    return combat_doc


@combat_router.post("/combat/{combat_id}/action")
async def combat_action(
    combat_id: str,
    body: ActionRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Non authentifié")

    combat_doc = get_doc(combat_id)
    if not combat_doc or combat_doc.get("type") != "combat":
        raise HTTPException(status_code=404, detail="Combat introuvable")

    if combat_doc["user_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="Accès refusé")

    if combat_doc["status"] != "active":
        raise HTTPException(status_code=400, detail="Ce combat est terminé")

    action_result = resolve_action(combat_doc, body.type, body.cible_id, body.dx, body.dy, body.sens)

    # Persist the combat state first (source of truth). couchdb2 met à jour le
    # _rev en place ; un échec (conflit 409) renvoie None → on prévient le client
    # au lieu de laisser le doc DB et l'UI se désynchroniser silencieusement.
    saved = save_doc(combat_doc)
    if saved is None:
        raise HTTPException(
            status_code=409,
            detail="Conflit de sauvegarde — le combat a été rechargé.",
        )

    # Combat persisté : applique les récompenses au personnage (idempotent).
    if combat_doc["status"] != "active":
        finalize_combat(combat_doc)
        save_doc(combat_doc)  # persiste le flag recompense_appliquee

    return {"combat": combat_doc, "action_result": action_result}
