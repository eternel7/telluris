import os
from typing import Annotated
from fastapi import FastAPI, HTTPException, Depends, APIRouter, Response, Request, Body
from urllib.parse import unquote
from pydantic import BaseModel
from db.config import db, get_doc, save_doc, find_docs
from utils.characters import get_selected_character
from utils.auth import get_current_user
from utils import acces

# Répertoires d'images servis par les mounts /towns et /pnj (cf. main.py).
TOWNS_IMAGES_PATH = "templates/resources/towns"
PNJ_IMAGES_PATH = "templates/resources/pnj"
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")

class User(BaseModel):
	email: str
	username: str | None = None
	disabled: bool | None = None
	
lieu_router = APIRouter()

def get_lieu_links(current_user: dict = Body(...), filtrer_acces: bool = True):
	"""Connexions de la case courante. `filtrer_acces` (défaut True) écarte toute
	connexion dont le nœud DESTINATION est verrouillé (utils.acces) : le portail d'un
	gardien n'apparaît pas dans la liste des sous-lieux tant que ses conditions ne sont
	pas remplies. Le lieu courant n'est jamais filtré (on ne s'expulse pas soi-même).

	⚠️ Ce filtre d'affichage n'est PAS un verrou : le déplaceur (routers/user.py,
	move_character) doit appeler avec `filtrer_acces=False` et poser sa propre garde
	403 explicite — sinon l'enforcement serait un effet de bord d'une fonction de
	rendu, et le message d'erreur serait « Incorrect movement info »."""
	if not current_user:
		return None

	character = get_selected_character(current_user)
	if not character:
		return None
	position = character["position"]
	lieu = character["lieu"]
	target_key = [ lieu, position["x"], position["y"] ]
	links = db.view("reseau", "liens_cases", key=target_key)
	connections = [row.value for row in links]

	out = []
	for conn in connections:
		ferme = False
		for node in conn["nodes"]:
			doc = get_doc(node["lieu"])
			if (filtrer_acces and node["lieu"] != lieu
					and not acces.acces_autorise(character, doc, get_doc)[0]):
				ferme = True
			doc.pop("cells",None)
			doc.pop("_rev",None)
			doc.pop("_id",None)
			doc.pop("acces",None)
			node["details"] = doc
			node["details"]["label"] = node.get("label") or doc.get("label")
		if not ferme:
			out.append(conn)

	return out
	
# [bit, dx, dy, opposé]
# 1: HAUT, 2: HAUT_DROITE, 4: DROITE, 8: BAS_DROITE, 16: BAS, 32: BAS_GAUCHE, 64: GAUCHE, 128: HAUT_GAUCHE
# ⚠️ Validateur serveur autoritatif. Miroir client : templates/scripts/nav.js — garder synchro.
VALID_MOVES = [
	[1,   0, -1, 16],
	[2,   1, -1, 32],
	[4,   1,  0, 64],
	[8,   1,  1, 128],
	[16,  0,  1, 1],
	[32, -1,  1, 2],
	[64, -1,  0, 4],
	[128, -1, -1, 8]
]

def get_final_mask(nav, x, y):
	# Par défaut, 0 = aucune direction interdite
	mask_actuel = nav.get(f"{x},{y}", 0)
	final_mask = 0
	
	for bit, dx, dy, op_bit in VALID_MOVES:
		# On vérifie si la direction est LIBRE (le bit d'interdiction est à 0)
		if not (mask_actuel & bit):
			# Vérifier si la case cible est aussi libre en entrée
			mask_cible = nav.get(f"{x + dx},{y + dy}", 0)
			if not (mask_cible & op_bit):
				# Si les deux sont libres, on marque la direction comme DISPONIBLE
				# (Le masque final reste un masque de directions autorisées)
				final_mask |= bit

	return final_mask

# (dx, dy) → bit de direction (dérivé de VALID_MOVES).
_DIR_BIT = {(dx, dy): bit for bit, dx, dy, _op in VALID_MOVES}

# Offsets (dx, dy) des 8 directions de déplacement, dérivés de VALID_MOVES.
# Source unique partagée par la nav joueur, l'A* et le flood fill de combat.
MOVE_OFFSETS = [(dx, dy) for _bit, dx, dy, _op in VALID_MOVES]

def nav_allows(nav, x, y, dx, dy):
	"""La direction (dx, dy) depuis (x, y) est-elle autorisée par le masque nav ?

	Réutilise get_final_mask (vérification bidirectionnelle source ↔ cible).
	nav vide → tout est permis. Miroir Python de navAllows() dans scripts/nav.js.
	"""
	if not nav:
		return True
	bit = _DIR_BIT.get((dx, dy))
	if bit is None:
		return False
	return bool(get_final_mask(nav, x, y) & bit)
	
