from typing import Annotated
from fastapi import FastAPI, HTTPException, Depends, APIRouter, Response, Request, Body
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
import bcrypt
import re
import uuid
from jose import jwt
from db.config import db, SECRET_KEY, ALGORITHM, save_doc, get_doc
from utils.auth import get_current_user, create_access_token
from utils.characters import get_user_characters, get_selected_character
from utils.lieux import get_lieu_links, get_lieu_directions
from models.character_stats import (
	BaseStats, EquipmentBonus, compute_derived_stats,
	compute_xp_cost, compute_stat_cap,
)

class User(BaseModel):
	email: str
	username: str | None = None
	disabled: bool | None = None
	
user_router = APIRouter()

class RegisterRequest(BaseModel):
	username: str
	email: str
	password: str
	password_again: str

@user_router.post("/register")
async def register_user(user: RegisterRequest, response: Response):
	user_id = "user:"+user.email
	user_doc = db.get(user_id)
	if user_doc:
		raise HTTPException(status_code=400, detail="L'utilisateur existe déjà")
	
	if user.password != user.password_again:
		raise HTTPException(status_code=400, detail="Les mots de passe ne correspondent pas")
	
	hashed_pw = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt())
	token = create_access_token({"user_id": user_id}) #jwt.encode({"user_id": user_id}, SECRET_KEY, algorithm=ALGORITHM)

	db.put({
		"_id": user_id,
		"username": user.username,
		"email": user.email,
		"type": "user",
		"password": hashed_pw.decode(),
		"token": token
	})
	content = {"token": token, "user_id": user_id, "username": user.username}
	response = JSONResponse(content=content)
	response.set_cookie(key="auth_token", value=token, httponly=True, samesite="lax")
	return response

class LoginRequest(BaseModel):
	email: str
	password: str
	
@user_router.post("/login")
async def login_user(user: LoginRequest, response: Response):
	user_doc = db.get("user:"+user.email)
	if not user_doc or not bcrypt.checkpw(user.password.encode(), user_doc["password"].encode()):
		raise HTTPException(status_code=400, detail="Invalid credentials")
		
	token = create_access_token({"user_id": user_doc["_id"]})
	content = {"token": token, "user_id":	user_doc["_id"], "username":	user_doc["username"]}
	response = JSONResponse(content=content)
	response.set_cookie(key="auth_token", value=token, httponly=True, samesite="lax")
	return	response
	
@user_router.post("/character")
async def add_character(response: Response, current_user: Annotated[User, Depends(get_current_user)], characterinfo: dict = Body(...),):
	if not current_user:
		raise HTTPException(status_code=400, detail="Invalid session credentials")
	
	user_id = current_user["_id"]
	db_user = db.get(user_id)
	if not db_user:
		raise HTTPException(status_code=404, detail="User not found")
		
	if (characterinfo and "bonusStats" in characterinfo):
		caractUp = characterinfo["bonusStats"]
		points_depenses = sum(
			sum(i * 5 if key == "V" else i for i in range(1, bonus + 1))
			for key, bonus in caractUp.items()
		)
		if points_depenses>10:
			raise HTTPException(status_code=406, detail="Incorrect info for character creation, to much points spend.")
		races = db.get("rules:races")
		race = next((r for r in races["value"] if r["id"] == characterinfo["race"]), None)
		caract = {
			k: race['stats'].get(k, 0) + caractUp.get(k, 0)
			for k in race['stats']
		}
		lieu = db.get(characterinfo["cite"])
		position = lieu.get("default_position",{"x" : 0, "y" : 0})
		unique_id = "character:" + user_id + "_" + str(uuid.uuid4())
		character_dict = {
			'_id' : unique_id,
			'user_id' : user_id,
			'type' : "character",
			'sex': characterinfo["sex"], 
			'race': characterinfo["race"], 
			'voc': characterinfo["voc"], 
			'image': characterinfo["image"], 
			'prenom': characterinfo["prenom"], 
			'nom': characterinfo["nom"], 
			'cite': characterinfo["cite"], 
			'lieu': characterinfo["cite"],
			'position': position,
			'caracteristiques_current': caract
			}
		db.put(character_dict)
	
	return get_user_characters(current_user)
	
