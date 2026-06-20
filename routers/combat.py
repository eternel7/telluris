import random
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from db.config import get_doc, save_doc, find_docs
from utils.auth import get_current_user
from utils.characters import get_selected_character
from utils.combat import (
    BATTLE_MAPS, instantiate_monsters, create_combat_doc,
    resolve_first_turns, resolve_action, finalize_combat, select_battle_map,
)

combat_router = APIRouter()


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

    nb_monstres = max(1, round(body.intensite * 3))

    especes = find_docs({"type": "espece"}) or []
    profils = find_docs({"type": "profil"}) or []

    if not especes:
        raise HTTPException(status_code=500, detail="Aucune espèce en base")

    monstres = instantiate_monsters(especes, profils, nb_monstres, body.tags)
    if not monstres:
        raise HTTPException(status_code=500, detail="Impossible d'instancier les monstres")

    # Sélection pondérée d'une battle map (lieu) selon les tags de la zone + lieu de départ.
    depart_lieu = get_doc(character.get("lieu")) if character.get("lieu") else None
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
