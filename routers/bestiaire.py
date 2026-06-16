import os
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Body
from urllib.parse import unquote
from db.config import get_doc, save_doc, find_docs, delete_doc
from utils.auth import get_current_user

bestiaire_router = APIRouter()

MONSTERS_PATH = "templates/resources/monsters"
VALID_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


def _require_admin(current_user: dict):
    if not current_user or current_user.get("admin") != 1:
        raise HTTPException(status_code=403, detail="Admin only")


# ── IMAGES ────────────────────────────────────────────────────────────────────

@bestiaire_router.get("/bestiaire/images")
async def list_monster_images(current_user: Annotated[dict, Depends(get_current_user)]):
    _require_admin(current_user)
    if not os.path.exists(MONSTERS_PATH):
        return []
    return sorted(
        f for f in os.listdir(MONSTERS_PATH)
        if os.path.isfile(os.path.join(MONSTERS_PATH, f))
        and f.lower().endswith(VALID_EXTENSIONS)
    )


# ── ESPECES ───────────────────────────────────────────────────────────────────

@bestiaire_router.get("/especes")
async def list_especes(current_user: Annotated[dict, Depends(get_current_user)]):
    _require_admin(current_user)
    return find_docs({"type": "espece"}) or []


@bestiaire_router.get("/especes/{espece_id:path}")
async def get_espece(espece_id: str, current_user: Annotated[dict, Depends(get_current_user)]):
    _require_admin(current_user)
    doc = get_doc(unquote(espece_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Espèce not found")
    return doc


@bestiaire_router.post("/especes")
async def create_espece(
    current_user: Annotated[dict, Depends(get_current_user)],
    data: dict = Body(...),
):
    _require_admin(current_user)
    if not data.get("_id", "").startswith("espece:"):
        raise HTTPException(status_code=422, detail="_id must start with 'espece:'")
    data["type"] = "espece"
    save_doc(data)
    return data


@bestiaire_router.put("/especes/{espece_id:path}")
async def update_espece(
    espece_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    data: dict = Body(...),
):
    _require_admin(current_user)
    existing = get_doc(unquote(espece_id))
    if not existing:
        raise HTTPException(status_code=404, detail="Espèce not found")
    data["_id"] = existing["_id"]
    data["_rev"] = existing["_rev"]
    data["type"] = "espece"
    save_doc(data)
    return data


@bestiaire_router.delete("/especes/{espece_id:path}")
async def delete_espece(espece_id: str, current_user: Annotated[dict, Depends(get_current_user)]):
    _require_admin(current_user)
    doc = get_doc(unquote(espece_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Espèce not found")
    delete_doc(doc)
    return {"deleted": espece_id}


# ── PROFILS ───────────────────────────────────────────────────────────────────

@bestiaire_router.get("/profils")
async def list_profils(current_user: Annotated[dict, Depends(get_current_user)]):
    _require_admin(current_user)
    return find_docs({"type": "profil"}) or []


@bestiaire_router.get("/profils/{profil_id:path}")
async def get_profil(profil_id: str, current_user: Annotated[dict, Depends(get_current_user)]):
    _require_admin(current_user)
    doc = get_doc(unquote(profil_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Profil not found")
    return doc


@bestiaire_router.post("/profils")
async def create_profil(
    current_user: Annotated[dict, Depends(get_current_user)],
    data: dict = Body(...),
):
    _require_admin(current_user)
    if not data.get("_id", "").startswith("profil:"):
        raise HTTPException(status_code=422, detail="_id must start with 'profil:'")
    data["type"] = "profil"
    save_doc(data)
    return data


@bestiaire_router.put("/profils/{profil_id:path}")
async def update_profil(
    profil_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    data: dict = Body(...),
):
    _require_admin(current_user)
    existing = get_doc(unquote(profil_id))
    if not existing:
        raise HTTPException(status_code=404, detail="Profil not found")
    data["_id"] = existing["_id"]
    data["_rev"] = existing["_rev"]
    data["type"] = "profil"
    save_doc(data)
    return data


@bestiaire_router.delete("/profils/{profil_id:path}")
async def delete_profil(profil_id: str, current_user: Annotated[dict, Depends(get_current_user)]):
    _require_admin(current_user)
    doc = get_doc(unquote(profil_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Profil not found")
    delete_doc(doc)
    return {"deleted": profil_id}
