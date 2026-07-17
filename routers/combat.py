import os
import random
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from db.config import get_doc, save_doc, find_docs
from utils.auth import get_current_user
from utils.characters import get_selected_character, carried_weight, charge_max_of, resolve_item_ref, item_ref_weight
from utils.consommables import liste_consommables_combat
from utils.sorts import (
    normaliser_sort, sort_utilisable_combat, composants_etat, effets_effectifs,
    liste_sorts_payload,
)
from utils.competences import (
    normaliser_competence, competence_utilisable_combat, liste_competences_payload,
    furtivite_passive,
)
from routers.user import _take_ref
from utils.zones import load_zone_defs_for_lieu, compute_zone_intensity, resolve_profil_weights
from utils import focalisation
from utils import recrutement
from utils import sorts as sorts_util
from utils import competences as competences_util
from utils.combat import (
    BATTLE_MAPS, instantiate_monsters, create_combat_doc, build_monster_snapshot,
    resolve_first_turns, resolve_action, finalize_combat, select_battle_map,
)
from utils import chasse
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


def _actor_character_id(combat_doc: dict) -> str:
    """Doc personnage de l'ACTEUR COURANT du combat : le `character_id` porté par le
    snapshot du joueur dont c'est le tour (un compagnon boit SES potions, lance SES
    sorts). Repli sur le personnage principal (tour d'un monstre, doc en vol)."""
    ordre = combat_doc.get("ordre_initiative", [])
    idx = combat_doc.get("acteur_courant_index", 0)
    actor_id = ordre[idx] if 0 <= idx < len(ordre) else None
    if actor_id and str(actor_id).startswith("joueur_"):
        for j in combat_doc.get("joueurs", []):
            if j.get("id") == actor_id and j.get("character_id"):
                return j["character_id"]
    return combat_doc["character_id"]


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


class LootAttribution(BaseModel):
    monstre_id: str
    beneficiaire_id: str  # character_id d'un membre du combat (character:* ou aventurier:*)


class CollectLootRequest(BaseModel):
    # Répartition du butin entre les membres du groupe : chaque carcasse va au sac du
    # bénéficiaire choisi (borné par SA charge). `monstre_ids` = repli legacy → tout au
    # principal (compat clients/appels antérieurs à la répartition).
    attributions: list[LootAttribution] = []
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
    profil_weights = resolve_profil_weights(active_placements, depart_lieu or {})

    # Compagnons recrutés : ils entrent en combat avec le joueur — l'opposition est
    # relevée d'un monstre par tranche de 2 compagnons (à équilibrer en jeu).
    compagnons = recrutement.groupe_effectif(character, get_doc)
    nb_monstres = max(1, round(body.intensite * 3)) + len(compagnons) // 2
    # Espèces déjà filtrées par zone → pas de re-filtrage par tags (zone_tags vide).
    # Focalisation : l'espèce ciblée pèse plus lourd dans le tirage (si présente au pool).
    monstres = instantiate_monsters(
        pool_especes, profils, nb_monstres, [], profil_weights=profil_weights,
        espece_weights=focalisation.espece_weights_focus(character),
    )
    if not monstres:
        return {"combat_id": None}

    # Quêtes de « chasse » : si un combat tire NATURELLEMENT l'espèce cible dans ce lieu, UN
    # monstre de cette espèce est promu en élite — on lui applique le profil déjà résolu à la
    # génération (pas de re-résolution ici). On ne force PAS l'espèce à apparaître : si elle
    # n'est pas au pool, rien n'est marqué. La variante « rang » (comptoir) porte une narration
    # pré-combat, affichée en overlay au chargement du combat.
    chasse_narration = None
    if depart_lieu:
        marques = set()
        for q in chasse.quetes_chasse_actives(character, depart_lieu["_id"]):
            obj = q.get("objectif", {})
            espece_id, profil_id = obj.get("cible"), obj.get("profil")
            if not espece_id or not profil_id:
                continue
            # L'élite ne surgit que si le combat se déclenche dans la zone 3×3 autour de la
            # position de la quête (la carte 🗺️ y mène le joueur). Sans position → lieu seul.
            if not chasse.dans_zone_chasse(obj, character.get("position")):
                continue
            idx = next(
                (i for i, m in enumerate(monstres)
                 if m.get("espece_id") == espece_id and m["id"] not in marques),
                None,
            )
            if idx is None:
                continue
            espece_doc = next((e for e in pool_especes if e["_id"] == espece_id), None)
            profil_doc = get_doc(profil_id)
            if not espece_doc or not profil_doc:
                continue
            ancien = monstres[idx]
            elite = build_monster_snapshot(espece_doc, profil_doc, idx)
            elite["id"] = ancien["id"]
            elite["pos"] = ancien.get("pos", elite["pos"])
            elite["quete_chasse"] = q.get("id") or q.get("_id")
            monstres[idx] = elite
            marques.add(elite["id"])
            if q.get("source") == "rang" and q.get("narration"):
                chasse_narration = q["narration"]

    # Sélection pondérée d'une battle map (lieu) selon les tags de la zone + lieu de départ.
    battle_map = select_battle_map(body.tags, depart_lieu)
    map_image = battle_map.get("image") if battle_map else random.choice(BATTLE_MAPS)
    # Furtivité passive à l'entrée en combat : conditions de terrain évaluées contre les
    # tags de la battle map ∪ tags de zone (ex. Furtivité sylvestre du forestier en forêt).
    map_tags = set((battle_map or {}).get("tags", [])) | set(body.tags or [])
    furtivite = furtivite_passive(character, get_doc, map_tags)
    # Le combat référence le lieu battle map (cells non dupliqué) ; repli grille ouverte.
    combat_doc = create_combat_doc(character, monstres, body.tags, map_image,
                                   battle_map=battle_map, furtivite_initiale=furtivite,
                                   compagnons=compagnons)
    if chasse_narration:
        combat_doc["chasse_narration"] = chasse_narration
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


