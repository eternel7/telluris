from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Body
from urllib.parse import unquote
from db.config import get_doc, save_doc, find_docs, delete_doc
from utils.auth import get_current_user
from utils import zones as zones_util
from utils.zones import compute_bbox

zones_router = APIRouter()

# Champs d'un doc zone que /admin/zones sait éditer : fusionnés sur le doc RELU (jamais un PUT
# complet — CLAUDE.md §11), le reste du doc est gardé tel quel.
CHAMPS_ZONE_EDITABLES = ("nom", "intensite_max", "terrain_tags", "modificateurs", "table_evenements",
                         "defauts_rencontres", "defauts_ressources")


def _require_admin(current_user: dict):
    if not current_user or current_user.get("admin") != 1:
        raise HTTPException(status_code=403, detail="Admin only")


def _clean_profil_weights(raw) -> dict:
    """Normalise une table {profil_id: poids} : ne garde que les poids numériques > 0."""
    out = {}
    if isinstance(raw, dict):
        for pid, w in raw.items():
            if pid and isinstance(w, (int, float)) and not isinstance(w, bool) and w > 0:
                out[pid] = w
    return out


@zones_router.get("/zones")
def list_zones(current_user: Annotated[dict, Depends(get_current_user)]):
    _require_admin(current_user)
    return find_docs({"type": "zone_influence"}) or []


