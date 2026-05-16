from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from routes.user import user_router
from jose import jwt, JWTError
from db.config import db, SECRET_KEY, ALGORITHM

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
async def get_embleme(request: Request):
	token = request.cookies.get("auth_token")
	if not token:
		return RedirectResponse(url="/auth")		

	try:
		# 2. Décoder le token pour obtenir le user_id
		payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
		user_id: str = payload.get("user_id")
		
		user_doc = db.get(user_id)
		
		if not user_doc:
			raise HTTPException(status_code=404)
			
		characters = ["Guerrier du Nord", "Mage d'Argent"] # Exemple
		
		return templates.TemplateResponse(
			name ="user_home_telluris.html",
			request=request, 
			context= {
				"user_doc": user_doc,
				"title": 'Your domain',
				"characters": characters
			}
		)

	except JWTError:
		return RedirectResponse(url="/auth")