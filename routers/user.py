from typing import Annotated
from fastapi import FastAPI, HTTPException, Depends, APIRouter, Response, Request, Body
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
import bcrypt
import re
import uuid
from db.config import save_doc, get_doc, delete_doc
from utils.auth import get_current_user, create_access_token
from utils.characters import get_user_characters, get_selected_character
from utils.lieux import get_lieu_links, get_lieu_directions
from models.character_stats import (
	BaseStats, EquipmentBonus, compute_derived_stats, DerivedStats,
	compute_xp_cost, compute_stat_cap, compute_character_level, XP_COEFF, XP_DECOUVERTE_LIEU, XP_VOC_COEFF
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
	user_doc = get_doc(user_id)
	if user_doc:
		raise HTTPException(status_code=400, detail="L'utilisateur existe déjà")
	
	if user.password != user.password_again:
		raise HTTPException(status_code=400, detail="Les mots de passe ne correspondent pas")
	
	hashed_pw = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt())
	token = create_access_token({"user_id": user_id})

	save_doc({
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
	user_doc = get_doc("user:"+user.email)
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
	db_user = get_doc(user_id)
	if not db_user:
		raise HTTPException(status_code=404, detail="User not found")
		
	if (characterinfo and "bonusStats" in characterinfo):
		caractUp = characterinfo["bonusStats"]
		points_depenses = sum(
			sum(i * XP_COEFF.get(key, 1) for i in range(1, bonus + 1))
			for key, bonus in caractUp.items()
		)
		if points_depenses>10:
			raise HTTPException(status_code=406, detail="Incorrect info for character creation, to much points spend.")
		races = get_doc("rules:races")
		race = next((r for r in races["value"] if r["id"] == characterinfo["race"]), None)
		caract = {
			k: race['stats'].get(k, 0) + caractUp.get(k, 0)
			for k in race['stats']
		}
		base = BaseStats(
			v=caract.get("V", 0),
			f=caract.get("F", 0),
			r=caract.get("R", 0),
			ag=caract.get("Ag", 0),
			vol=caract.get("Vol", 0),
			int_=caract.get("Int", 0),
			cha=caract.get("Cha", 0),
			ch=caract.get("Ch", 0),
		)
		derived = compute_derived_stats(base=base, niveau=0)
		lieu = get_doc(characterinfo["cite"])
		position = lieu.get("default_position",{"x" : 0, "y" : 0})
		vocations = get_doc("rules:vocations")
		vocation = next((v for v in vocations["value"] if v["id"] == characterinfo["voc"]), None)
		inventaire_de_base = vocation.get("equipement_de_base", []) if vocation else []
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
			'caracteristiques_current': caract,
			'currentPV': derived.pv_max,
			'currentPM': derived.pm_max,
			'lieux_visites': [characterinfo["cite"]],
			'xp_total': 0,
			'attribute_points': 0,
			'vocations_niveaux': {characterinfo["voc"]: 0},
			'inventaire': list(inventaire_de_base),
			'slots': {s: None for s in ['main_droite', 'main_gauche', 'torse', 'tete', 'jambes', 'pieds', 'mains', 'anneau_1', 'anneau_2', 'cou', 'ceinture']},
			'equipment_bonus': {},
			}
		save_doc(character_dict)
	
	return get_user_characters(current_user)
	
@user_router.delete("/character")
async def delete_character(	
	response: Response, 
	current_user: Annotated[User, Depends(get_current_user)], 
	characterinfo: dict = Body(...)):

	if not current_user:
		raise HTTPException(status_code=400, detail="Invalid session credentials")
	
	current_user_id = current_user["_id"]
	db_user = get_doc(current_user_id)
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
			delete_doc(characterToDelete)
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
	db_user = get_doc(current_user_id)
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
			save_doc(db_user)
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
			save_doc(character_to_update)
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
					lieu_doc = get_doc(destination)
					if lieu_doc:
						destination_pos = {"x": node["pos"][0], "y": node["pos"][1] }
						print("move to ", destination, destination_pos)
						character_to_update["lieu"] = destination
						character_to_update["position"] = destination_pos
						xp_gain = 0
						niveau_up = False
						niveau_new = compute_character_level(character_to_update.get("xp_total", 0))
						lieux_visites = character_to_update.get("lieux_visites", [])
						if destination not in lieux_visites:
							lieux_visites.append(destination)
							character_to_update["lieux_visites"] = lieux_visites
							xp_gain = lieu_doc.get("xp_decouverte", XP_DECOUVERTE_LIEU)
							xp_total_new = character_to_update.get("xp_total", 0) + xp_gain
							character_to_update["xp_total"] = xp_total_new
							niveau_after = compute_character_level(xp_total_new)
							if niveau_after > niveau_new:
								niveau_up = True
								for n in range(niveau_new + 1, niveau_after + 1):
									character_to_update["attribute_points"] = character_to_update.get("attribute_points", 0) + n
								niveau_new = niveau_after
						save_doc(character_to_update)
						return {"moved": 1, "xp_gain": xp_gain, "niveau_up": niveau_up, "niveau": niveau_new}
				raise HTTPException(status_code=404, detail="Incorrect movement info")
		elif ("x" in move and "y" in move
			and isinstance(move["x"], int) and isinstance(move["y"], int)):
			movex = (move["x"] > 0) - (move["x"] < 0) # -1 0 1
			movey = (move["y"] > 0) - (move["y"] < 0) # -1 0 1
			position["x"] += movex
			position["y"] += movey
			lieu_doc = get_doc(lieu_courant)
			if (lieu_doc and
				position["x"]>=0 and position["y"]>=0
				and position["x"]<=lieu_doc["dimensions"]["x"] and position["y"]<=lieu_doc["dimensions"]["y"]):
				character_to_update["position"] = position
				save_doc(character_to_update)
				links = get_lieu_links(current_user)
				if lieu_doc:
					access = get_lieu_directions(current_user, lieu_doc, position)
					return {"position" : character_to_update["position"], "links" : links, "access" : access}
	raise HTTPException(status_code=404, detail="Incorrect movement info")


_VALID_STATS = {"V", "F", "R", "Ag", "Vol", "Int", "Cha", "Ch"}

_VALID_SLOTS = {
    "main_droite", "main_gauche", "torse", "tete", "jambes",
    "pieds", "mains", "anneau_1", "anneau_2", "cou", "ceinture",
}

def _recompute_equipment_bonus(slots: dict) -> EquipmentBonus:
    bonus = EquipmentBonus()
    for item_id in slots.values():
        if not item_id:
            continue
        item = get_doc(item_id)
        if not item:
            continue
        bonus.pa           += item.get("bonus_pa", 0)
        bonus.pv           += item.get("bonus_pv", 0)
        bonus.pm           += item.get("bonus_pm", 0)
        bonus.malus_depl   += item.get("bonus_malus_depl", 0)
        bonus.cc_bonus     += item.get("bonus_cc", 0)
        bonus.cd_bonus     += item.get("bonus_cd", 0)
        bonus.degats_bonus += item.get("bonus_degats", 0)
        bonus.initiative   += item.get("bonus_initiative", 0)
    return bonus

def _derived_from_character(character: dict, equipment: EquipmentBonus) -> DerivedStats:
    stats = character["caracteristiques_current"]
    base = BaseStats(
        v=stats.get("V", 0), f=stats.get("F", 0),
        r=stats.get("R", 0), ag=stats.get("Ag", 0),
        vol=stats.get("Vol", 0), int_=stats.get("Int", 0),
        cha=stats.get("Cha", 0), ch=stats.get("Ch", 0),
    )
    voc_niveau = character.get("vocations_niveaux", {}).get(character.get("voc", ""), 0)
    return compute_derived_stats(base, niveau=voc_niveau, equipment=equipment)

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

	races = get_doc("rules:races")
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
	attribute_points = character.get("attribute_points", 0)
	if attribute_points < cost:
		raise HTTPException(status_code=422, detail=f"Points insuffisants (besoin {cost}, disponible {attribute_points})")

	# Appliquer la montée de stat
	character["caracteristiques_current"][stat_key] = new_value
	character["attribute_points"] = attribute_points - cost
	if use_bonus:
		character["max_bonus_used"] = stat_key

	save_doc(character)

	# Recalculer les stats dérivées et les nouveaux plafonds
	stats_cur = character["caracteristiques_current"]
	base = BaseStats(
		v=stats_cur.get("V", 0), f=stats_cur.get("F", 0),
		r=stats_cur.get("R", 0), ag=stats_cur.get("Ag", 0),
		vol=stats_cur.get("Vol", 0), int_=stats_cur.get("Int", 0),
		cha=stats_cur.get("Cha", 0), ch=stats_cur.get("Ch", 0),
	)
	voc_niveau = character.get("vocations_niveaux", {}).get(character.get("voc", ""), 0)
	derived = compute_derived_stats(base, niveau=voc_niveau)

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
		"attribute_points": character["attribute_points"],
		"stat_caps":     new_caps,
		"derived_stats": derived.model_dump(),
	}


