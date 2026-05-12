import os
import couchdb2
import urllib.parse
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Definit ou se trouvent les fichiers HTML
templates = Jinja2Templates(directory="templates")
app.mount("/scripts", StaticFiles(directory="templates/scripts"), name="scripts")
app.mount("/battle_maps", StaticFiles(directory="templates/resources/battle_maps"), name="battle_maps")
app.mount("/icons", StaticFiles(directory="templates/resources/icons"), name="icons")


DB_PASSWORD = os.getenv("COUCHDB_PASSWORD", "password_par_defaut_Non_mais_tente_meme_pas")
DB_USER = os.getenv("COUCHDB_USER", "admin_qui_pourra")

safe_password = urllib.parse.quote_plus(DB_PASSWORD)

DB_URL = f"http://{DB_USER}:{safe_password}@couchdb:5984"
server = couchdb2.Server(DB_URL)
db = server["telluris"] 

@app.get("/")
def read_root():
	return {"status": "success", "message": "No woman don't cry"}
	
@app.get("/dev", response_class=HTMLResponse)
async def read_page_dev(request: Request):
	grid_doc = db.get("grid:lutecia")
	links = db.view("reseau", "liens_cases", key={"lieu": "lutecia"})
	return templates.TemplateResponse(
		request=request, 
		name="battle_map.html", 
		context={"title": "Dev place for Telluris"}
	)
	
@app.get("/dev/{lieu_id}", response_class=HTMLResponse)
def read_page_lieu(request: Request, lieu_id: str):
	grid_doc = db.get(lieu_id)
	links = db.view(
		"reseau", 
		"liens_cases", 
		startkey=[lieu_id], 
        endkey=[lieu_id, {}])
	titre = grid_doc.get("label")
	return templates.TemplateResponse(
		request=request, 
		name="battle_map.html",
		context={
			"title": titre,
			"lieu": lieu_id,
			"image": grid_doc.get("image")
		}
	)
	
@app.get("/api/map-data/{lieu_id}")
async def get_map_data(lieu_id: str):
    # Récupération des données CouchDB
    grid_doc = db.get(lieu_id)
    links = db.view("reseau", "liens_cases", startkey=[lieu_id], endkey=[lieu_id, {}])
    return {
        "grid":  grid_doc.get("cells"),
        "dims":  grid_doc.get("dimensions"),
        "links": [row.value for row in links]
    }
	
@app.get("/passage/{lieu_id}/{x}/{y}")
def get_destination(lieu_id: str, x: int, y: int):
	# La clé correspond à la structure [lieu_id, x, y] définie dans votre vue Map
	target_key = [ lieu_id, x, y ]
	
	# Interrogation de la vue (design_doc/view_name)
	results = db.view("reseau", "liens_cases", key=target_key)
	
	if not results:
		raise HTTPException(status_code=404, detail="Aucun lien ici")
	
	# On retourne la liste complète des valeurs
	destinations = [row.value for row in results]
	
	return {
		"depart": {"lieu": lieu_id, "x": x, "y": y},
		"destinations": destinations,
		"count": len(destinations)
	}
	
@app.get("/test", response_class=HTMLResponse)
async def read_page_test(request: Request):
	return templates.TemplateResponse(
		request=request, 
		name="battle_map2.html", 
		context={"title": "Test place for Telluris"}
	)

@app.get("/former", response_class=HTMLResponse)
async def read_page_former(request: Request):
	return templates.TemplateResponse(
		request=request, 
		name="prototype_combat_telluris.html", 
		context={"title": "combat interface old"})
		
		
@app.get("/test-db")
def test_couchdb_connection():
	try:
		version = server.version
		
		return {
			"status": "connected",
			"couchdb_version": version
		}
	except Exception as e:
		return {"status": "error", "message": str(e)}
		
		
@app.get("/setup-db")
def setup_db():
	db_name = "test_db"
	try:
		# Vérification et sélection
		if db_name not in server:
			db = server.create(db_name)
		else:
			# On accède à la base comme dans un dictionnaire
			db = server[db_name] 
		
		doc = {"type": "test", "content": "Hello de FastAPI !"}
		db.put(doc) # Ajoute _id et _rev à l'objet 'doc'
		
		return {"message": "Document créé", "id": doc.get('_id')}
	except Exception as e:
		return {"status": "error", "message": str(e)}