def get_lieu_directions(current_user: dict = Body(...), lieu_doc: dict = Body(...), position: dict = Body(...)):
	if not current_user:
		return None
	cells = lieu_doc.get("cells",None)
	nav = lieu_doc.get("nav", {})
	access = 1 # full access
	mask = 255 # full access
	if cells:
		x = position["x"]
		y = position["y"]
		mask = get_final_mask(nav, x, y)
		
		rows = len(cells)
		cols = len(cells[0]) if rows > 0 else 0
		access = [
			[cells[r][c] if (0 <= r < rows and 0 <= c < cols) else -1 for c in range(x-1, x+2)]
			for r in range(y-1, y+2)
		]
	return { "access": access, "nav" : mask }

def get_lieux_ids(current_user: dict = Body(...)):
	if not current_user:
		return None
	selector = {
		"type": "lieu",
		"cells": {"$exists": True}
	}
	results = db.find(selector, fields=["_id","label","image"])
	return results["docs"]

@lieu_router.get("/lieu/{lieu_id}")
async def get_lieu(
	response: Response,
	current_user: Annotated[User, Depends(get_current_user)],
	lieu_id: str):
	if (not current_user or
		"admin" not in current_user or
		current_user["admin"] != 1 ):
		return None
	
	decoded_id = unquote(lieu_id)
	try:
		doc = get_doc(decoded_id)

		if not doc:
			raise HTTPException(status_code=404, detail="Lieu introuvable")

		return doc

	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Erreur CouchDB : {str(e)}")

@lieu_router.get("/lieu/{lieu_id}/connections")
async def get_lieu_connections(
	response: Response,
	current_user: Annotated[User, Depends(get_current_user)],
	lieu_id: str):
	"""Toutes les connexions touchant un lieu (admin, éditeur de carte).

	Requête range sur la vue reseau/liens_cases (contrairement à
	get_lieu_links qui est scoppé à la case courante du personnage).
	Chaque node est enrichi de `details` (doc du lieu, sans cells/_rev/_id)
	comme get_lieu_links.
	"""
	if (not current_user or
		"admin" not in current_user or
		current_user["admin"] != 1 ):
		return None

	decoded_id = unquote(lieu_id)
	try:
		rows = db.view("reseau", "liens_cases", startkey=[decoded_id], endkey=[decoded_id, {}])
		connections = []
		seen = set()
		for row in rows:
			conn = row.value
			cid = conn.get("_id")
			if cid in seen:
				continue
			seen.add(cid)
			for node in conn["nodes"]:
				doc = get_doc(node["lieu"])
				if not doc:
					continue
				doc.pop("cells", None)
				doc.pop("_rev", None)
				doc.pop("_id", None)
				node["details"] = doc
				node["details"]["label"] = node.get("label") or doc.get("label")
			connections.append(conn)
		return connections

	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Erreur CouchDB : {str(e)}")


@lieu_router.get("/lieu/{lieu_id}/placement_test")
async def get_placement_test(
	response: Response,
	current_user: Annotated[User, Depends(get_current_user)],
	lieu_id: str,
	monstres: int = 0):
	"""Où un acteur naîtrait-il sur cette carte ? (admin, mode « test de déplacement »).

	Le placement RESTE DU PYTHON : cet endpoint ne réimplémente rien, il rebâtit le `grid`
	EXACTEMENT comme `create_combat_doc` et appelle `combat._place_actors`, qui écrit les
	`pos`. Une règle de placement recopiée en JS divergerait du jeu au premier réglage.

	⚠️ Import PARESSEUX de `utils.combat`, DANS LE CORPS : `utils/combat.py` importe ce
	module-ci (`nav_allows`, `MOVE_OFFSETS`) — un import de tête créerait un cycle. Même
	remède que `utils/chasse.py` et `utils/focalisation.py`.

	⚠️ `?monstres=N` (défaut 0) n'est pas décoratif. Avec `monstres: []`, `need` vaut 1 et la
	région d'une case type 1 contient au minimum cette case : la boucle de candidats CASSE
	TOUJOURS sur le premier et ne fait qu'un seul flood fill. Le coût est nul, mais la
	fidélité aussi — on n'éprouve jamais « la région est-elle assez grande ? », ni l'étape 4
	(dispersion des monstres). À N > 0, la vraie règle est exercée et le mode test peut poser
	des jetons rouges. Défaut 0 parce que la demande courante est « un jeton ».

	⚠️ Le JOUEUR ne se pose que sur du terrain EXACTEMENT 1 (`_is_type1`), pas sur du `>= 1`
	(réservé aux monstres) — ne pas « simplifier » vers `_walkable`.
	"""
	if (not current_user or
		"admin" not in current_user or
		current_user["admin"] != 1):
		raise HTTPException(status_code=400, detail="Invalid session credentials")

	from utils import combat as combat_mod   # cf. ⚠️ ci-dessus

	decoded_id = unquote(lieu_id)
	doc = get_doc(decoded_id)
	if not doc:
		raise HTTPException(status_code=404, detail="Lieu introuvable")
	# ⚠️ Gardes d'ENTRÉE : `grid["dims"]` lèverait un KeyError sur un lieu sans `dimensions`,
	# et `cells` peut manquer. 400 explicite dans les deux cas, jamais un 500.
	dimensions, cells = doc.get("dimensions"), doc.get("cells")
	if not isinstance(dimensions, dict) or "x" not in dimensions or "y" not in dimensions:
		raise HTTPException(status_code=400, detail="Ce lieu n'a pas de `dimensions` : aucune grille où placer un acteur.")
	if not isinstance(cells, list) or not cells:
		raise HTTPException(status_code=400, detail="Ce lieu n'a pas de `cells` : aucune grille où placer un acteur.")

	nb = max(0, min(int(monstres or 0), 20))
	grid = {"dims": dimensions, "cells": cells, "nav": doc.get("nav", {})}
	faux_combat = {"joueurs": [{}], "monstres": [{} for _ in range(nb)]}
	combat_mod._place_actors(faux_combat, grid)
	return {
		"pos": faux_combat["joueurs"][0]["pos"],
		"monstres": [m["pos"] for m in faux_combat["monstres"]],
	}


