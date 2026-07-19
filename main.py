import os
import json
import logging
from typing import Annotated
from fastapi import FastAPI, Request, Depends, HTTPException, Response, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from PIL import Image
from routers.user import user_router, User
from routers.oauth import router as oauth_router
from routers.zones import zones_router
from routers.bestiaire import bestiaire_router
from routers.combat import combat_router, _actor_character_id
from routers.quetes import quetes_router
from routers.pnj import pnj_router
from routers.recrutement import recrutement_router
from routers.montures import montures_router
from utils.combat import get_combat_grid, finalize_combat
from db.config import find_docs, get_doc, save_doc, delete_doc, dump_all_docs
from utils.auth import get_current_user
from utils.characters import get_user_characters, get_selected_character, sync_equipment_bonus, resolve_item_ref, charge_max_of
from utils import quetes
from utils import bois
from utils import consommables
from utils import sorts as sorts_util
from utils import competences as competences_util
from utils import focalisation
from utils import pnj as pnj_util
from utils import intro as intro_util
from utils import transport as transport_util
from utils import chasse as chasse_util
from utils import recrutement as recrutement_util
from utils import montures as montures_util
from utils import fiche as fiche_util
from utils import lint_dialogues
from utils.marche import tick_atelier, reset_prix_cache, besoins_categorie, appro_leaves_categorie, relations_lieux_payload
from utils.lieux import get_lieu_links, get_lieu_directions, get_lieux_ids, lieu_router
from models import character_stats
from models.character_stats import compute_derived_stats, BaseStats, compute_stat_cap, compute_character_level, xp_seuil_niveau, load_world_variables

app = FastAPI()

logger = logging.getLogger("telluris")
if not logger.handlers:
	_log_handler = logging.StreamHandler()
	_log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
	logger.addHandler(_log_handler)
logger.setLevel(logging.INFO)
logger.propagate = False


@app.on_event("startup")
def _charger_variables_monde() -> None:
	"""Charge les variables de monde (rules:world_variables) au démarrage.
	Fallback silencieux sur les valeurs par défaut du module si la DB/doc manque."""
	load_world_variables()


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
PNJ_IMAGES_PATH = "templates/resources/pnj"
app.mount("/pnj", StaticFiles(directory=PNJ_IMAGES_PATH), name="pnj")

app.include_router(user_router, prefix="/api")
app.include_router(lieu_router, prefix="/api")
app.include_router(zones_router, prefix="/api")
app.include_router(bestiaire_router, prefix="/api")
app.include_router(combat_router, prefix="/api")
app.include_router(quetes_router, prefix="/api")
app.include_router(pnj_router, prefix="/api")
app.include_router(recrutement_router, prefix="/api")
app.include_router(montures_router, prefix="/api")
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
		name="admin_bestiaire_editor.html",
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
		name="admin_map_editor.html",
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

@app.get("/admin", response_class=HTMLResponse)
def admin_home(request: Request, current_user: Annotated[User, Depends(get_current_user)]):
	redirect = _require_admin_page(request, current_user)
	if redirect:
		return redirect
	return templates.TemplateResponse(
		request=request,
		name="admin_telluris.html",
		context={"title": "Administration"}
	)

def _distinct_doc_types() -> list:
	"""Types de documents réellement présents en base (user:* exclus, comme le dump).
	Partagé par /admin/exports et /admin/table (liste de sélection)."""
	return sorted({
		d["type"] for d in dump_all_docs()
		if isinstance(d, dict) and d.get("type")
		and not str(d.get("_id", "")).startswith("user:")
	})

@app.get("/admin/exports", response_class=HTMLResponse)
def admin_exports(request: Request, current_user: Annotated[User, Depends(get_current_user)]):
	redirect = _require_admin_page(request, current_user)
	if redirect:
		return redirect
	return templates.TemplateResponse(
		request=request,
		name="admin_exports.html",
		context={"title": "Exports", "doc_types": _distinct_doc_types()}
	)

