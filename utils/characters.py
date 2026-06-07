from fastapi import FastAPI, HTTPException, Depends, APIRouter, Response, Request, Body
from db.config import get_doc, save_doc, find_docs

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
	
	if not character["user_id"] == user_id:
		return None
	
	return character