@user_router.post("/equip")
async def equip_item(
	current_user: Annotated[User, Depends(get_current_user)],
	body: dict = Body(...),
):
	item_id = body.get("item_id")
	slot    = body.get("slot")

	if not item_id or slot not in _VALID_SLOTS:
		raise HTTPException(status_code=422, detail="Paramètres invalides")

	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")

	inventaire = character.get("inventaire", [])
	if item_id not in inventaire:
		raise HTTPException(status_code=422, detail="Objet absent de l'inventaire")

	item = get_doc(item_id)
	if not item:
		raise HTTPException(status_code=404, detail="Objet introuvable")

	if slot not in item.get("slots", []):
		raise HTTPException(status_code=422, detail=f"Slot '{slot}' incompatible avec cet objet")

	slots = character.get("slots", {})

	displaced = slots.get(slot)
	if displaced:
		inventaire.append(displaced)

	slots[slot] = item_id
	inventaire.remove(item_id)
	character["slots"]      = slots
	character["inventaire"] = inventaire

	eq_bonus = _recompute_equipment_bonus(slots)
	character["equipment_bonus"] = eq_bonus.model_dump()
	save_doc(character)

	derived = _derived_from_character(character, eq_bonus)
	return {
		"slots":           {s: get_doc(v) if v else None for s, v in slots.items()},
		"inventaire":      [get_doc(i) for i in inventaire if i],
		"equipment_bonus": character["equipment_bonus"],
		"derived_stats":   derived.model_dump(),
	}