@zones_router.get("/zones/{zone_id:path}")
def get_zone(zone_id: str, current_user: Annotated[dict, Depends(get_current_user)]):
    _require_admin(current_user)
    doc = get_doc(unquote(zone_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Zone not found")
    return doc


@zones_router.post("/zones")
async def create_zone(
    current_user: Annotated[dict, Depends(get_current_user)],
    zone_data: dict = Body(...),
):
    _require_admin(current_user)
    zone_id = zone_data.get("_id", "")
    if not zone_id.startswith("zone::"):
        raise HTTPException(status_code=422, detail="_id must start with 'zone::'")
    zone_data["type"] = "zone_influence"
    save_doc(zone_data)
    return zone_data


@zones_router.put("/zones/{zone_id:path}")
async def update_zone(
    zone_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    zone_data: dict = Body(...),
):
    _require_admin(current_user)
    existing = get_doc(unquote(zone_id))
    if not existing:
        raise HTTPException(status_code=404, detail="Zone not found")
    zone_data["_id"] = existing["_id"]
    zone_data["_rev"] = existing["_rev"]
    zone_data["type"] = "zone_influence"
    save_doc(zone_data)
    return zone_data


@zones_router.delete("/zones/{zone_id:path}")
async def remove_zone(zone_id: str, current_user: Annotated[dict, Depends(get_current_user)]):
    _require_admin(current_user)
    doc = get_doc(unquote(zone_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Zone not found")
    delete_doc(doc)
    return {"deleted": zone_id}


@zones_router.put("/lieu/{lieu_id:path}/zone_influences")
async def update_lieu_zone_influences(
    lieu_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    body: dict = Body(...),
):
    _require_admin(current_user)
    lieu_doc = get_doc(unquote(lieu_id))
    if not lieu_doc:
        raise HTTPException(status_code=404, detail="Lieu not found")
    placements = body.get("zone_influences", [])
    for p in placements:
        p["bbox"] = compute_bbox(p)
        # Contenu PROPRE du placement (espèces / ressources de sa seule forme) : listes d'ids
        # propres, et jamais la `_cle` de lecture de `peupler_lieu`.
        zones_util.normaliser_contenu_placement(p)
        # Override de grades propre à l'instance (optionnel) : normalisé, retiré si vide.
        pw = _clean_profil_weights(p.get("profil_weights"))
        if pw:
            p["profil_weights"] = pw
        else:
            p.pop("profil_weights", None)
    lieu_doc["zone_influences"] = placements
    # ⚠️ `save_doc` avale le conflit de révision et renvoie None : sans ce contrôle, l'endpoint
    # répondait 200 sans avoir rien écrit. Le redimensionnement de grille enchaîne sur cet appel
    # et doit pouvoir dire à l'admin que les zones n'ont PAS suivi la carte.
    if save_doc(lieu_doc) is None:
        raise HTTPException(status_code=409, detail="Conflit de sauvegarde — rechargez et réessayez.")
    return {"saved": len(placements), "zone_influences": placements}


@zones_router.put("/lieu/{lieu_id:path}/rencontres")
async def update_lieu_rencontres(
    lieu_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    body: dict = Body(...),
):
    """Espèces rencontrables sur le lieu. Chaque entrée : {espece, zones:[zone_def_id]}.

    On ne référence que l'id de la zone-def (pas un placement) → toutes les instances
    d'une même zone partagent les espèces applicables.
    """
    _require_admin(current_user)
    lieu_doc = get_doc(unquote(lieu_id))
    if not lieu_doc:
        raise HTTPException(status_code=404, detail="Lieu not found")
    rencontres = body.get("rencontres", [])
    # Normalisation défensive.
    clean = [
        {"espece": r.get("espece"), "zones": list(r.get("zones", []))}
        for r in rencontres if r.get("espece")
    ]
    lieu_doc["rencontres"] = clean
    # Distribution de grades (profils) par défaut du lieu (optionnelle) : {profil_id: poids>0}.
    if "profil_weights" in body:
        lieu_doc["profil_weights"] = _clean_profil_weights(body.get("profil_weights"))
    save_doc(lieu_doc)
    return {
        "saved": len(clean),
        "rencontres": clean,
        "profil_weights": lieu_doc.get("profil_weights", {}),
    }


@zones_router.put("/lieu/{lieu_id:path}/ressources")
async def update_lieu_ressources(
    lieu_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    body: dict = Body(...),
):
    """Ressources récoltables sur le lieu. Chaque entrée : {ressource: "item:x", zones:[zone_def_id]}.

    Strictement parallèle à `rencontres` (monstres par zone) : on ne référence que l'id de
    la zone-def. Sert de source aux quêtes de collecte (cf. utils/quetes.py).
    """
    _require_admin(current_user)
    lieu_doc = get_doc(unquote(lieu_id))
    if not lieu_doc:
        raise HTTPException(status_code=404, detail="Lieu not found")
    ressources = body.get("ressources", [])
    clean = [
        {"ressource": r.get("ressource"), "zones": list(r.get("zones", []))}
        for r in ressources if r.get("ressource")
    ]
    lieu_doc["ressources"] = clean
    save_doc(lieu_doc)
    return {"saved": len(clean), "ressources": clean}


@zones_router.put("/lieu/{lieu_id:path}/exclusions")
async def update_lieu_exclusions(
    lieu_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    body: dict = Body(...),
):
    """Défauts de zones RETIRÉS de ce lieu : `exclusions: [{espece|ressource, zones?}]` (sans
    `zones` : toutes ses zones) et `sans_defauts` (tag `sans_defauts_zones` : plus aucun défaut).
    Fusion sur le doc relu ; 409 si la sauvegarde échoue."""
    _require_admin(current_user)
    lieu_doc = get_doc(unquote(lieu_id))
    if not lieu_doc:
        raise HTTPException(status_code=404, detail="Lieu not found")
    exclusions = zones_util.normaliser_exclusions(body.get("exclusions"))
    if exclusions:
        lieu_doc["exclusions"] = exclusions
    else:
        lieu_doc.pop("exclusions", None)
    if "sans_defauts" in body:
        tags = [t for t in (lieu_doc.get("tags") or []) if t != zones_util.TAG_SANS_DEFAUTS]
        if body.get("sans_defauts"):
            tags.append(zones_util.TAG_SANS_DEFAUTS)
        lieu_doc["tags"] = tags
    if save_doc(lieu_doc) is None:
        raise HTTPException(status_code=409, detail="Conflit de sauvegarde — rechargez et réessayez.")
    return {"exclusions": exclusions,
            "sans_defauts": zones_util.TAG_SANS_DEFAUTS in (lieu_doc.get("tags") or [])}


@zones_router.put("/lieu/{lieu_id:path}/entrees")
async def update_lieu_entrees(
    lieu_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    body: dict = Body(...),
):
    """Cases d'entrée d'un lieu modèle de colonisation (carte 🚪 de /admin/editor) : n'écrit
    QUE `entrees`, sur le doc relu ; chaque case éprouvée sur les `cells` EN BASE (422)."""
    from utils import colonisation
    _require_admin(current_user)
    lieu_doc = get_doc(unquote(lieu_id))
    if not lieu_doc:
        raise HTTPException(status_code=404, detail="Lieu not found")
    entrees, erreur = colonisation.normaliser_entrees(lieu_doc, body.get("entrees"))
    if erreur:
        raise HTTPException(status_code=422, detail=erreur)
    if entrees:
        lieu_doc["entrees"] = entrees
    else:
        lieu_doc.pop("entrees", None)
    if save_doc(lieu_doc) is None:
        raise HTTPException(status_code=409, detail="Conflit de sauvegarde — rechargez et réessayez.")
    return {"entrees": entrees, "_rev": lieu_doc.get("_rev")}


# ── /admin/zones : défauts, usage, doc zone, régions, aperçu d'un lieu ─────────

def _lieux_a_zones() -> list:
    """Lieux qui posent au moins une zone (projection légère : jamais les `cells`)."""
    lieux = find_docs({"type": "lieu"}, ["_id", "label", "nom", "zone_influences"]) or []
    return [l for l in lieux if l.get("zone_influences")]


@zones_router.get("/zones-admin/catalogue")
def zones_admin_catalogue(current_user: Annotated[dict, Depends(get_current_user)]):
    """Tout ce que lit /admin/zones : zones (+ usage), régions, et les listes d'espèces /
    d'items / de lieux pour les sélecteurs."""
    _require_admin(current_user)
    lieux = _lieux_a_zones()
    usage = zones_util.usage_des_zones(lieux)
    zones = sorted(find_docs({"type": "zone_influence"}) or [], key=lambda z: z.get("_id", ""))
    for z in zones:
        z["usage"] = usage.get(z.get("_id"), [])
    regles = get_doc(zones_util.REGLES_REGIONS) or {}
    especes = find_docs({"type": "espece"}, ["_id", "nom"]) or []
    items = find_docs({"type": "item"}, ["_id", "nom", "categorie"]) or []
    tous_lieux = find_docs({"type": "lieu"}, ["_id", "label", "nom", "categorie"]) or []
    return {
        "zones": zones,
        "regions": regles.get("regions") or {},
        "especes": sorted(({"id": e["_id"], "nom": e.get("nom") or e["_id"]} for e in especes),
                          key=lambda e: e["nom"].lower()),
        "items": sorted(({"id": i["_id"], "nom": i.get("nom") or i["_id"], "categorie": i.get("categorie") or ""}
                         for i in items), key=lambda i: i["nom"].lower()),
        "lieux_a_zones": sorted(({"id": l["_id"], "label": l.get("label") or l.get("nom") or l["_id"],
                                  "placements": len(l["zone_influences"])} for l in lieux),
                                key=lambda l: l["label"].lower()),
        "pays": sorted(({"id": l["_id"], "label": l.get("label") or l.get("nom") or l["_id"]}
                        for l in tous_lieux if l.get("categorie") == "pays"), key=lambda l: l["label"].lower()),
    }


@zones_router.get("/zones-admin/apercu/{lieu_id:path}")
def zones_admin_apercu(lieu_id: str, current_user: Annotated[dict, Depends(get_current_user)]):
    """Aperçu LECTURE SEULE du contenu effectif d'un lieu, zone par zone, avec la provenance."""
    _require_admin(current_user)
    lieu = get_doc(unquote(lieu_id))
    if not lieu:
        raise HTTPException(status_code=404, detail="Lieu not found")
    zone_defs = zones_util.load_zone_defs_for_lieu(lieu, get_doc)
    region = zones_util.region_de(lieu, get_doc(zones_util.REGLES_REGIONS), get_doc)
    out = zones_util.apercu_lieu(lieu, zone_defs, region)
    out["label"] = lieu.get("label") or lieu.get("nom") or lieu["_id"]
    out["exclusions"] = lieu.get("exclusions") or []
    return out


def _valider_zone(body: dict) -> dict:
    """Champs éditables validés (422 sinon) ; seuls ceux présents dans `body` sont rendus."""
    out = {}
    try:
        if "nom" in body:
            out["nom"] = str(body.get("nom") or "").strip()[:80]
            if not out["nom"]:
                raise ValueError("nom vide")
        if "intensite_max" in body:
            v = body.get("intensite_max")
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1:
                raise ValueError("intensite_max doit être un nombre entre 0 et 1")
            out["intensite_max"] = v
        if "terrain_tags" in body:
            raw = body.get("terrain_tags")
            if not isinstance(raw, list):
                raise ValueError("terrain_tags doit être une liste")
            out["terrain_tags"] = list(dict.fromkeys(str(t).strip() for t in raw if str(t or "").strip()))
        if "modificateurs" in body:
            raw = body.get("modificateurs")
            if not isinstance(raw, dict) or not all(isinstance(v, (int, float, bool)) for v in raw.values()):
                raise ValueError("modificateurs : objet {clé: nombre ou booléen}")
            out["modificateurs"] = raw
        if "table_evenements" in body:
            raw = body.get("table_evenements")
            if not isinstance(raw, list):
                raise ValueError("table_evenements doit être une liste")
            for e in raw:
                if not isinstance(e, dict) or not str(e.get("type") or "").strip():
                    raise ValueError("chaque événement porte un `type`")
                p = e.get("poids", 1)
                if isinstance(p, bool) or not isinstance(p, (int, float)) or p < 0:
                    raise ValueError("`poids` d'un événement : nombre ≥ 0")
                if "tags" in e and not isinstance(e["tags"], list):
                    raise ValueError("`tags` d'un événement : liste")
            out["table_evenements"] = raw
        for champ, cle, champ_defaut in zones_util.CHAMPS_CONTENU:
            if champ_defaut in body:
                out[champ_defaut] = zones_util.normaliser_defauts(body.get(champ_defaut), cle)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return out


@zones_router.put("/zones-admin/zone/{zone_id:path}")
async def zones_admin_modifier(
    zone_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    body: dict = Body(...),
):
    """Fusionne les champs éditables sur le doc zone RELU (le reste est gardé) ; 409 en conflit."""
    _require_admin(current_user)
    zone = get_doc(unquote(zone_id))
    if not zone or zone.get("type") != "zone_influence":
        raise HTTPException(status_code=404, detail="Zone introuvable")
    zone.update(_valider_zone({k: v for k, v in body.items() if k in CHAMPS_ZONE_EDITABLES}))
    zone.pop("usage", None)
    if save_doc(zone) is None:
        raise HTTPException(status_code=409, detail="Conflit de sauvegarde — rechargez et réessayez.")
    return zone


@zones_router.post("/zones-admin/zone")
async def zones_admin_creer(
    current_user: Annotated[dict, Depends(get_current_user)],
    body: dict = Body(...),
):
    """Nouvelle zone `zone:<slug>` ; refuse un `_id` déjà pris (jamais d'écrasement)."""
    import re
    _require_admin(current_user)
    zid = str(body.get("_id") or "").strip()
    if not re.fullmatch(r"zone:[a-z0-9_]+", zid):
        raise HTTPException(status_code=422, detail="Identifiant attendu : zone:<lettres_chiffres_soulignés>")
    if get_doc(zid):
        raise HTTPException(status_code=409, detail=f"{zid} existe déjà")
    doc = {"_id": zid, "type": "zone_influence", "nom": zid.split(":", 1)[1].replace("_", " ").capitalize(),
           "intensite_max": 0.5, "terrain_tags": [], "modificateurs": {},
           "table_evenements": [{"type": "combat", "poids": 30}, {"type": "ressource", "poids": 40},
                                {"type": "rien", "poids": 30}],
           "defauts_rencontres": [], "defauts_ressources": []}
    doc.update(_valider_zone({k: v for k, v in body.items() if k in CHAMPS_ZONE_EDITABLES}))
    if save_doc(doc) is None:
        raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
    doc["usage"] = []
    return doc


@zones_router.delete("/zones-admin/zone/{zone_id:path}")
async def zones_admin_supprimer(zone_id: str, current_user: Annotated[dict, Depends(get_current_user)]):
    """Supprime une zone qu'AUCUN lieu ne pose (409 sinon, avec les lieux) : un placement orphelin
    serait ignoré en silence par tous les tirages."""
    _require_admin(current_user)
    zone = get_doc(unquote(zone_id))
    if not zone or zone.get("type") != "zone_influence":
        raise HTTPException(status_code=404, detail="Zone introuvable")
    usage = zones_util.usage_des_zones(_lieux_a_zones()).get(zone["_id"])
    if usage:
        noms = ", ".join(u["label"] for u in usage)
        raise HTTPException(status_code=409, detail=f"Zone posée sur : {noms}. Retirez ses placements d'abord.")
    delete_doc(zone)
    return {"deleted": zone["_id"]}


@zones_router.put("/zones-admin/regions")
async def zones_admin_regions(
    current_user: Annotated[dict, Depends(get_current_user)],
    body: dict = Body(...),
):
    """Remplace les `regions` de `rules:regions` (le reste du doc est gardé) ; 409 en conflit."""
    _require_admin(current_user)
    try:
        regions = zones_util.normaliser_regions(body.get("regions"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    doc = get_doc(zones_util.REGLES_REGIONS) or {"_id": zones_util.REGLES_REGIONS, "type": "rules"}
    doc["regions"] = regions
    if save_doc(doc) is None:
        raise HTTPException(status_code=409, detail="Conflit de sauvegarde — rechargez et réessayez.")
    return {"regions": regions}


@zones_router.get("/items")
def list_items(
    current_user: Annotated[dict, Depends(get_current_user)],
    categorie: str | None = None,
    sous_categorie: str | None = None,
):
    """Liste des items (pour le picker de ressources de l'éditeur). Filtrable par
    `categorie` / `sous_categorie`. Miroir de GET /especes."""
    _require_admin(current_user)
    selector = {"type": "item"}
    if categorie:
        selector["categorie"] = categorie
    if sous_categorie:
        selector["sous_categorie"] = sous_categorie
    return find_docs(selector) or []