@user_router.delete("/character")
async def delete_character(	
	response: Response, 
	current_user: Annotated[User, Depends(get_current_user)], 
	characterinfo: dict = Body(...)):

	if not current_user:
		raise HTTPException(status_code=400, detail="Invalid session credentials")
	
	current_user_id = current_user["_id"]
	db_user = db.get(current_user_id)
	if not db_user:
		raise HTTPException(status_code=404, detail="User not found")
		
	if characterinfo:
		index = characterinfo["id"]
		character_id = characterinfo["character"]["_id"]	
		characterToDelete = get_doc(character_id)
		character = characterinfo["character"]
		if (
			characterToDelete["user_id"] == current_user_id and 
			characterToDelete["sex"] == character["sex"] and
			characterToDelete["voc"] == character["voc"] and
			characterToDelete["race"] == character["race"] and
			characterToDelete["nom"] == character["nom"] and
			characterToDelete["prenom"] == character["prenom"]
		 ):
			db.delete(characterToDelete)
		else:
			raise HTTPException(status_code=404, detail="Character not found")
	
	return get_user_characters(current_user)	
	
@user_router.post("/select_character")
async def select_character(
	response: Response, 
	current_user: Annotated[User, Depends(get_current_user)], 
	characterinfo: dict = Body(...)):
	
	if not current_user:
		raise HTTPException(status_code=400, detail="Invalid session credentials")
	
	current_user_id = current_user["_id"]
	db_user = db.get(current_user_id)
	if not db_user:
		raise HTTPException(status_code=404, detail="User not found")
		
	if characterinfo:
		index = characterinfo["id"]
		character_id = characterinfo["character"]["_id"]	
		characterSelected = get_doc(character_id)
		character = characterinfo["character"]
		if (
			characterSelected["user_id"] == current_user_id and 
			characterSelected["sex"] == character["sex"] and
			characterSelected["voc"] == character["voc"] and
			characterSelected["race"] == character["race"] and
			characterSelected["nom"] == character["nom"] and
			characterSelected["prenom"] == character["prenom"]
		 ):
			db_user["selected_character"] = character_id
			db.put(db_user)
			return characterSelected
		else:
			raise HTTPException(status_code=404, detail="Character not found")
	else:
		raise HTTPException(status_code=404, detail="Invalid character selection")

@user_router.post("/update_character_portrait")
async def update_character_portrait(
	response: Response, 
	current_user: Annotated[User, Depends(get_current_user)], 
	portrait_info: dict = Body(...)):
	
	if not current_user:
		raise HTTPException(status_code=400, detail="Invalid session credentials")
	
	if portrait_info:
		character_to_update = get_selected_character(current_user)
		if not character_to_update:
			raise HTTPException(status_code=406, detail="Incorrect info for character portrait update")
			
		match = re.search(r"translate\((-?\d+\.?\d*)px,\s*(-?\d+\.?\d*)px\)", portrait_info["value"])
		zoom = portrait_info["zoom"]
		if match:
			x = float(match.group(1))
			y = float(match.group(2))
			character_to_update["portrait_translate"] = {"x": x, "y": y}
			character_to_update["portrait_zoom"] = zoom
			db.put(character_to_update)
			return character_to_update
		else:
			raise HTTPException(status_code=406, detail="Incorrect info for character portrait update")
	else:
		raise HTTPException(status_code=405, detail="No info for character portrait update")

@user_router.post("/move_character")
async def move_character(
	response: Response, 
	current_user: Annotated[User, Depends(get_current_user)], 
	move: dict = Body(...)):
	
	if not current_user:
		raise HTTPException(status_code=400, detail="Invalid session credentials")
		
	if move :
		character_to_update = get_selected_character(current_user)
		if not character_to_update:
			raise HTTPException(status_code=406, detail="Incorrect info for character move")
			
		position = character_to_update["position"]
		lieu_courant = character_to_update["lieu"]
		
		if "link" in move:
			links = get_lieu_links(current_user)
			target_id = move["link"]
			# 1. Trouver le bon lien par son _id
			link = next((l for l in links if l["_id"] == target_id), None)

			# 2. Trouver le nœud qui n'a PAS le lieu_id
			if link:
				node = next((n for n in link["nodes"] if n["lieu"] != lieu_courant), None)
				if node:
					destination = node["lieu"]
					destination_pos = {"x": node["pos"][0], "y": node["pos"][1] }
					print("move to ", destination, destination_pos)
					character_to_update["lieu"] = destination
					character_to_update["position"] = destination_pos
					db.put(character_to_update)
					return {"moved" : 1}
		elif ("x" in move and "y" in move
			and isinstance(move["x"], int) and isinstance(move["y"], int)):
			movex = (move["x"] > 0) - (move["x"] < 0) # -1 0 1
			movey = (move["y"] > 0) - (move["y"] < 0) # -1 0 1
			position["x"] += movex
			position["y"] += movey
			lieu_doc = db.get(lieu_courant)
			if (lieu_doc and
				position["x"]>=0 and position["y"]>=0
				and position["x"]<=lieu_doc["dimensions"]["x"] and position["y"]<=lieu_doc["dimensions"]["y"]):
				character_to_update["position"] = position
				db.put(character_to_update)
				links = get_lieu_links(current_user)
				if lieu_doc:
					access = get_lieu_directions(current_user, lieu_doc, position)
					return {"position" : character_to_update["position"], "links" : links, "access" : access}
	raise HTTPException(status_code=404, detail="Incorrect movement info")


