from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Definit ou se trouvent les fichiers HTML
templates = Jinja2Templates(directory="templates")
app.mount("/scripts", StaticFiles(directory="templates/scripts"), name="scripts")
app.mount("/battle_maps", StaticFiles(directory="templates/resources/battle_maps"), name="battle_maps")

@app.get("/")
def read_root():
    return {"status": "success", "message": "Serveur Python sur Synology"}
	
@app.get("/dev", response_class=HTMLResponse)
async def read_page2(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="battle_map.html", 
        context={"title": "Dev place for Telluris"}
    )
	
@app.get("/test", response_class=HTMLResponse)
async def read_page2(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="battle_map2.html", 
        context={"title": "Test place for Telluris"}
    )

@app.get("/former", response_class=HTMLResponse)
async def read_page3(request: Request):
    return templates.TemplateResponse(
	    request=request, 
		name="prototype_combat_telluris.html", 
		context={"title": "combat interface old"})
