import os
from typing import Annotated
from fastapi import FastAPI, Request, Depends, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from PIL import Image
from routers.user import user_router, User
from routers.oauth import router as oauth_router
from routers.zones import zones_router
from routers.bestiaire import bestiaire_router
from routers.combat import combat_router
from utils.combat import get_combat_grid, finalize_combat
from db.config import find_docs, get_doc, save_doc, delete_doc, dump_all_docs
from utils.auth import get_current_user
from utils.characters import get_user_characters, get_selected_character
from utils.lieux import get_lieu_links, get_lieu_directions, get_lieux_ids, lieu_router
from models.character_stats import compute_derived_stats, BaseStats, compute_stat_cap, compute_character_level, XP_COEFF, XP_VOC_COEFF

app = FastAPI()

# Add CORS middleware
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],	# In production, limit this to your frontend domain
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)
# SameSite=none required for Apple's cross-site POST callback; fine for Google/Facebook too
app.add_middleware(
	SessionMiddleware,
	secret_key=os.getenv("SESSION_SECRET", os.getenv("SECRET_KEY")),
	same_site="none",
	https_only=False,
)

# Definit ou se trouvent les fichiers HTML
templates = Jinja2Templates(directory="templates")
templates.env.policies["json.dumps_kwargs"] = {"sort_keys": False}

app.mount("/scripts", StaticFiles(directory="templates/scripts"), name="scripts")
app.mount("/icons", StaticFiles(directory="templates/resources/icons"), name="icons")
CHARACTERS_IMAGES_PATH = "templates/resources/characters"
app.mount("/characters", StaticFiles(directory=CHARACTERS_IMAGES_PATH), name="characters")
BATTLE_MAPS_IMAGES_PATH = "templates/resources/battle_maps"
app.mount("/battle_maps", StaticFiles(directory=BATTLE_MAPS_IMAGES_PATH), name="battle_maps")
MAPS_IMAGES_PATH = "templates/resources/maps"
app.mount("/maps", StaticFiles(directory=MAPS_IMAGES_PATH), name="maps")
TOWNS_IMAGES_PATH = "templates/resources/towns"
app.mount("/towns", StaticFiles(directory=TOWNS_IMAGES_PATH), name="towns")
MONSTERS_IMAGES_PATH = "templates/resources/monsters"
app.mount("/monsters", StaticFiles(directory=MONSTERS_IMAGES_PATH), name="monsters")

app.include_router(user_router, prefix="/api")
app.include_router(lieu_router, prefix="/api")
app.include_router(zones_router, prefix="/api")
app.include_router(bestiaire_router, prefix="/api")
app.include_router(combat_router, prefix="/api")
app.include_router(oauth_router)
	
@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
	return templates.TemplateResponse(
		request=request, 
		name="home_telluris.html", 
		context={"title": "Ubi Chartae Finiunt"}
	)
	
@app.get("/admin/bestiaire", response_class=HTMLResponse)
def bestiaire_editor(request: Request, current_user: Annotated[User, Depends(get_current_user)]):
	if (not current_user or
		"admin" not in current_user or
		current_user["admin"] != 1):
		return RedirectResponse(url="/auth", headers=request.headers)
	return templates.TemplateResponse(
		request=request,
		name="bestiaire_editor.html",
		context={"title": "Éditeur Bestiaire"}
	)

@app.get("/admin/editor", response_class=HTMLResponse)
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

def _require_admin_page(request: Request, current_user):
	"""Retourne une RedirectResponse vers /auth si l'utilisateur n'est pas admin, sinon None."""
	if (not current_user or "admin" not in current_user or current_user["admin"] != 1):
		return RedirectResponse(url="/auth", headers=request.headers)
	return None

@app.get("/admin/exports", response_class=HTMLResponse)
def admin_exports(request: Request, current_user: Annotated[User, Depends(get_current_user)]):
	redirect = _require_admin_page(request, current_user)
	if redirect:
		return redirect
	return templates.TemplateResponse(
		request=request,
		name="admin_exports.html",
		context={"title": "Exports"}
	)

@app.get("/admin/exports/bestiaire")
def admin_export_bestiaire(request: Request, current_user: Annotated[User, Depends(get_current_user)]):
	if (not current_user or "admin" not in current_user or current_user["admin"] != 1):
		raise HTTPException(status_code=403, detail="Admin only")
	from dev.export_bestiaire import build_bestiaire_xlsx_bytes
	data = build_bestiaire_xlsx_bytes()
	return Response(
		content=data,
		media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
		headers={"Content-Disposition": 'attachment; filename="bestiaire.xlsx"'},
	)