@app.get("/admin/table", response_class=HTMLResponse)
def admin_table(request: Request, current_user: Annotated[User, Depends(get_current_user)]):
	"""Écran « Mise à jour en tableau » : visualisation tabulaire des docs CouchDB par type,
	avec édition du JSON d'un élément."""
	redirect = _require_admin_page(request, current_user)
	if redirect:
		return redirect
	return templates.TemplateResponse(
		request=request,
		name="admin_table.html",
		context={"title": "Mise à jour en tableau", "doc_types": _distinct_doc_types()}
	)

@app.get("/admin/table/data")
def admin_table_data(
	current_user: Annotated[User, Depends(get_current_user)],
	doc_type: str = Query("", alias="type"),
):
	"""Documents d'un type (JSON simple pour l'UI tableau ; user:* exclus)."""
	if (not current_user or "admin" not in current_user or current_user["admin"] != 1):
		raise HTTPException(status_code=403, detail="Admin only")
	t = (doc_type or "").strip()
	if not t:
		raise HTTPException(status_code=400, detail="Paramètre 'type' requis")
	docs = [d for d in (find_docs({"type": t}) or [])
			if not str(d.get("_id", "")).startswith("user:")]
	return {"type": t, "docs": docs}

@app.put("/admin/doc")
def admin_update_doc(
	current_user: Annotated[User, Depends(get_current_user)],
	payload: dict = Body(...),
):
	"""Met à jour (ou crée) un document depuis le JSON édité dans l'écran tableau.
	Réattache le `_rev` courant de la base (anti-conflit) avant l'écriture."""
	if (not current_user or "admin" not in current_user or current_user["admin"] != 1):
		raise HTTPException(status_code=403, detail="Admin only")
	doc_id = payload.get("_id")
	if not doc_id:
		raise HTTPException(status_code=400, detail="Champ '_id' requis.")
	existing = get_doc(doc_id)
	if existing and existing.get("_rev"):
		payload["_rev"] = existing["_rev"]   # _rev courant → évite le conflit d'écriture
	elif "_rev" in payload and not existing:
		payload.pop("_rev")                  # doc absent en base → création (pas de _rev)
	saved = save_doc(payload)
	if saved is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — rechargez et réessayez.")
	return {"saved": True, "doc": payload}

@app.delete("/admin/doc")
def admin_delete_doc(
	current_user: Annotated[User, Depends(get_current_user)],
	doc_id: str = Query("", alias="id"),
):
	"""Supprime un document depuis l'écran tableau (bouton Delete de l'overlay JSON).
	Le `_rev` est relu en base (jamais celui du client), comme pour la mise à jour."""
	if (not current_user or "admin" not in current_user or current_user["admin"] != 1):
		raise HTTPException(status_code=403, detail="Admin only")
	doc_id = (doc_id or "").strip()
	if not doc_id:
		raise HTTPException(status_code=400, detail="Paramètre 'id' requis.")
	existing = get_doc(doc_id)
	if not existing:
		raise HTTPException(status_code=404, detail="Document introuvable.")
	delete_doc(existing)
	# `delete_doc` avale les exceptions et renvoie None dans TOUS les cas : le succès
	# ne se lit pas au retour, on le vérifie par relecture.
	if get_doc(doc_id) is not None:
		raise HTTPException(status_code=409, detail="Échec de la suppression — rechargez et réessayez.")
	return {"deleted": True, "_id": doc_id}

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