def _lister_images(chemin: str) -> list[str]:
	"""Fichiers image d'un répertoire de ressources (miroir de bestiaire.list_monster_images).

	Le filtre d'extension écarte au passage les Thumbs.db et les .md qui traînent
	dans templates/resources/pnj/."""
	if not os.path.exists(chemin):
		return []
	return sorted(
		f for f in os.listdir(chemin)
		if os.path.isfile(os.path.join(chemin, f))
		and f.lower().endswith(IMAGE_EXTENSIONS)
	)

CITE_DEPART_MARQUEUR = "_start_"


def cites_de_depart(get_doc_fn=get_doc) -> list[dict]:
	"""Les cités où un personnage PEUT NAÎTRE — SOURCE UNIQUE de l'écran de création.

	La règle est un NOMMAGE de fichier : `<nom>_start_*.<ext>` dans le dossier des images
	de villes, ET un doc `lieu:<nom>` qui existe réellement en base. L'image sans le doc
	(ou l'inverse) ne propose rien — c'est ce qui rend l'ouverture d'une cité de départ
	purement déclarative : déposer l'image et importer le lieu suffit, sans une ligne de code.

	Renvoie `[{id, label, filename}]`, trié par nom de fichier (`_lister_images`).
	⚠️ Aucune URL : la construire demande le `Request` de la requête (`url_for`), qui n'a
	rien à faire dans un helper — c'est l'appelant qui l'ajoute.
	⚠️ Le filtre d'extension est celui de `_lister_images` (`IMAGE_EXTENSIONS`), donc sans
	`.gif` : brique partagée plutôt que liste recopiée par appelant."""
	cites = []
	for filename in _lister_images(TOWNS_IMAGES_PATH):
		if CITE_DEPART_MARQUEUR not in filename:
			continue
		label = filename[:filename.index("_")]
		lieu_id = "lieu:" + label
		if get_doc_fn(lieu_id):
			cites.append({"id": lieu_id, "label": label, "filename": filename})
	return cites


def est_cite_de_depart(cite_id, get_doc_fn=get_doc) -> bool:
	"""Cette cité est-elle RÉELLEMENT proposée à la création ? Garde serveur d'`add_character` :
	vérifier que le `lieu:*` existe ne suffit pas, sinon une requête forgée ferait naître un
	personnage dans n'importe quel lieu — une boutique, une salle de donjon, une carte de
	combat. Le client ne propose que cette liste : le serveur exige la même."""
	if not isinstance(cite_id, str) or not cite_id:
		return False
	return any(c["id"] == cite_id for c in cites_de_depart(get_doc_fn))


