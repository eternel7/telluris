import os
import random
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from db.config import get_doc, save_doc, find_docs
from utils.auth import get_current_user
from utils.characters import get_selected_character, carried_weight, resolve_item_ref, item_ref_weight
from utils.consommables import liste_consommables_combat
from utils.sorts import (
    normaliser_sort, sort_utilisable_combat, composants_etat, effets_effectifs,
    liste_sorts_payload,
)
from utils.competences import (
    normaliser_competence, competence_utilisable_combat, liste_competences_payload,
)
from routers.user import _take_ref
from utils.zones import load_zone_defs_for_lieu, compute_zone_intensity
from utils import focalisation
from utils.combat import (
    BATTLE_MAPS, instantiate_monsters, create_combat_doc,
    resolve_first_turns, resolve_action, finalize_combat, select_battle_map,
)
from models import character_stats

combat_router = APIRouter()

TOWNS_IMAGES_PATH = "templates/resources/towns"
# TOWN_PROFIL_NIVEAU_MAX : variable de monde (rules:world_variables), lue via
# character_stats.TOWN_PROFIL_NIVEAU_MAX pour rester vivante après un reload.


def _is_town_lieu(lieu: dict | None) -> bool:
    """Le lieu est-il associé à une image du dossier TOWNS ?"""
    img = (lieu or {}).get("image")
    return bool(img) and os.path.exists(os.path.join(TOWNS_IMAGES_PATH, img))


def _active_zone_placements(lieu: dict, character: dict) -> list:
    """Placements de zone actifs (intensité > 0) à la position du personnage.

    On renvoie les placements eux-mêmes (pas seulement les ids de def) pour pouvoir
    lire un éventuel `profil_weights` propre à l'instance de zone.
    """
    placements = lieu.get("zone_influences", [])
    if not placements:
        return []
    pos = character.get("position", {})
    px, py = pos.get("x", 0), pos.get("y", 0)
    zone_defs = load_zone_defs_for_lieu(lieu, get_doc)
    actifs = []
    for placement in placements:
        zone_def = zone_defs.get(placement.get("zone"))
        if zone_def and compute_zone_intensity(px, py, placement, zone_def) > 0.0:
            actifs.append(placement)
    return actifs


def _resolve_profil_weights(active_placements: list, lieu: dict) -> dict | None:
    """Poids de profils effectifs pour le tirage du grade des monstres.

    Chaîne (cf. design) : cumul (somme) des `profil_weights` des zones actives qui
    en définissent un → sinon `profil_weights` par défaut du lieu → sinon None
    (tirage uniforme parmi les profils). Les poids non numériques ou ≤ 0 sont ignorés.
    """
    merged: dict = {}
    for placement in active_placements:
        for pid, w in (placement.get("profil_weights") or {}).items():
            if isinstance(w, bool) or not isinstance(w, (int, float)) or w <= 0:
                continue
            merged[pid] = merged.get(pid, 0) + w
    if merged:
        return merged
    return lieu.get("profil_weights") or None


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
    mode: str | None = None
    # Action « consommer » : adressage de l'item du sac par index vérifié item_id.
    index: int | None = None
    item_id: str | None = None
    # Action « sort » : id du sort + composants à engager (ids item, re-vérifiés serveur).
    sort_id: str | None = None
    composants: list[str] = []
    # Action « competence » : id de la compétence active (re-vérifiée serveur).
    competence_id: str | None = None


class CollectLootRequest(BaseModel):
    monstre_ids: list[str] = []


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
    active_placements = _active_zone_placements(depart_lieu, character) if depart_lieu else []
    actives = {p.get("zone") for p in active_placements}
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
        profils = [p for p in profils_all if p.get("niveau", 1) <= character_stats.TOWN_PROFIL_NIVEAU_MAX]

    # Distribution de grades (profils) : override des zones actives, sinon défaut lieu.
    profil_weights = _resolve_profil_weights(active_placements, depart_lieu or {})

    nb_monstres = max(1, round(body.intensite * 3))
    # Espèces déjà filtrées par zone → pas de re-filtrage par tags (zone_tags vide).
    # Focalisation : l'espèce ciblée pèse plus lourd dans le tirage (si présente au pool).
    monstres = instantiate_monsters(
        pool_especes, profils, nb_monstres, [], profil_weights=profil_weights,
        espece_weights=focalisation.espece_weights_focus(character),
    )
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


