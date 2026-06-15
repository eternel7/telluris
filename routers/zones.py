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
    lieu_doc["zone_influences"] = placements
    save_doc(lieu_doc)
    return {"saved": len(placements), "zone_influences": placements}
