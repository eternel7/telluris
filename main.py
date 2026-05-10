import os
import couchdb2
import urllib.parse
from fastapi import FastAPI, Request
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

@app.get("/")
def read_root():
	return {"status": "success", "message": "Serveur Python sur Synology"}
	
@app.get("/dev", response_class=HTMLResponse)
async def read_page_dev(request: Request):
	return templates.TemplateResponse(
		request=request, 
		name="battle_map.html", 
		context={"title": "Dev place for Telluris"}
	)
	
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
		databases = list(server)
		
		return {
			"status": "connected",
			"couchdb_version": version,
			"databases": databases
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