@user_router.post("/unequip")
async def unequip_item(
	current_user: Annotated[User, Depends(get_current_user)],
	body: dict = Body(...),
):
	slot = body.get("slot")

	if slot not in _VALID_SLOTS:
		raise HTTPException(status_code=422, detail="Slot invalide")

	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")

	slots   = character.get("slots", {})
	item_id = slots.get(slot)
	if not item_id:
		raise HTTPException(status_code=422, detail="Slot déjà vide")

	inventaire = character.get("inventaire", [])
	inventaire.append(item_id)
	slots[slot] = None
	character["slots"]      = slots
	character["inventaire"] = inventaire

	eq_bonus = _recompute_equipment_bonus(slots)
	character["equipment_bonus"] = eq_bonus.model_dump()
	save_doc(character)

	derived = _derived_from_character(character, eq_bonus)
	return {
		"slots":           {s: get_doc(v) if v else None for s, v in slots.items()},
		"inventaire":      [get_doc(i) for i in inventaire if i],
		"equipment_bonus": character["equipment_bonus"],
		"derived_stats":   derived.model_dump(),
	}


@user_router.post("/spend_xp_vocation")
async def spend_xp_vocation(
	current_user: Annotated[User, Depends(get_current_user)],
):
	if not current_user:
		raise HTTPException(status_code=400, detail="Invalid session credentials")

	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")

	voc = character.get("voc", "")
	vocations_niveaux = character.get("vocations_niveaux", {})
	voc_niveau = vocations_niveaux.get(voc, 0)
	cout = (voc_niveau + 1) * XP_VOC_COEFF

	attribute_points = character.get("attribute_points", 0)
	if attribute_points < cout:
		raise HTTPException(status_code=422, detail=f"Points insuffisants (besoin {cout}, disponible {attribute_points})")

	vocations_niveaux[voc] = voc_niveau + 1
	character["vocations_niveaux"] = vocations_niveaux
	character["attribute_points"] = attribute_points - cout
	save_doc(character)

	return {
		"attribute_points": character["attribute_points"],
		"voc_niveau":    voc_niveau + 1,
		"xp_cout_next":  (voc_niveau + 2) * 5,
	}