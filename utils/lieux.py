from typing import Annotated
from fastapi import FastAPI, HTTPException, Depends, APIRouter, Response, Request, Body
from pydantic import BaseModel
from db.config import db, SECRET_KEY, ALGORITHM
		
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