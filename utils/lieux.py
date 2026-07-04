from typing import Annotated
from fastapi import FastAPI, HTTPException, Depends, APIRouter, Response, Request, Body
from urllib.parse import unquote
from pydantic import BaseModel
from db.config import db, get_doc, save_doc
from utils.characters import get_selected_character
from utils.auth import get_current_user

class User(BaseModel):
	email: str
	username: str | None = None
	disabled: bool | None = None
	
lieu_router = APIRouter()

def get_lieu_links(current_user: dict = Body(...)):
	if not current_user:
		return None
		
	character = get_selected_character(current_user)
	if not character:
		return None
	position = character["position"]
	lieu = character["lieu"]
	target_key = [ lieu, position["x"], position["y"] ]
	links = db.view("reseau", "liens_cases", key=target_key)
	connections = [row.value for row in links]
	
	for conn in connections:
		for node in conn["nodes"]:
			doc = get_doc(node["lieu"])
			doc.pop("cells",None)
			doc.pop("_rev",None)
			doc.pop("_id",None)
			node["details"] = doc
			node["details"]["label"] = node.get("label") or doc.get("label")
			
	return connections
	
# [bit, dx, dy, opposé]
# 1: HAUT, 2: HAUT_DROITE, 4: DROITE, 8: BAS_DROITE, 16: BAS, 32: BAS_GAUCHE, 64: GAUCHE, 128: HAUT_GAUCHE
# ⚠️ Validateur serveur autoritatif. Miroir client : templates/scripts/nav.js — garder synchro.
VALID_MOVES = [
	[1,   0, -1, 16],
	[2,   1, -1, 32],
	[4,   1,  0, 64],
	[8,   1,  1, 128],
	[16,  0,  1, 1],
	[32, -1,  1, 2],
	[64, -1,  0, 4],
	[128, -1, -1, 8]
]

def get_final_mask(nav, x, y):
	# Par défaut, 0 = aucune direction interdite
	mask_actuel = nav.get(f"{x},{y}", 0)
	final_mask = 0
	
	for bit, dx, dy, op_bit in VALID_MOVES:
		# On vérifie si la direction est LIBRE (le bit d'interdiction est à 0)
		if not (mask_actuel & bit):
			# Vérifier si la case cible est aussi libre en entrée
			mask_cible = nav.get(f"{x + dx},{y + dy}", 0)
			if not (mask_cible & op_bit):
				# Si les deux sont libres, on marque la direction comme DISPONIBLE
				# (Le masque final reste un masque de directions autorisées)
				final_mask |= bit

	return final_mask

# (dx, dy) → bit de direction (dérivé de VALID_MOVES).
_DIR_BIT = {(dx, dy): bit for bit, dx, dy, _op in VALID_MOVES}

# Offsets (dx, dy) des 8 directions de déplacement, dérivés de VALID_MOVES.
# Source unique partagée par la nav joueur, l'A* et le flood fill de combat.
MOVE_OFFSETS = [(dx, dy) for _bit, dx, dy, _op in VALID_MOVES]

def nav_allows(nav, x, y, dx, dy):
	"""La direction (dx, dy) depuis (x, y) est-elle autorisée par le masque nav ?

	Réutilise get_final_mask (vérification bidirectionnelle source ↔ cible).
	nav vide → tout est permis. Miroir Python de navAllows() dans scripts/nav.js.
	"""
	if not nav:
		return True
	bit = _DIR_BIT.get((dx, dy))
	if bit is None:
		return False
	return bool(get_final_mask(nav, x, y) & bit)
	
def get_lieu_directions(current_user: dict = Body(...), lieu_doc: dict = Body(...), position: dict = Body(...)):
	if not current_user:
		return None
	cells = lieu_doc.get("cells",None)
	nav = lieu_doc.get("nav", {})
	access = 1 # full access
	mask = 255 # full access
	if cells:
		x = position["x"]
		y = position["y"]
		mask = get_final_mask(nav, x, y)
		
		rows = len(cells)
		cols = len(cells[0]) if rows > 0 else 0
		access = [
			[cells[r][c] if (0 <= r < rows and 0 <= c < cols) else -1 for c in range(x-1, x+2)]
			for r in range(y-1, y+2)
		]
	return { "access": access, "nav" : mask }

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
		doc = get_doc(decoded_id)

		if not doc:
			raise HTTPException(status_code=404, detail="Lieu introuvable")

		return doc

	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Erreur CouchDB : {str(e)}")

@lieu_router.get("/lieu/{lieu_id}/connections")
async def get_lieu_connections(
	response: Response,
	current_user: Annotated[User, Depends(get_current_user)],
	lieu_id: str):
	"""Toutes les connexions touchant un lieu (admin, éditeur de carte).

	Requête range sur la vue reseau/liens_cases (contrairement à
	get_lieu_links qui est scoppé à la case courante du personnage).
	Chaque node est enrichi de `details` (doc du lieu, sans cells/_rev/_id)
	comme get_lieu_links.
	"""
	if (not current_user or
		"admin" not in current_user or
		current_user["admin"] != 1 ):
		return None

	decoded_id = unquote(lieu_id)
	try:
		rows = db.view("reseau", "liens_cases", startkey=[decoded_id], endkey=[decoded_id, {}])
		connections = []
		seen = set()
		for row in rows:
			conn = row.value
			cid = conn.get("_id")
			if cid in seen:
				continue
			seen.add(cid)
			for node in conn["nodes"]:
				doc = get_doc(node["lieu"])
				if not doc:
					continue
				doc.pop("cells", None)
				doc.pop("_rev", None)
				doc.pop("_id", None)
				node["details"] = doc
				node["details"]["label"] = node.get("label") or doc.get("label")
			connections.append(conn)
		return connections

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
		nav = cells_info["nav"]
		lieu_id = cells_info["_id"]
		lieu_doc = get_doc(lieu_id)
		if lieu_doc:
			lieu_doc["cells"] = cells
			lieu_doc["nav"] = nav
			# Métadonnées battle map (optionnelles) : tags + catégorie pour la sélection pondérée.
			if "tags" in cells_info:
				lieu_doc["tags"] = cells_info["tags"]
			if "categorie" in cells_info:
				lieu_doc["categorie"] = cells_info["categorie"]
			save_doc(lieu_doc)
			return lieu_doc
	raise HTTPException(status_code=404, detail="Incorrect location grid info")