@combat_router.get("/combat/{combat_id}/acteur")
async def combat_acteur(
    combat_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Ressources de l'ACTEUR COURANT (principal ou compagnon) pour le client :
    consommables/sorts/compétences utilisables en combat + épinglés + portrait —
    mêmes helpers que la page /combat, le doc `aventurier:*` étant character-shaped.
    Appelé au changement d'acteur (hook client) pour recharger les sélecteurs."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Non authentifié")

    combat_doc = get_doc(combat_id)
    if not combat_doc or combat_doc.get("type") != "combat":
        raise HTTPException(status_code=404, detail="Combat introuvable")
    if combat_doc["user_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="Accès refusé")

    acteur_id = _actor_character_id(combat_doc)
    doc = get_doc(acteur_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Personnage introuvable")

    return {
        "character_id": acteur_id,
        "nom": doc.get("nom", ""),
        "prenom": doc.get("prenom", ""),
        "image": doc.get("image", ""),
        "consommables": liste_consommables_combat(doc, resolve_item_ref),
        "sorts": liste_sorts_payload(doc, get_doc, "combat"),
        "sorts_epingles": sorts_util.sorts_epingles_effectifs(doc),
        "competences": liste_competences_payload(doc, get_doc, "combat"),
        "competences_epinglees": competences_util.competences_epinglees_effectives(doc, get_doc),
    }


@combat_router.post("/combat/{combat_id}/collect")
async def collect_loot(
    combat_id: str,
    body: CollectLootRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Ramasse à la victoire les carcasses, réparties entre les membres du groupe.

    Le butin n'est jamais ajouté automatiquement : le client envoie des `attributions`
    `{monstre_id, beneficiaire_id}` (repli legacy `monstre_ids` → tout au principal).
    Chaque carcasse rejoint l'inventaire de SON bénéficiaire sous forme de référence
    {item, poids} (poids d'instance tiré au butin), borné par la charge max de ce membre.
    La garde d'idempotence `butin_collectes[combat_id]` (sur le principal) mémorise les
    carcasses encaissées → une reprise après échec partiel ne peut jamais les dupliquer.
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
    principal_id = character["_id"]

    dispo = {d["monstre_id"]: d for d in combat_doc.get("butin_disponible", [])}
    # Bénéficiaires légitimes = les membres qui ont combattu (source de vérité : joueurs[]).
    snap_par_cid = {
        j["character_id"]: j
        for j in combat_doc.get("joueurs", []) if j.get("character_id")
    }

    guard = character.get("butin_collectes", {})
    if not isinstance(guard, dict):
        guard = {}
    deja = set(guard.get(combat_id, []))

    # Repli legacy : une liste de monstre_ids nus → tout au principal.
    attributions = body.attributions or [
        LootAttribution(monstre_id=mid, beneficiaire_id=principal_id)
        for mid in (body.monstre_ids or [])
    ]

    # Regroupement par bénéficiaire ; carcasses non proposées / déjà encaissées ignorées.
    par_benef: dict[str, list[str]] = {}
    for a in attributions:
        if a.monstre_id not in dispo or a.monstre_id in deja:
            continue
        if a.beneficiaire_id not in snap_par_cid:
            raise HTTPException(status_code=422, detail="Bénéficiaire hors du groupe de combat.")
        par_benef.setdefault(a.beneficiaire_id, []).append(a.monstre_id)

    # Docs des bénéficiaires : le principal est déjà chargé (ne pas le re-fetcher → éviter
    # deux versions du même doc / conflit _rev).
    docs: dict[str, dict] = {principal_id: character}
    for cid in par_benef:
        if cid not in docs:
            d = get_doc(cid)
            if not d:
                raise HTTPException(status_code=404, detail="Bénéficiaire introuvable.")
            docs[cid] = d

    # Contrôle de charge PAR bénéficiaire — refus global (aucune carcasse encaissée) pour
    # que la validation reste atomique. charge_max = celle du snapshot (cohérente avec l'UI).
    for cid, mids in par_benef.items():
        doc = docs[cid]
        add_w = sum(dispo[mid]["poids"] for mid in mids)
        charge_max = snap_par_cid[cid].get("charge_max") or charge_max_of(doc)
        if carried_weight(doc) + add_w > charge_max + 1e-6:
            nom = snap_par_cid[cid].get("nom", "Ce personnage")
            raise HTTPException(status_code=422, detail=f"Charge maximale dépassée pour {nom}.")

    # Encaissement en mémoire.
    noms = []
    encaisses = set(deja)
    for cid, mids in par_benef.items():
        doc = docs[cid]
        inventaire = doc.get("inventaire", [])
        for mid in mids:
            # Référence {item, poids} : on conserve le poids d'instance tiré au butin.
            inventaire.append({"item": dispo[mid]["item_id"], "poids": dispo[mid]["poids"]})
            noms.append(dispo[mid]["nom"])
            encaisses.add(mid)
        doc["inventaire"] = inventaire

    # Garde d'idempotence sur le principal : on MÉMORISE les carcasses encaissées (au lieu
    # de purger) → sans atomicité multi-docs, une reprise ne peut pas re-créditer.
    guard[combat_id] = sorted(encaisses)
    character["butin_collectes"] = guard

    # Principal d'abord (il porte la garde) : si le save d'un compagnon échoue ensuite, la
    # garde est déjà posée → au pire une carcasse de compagnon est perdue, jamais dupliquée.
    if save_doc(character) is None:
        raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
    for cid, doc in docs.items():
        if cid == principal_id:
            continue
        if save_doc(doc) is None:
            raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")

    # Best-effort : refléter les carcasses encaissées sur le doc combat (cosmétique,
    # le combat est supprimé au retour sur /play). Non bloquant si la sauvegarde échoue.
    for mid in encaisses:
        for m in combat_doc["monstres"]:
            if m["id"] == mid:
                m["loote"] = True
    combat_doc["butin_disponible"] = [
        d for d in combat_doc.get("butin_disponible", []) if d["monstre_id"] not in encaisses
    ]
    save_doc(combat_doc)

    par_membre = {cid: round(carried_weight(docs[cid]), 2) for cid in par_benef}
    return {"collected": noms, "par_membre": par_membre}


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

    # Doc personnage de l'ACTEUR COURANT (principal ou compagnon `aventurier:*`) :
    # consommer/sort/compétence lisent et mutent le sac/les sorts de CE membre.
    # Résolu AVANT resolve_action (qui peut faire avancer le tour).
    acteur_id = _actor_character_id(combat_doc)

    # Action « consommer » : l'inventaire vit sur le doc character, pas dans le combat.
    # On retire la ref ICI (en mémoire seulement) et on passe le doc résolu à
    # resolve_action ; le character n'est sauvegardé qu'après le combat (voir plus bas).
    character = None
    item_doc = None
    if body.type == "consommer":
        character = get_doc(acteur_id)
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
        character = get_doc(acteur_id)
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
        character = get_doc(acteur_id)
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
                character = get_doc(acteur_id) or character
        else:
            # Action refusée : rien n'a été consommé, relire l'état réel pour le sélecteur.
            character = get_doc(acteur_id) or character
        consommables_payload = liste_consommables_combat(character, resolve_item_ref)

    # Sort réussi avec composant(s) consommé(s) : retirer les items du sac, même
    # séquence que « consommer » (échec bénin en faveur du joueur).
    sorts_payload = None
    if body.type == "sort" and character is not None:
        if "error" not in action_result:
            if sort_consomme_items and save_doc(character) is None:
                print(f"sort: échec de sauvegarde du personnage {character.get('_id')} (composants non retirés)")
                character = get_doc(acteur_id) or character
        else:
            # Action refusée : rien n'a été consommé, relire l'état réel.
            character = get_doc(acteur_id) or character
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