@app.get("/admin/exports/couchdb")
def admin_export_couchdb(request: Request, current_user: Annotated[User, Depends(get_current_user)]):
	if (not current_user or "admin" not in current_user or current_user["admin"] != 1):
		raise HTTPException(status_code=403, detail="Admin only")
	import json, datetime
	# Exclut les documents utilisateurs (données sensibles : hash de mot de passe, etc.).
	docs = [d for d in dump_all_docs() if not str(d.get("_id", "")).startswith("user:")]
	now = datetime.datetime.utcnow()
	payload = {
		"db": "telluris",
		"exported_at": now.isoformat() + "Z",
		"doc_count": len(docs),
		"docs": docs,
	}
	data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
	filename = f"telluris-dump-{now:%Y%m%d-%H%M%S}.json"
	return Response(
		content=data,
		media_type="application/json",
		headers={"Content-Disposition": f'attachment; filename="{filename}"'},
	)

@app.get("/auth", response_class=HTMLResponse)
async def read_page_auth(request: Request):
	is_new = "new" in request.query_params
	is_google_auth = bool(os.getenv("GOOGLE_CLIENT_ID"))
	is_apple_auth = bool(os.getenv("APPLE_CLIENT_ID"))
	is_facebook_auth = bool(os.getenv("FACEBOOK_CLIENT_ID"))
	return templates.TemplateResponse(
		request=request, 
		name="auth_telluris.html", 
		context={
			"title": "Authentification",
			"is_new": is_new,
			"is_google_auth": is_google_auth,
			"is_apple_auth": is_apple_auth,
			"is_facebook_auth": is_facebook_auth
		}
	)
	