@combat_router.post("/combat/{combat_id}/collect")
async def collect_loot(
    combat_id: str,
    body: CollectLootRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Ramasse à la victoire les carcasses sélectionnées par le joueur.

    Le butin n'est jamais ajouté automatiquement : le client envoie la liste des
    `monstre_ids` choisis. Chaque carcasse est ajoutée à l'inventaire sous forme de
    référence {item, poids} (poids d'instance tiré au butin). La somme des poids
    ajoutés ne peut faire dépasser la charge max. Une fois le butin validé et
    l'inventaire mis à jour, l'entrée `butin_collectes[combat_id]` est purgée du
    personnage (pas de garde persistante ; le doc combat est supprimé au retour /play).
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Non authentifié")

    combat_doc = get_doc(combat_id)
    if not combat_doc or combat_doc.get("type") != "combat":
        raise HTTPException(status_code=404, detail="Combat introuvable")
    if combat_doc["user_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    if combat_doc.get("status") != "victoire":
        raise HTTPException(status_code=400, detail="Butin disponible uniquement après une victoire.")

    character = get_doc(combat_doc["character_id"])
    if not character:
        raise HTTPException(status_code=404, detail="Personnage introuvable")

    dispo = {d["monstre_id"]: d for d in combat_doc.get("butin_disponible", [])}
    charge_max = combat_doc["joueurs"][0].get("charge_max", 0)

    guard = character.get("butin_collectes", {})
    if not isinstance(guard, dict):
        guard = {}
    deja = set(guard.get(combat_id, []))

    # Sélection valide = carcasses proposées, pas encore encaissées.
    selected = [mid for mid in (body.monstre_ids or []) if mid in dispo and mid not in deja]
    add_w = sum(dispo[mid]["poids"] for mid in selected)
    current_w = carried_weight(character)
    if selected and current_w + add_w > charge_max + 1e-6:
        raise HTTPException(status_code=422, detail="Charge maximale dépassée.")

    inventaire = character.get("inventaire", [])
    noms = []
    for mid in selected:
        # Référence {item, poids} : on conserve le poids d'instance tiré au butin.
        inventaire.append({"item": dispo[mid]["item_id"], "poids": dispo[mid]["poids"]})
        noms.append(dispo[mid]["nom"])
    character["inventaire"] = inventaire

    encaisses = deja | set(selected)
    # Le butin est validé : on purge la garde de ce combat (plus de trace persistante
    # sur le personnage une fois l'inventaire mis à jour). Sauvé dans le même doc.
    guard.pop(combat_id, None)
    character["butin_collectes"] = guard

    if save_doc(character) is None:
        raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")

    # Best-effort : refléter les carcasses encaissées sur le doc combat (cosmétique,
    # le combat est supprimé au retour sur /play). Non bloquant si la sauvegarde échoue.
    for mid in selected:
        for m in combat_doc["monstres"]:
            if m["id"] == mid:
                m["loote"] = True
    combat_doc["butin_disponible"] = [
        d for d in combat_doc.get("butin_disponible", []) if d["monstre_id"] not in encaisses
    ]
    save_doc(combat_doc)

    return {"collected": noms, "charge": round(current_w + add_w, 2), "charge_max": charge_max}


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

    # Action « consommer » : l'inventaire vit sur le doc character, pas dans le combat.
    # On retire la ref ICI (en mémoire seulement) et on passe le doc résolu à
    # resolve_action ; le character n'est sauvegardé qu'après le combat (voir plus bas).
    character = None
    item_doc = None
    if body.type == "consommer":
        character = get_doc(combat_doc["character_id"])
        if not character:
            raise HTTPException(status_code=404, detail="Personnage introuvable")
        inventaire = character.get("inventaire", [])
        ref = _take_ref(inventaire, body.index, body.item_id)
        if ref is None:
            raise HTTPException(status_code=422, detail="Objet absent de l'inventaire")
        item_doc = resolve_item_ref(ref)  # poids d'instance scalaire, `effets` préservé
        if item_doc is None:
            raise HTTPException(status_code=422, detail="Objet introuvable")
        character["inventaire"] = inventaire

    # Action « sort » : le sort est re-vérifié serveur (connu + utilisable en combat),
    # les composants engagés aussi (indisponibles ignorés = mode dégradé) ; les
    # composants CONSOMMÉS sont retirés du sac ICI (en mémoire seulement), le character
    # n'est sauvegardé qu'après le combat (même séquence que « consommer »).
    sort_arg = None
    sort_consomme_items = False
    if body.type == "sort":
        character = get_doc(combat_doc["character_id"])
        if not character:
            raise HTTPException(status_code=404, detail="Personnage introuvable")
        if body.sort_id not in (character.get("sorts_connus") or []):
            raise HTTPException(status_code=422, detail="Sort inconnu du personnage")
        sort_norm = normaliser_sort(get_doc(body.sort_id))
        if sort_norm is None or not sort_utilisable_combat(sort_norm):
            raise HTTPException(status_code=422, detail="Sort inutilisable en combat")
        etat = {c["item"]: c for c in composants_etat(sort_norm, character)}
        inventaire = character.get("inventaire", [])
        engages: list = []
        poids_consommes = 0.0
        for cid in (body.composants or []):
            c = etat.get(cid)
            if not c or not c["disponible"] or cid in engages:
                continue
            if c["consomme"]:
                ref = _take_ref(inventaire, None, cid)
                if ref is None:
                    continue
                poids_consommes += item_ref_weight(ref)
                sort_consomme_items = True
            engages.append(cid)
        character["inventaire"] = inventaire
        sort_arg = {
            "doc": sort_norm,
            "effets": effets_effectifs(sort_norm, engages),
            "composants_engages": engages,
            "poids_consommes": round(poids_consommes, 2),
        }

    # Action « compétence » : re-vérifiée serveur (connue + active + utilisable en combat).
    # Bien plus simple qu'un sort : aucun composant, donc aucune mutation d'inventaire. Les PM
    # vivent sur le snapshot du combat et sont réécrits sur le personnage par finalize_combat.
    competence_arg = None
    if body.type == "competence":
        character = get_doc(combat_doc["character_id"])
        if not character:
            raise HTTPException(status_code=404, detail="Personnage introuvable")
        if body.competence_id not in (character.get("competences_connues") or []):
            raise HTTPException(status_code=422, detail="Compétence inconnue du personnage")
        competence_arg = normaliser_competence(get_doc(body.competence_id))
        if competence_arg is None or not competence_utilisable_combat(competence_arg):
            raise HTTPException(status_code=422, detail="Compétence inutilisable en combat")

    action_result = resolve_action(combat_doc, body.type, body.cible_id, body.dx, body.dy, body.sens, body.mode, item=item_doc, sort=sort_arg, competence=competence_arg)

    # Persist the combat state first (source of truth). couchdb2 met à jour le
    # _rev en place ; un échec (conflit 409) renvoie None → on prévient le client
    # au lieu de laisser le doc DB et l'UI se désynchroniser silencieusement.
    saved = save_doc(combat_doc)
    if saved is None:
        raise HTTPException(
            status_code=409,
            detail="Conflit de sauvegarde — le combat a été rechargé.",
        )

    # Consommation réussie : retirer l'item du sac, APRÈS le combat (409 combat → rien
    # n'est perdu, l'item reste au sac) mais AVANT finalize_combat (qui relit le
    # character frais). Un échec ici est bénin et en faveur du joueur (soin acquis,
    # potion gardée, borné par le budget d'action) : on ne fait pas échouer la requête.
    consommables_payload = None
    if body.type == "consommer" and character is not None:
        if "error" not in action_result:
            if save_doc(character) is None:
                print(f"consommer: échec de sauvegarde du personnage {character.get('_id')} (item non retiré)")
                character = get_doc(combat_doc["character_id"]) or character
        else:
            # Action refusée : rien n'a été consommé, relire l'état réel pour le sélecteur.
            character = get_doc(combat_doc["character_id"]) or character
        consommables_payload = liste_consommables_combat(character, resolve_item_ref)

    # Sort réussi avec composant(s) consommé(s) : retirer les items du sac, même
    # séquence que « consommer » (échec bénin en faveur du joueur).
    sorts_payload = None
    if body.type == "sort" and character is not None:
        if "error" not in action_result:
            if sort_consomme_items and save_doc(character) is None:
                print(f"sort: échec de sauvegarde du personnage {character.get('_id')} (composants non retirés)")
                character = get_doc(combat_doc["character_id"]) or character
        else:
            # Action refusée : rien n'a été consommé, relire l'état réel.
            character = get_doc(combat_doc["character_id"]) or character
        sorts_payload = liste_sorts_payload(character, get_doc, "combat")

    # Combat persisté : applique les récompenses au personnage (idempotent).
    if combat_doc["status"] != "active":
        finalize_combat(combat_doc)
        save_doc(combat_doc)  # persiste le flag recompense_appliquee

    response = {"combat": combat_doc, "action_result": action_result}
    if consommables_payload is not None:
        response["consommables"] = consommables_payload
    if sorts_payload is not None:
        response["sorts"] = sorts_payload
    return response
