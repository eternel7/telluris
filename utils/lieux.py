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