@app.post("/admin/table/export.xlsx")
def admin_table_export_xlsx(
	current_user: Annotated[User, Depends(get_current_user)],
	payload: dict = Body(...),
):
	"""Export Excel des lignes affichées dans l'écran tableau. Le client envoie les
	colonnes (clés de 1er niveau ordonnées) et les documents complets déjà filtrés ;
	la sérialisation OOXML est mutualisée avec l'export bestiaire (utils/xlsx)."""
	if (not current_user or "admin" not in current_user or current_user["admin"] != 1):
		raise HTTPException(status_code=403, detail="Admin only")
	import re
	from utils.xlsx import build_xlsx_bytes, rows_from_docs
	columns = payload.get("columns")
	rows = payload.get("rows")
	if not isinstance(columns, list) or not isinstance(rows, list):
		raise HTTPException(status_code=400, detail="Champs 'columns' et 'rows' (listes) requis.")
	sheet = rows_from_docs(columns, rows)
	data = build_xlsx_bytes([("Export", sheet, frozenset())])
	# Nom fourni par le client (type + filtres + horodatage) ; assaini par sécurité.
	name = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(payload.get("filename") or "")) or "export.xlsx"
	if not name.lower().endswith(".xlsx"):
		name += ".xlsx"
	return Response(
		content=data,
		media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
		headers={"Content-Disposition": f'attachment; filename="{name}"'},
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

@app.get("/admin/exports/by-type")
def admin_export_by_type(
	request: Request,
	current_user: Annotated[User, Depends(get_current_user)],
	doc_type: str = Query("", alias="type"),
):
	"""Export JSON de tous les documents partageant la même valeur de champ `type`.
	Fichier nommé `<type>-AAAAMMJJ-HHMMSS.json`."""
	if (not current_user or "admin" not in current_user or current_user["admin"] != 1):
		raise HTTPException(status_code=403, detail="Admin only")
	import json, datetime, re
	t = (doc_type or "").strip()
	if not t:
		raise HTTPException(status_code=400, detail="Paramètre 'type' requis")
	# Exclut les user:* (cohérent avec le dump complet : données sensibles).
	docs = [d for d in (find_docs({"type": t}) or [])
			if not str(d.get("_id", "")).startswith("user:")]
	now = datetime.datetime.utcnow()
	payload = {
		"db": "telluris",
		"type": t,
		"exported_at": now.isoformat() + "Z",
		"doc_count": len(docs),
		"docs": docs,
	}
	data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
	safe_t = re.sub(r"[^A-Za-z0-9_-]+", "_", t) or "type"   # nom de fichier sûr
	filename = f"{safe_t}-{now:%Y%m%d-%H%M%S}.json"
	return Response(
		content=data,
		media_type="application/json",
		headers={"Content-Disposition": f'attachment; filename="{filename}"'},
	)

@app.get("/admin/world_variables")
def admin_get_world_variables(request: Request, current_user: Annotated[User, Depends(get_current_user)]):
	"""Renvoie les variables de monde actuellement appliquées en mémoire."""
	if (not current_user or "admin" not in current_user or current_user["admin"] != 1):
		raise HTTPException(status_code=403, detail="Admin only")
	return character_stats.current_world_variables()

@app.get("/admin/world_variables/defaults")
def admin_get_world_variables_defaults(request: Request, current_user: Annotated[User, Depends(get_current_user)]):
	"""Valeurs PAR DÉFAUT du code (snapshot figé à l'import, hors doc CouchDB) — référence
	lecture seule pour /admin."""
	if (not current_user or "admin" not in current_user or current_user["admin"] != 1):
		raise HTTPException(status_code=403, detail="Admin only")
	return character_stats.CODE_DEFAULTS

@app.put("/admin/world_variables")
def admin_save_world_variables(
	current_user: Annotated[User, Depends(get_current_user)],
	payload: dict = Body(...),
):
	"""Persiste les variables éditées dans le doc CouchDB rules:world_variables.
	N'applique PAS les valeurs en mémoire : utiliser /reload pour les charger à chaud.

	CouchDB exige le _rev courant pour mettre à jour un doc existant : on le lit
	juste avant l'écriture et on l'attache (création sans _rev si le doc n'existe pas)."""
	if (not current_user or "admin" not in current_user or current_user["admin"] != 1):
		raise HTTPException(status_code=403, detail="Admin only")

	doc_id = character_stats.WORLD_VARIABLES_DOC_ID

	def _save_with_current_rev():
		doc = {"_id": doc_id, "type": "rules", "value": payload}
		existing = get_doc(doc_id)
		print("existing",existing)
		if existing and existing.get("_rev"):
			doc["_rev"] = existing["_rev"]
		return save_doc(doc)

	saved = _save_with_current_rev()
	if saved is None:
		raise HTTPException(status_code=500, detail="Échec de la sauvegarde CouchDB (rules:world_variables).")
	return {"saved": True, "id": doc_id, "value": payload}

@app.post("/admin/world_variables/reload")
def admin_reload_world_variables(request: Request, current_user: Annotated[User, Depends(get_current_user)]):
	"""Recharge rules:world_variables depuis CouchDB à chaud (sans redéploiement)."""
	if (not current_user or "admin" not in current_user or current_user["admin"] != 1):
		raise HTTPException(status_code=403, detail="Admin only")
	variables = load_world_variables()
	reset_prix_cache()   # MARGE_TRANSFO / recettes / items peuvent avoir changé → vider le cache de coût
	return {"reloaded": True, "variables": variables}

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
			"xp_coeff": character_stats.XP_COEFF,
			# Choix du sort de départ à la création : vocations « pures magiciennes »
			# + sorts niveau 0 par vocation (id, nom, icon, description).
			"sort_vocations_depart": list(character_stats.SORT_VOCATIONS_DEPART),
			"sorts_depart": sorts_util.sorts_depart_par_vocation(find_docs),
			# Compétences niveau 0 par vocation : les vocations HORS sort_vocations_depart
			# choisissent une compétence à la place du sort (complément exact, dérivé client).
			"competences_depart": competences_util.competences_depart_par_vocation(find_docs),
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
	# Atelier : chaque visite du lieu lance un tick marché (approvisionnement + production +
	# écoulement PNJ des produits finis), comme à chaque vente. On ne déclenche que s'il y a de la
	# matière/produits en stock OU un approvisionnement configuré pour la catégorie (sinon le lieu
	# ne pourrait jamais s'amorcer) ; on ne persiste que si quelque chose a changé.
	if grid_doc and (grid_doc.get("stock_matieres") or grid_doc.get("stock_vente")
			or appro_leaves_categorie(grid_doc.get("categorie"))):
		if tick_atelier(grid_doc):
			save_doc(grid_doc)
	# Courses de transport échues : l'expiration est PARESSEUSE (aucun tick de fond dans le
	# jeu) — on la solde à chaque point de passage. La sanction de réputation part avec.
	transports_echoues = transport_util.traiter_expirations(
		character, quetes.now_epoch(), get_doc, save_doc)
	# PNJ de lieu : tirage de présence à l'ENTRÉE (persisté → un refresh ne re-tire pas).
	# Un magasin n'a pas de champ `pnj` : son tenancier est dérivé de sa catégorie.
	# Écriture dans le GET assumée (précédent : tick_atelier) ; un conflit de save serait
	# rejoué au prochain rendu, on ne lève pas de 409 ici.
	change = bool(transports_echoues)
	change |= pnj_util.poser_pnj_present(character, grid_doc, marchand_fn=transport_util.entree_marchand)
	# Le PNJ arrêté pour cette entrée est résolu AVANT l'offre de course : c'est lui qui peut
	# porter une course écrite (`services.transport.offre`), auquel cas le lieu n'a pas à être
	# un magasin (le réceptionniste de la guilde confie sa mission d'initiation).
	pnj_entree = pnj_util.entree_pnj_active(character, grid_doc, transport_util.entree_marchand)
	pnj_doc = get_doc(pnj_entree["character"]) if pnj_entree else None
	# Offre de course : tirée à l'entrée, persistée (même sémantique que pnj_present).
	change |= transport_util.poser_transport_offert(character, grid_doc, find_docs, get_doc,
													pnj_doc=pnj_doc)
	# Compagnons : départs volontaires paresseux (affinité tombée sous le seuil pendant
	# l'absence) — les docs `aventurier:*` sont annexes, persistés séparément ; le retrait
	# du groupe part avec le save du personnage ci-dessous. Toast au rendu.
	# Offre d'épreuve de RANG : au comptoir de guilde avec PNJ présent, tirée à l'entrée (même
	# sémantique que l'offre de course). Hors comptoir, purge un éventuel reliquat d'offre.
	change |= chasse_util.poser_rang_offert(character, grid_doc, get_doc, find_docs,
		pnj_present=bool(pnj_entree and pnj_doc))
	compagnons_partis = recrutement_util.departs_volontaires(character, get_doc)
	for _av in compagnons_partis:
		save_doc(_av)
	change |= bool(compagnons_partis)
	if change:
		save_doc(character)
	pnj_present = pnj_util.pnj_payload(pnj_entree, pnj_doc) if (pnj_entree and pnj_doc) else None
	position = character.get("position", {"x" : 1 ,"y" : 1})
	links = get_lieu_links(current_user)
	# Gestion de la grille
	dimensions = grid_doc.get("dimensions",None)
	image = grid_doc.get("image")
	# PNJ présent : l'entrée du lieu peut fournir une variante d'image AVEC le PNJ visible
	# (repli silencieux sur l'image de base — ex. version « _vide » — si absente du disque).
	if pnj_present and pnj_present.get("image_lieu") and os.path.exists(
			os.path.join(TOWNS_IMAGES_PATH, pnj_present["image_lieu"])):
		image = pnj_present["image_lieu"]
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

	# Dérivées bufées (équipement, passives, consommables/sorts), charge max exceptée : elle
	# reste brute, c'est la limite réellement appliquée par la garde de surcharge. Les stats
	# BRUTES restent la référence des plafonds/coûts d'XP (stat_caps, dans bloc_fiche).
	# Les stats dérivées ne sont jamais stockées.
	character["derived_stats"] = fiche_util.derived_de(character)
	character["niveau"] = compute_character_level(character.get("xp_total", 0))

	# Résolution inventaire : références → documents complets (poids d'instance inclus)
	character["inventaire"] = [
		doc for ref in character.get("inventaire", [])
		if (doc := resolve_item_ref(ref))
	]
	# Résolution slots : références → documents complets (None si vide)
	character["slots"] = {
		slot: resolve_item_ref(ref) if ref else None
		for slot, ref in character.get("slots", {}).items()
	}
	# Résolution des objets au sol (transitoires) : références → documents complets
	character["objets_au_sol"] = [
		doc for ref in character.get("objets_au_sol", [])
		if (doc := resolve_item_ref(ref))
	]

	# Contenu des onglets Stats et ⚡ (plafonds, seuils d'XP, profil modifié, sorts, écoles,
	# compétences) : SOURCE UNIQUE `utils/fiche.bloc_fiche`, partagée avec la fiche d'un
	# compagnon (GET /api/groupe/compagnon/{id}) — le client rend les deux avec les mêmes
	# fonctions, sous les mêmes clés.
	fiche_bloc = fiche_util.bloc_fiche(character, get_doc, find_docs, race or {})

	# Pas de mesure du portrait ici : la fiche sert aussi les COMPAGNONS, dont l'image n'a pas
	# les dimensions de celle du joueur. La taille native est mesurée dans le navigateur
	# (naturalWidth/Height, cf. makePortraitViewport) — la mesurer ici la figerait sur le
	# personnage de la page. (La page de combat, elle, garde sa mesure : cf. /combat.)

	# Quêtes : suivi rendu serveur dans l'onglet 📜 de la fiche (progression + récompenses).
	# `quete_detail` lit l'inventaire pour la progression des collectes (item_ref_id gère les
	# refs déjà résolues en docs ci-dessus). `est_guilde` conditionne le bouton « Tableau ».
	character["quetes_actives_detail"], character["quetes_terminees_detail"] = quetes.fiche_details(character)
	est_guilde = (grid_doc.get("categorie") == "guilde_aventurier")

	# Recrutement : `est_recrutement` conditionne le bouton « Recrues » (le contrôle de la
	# carte d'aventurier se fait à l'ouverture du board — 403 explicite).
	est_recrutement = recrutement_util.lieu_recrute(grid_doc)

	# Étable : `est_etable` conditionne le bouton « Montures ». Pas de contrôle d'accès
	# ici (ni carte, ni relation) — acheter une bête de somme ne demande rien d'autre
	# que de l'argent, contrairement au tableau de recrutement.
	est_etable = montures_util.lieu_vend_montures(grid_doc)

	# Ressource récoltable (événement de zone « ressource ») : résolue pour l'affichage initial
	# du bouton « Récolter » dans la sidebar (champ transitoire posé par move_character).
	ressource_recoltable = None
	_rec_ref = character.get("ressource_recoltable")
	if _rec_ref:
		_rec_doc = resolve_item_ref(_rec_ref)
		if _rec_doc:
			ressource_recoltable = {
				"item": _rec_doc.get("item"),
				"nom": _rec_doc.get("nom", "Ressource"),
				"icon": _rec_doc.get("icon", "🌿"),
				"poids": _rec_doc.get("poids", 0),
				"a_couper": bois.item_est_coupable(_rec_doc),
			}

	# Relations de lieu : vue agrégée des relations marchandes du personnage (docs
	# type:"relation"). Échelle 0–100 (neutre 50 ; 0 = transactions interdites), distincte
	# des affinités PNJ (0–100, neutre 50, champ affinites_detail). Rendu serveur dans l'onglet 🤝 ;
	# le même payload est resynchronisé côté client via quotes/marchander (renderFicheRelations).
	relations_lieux = relations_lieux_payload(character)

	# Focalisation : état (boutons 🧭/🎯) + guidage éventuel vers un lieu, servis au rendu
	# initial (le changement de lieu recharge la page → l'état doit survivre au reload).
	focalisation_payload = focalisation.payload_client(character, get_doc)
	guidage_payload = focalisation.guidage(character, grid_doc, find_docs, get_doc)

	# Intro narrative : overlay au premier rendu (tant qu'aucune raison de fuite n'est
	# choisie) — le bloc de personnalisation vit sur le doc lieu de la cité.
	intro_payload = intro_util.payload_overlay(character, grid_doc)

	return templates.TemplateResponse(
		request=request,
		name ="play_town_telluris.html",
		context= {
			"title": grid_doc.get("label"),
			"image_route": image_route,
			"character": character,
			"lieu": lieu,
			"image": image,
			"position": position,
			"links": links,
			"vocation": vocation,
			# Icône + libellé par vocation : la fiche sert aussi les compagnons, qui n'ont
			# pas forcément la vocation du joueur (cf. openCompagnonSheet).
			"vocations_labels": {
				v["id"]: {"icon": v.get("icon", ""), "label": v.get("label", v["id"])}
				for v in (vocations.get("value") or [])
			},
			"race": race,
			"dimensions": dimensions,
			"dim_x": dim_x,
			"dim_y": dim_y,
			"access" : access,
			# stat_caps, xp_coeff/xp_voc_coeff, xp_niv_prev/next, effets_actifs,
			# caracts_detail, sorts*, competences* — cf. utils/fiche.bloc_fiche.
			**fiche_bloc,
			"lieu_categorie": grid_doc.get("categorie"),
			"achat_sous_categories": besoins_categorie(grid_doc.get("categorie")),
			"est_guilde": est_guilde,
			"est_recrutement": est_recrutement,
			"est_etable": est_etable,
			# Compagnons connus + affinités (onglet 🤝 section 👥, rendu client) — resynchronisé
			# après embauche/congédiement/retour de combat.
			"affinites_detail": recrutement_util.affinites_detail_payload(character, get_doc),
			# Compagnons partis d'eux-mêmes pendant l'absence (affinité sous le seuil) : toast.
			"compagnons_partis": [
				f"{av.get('prenom', '')} {av.get('nom', '')}".strip() for av in compagnons_partis
			],
			"pnj_present": pnj_present,
			# Courses échues pendant l'absence du joueur : toast d'échec au rendu.
			"transports_echoues": [
				{"titre": q.get("titre", "—")} for q in transports_echoues
			],
			"intro": intro_payload,
			"ressource_recoltable": ressource_recoltable,
			"relations_lieux": relations_lieux,
			"focalisation": focalisation_payload,
			"guidage": guidage_payload,
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

	# Taille native du portrait : permet de reproduire dans les jetons de combat la portion
	# d'image cadrée par le joueur (portrait_zoom/portrait_translate), comme dans play_town.
	try:
		with Image.open(CHARACTERS_IMAGES_PATH + "/" + character.get("image", "")) as portrait:
			portrait_largeur, portrait_hauteur = portrait.size
	except Exception:
		portrait_largeur, portrait_hauteur = 100, 100

	# ⚠️ Les ressources rendues sont celles de l'ACTEUR COURANT, pas du principal : si
	# l'initiative revient d'abord à un compagnon, la page doit s'ouvrir sur SES sorts /
	# consommables / compétences. Le client ne resynchronise qu'au CHANGEMENT d'acteur
	# (hook `lastActorId`), donc le premier rendu doit déjà être le bon — sinon le joueur
	# voit et peut déclencher les commandes du principal pendant le tour du compagnon.
	acteur = get_doc(_actor_character_id(combat_doc)) or character

	# Portraits de TOUS les membres du groupe (joueur + compagnons `aventurier:*`) :
	# le client rend les tokens alliés et le panneau du membre actif à partir de là.
	portraits_joueurs = {}
	for j in combat_doc.get("joueurs", []):
		cid = j.get("character_id")
		cdoc = character if cid == character["_id"] else (get_doc(cid) if cid else None)
		img = (cdoc or {}).get("image") or j.get("image", "")
		# Une monture est illustrée par l'image de son ESPÈCE, servie par /monsters : ni le
		# dossier ni le mount ne sont ceux d'un portrait de personnage.
		est_monture = bool(j.get("est_monture"))
		dossier = MONSTERS_IMAGES_PATH if est_monture else CHARACTERS_IMAGES_PATH
		try:
			with Image.open(dossier + "/" + img) as p:
				largeur, hauteur = p.size
		except Exception:
			largeur, hauteur = 100, 100
		portraits_joueurs[j["id"]] = {
			"image": img,
			"base": "/monsters" if est_monture else "/characters",
			"largeur": largeur,
			"hauteur": hauteur,
			"portrait_zoom": (cdoc or {}).get("portrait_zoom"),
			"portrait_translate": (cdoc or {}).get("portrait_translate"),
			"nom": (cdoc or {}).get("nom", j.get("nom", "")),
			"prenom": (cdoc or {}).get("prenom", ""),
		}

	return templates.TemplateResponse(
		request=request,
		name="combat_telluris.html",
		context={
			"title": "Combat",
			"combat": combat_doc,
			"character": character,
			"portrait_largeur": portrait_largeur,
			"portrait_hauteur": portrait_hauteur,
			"grid": get_combat_grid(combat_doc),
			# Consommables du sac utilisables en combat (effet instantané pv/pm), avec
			# index d'origine — resynchronisés par la réponse de l'action « consommer ».
			"consommables": consommables.liste_consommables_combat(acteur, resolve_item_ref),
			# Sorts connus utilisables en combat (part instantanée degats/pv/pm), avec
			# disponibilité des composants — resynchronisés par la réponse de l'action « sort ».
			"sorts": sorts_util.liste_sorts_payload(acteur, get_doc, "combat"),
			# Sorts épinglés en accès rapide (icônes directement cliquables de la barre
			# d'action) — sous-ensemble ordonné des sorts connus.
			"sorts_epingles": sorts_util.sorts_epingles_effectifs(acteur),
			# Compétences ACTIVES utilisables en combat (part instantanée degats/pv/pm/
			# furtivité) — les passives buffent déjà le snapshot, elles n'apparaissent pas ici.
			"competences": competences_util.liste_competences_payload(acteur, get_doc, "combat"),
			# Compétences épinglées en accès rapide (miroir des sorts épinglés).
			"competences_epinglees": competences_util.competences_epinglees_effectives(acteur, get_doc),
			# Portraits du groupe (tokens alliés + panneau du membre actif côté client).
			"portraits_joueurs": portraits_joueurs,
		},
		headers={"Cache-Control": "no-store"},
	)

@app.post("/admin/import-bulk")
def admin_import_bulk(
	current_user: Annotated[User, Depends(get_current_user)],
	payload: list | dict = Body(...),
):
	"""Import en masse de documents dans CouchDB, avec suivi de progression.

	Accepte deux formats : un tableau d'objets (``[ {...}, ... ]``) ou le format
	``_bulk_docs`` (``{"docs": [ {...}, ... ]}``). Chaque document est upserté :
	si un doc de même ``_id`` existe déjà, son ``_rev`` courant est réattaché pour
	éviter un conflit d'écriture CouchDB.

	La réponse est un flux NDJSON (``application/x-ndjson``) : une ligne JSON par
	événement (``start`` → ``progress`` par document → ``done``), ce qui permet au
	client d'afficher une barre de progression en temps réel sans WebSocket."""
	if (not current_user or "admin" not in current_user or current_user["admin"] != 1):
		raise HTTPException(status_code=403, detail="Admin only")

	# Normalise les deux formats acceptés vers une liste de docs.
	# (Validation faite AVANT le streaming pour pouvoir renvoyer un vrai 400 ;
	# une fois le flux commencé, le statut HTTP 200 est déjà parti.)
	if isinstance(payload, dict) and isinstance(payload.get("docs"), list):
		docs = payload["docs"]
	elif isinstance(payload, list):
		docs = payload
	else:
		raise HTTPException(
			status_code=400,
			detail='Format attendu : tableau d\'objets ou {"docs": [...]}.',
		)

	if not docs:
		raise HTTPException(status_code=400, detail="Aucun document à importer.")

	who = current_user.get("_id", "?")
	total = len(docs)

	def _stream():
		"""Générateur synchrone (exécuté en threadpool par Starlette) : importe les
		documents un à un en émettant une ligne NDJSON de progression à chaque étape."""
		logger.info("Import bulk demandé par %s : %d document(s) à traiter.", who, total)
		yield json.dumps({"event": "start", "total": total}) + "\n"

		saved, failed, errors = 0, 0, []
		for i, doc in enumerate(docs):
			if not isinstance(doc, dict):
				failed += 1
				msg = f"#{i}: élément ignoré (pas un objet JSON)."
				errors.append(msg)
				logger.warning("Import bulk : %s", msg)
				doc_id, ok = None, False
			else:
				# Upsert : si l'_id existe déjà en base, on attache son _rev courant.
				doc_id = doc.get("_id")
				if doc_id:
					existing = get_doc(doc_id)
					if existing and existing.get("_rev"):
						doc["_rev"] = existing["_rev"]
				if save_doc(doc) is None:
					failed += 1
					msg = f"#{i} ({doc_id or '?'}): échec d'écriture CouchDB."
					errors.append(msg)
					logger.warning("Import bulk : %s", msg)
					ok = False
				else:
					saved += 1
					logger.info("Import bulk : doc sauvegardé %s", doc_id or "(sans _id)")
					ok = True

			yield json.dumps({
				"event": "progress", "processed": i + 1, "total": total,
				"saved": saved, "failed": failed, "id": doc_id, "ok": ok,
			}) + "\n"

		logger.info(
			"Import bulk terminé par %s : %d importé(s), %d échec(s), %d au total.",
			who, saved, failed, total,
		)
		yield json.dumps({
			"event": "done", "imported": saved, "failed": failed,
			"total": total, "errors": errors[:20],
		}) + "\n"

	return StreamingResponse(
		_stream(),
		media_type="application/x-ndjson",
		headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
	)


@app.post("/admin/lint-dialogues")
def admin_lint_dialogues(
	current_user: Annotated[User, Depends(get_current_user)],
	payload: list | dict = Body(...),
):
	"""Contrôle de cohérence des arbres de dialogue AVANT import — en LECTURE SEULE, rien
	n'est écrit en base.

	Un dialogue est de la donnée : ni typée, ni exécutée à l'import. Un `next` vers un nœud
	inexistant, un nœud de service mal nommé ou une condition mal orthographiée ne se voient
	qu'en jouant la branche — et une branche conditionnée qui ne s'affiche jamais est
	indiscernable d'un tirage malheureux. D'où ce passage préalable.

	Même moteur que `dev/lint_dialogues.py` (`utils/lint_dialogues.analyser`), et mêmes deux
	formats de corps que `/admin/import-bulk` : le bouton peut porter sur ce que contient
	déjà la zone de saisie, sans rien reformater."""
	if (not current_user or "admin" not in current_user or current_user["admin"] != 1):
		raise HTTPException(status_code=403, detail="Admin only")
	return lint_dialogues.analyser(payload)
