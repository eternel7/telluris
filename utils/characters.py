from fastapi import FastAPI, HTTPException, Depends, APIRouter, Response, Request, Body
from db.config import get_doc, save_doc, find_docs
from models.character_stats import compute_character_level

def get_user_characters(current_user: dict = Body(...)):
	if not current_user:
		return None
	
	db_user = get_doc(current_user["_id"])
	if not db_user:
		return None
	
	# characters :
	selector = {
		"type": "character",
		"user_id": current_user["_id"]
	}
	characters = find_docs(selector)
	for c in characters:
		c["niveau"] = compute_character_level(c.get("xp_total", 0))
	return characters
	
def get_selected_character(current_user: dict = Body(...)):
	if not current_user:
		return None
	user_id = current_user["_id"]
	db_user = get_doc(user_id)
	if not db_user:
		return None
	
	#selected character for current user
	character_id = db_user["selected_character"]
	character = get_doc(character_id)
	
	if not character or not character["user_id"] == user_id:
		return None

	return character

def grant_xp(character: dict, amount: int) -> dict:
	"""Ajoute `amount` XP au personnage et attribue les points de montée de niveau.

	Mute `character` en place (`xp_total`, `attribute_points`) mais NE SAUVEGARDE PAS :
	l'appelant persiste le personnage avec ses autres modifications (régén, position,
	PV de sortie de combat…). Règle : +N points par niveau gagné (passage au niveau N
	→ +N points), partagée entre la découverte de lieux et les récompenses de combat.

	Retourne un récap : {xp_gain, niveau_avant, niveau_apres, niveau_up, points_gagnes}.
	"""
	amount = max(0, int(amount or 0))
	xp_before = character.get("xp_total", 0)
	niveau_avant = compute_character_level(xp_before)
	character["xp_total"] = xp_before + amount
	niveau_apres = compute_character_level(character["xp_total"])
	points_gagnes = sum(range(niveau_avant + 1, niveau_apres + 1))
	if points_gagnes:
		character["attribute_points"] = character.get("attribute_points", 0) + points_gagnes
	return {
		"xp_gain": amount,
		"niveau_avant": niveau_avant,
		"niveau_apres": niveau_apres,
		"niveau_up": niveau_apres > niveau_avant,
		"points_gagnes": points_gagnes,
	}