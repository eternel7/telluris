import os
from typing import Annotated
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from jose import jwt, JWTError
from routes.user import user_router, User
from db.config import db, SECRET_KEY, ALGORITHM
from utils.auth import get_current_user

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
app.mount("/scripts", StaticFiles(directory="templates/scripts"), name="scripts")
app.mount("/battle_maps", StaticFiles(directory="templates/resources/battle_maps"), name="battle_maps")
app.mount("/icons", StaticFiles(directory="templates/resources/icons"), name="icons")
CHARACTERS_IMAGES_PATH = "templates/resources/characters"
app.mount("/characters", StaticFiles(directory=CHARACTERS_IMAGES_PATH), name="characters")
TOWNS_IMAGES_PATH = "templates/resources/towns"
app.mount("/towns", StaticFiles(directory=TOWNS_IMAGES_PATH), name="towns")

app.include_router(user_router, prefix="/api")

@app.get("/")
def read_root(request: Request):
	return templates.TemplateResponse(
		request=request, 
		name="home_telluris.html", 
		context={"title": "Ubi Chartae Finiunt"}
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
		
	characters = ["Guerrier du Nord", "Mage d'Argent"] # Exemple

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
			"characters": characters,
			"characters_images": characters_images,
			"towns_images": towns_images
		}
	)