@lieu_router.get("/lieux/creation_options")
async def get_creation_options(
	current_user: Annotated[User, Depends(get_current_user)]):
	"""Tout ce dont le formulaire « Ajouter un lieu » de l'éditeur a besoin, en un appel.

	Les find_docs sont PROJETÉS (`fields`) : lister les lieux sans projection
	rapatrierait les `cells` de chaque carte.
	`lieu_ids` sert au contrôle de collision d'_id côté client — `GET /lieu/{id}`
	ne peut pas le faire, son 404 étant ravalé en 500 par son propre try/except.
	"""
	if (not current_user or
		"admin" not in current_user or
		current_user["admin"] != 1 ):
		raise HTTPException(status_code=403, detail="Admin only")

	lieux = find_docs({"type": "lieu"}, fields=["_id", "categorie"]) or []
	recettes = find_docs({"type": "recette"}, fields=["lieu_categorie"]) or []
	pnjs = find_docs({"type": "pnj"}, fields=["_id", "nom"]) or []

	categories = {str(d["categorie"]).strip() for d in lieux if d.get("categorie")}
	categories |= {str(r["lieu_categorie"]).strip() for r in recettes if r.get("lieu_categorie")}

	return {
		"categories": sorted(categories),
		"images": _lister_images(TOWNS_IMAGES_PATH),
		"portraits": _lister_images(PNJ_IMAGES_PATH),
		"pnj": sorted(
			({"_id": p.get("_id"), "nom": p.get("nom") or p.get("_id")} for p in pnjs),
			key=lambda p: p["_id"] or ""
		),
		"lieu_ids": sorted(d["_id"] for d in lieux if d.get("_id")),
	}

def dimensions_coherentes(dimensions, cells) -> dict:
	"""Valide une `dimensions` soumise AVEC ses `cells`, et la renvoie normalisée.

	⚠️ `dimensions` se lit en COMPTES DE CASES (`{"x":86,"y":48}` ⇒ indices 0..85 / 0..47),
	convention de `chasse.borner_position` et du client. On exige donc `len(cells) == y` et
	`len(ligne) == x` pour chaque ligne : `update_cells` est la SEULE écriture du jeu capable de
	désynchroniser les deux champs (l'éditeur de carte sait redimensionner une grille), et des docs
	où ils se contredisent existent déjà en base — `utils/chasse.py` balaie la grille entière pour
	s'en prémunir. On refuse d'en produire un de plus.
	"""
	if not isinstance(dimensions, dict):
		raise HTTPException(status_code=422, detail="`dimensions` doit être un objet {x, y}.")
	try:
		x, y = int(dimensions.get("x")), int(dimensions.get("y"))
	except (TypeError, ValueError):
		raise HTTPException(status_code=422, detail="`dimensions.x` et `dimensions.y` doivent être des entiers.")
	if x < 1 or y < 1:
		raise HTTPException(status_code=422, detail="`dimensions` doit valoir au moins 1×1.")
	if not isinstance(cells, list) or not cells or not isinstance(cells[0], list):
		raise HTTPException(status_code=422, detail="`cells` doit être une matrice non vide pour porter des `dimensions`.")
	if len(cells) != y or any(len(ligne) != x for ligne in cells):
		raise HTTPException(status_code=422, detail=(
			f"`dimensions` ({x}×{y}) et `cells` ({len(cells[0])}×{len(cells)}) se contredisent."))
	return {"x": x, "y": y}


@lieu_router.put("/update_cells")
async def update_cells(
	response: Response,
	current_user: Annotated[User, Depends(get_current_user)],
	cells_info: dict = Body(...)):
	
	if ( not current_user or
		"admin" not in current_user or
		current_user["admin"] != 1 ):
		raise HTTPException(status_code=400, detail="Invalid session credentials")
	
	if cells_info :
		cells = cells_info["cells"]
		nav = cells_info["nav"]
		lieu_id = cells_info["_id"]
		# Redimensionnement de la grille (éditeur de carte). ⚠️ Contrôlé AVANT la moindre lecture :
		# une taille incohérente doit être refusée sans avoir touché à la base. Clé ABSENTE ⇒ champ
		# jamais écrit — c'est le chemin de l'auto-sauvegarde du pinceau, rigoureusement inchangé.
		dimensions = (dimensions_coherentes(cells_info["dimensions"], cells)
			if "dimensions" in cells_info else None)
		lieu_doc = get_doc(lieu_id)
		if lieu_doc:
			lieu_doc["cells"] = cells
			lieu_doc["nav"] = nav
			if dimensions:
				lieu_doc["dimensions"] = dimensions
			# Métadonnées battle map (optionnelles) : tags + catégorie pour la sélection pondérée.
			if "tags" in cells_info:
				lieu_doc["tags"] = cells_info["tags"]
			if "categorie" in cells_info:
				lieu_doc["categorie"] = cells_info["categorie"]
			# ⚠️ `save_doc` AVALE le conflit de révision et renvoie None (db/config.py) : sans ce
			# contrôle, l'endpoint répondait 200 avec le doc d'AVANT écriture. Le client en déduisait
			# un `_rev` périmé, et surtout le redimensionnement enchaînait zones et portes sur une
			# grille qui n'avait pas bougé — l'incohérence même que `dimensions_coherentes` refuse.
			if save_doc(lieu_doc) is None:
				raise HTTPException(status_code=409, detail="Conflit de sauvegarde — rechargez et réessayez.")
			return lieu_doc
	raise HTTPException(status_code=404, detail="Incorrect location grid info")