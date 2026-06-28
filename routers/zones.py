from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Body
from urllib.parse import unquote
from db.config import get_doc, save_doc, find_docs, delete_doc
from utils.auth import get_current_user
from utils.zones import compute_bbox

zones_router = APIRouter()


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
async def list_zones(current_user: Annotated[dict, Depends(get_current_user)]):
    _require_admin(current_user)
    return find_docs({"type": "zone_influence"}) or []


@zones_router.get("/zones/{zone_id:path}")
async def get_zone(zone_id: str, current_user: Annotated[dict, Depends(get_current_user)]):
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
        # Override de grades propre à l'instance (optionnel) : normalisé, retiré si vide.
        pw = _clean_profil_weights(p.get("profil_weights"))
        if pw:
            p["profil_weights"] = pw
        else:
            p.pop("profil_weights", None)
    lieu_doc["zone_influences"] = placements
    save_doc(lieu_doc)
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


@zones_router.get("/items")
async def list_items(
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