@app.get("/embleme", response_class=HTMLResponse)
async def get_embleme(request: Request, current_user: Annotated[User, Depends(get_current_user)]):
	if not current_user:
		return RedirectResponse(url="/auth", headers=request.headers)
	# rules :
	races = get_doc("rules:races")
	races_proximity = get_doc("rules:races_proximity")
	vocations = get_doc("rules:vocations")
	vocations_proximity = get_doc("rules:vocations_proximity")
	
	# characters :
	characters = get_user_characters(current_user)
	
	# characters available images : 
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
					name = filename[:filename.index("_")]
					lieu_id = "lieu:"+ name
					if get_doc(lieu_id):
						file_url = request.url_for("towns", path=filename)
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
			"characters": characters,
			"title": 'Your domain',
			"races" : races,
			"races_proximity" : races_proximity,
			"vocations" : vocations,
			"vocations_proximity" : vocations_proximity,
			"characters_images": characters_images,
			"towns_images": towns_images,
			"xp_coeff": XP_COEFF,
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
	
	user_id = current_user["_id"]
	db_user = get_doc(user_id)
	if not db_user:
		return RedirectResponse(url="/auth", headers=request.headers)
	
	# Selected character for current user
	character = get_selected_character(current_user)

	if not character:
		return RedirectResponse(url="/auth", headers=request.headers)

	# Combats : on ne peut pas abandonner un combat actif en quittant la page.
	# Un combat actif → on y retourne ; les combats terminés → récompense (filet de
	# sécurité, idempotent) puis nettoyage.
	user_combats = find_docs({"type": "combat", "user_id": user_id}) or []
	for c in user_combats:
		if c.get("character_id") != character["_id"]:
			continue
		if c.get("status") == "active":
			return RedirectResponse(url=f"/combat/{c['_id']}", headers=request.headers)
		finalize_combat(c)  # filet de sécurité, idempotent
		delete_doc(c)
	# Relire le personnage frais juste avant le rendu : issue d'un combat 
	character = get_doc(character["_id"]) or character

	vocations = get_doc("rules:vocations")
	vocation = next((v for v in vocations["value"] if v["id"] == character["voc"]), None)
	races = get_doc("rules:races")
	race = next((r for r in races["value"] if r["id"] == character["race"]), None)
	lieu = character.get("lieu",character["cite"])
	grid_doc = get_doc(lieu)
	position = character.get("position", {"x" : 1 ,"y" : 1})
	links = get_lieu_links(current_user)
	# Gestion de la grille
	dimensions = grid_doc.get("dimensions",None)
	image = grid_doc.get("image")
	if os.path.exists(os.path.join(TOWNS_IMAGES_PATH, image)):
		image_path = os.path.join(TOWNS_IMAGES_PATH, image)
		image_route = "towns"
	elif os.path.exists(os.path.join(MAPS_IMAGES_PATH, image)):
		image_path = os.path.join(MAPS_IMAGES_PATH, image)
		image_route = "maps"
	elif os.path.exists(os.path.join(BATTLE_MAPS_IMAGES_PATH, image)):
		image_path = os.path.join(BATTLE_MAPS_IMAGES_PATH, image)
		image_route = "battle_maps"
	else:
		raise HTTPException(status_code=404, detail=f"Image introuvable : {image}")
	with Image.open(image_path) as img:
		# Récupérer les dimensions (largeur, hauteur)
		largeur, hauteur = img.size
		if dimensions:
			dim_x = round(largeur/dimensions["x"])
			dim_y = round(hauteur/dimensions["y"])
		else:
			dim_x = largeur
			dim_y = hauteur

	access = get_lieu_directions(current_user, grid_doc, position)

	stats_cur = character.get("caracteristiques_current", {})
	base = BaseStats(
		v=stats_cur.get("V", 0),
		f=stats_cur.get("F", 0),
		r=stats_cur.get("R", 0),
		ag=stats_cur.get("Ag", 0),
		vol=stats_cur.get("Vol", 0),
		int_=stats_cur.get("Int", 0),
		cha=stats_cur.get("Cha", 0),
		ch=stats_cur.get("Ch", 0),
	)
	voc_niveau = character.get("vocations_niveaux", {}).get(character.get("voc", ""), 0)
	derived = compute_derived_stats(
		base=base,
		niveau=voc_niveau,
	)
	character["derived_stats"] = derived.model_dump()
	character["niveau"] = compute_character_level(character.get("xp_total", 0))

	# Résolution inventaire : IDs → documents complets
	character["inventaire"] = [
		doc for item_id in character.get("inventaire", [])
		if item_id and (doc := get_doc(item_id))
	]
	# Résolution slots : IDs → documents complets (None si vide)
	character["slots"] = {
		slot: get_doc(item_id) if item_id else None
		for slot, item_id in character.get("slots", {}).items()
	}

	nb_max = race.get("nb_max_accessibles", 3) if race else 3
	stats_max_race = race.get("stats_max", {}) if race else {}
	max_bonus = race.get("max_bonus") if race else None
	max_bonus_used = character.get("max_bonus_used")
	stat_caps = {
		code: compute_stat_cap(
			stat_key=code,
			stats_max=stats_max_race,
			nb_max_accessibles=nb_max,
			current_stats=stats_cur,
			max_bonus=max_bonus,
			max_bonus_used=max_bonus_used,
		)
		for code in ["V", "F", "R", "Ag", "Vol", "Int", "Cha", "Ch"]
	}

	with Image.open(CHARACTERS_IMAGES_PATH+"/"+character["image"]) as portrait:
		portrait_largeur, portrait_hauteur = portrait.size
		
	return templates.TemplateResponse(
		request=request,
		name ="play_town_telluris.html",
		context= {
			"title": grid_doc.get("label"),
			"image_route": image_route,
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
			"race": race,
			"dimensions": dimensions,
			"dim_x": dim_x,
			"dim_y": dim_y,
			"access" : access,
			"stat_caps": stat_caps,
			"xp_coeff": XP_COEFF,
			"xp_voc_coeff": XP_VOC_COEFF,
		},
		# Page dynamique par-personnage (PV/XP changent après combat) : jamais en cache,
		# sinon le retour de combat affiche un état périmé tant qu'on n'a pas rechargé.
		headers={"Cache-Control": "no-store"},
	)

@app.get("/combat/{combat_id}", response_class=HTMLResponse)
async def get_combat_page(
	request: Request,
	combat_id: str,
	current_user: Annotated[User, Depends(get_current_user)],
):
	if not current_user:
		return RedirectResponse(url="/auth", headers=request.headers)

	combat_doc = get_doc(combat_id)
	if not combat_doc or combat_doc.get("type") != "combat":
		raise HTTPException(status_code=404, detail="Combat introuvable")

	if combat_doc["user_id"] != current_user["_id"]:
		return RedirectResponse(url="/play", headers=request.headers)

	character = get_doc(combat_doc["character_id"])
	if not character:
		return RedirectResponse(url="/play", headers=request.headers)

	return templates.TemplateResponse(
		request=request,
		name="combat_telluris.html",
		context={
			"title": "Combat",
			"combat": combat_doc,
			"character": character,
			"grid": get_combat_grid(combat_doc),
		},
		headers={"Cache-Control": "no-store"},
	)

@app.get("/insert-bulck-db")
async def insert_bulck_db():
	try:
		items = []
		count: int = 0
		for item in items:
			#print(item["nom"])
			#save_doc(item)
			count += 1
		return {
			"status": "done",
			"count": count
		}
	except Exception as e:
		return {"status": "error", "message": str(e)}