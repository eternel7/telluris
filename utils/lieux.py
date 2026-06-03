from typing import Annotated
from fastapi import FastAPI, HTTPException, Depends, APIRouter, Response, Request, Body
from urllib.parse import unquote
from pydantic import BaseModel
from db.config import db
from utils.auth import get_current_user

class User(BaseModel):
	email: str
	username: str | None = None
	disabled: bool | None = None
	
lieu_router = APIRouter()

def get_lieu_links(current_user: dict = Body(...)):
	if not current_user:
		return None
	
	db_user = db.get(current_user["_id"])
	if not db_user:
		return None
	
	index = db_user["selected_character"]
	character = db_user["characters"][index]
	position = character["position"]
	lieu = character["lieu"]
	target_key = [ lieu, position["x"], position["y"] ]
	links = db.view("reseau", "liens_cases", key=target_key)
	connections = [row.value for row in links]
	
	for conn in connections:
		for node in conn["nodes"]:
			doc = db.get(node["lieu"])
			doc.pop("cells",None)
			doc.pop("_rev",None)
			doc.pop("_id",None)
			node["details"] = doc
						
	return connections

def get_lieu_directions(current_user: dict = Body(...), lieu_doc: dict = Body(...), position: dict = Body(...)):
	if not current_user:
		return None
	cells = lieu_doc.get("cells",None)
	access = 1
	if cells:
		x = position["x"]
		y = position["y"]
		rows = len(cells)
		cols = len(cells[0]) if rows > 0 else 0
		access = [
			[cells[r][c] if (0 <= r < rows and 0 <= c < cols) else -1 for c in range(x-1, x+2)]
			for r in range(y-1, y+2)
		]
	return access

def get_lieux_ids(current_user: dict = Body(...)):
	if not current_user:
		return None
	selector = {
		"type": "lieu",
		"cells": {"$exists": True}
	}
	results = db.find(selector, fields=["_id","label","image"])
	return results["docs"]

@lieu_router.get("/lieu/{lieu_id}")
async def get_lieu(
	response: Response,
	current_user: Annotated[User, Depends(get_current_user)],
	lieu_id: str):
	if (not current_user or
		"admin" not in current_user or
		current_user["admin"] != 1 ):
		return None
	
	decoded_id = unquote(lieu_id)
	try:
		doc = db.get(decoded_id)

		if not doc:
			raise HTTPException(status_code=404, detail="Lieu introuvable")

		return doc

	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Erreur CouchDB : {str(e)}")
	
@lieu_router.put("/update_cells")
async def update_cells(
	response: Response,
	current_user: Annotated[User, Depends(get_current_user)],
	cells_info: dict = Body(...)):
	
	if ( not current_user or
		"admin" not in current_user or
		current_user["admin"] != 1 ):
		raise HTTPException(status_code=400, detail="Invalid session credentials")
		
	if cells_info :
		cells = cells_info["cells"]
		lieu_id = cells_info["_id"]
		lieu_doc = db.get(lieu_id)
		if lieu_doc:
			lieu_doc["cells"] = cells
			db.put(lieu_doc)
			return lieu_doc
	raise HTTPException(status_code=404, detail="Incorrect location grid info")