_VALID_STATS = {"V", "F", "R", "Ag", "Vol", "Int", "Cha", "Ch"}

@user_router.post("/spend_xp")
async def spend_xp(
	current_user: Annotated[User, Depends(get_current_user)],
	body: dict = Body(...),
):
	if not current_user:
		raise HTTPException(status_code=400, detail="Invalid session credentials")

	stat_key  = body.get("stat")
	new_value = body.get("new_value")
	use_bonus = body.get("use_max_bonus", False)

	if stat_key not in _VALID_STATS or not isinstance(new_value, int):
		raise HTTPException(status_code=422, detail="Paramètres invalides")

	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")

	races = db.get("rules:races")
	race  = next((r for r in races["value"] if r["id"] == character["race"]), None)
	if not race:
		raise HTTPException(status_code=404, detail="Race introuvable")

	stats_max_race     = race.get("stats_max", {})
	race_min           = race.get("stats", {}).get(stat_key, 0)
	nb_max_accessibles = race.get("nb_max_accessibles", 3)
	max_bonus          = race.get("max_bonus")
	max_bonus_used     = character.get("max_bonus_used")

	current_stats = character.get("caracteristiques_current", {})
	current_val   = current_stats.get(stat_key, 0)

	if new_value <= current_val:
		raise HTTPException(status_code=422, detail="La nouvelle valeur doit être supérieure à la valeur actuelle")

	# Calculer le plafond effectif (avant d'activer un éventuel bonus)
	effective_bonus_used = max_bonus_used
	if use_bonus:
		if max_bonus_used is not None:
			raise HTTPException(status_code=422, detail="Le bonus racial est déjà utilisé")
		if not max_bonus:
			raise HTTPException(status_code=422, detail="Cette race n'a pas de bonus de dépassement")
		effective_bonus_used = stat_key

	cap = compute_stat_cap(
		stat_key=stat_key,
		stats_max=stats_max_race,
		nb_max_accessibles=nb_max_accessibles,
		current_stats=current_stats,
		max_bonus=max_bonus,
		max_bonus_used=effective_bonus_used,
	)

	if new_value > cap:
		raise HTTPException(status_code=422, detail=f"Plafond de {cap} atteint pour {stat_key}")

	cost = compute_xp_cost(stat_key, current_val, new_value, race_min)
	xp_libre = character.get("xp_libre", 0)
	if xp_libre < cost:
		raise HTTPException(status_code=422, detail=f"XP insuffisante (besoin {cost}, disponible {xp_libre})")

	# Appliquer la montée de stat
	character["caracteristiques_current"][stat_key] = new_value
	character["xp_libre"] = xp_libre - cost
	if use_bonus:
		character["max_bonus_used"] = stat_key

	db.put(character)

	# Recalculer les stats dérivées et les nouveaux plafonds
	stats_cur = character["caracteristiques_current"]
	base = BaseStats(
		v=stats_cur.get("V", 0), f=stats_cur.get("F", 0),
		r=stats_cur.get("R", 0), ag=stats_cur.get("Ag", 0),
		vol=stats_cur.get("Vol", 0), int_=stats_cur.get("Int", 0),
		cha=stats_cur.get("Cha", 0), ch=stats_cur.get("Ch", 0),
	)
	derived = compute_derived_stats(base, niveau=character.get("niveau", 0))

	new_caps = {
		code: compute_stat_cap(
			stat_key=code,
			stats_max=stats_max_race,
			nb_max_accessibles=nb_max_accessibles,
			current_stats=stats_cur,
			max_bonus=max_bonus,
			max_bonus_used=character.get("max_bonus_used"),
		)
		for code in _VALID_STATS
	}

	return {
		"stat":          stat_key,
		"new_value":     new_value,
		"xp_libre":      character["xp_libre"],
		"stat_caps":     new_caps,
		"derived_stats": derived.model_dump(),
	}