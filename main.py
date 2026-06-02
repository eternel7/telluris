import os
from typing import Annotated
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from jose import jwt, JWTError
from PIL import Image
from routes.user import user_router, User
from db.config import db, SECRET_KEY, ALGORITHM
from utils.auth import get_current_user
from utils.lieux import get_lieu_links, get_lieu_directions, get_lieux_ids, lieu_router

app = FastAPI()

# Add CORS middleware
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],	# In production, limit this to your frontend domain
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

# Definit ou se trouvent les fichiers HTML
templates = Jinja2Templates(directory="templates")
templates.env.policies["json.dumps_kwargs"] = {"sort_keys": False}

app.mount("/scripts", StaticFiles(directory="templates/scripts"), name="scripts")
app.mount("/battle_maps", StaticFiles(directory="templates/resources/battle_maps"), name="battle_maps")
app.mount("/icons", StaticFiles(directory="templates/resources/icons"), name="icons")
CHARACTERS_IMAGES_PATH = "templates/resources/characters"
app.mount("/characters", StaticFiles(directory=CHARACTERS_IMAGES_PATH), name="characters")
TOWNS_IMAGES_PATH = "templates/resources/towns"
app.mount("/towns", StaticFiles(directory=TOWNS_IMAGES_PATH), name="towns")

app.include_router(user_router, prefix="/api")
app.include_router(lieu_router, prefix="/api")
	
@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
	return templates.TemplateResponse(
		request=request, 
		name="home_telluris.html", 
		context={"title": "Ubi Chartae Finiunt"}
	)
	
@app.get("/editor", response_class=HTMLResponse)
def read_root(request: Request, current_user: Annotated[User, Depends(get_current_user)]):
	if (not current_user or
		"admin" not in current_user or
		current_user["admin"] != 1 ):
		return RedirectResponse(url="/auth", headers=request.headers)
	
	lieux = get_lieux_ids(current_user)
	return templates.TemplateResponse(
		request=request, 
		name="map_editor.html", 
		context={
			"title": "Map Grid Editor",
			"lieux": lieux
			}
	)
	
@app.get("/auth", response_class=HTMLResponse)
async def read_page_auth(request: Request):
	is_new = "new" in request.query_params
	return templates.TemplateResponse(
		request=request, 
		name="auth_telluris.html", 
		context={
			"title": "Authentification",
			"is_new": is_new
		}
	)
	
@app.get("/embleme", response_class=HTMLResponse)
async def get_embleme(request: Request, current_user: Annotated[User, Depends(get_current_user)]):
	if not current_user:
		return RedirectResponse(url="/auth", headers=request.headers)
	# rules :
	races = db.get("rules:races")
	races_proximity = db.get("rules:races_proximity")
	vocations = db.get("rules:vocations")
	vocations_proximity = db.get("rules:vocations_proximity")
	
	# characters images : 
	valid_extensions = (".jpg", ".jpeg", ".png", ".webp", ".gif")
	characters_images = []
	if os.path.exists(CHARACTERS_IMAGES_PATH):
		for filename in os.listdir(CHARACTERS_IMAGES_PATH):
			full_path = os.path.join(CHARACTERS_IMAGES_PATH, filename)
			if (os.path.isfile(full_path) and filename.lower().endswith(valid_extensions)):
				file_url = request.url_for("characters", path=filename)
				race = filename[filename.rfind("_")+1:-6]
				characters_images.append({
					"name": filename,
					"sex": "F" if "_f_" in filename else "M",
					"voc": filename[:filename.index("_")],
					"race": race,
					"url": str(file_url)
				})
	# towns images : 
	towns_images = []
	if os.path.exists(TOWNS_IMAGES_PATH):
		for filename in os.listdir(TOWNS_IMAGES_PATH):
			if "_start_" in filename:
				full_path = os.path.join(TOWNS_IMAGES_PATH, filename)
				if (os.path.isfile(full_path) and filename.lower().endswith(valid_extensions) and filename[:]):
					file_url = request.url_for("towns", path=filename)
					name = filename[:filename.index("_")]
					towns_images.append({
						"id": "lieu:"+ name,
						"label": name,
						"blurb": name,
						"filename": filename,
						"url": str(file_url)
					})
	return templates.TemplateResponse(
		request=request,
		name ="user_home_telluris.html",
		context= {
			"user_doc": current_user,
			"title": 'Your domain',
			"races" : races,
			"races_proximity" : races_proximity,
			"vocations" : vocations,
			"vocations_proximity" : vocations_proximity,
			"characters_images": characters_images,
			"towns_images": towns_images
		}
	)
	
@app.get("/tableau/{x}/{y}")
def get_tableau(x: int, y: int):
    # Génère dynamiquement le tableau de 24 lignes et 43 colonnes
    tableau = [[1] * x for _ in range(y)]
	
    return {
			  "type": "lieu",
			  "label": "La capitale Lutecia",
			  "image": "lutecia.png",
			  "dimensions": {
				"x": x,
				"y": y
			  },
			  "cells": tableau}
	
@app.get("/play", response_class=HTMLResponse)
async def get_playground(request: Request, current_user: Annotated[User, Depends(get_current_user)]):
	if not current_user:
		return RedirectResponse(url="/auth", headers=request.headers)
	
	character_id = current_user["selected_character"]
	character = current_user["characters"][character_id]
	vocations = db.get("rules:vocations")
	vocation = next((v for v in vocations["value"] if v["id"] == character["voc"]), None)
	lieu = character.get("lieu",character["cite"])
	grid_doc = db.get(lieu)
	position = character.get("position", {"x" : 1 ,"y" : 1})
	links = get_lieu_links(current_user)
	# Gestion de la grille
	dimensions = grid_doc.get("dimensions",None)
	image = grid_doc.get("image")
	with Image.open(TOWNS_IMAGES_PATH+"/"+image) as img:
		# Récupérer les dimensions (largeur, hauteur)
		largeur, hauteur = img.size
		if dimensions:
			dim_x = round(largeur/dimensions["x"])
			dim_y = round(hauteur/dimensions["y"])
		else:
			dim_x = largeur
			dim_y = hauteur

	access = get_lieu_directions(current_user, grid_doc, position)
	
	with Image.open(CHARACTERS_IMAGES_PATH+"/"+character["portrait"]) as portrait:
		portrait_largeur, portrait_hauteur = portrait.size
		
	return templates.TemplateResponse(
		request=request,
		name ="play_town_telluris.html",
		context= {
			"title": grid_doc.get("label"),
			"character": character,
			"portrait_largeur": portrait_largeur,
			"portrait_hauteur": portrait_hauteur,
			"portrait_disp_largeur": 100,
			"portrait_disp_hauteur": 100,
			"lieu": lieu,
			"image": image,
			"position": position,
			"links": links,
			"vocation": vocation,
			"dimensions": dimensions,
			"dim_x": dim_x,
			"dim_y": dim_y,
			"access" : access
		}
	)