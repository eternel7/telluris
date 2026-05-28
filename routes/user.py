from typing import Annotated
from fastapi import FastAPI, HTTPException, Depends, APIRouter, Response, Request, Body
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
import bcrypt
import re
from jose import jwt
from db.config import db, SECRET_KEY, ALGORITHM
from utils.auth import get_current_user, create_access_token
from utils.lieux import get_lieu_links

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
		"token": token,
		"characters": []
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
		
	token = create_access_token({"user_id": user_doc["_id"]}) #jwt.encode({"user_id": user_doc["_id"]}, SECRET_KEY, algorithm=ALGORITHM)
	content = {"token": token, "user_id":	user_doc["_id"], "username":	user_doc["username"]}
	response = JSONResponse(content=content)
	response.set_cookie(key="auth_token", value=token, httponly=True, samesite="lax")
	return	response
	
class CharacterRequest(BaseModel):
	sex: str
	race: str
	voc: str
	portrait: str
	prenom: str
	nom: str
	cite: str
	
@user_router.post("/character")
async def add_character(character: CharacterRequest, response: Response, current_user: Annotated[User, Depends(get_current_user)]):
	if not current_user:
		raise HTTPException(status_code=400, detail="Invalid session credentials")
	
	db_user = db.get(current_user["_id"])
	if not db_user:
		raise HTTPException(status_code=404, detail="User not found")
		
	if "characters" not in db_user:
		db_user["characters"] = []
		
	if character:
		character_dict = character.model_dump()
		db_user["characters"].append(character_dict)
		db.put(db_user)
	
	return db_user["characters"]
	
@user_router.delete("/character")
async def delete_character(	
	response: Response, 
	current_user: Annotated[User, Depends(get_current_user)], 
	characterinfo: dict = Body(...)):

	if not current_user:
		raise HTTPException(status_code=400, detail="Invalid session credentials")
	
	db_user = db.get(current_user["_id"])
	if not db_user:
		raise HTTPException(status_code=404, detail="User not found")
		
	if "characters" not in db_user:
		return []
		
	if characterinfo:
		index = characterinfo["id"]
		if index < 0 or index >= len(db_user["characters"]):
			raise HTTPException(status_code=404, detail="Character index out of range")
			
		characterToDelete = db_user["characters"][index]
		character = characterinfo["character"]
		if (
		 characterToDelete["sex"] == character["sex"] and
		 characterToDelete["voc"] == character["voc"] and
		 characterToDelete["race"] == character["race"] and
		 characterToDelete["nom"] == character["nom"] and
		 characterToDelete["prenom"] == character["prenom"] and
		 characterToDelete["portrait"] == character["portrait"]
		 ):	
			characterToDelete = db_user["characters"].pop(index)
			print("deleted:", characterToDelete, " from user", current_user["_id"])
			db.put(db_user)
		else:
			raise HTTPException(status_code=404, detail="Character not found")
	
	return db_user["characters"]	
	
@user_router.post("/select_character")
async def select_character(
	response: Response, 
	current_user: Annotated[User, Depends(get_current_user)], 
	characterinfo: dict = Body(...)):
	
	if not current_user:
		raise HTTPException(status_code=400, detail="Invalid session credentials")
	
	db_user = db.get(current_user["_id"])
	if not db_user:
		raise HTTPException(status_code=404, detail="User not found")
		
	if characterinfo:
		index = characterinfo["id"]
		if index < 0 or index >= len(db_user["characters"]):
			raise HTTPException(status_code=404, detail="Character index out of range")
			
		characterToDelete = db_user["characters"][index]
		character = characterinfo["character"]
		if (
		 characterToDelete["sex"] == character["sex"] and
		 characterToDelete["voc"] == character["voc"] and
		 characterToDelete["race"] == character["race"] and
		 characterToDelete["nom"] == character["nom"] and
		 characterToDelete["prenom"] == character["prenom"] and
		 characterToDelete["portrait"] == character["portrait"]
		 ):	
			db_user["selected_character"] = index
			db.put(db_user)
			return db_user["characters"][index]
		else:
			raise HTTPException(status_code=404, detail="Character not found")
	else:
		raise HTTPException(status_code=404, detail="Character not found")

@user_router.post("/update_character_portrait")
async def update_character_portrait(
	response: Response, 
	current_user: Annotated[User, Depends(get_current_user)], 
	portrait_info: dict = Body(...)):
	
	if not current_user:
		raise HTTPException(status_code=400, detail="Invalid session credentials")
	
	db_user = db.get(current_user["_id"])
	if not db_user:
		raise HTTPException(status_code=404, detail="User not found")

	if portrait_info:
		match = re.search(r"translate\(-(\d+\.?\d*)px,\s*-(\d+\.?\d*)px\)", portrait_info["value"])
		if match:
			x = float(match.group(1))
			y = float(match.group(2))
			index = db_user["selected_character"]					
			character_to_update = db_user["characters"][index]
			character_to_update["portrait_translate"] = {"x": x, "y": y}
			db.put(db_user)
			return db_user["characters"][index]
		else:
			raise HTTPException(status_code=404, detail="Incorrect info for character portrait update")
	else:
		raise HTTPException(status_code=404, detail="No info for character portrait update")

@user_router.post("/move_character")
async def move_character(
	response: Response, 
	current_user: Annotated[User, Depends(get_current_user)], 
	move: dict = Body(...)):
	
	if not current_user:
		raise HTTPException(status_code=400, detail="Invalid session credentials")
	
	db_user = db.get(current_user["_id"])
	if not db_user:
		raise HTTPException(status_code=404, detail="User not found")

	if (move and "x" in move and "y" in move
			and isinstance(move["x"], int) and isinstance(move["y"], int)):
		movex = (move["x"] > 0) - (move["x"] < 0) # -1 0 1
		movey = (move["y"] > 0) - (move["y"] < 0) # -1 0 1
		index = db_user["selected_character"]
		character_to_update = db_user["characters"][index]
		position = character_to_update["position"]
		position["x"] += movex
		position["y"] += movey
		character_to_update["position"] = position
		db.put(db_user)
		target_key = [ character_to_update["lieu"], position["x"], position["y"] ]
		links = get_lieu_links(current_user)
		return {"position" : character_to_update["position"], "links" : links}
	else:
		raise HTTPException(status_code=404, detail="Incorrect movement info")