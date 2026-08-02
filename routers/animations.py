# routers/animations.py
# Administration des animations de combat : scan du dossier de feuilles de sprites,
# catalogue, et LIAISON d'une animation à un doc de contenu (sort, compétence, item,
# espèce).
#
# Le CRUD des docs `animation:*` eux-mêmes n'a AUCUN endpoint ici : `PUT /admin/doc` et
# `DELETE /admin/doc` (main.py) sont génériques et relisent déjà le `_rev` en base.
# Ce router ne porte que ce qu'ils ne savent pas faire : lire le disque, deviner une
# grille, et écrire UN SEUL champ dans un doc de contenu sans réécrire tout le reste
# (à l'opposé du PUT complet d'`admin_import_bulk`, cf. Conventions §11).

import os
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from db.config import find_docs, get_doc, save_doc
from utils import animations as animations_util
from utils.auth import get_current_user

animations_router = APIRouter()

# Servi par le mount `/icons` (main.py) : `/icons/effects/<fichier>` est déjà accessible,
# il n'y a aucun mount à ajouter.
EFFECTS_PATH = "templates/resources/icons/effects"
# Servi par le mount `/sounds` (main.py). Une animation peut n'être QU'un son — c'est ce
# que veulent les canaux `miss`/`fumble`, qui n'ont rien à montrer.
SOUNDS_PATH = "templates/resources/sounds"

# Types de docs auxquels une animation peut être liée. `item` couvre les armes ET les
# consommables — c'est le même champ, lu à deux endroits différents du combat.
TYPES_LIABLES = ("sort", "competence", "item", "espece")


def _require_admin(current_user: dict) -> None:
	if not current_user or current_user.get("admin") != 1:
		raise HTTPException(status_code=403, detail="Admin only")


def _dimensions(chemin: str) -> tuple:
	"""(largeur, hauteur) d'une image, ou (0, 0) si elle est illisible.

	⚠️ Import de Pillow PARESSEUX : `tests/` importe `utils/*` → `routers/*`, et Pillow
	n'est pas dans les dépendances de collecte locale (cf. CLAUDE.md). Un import en tête
	de module ferait échouer la COLLECTE de toute la suite de tests purs."""
	try:
		from PIL import Image
		with Image.open(chemin) as img:
			return int(img.size[0]), int(img.size[1])
	except Exception:
		return 0, 0


def _fichiers_effets() -> list:
	"""Feuilles de sprites présentes sur le disque, triées (le dossier contient aussi
	des fichiers non-images, comme Thumbs.db)."""
	if not os.path.isdir(EFFECTS_PATH):
		return []
	return sorted(
		f for f in os.listdir(EFFECTS_PATH)
		if os.path.isfile(os.path.join(EFFECTS_PATH, f)) and animations_util.est_image(f)
	)


def _fichiers_sons() -> list:
	"""Sons présents sur le disque, triés — jumeau de `_fichiers_effets`.

	⚠️ Aucune lecture de métadonnées ici, contrairement aux images : un son n'a pas de
	dimensions, et sa DURÉE n'est lisible que par le navigateur (aucune dépendance audio
	côté serveur). C'est l'éditeur qui l'affiche, à partir de l'élément `<audio>`."""
	if not os.path.isdir(SOUNDS_PATH):
		return []
	return sorted(
		f for f in os.listdir(SOUNDS_PATH)
		if os.path.isfile(os.path.join(SOUNDS_PATH, f)) and animations_util.est_son(f)
	)


def _docs_animations() -> list:
	return find_docs({"type": "animation"}) or []


@animations_router.get("/api/admin/animations")
async def liste_animations(current_user: Annotated[dict, Depends(get_current_user)]):
	"""Catalogue complet pour l'éditeur : les docs `animation:*` (actifs ET brouillons)
	et les fichiers réellement présents sur le disque.

	Le scan du répertoire est refait à chaud pour lister AUSSI les feuilles qu'aucun doc
	ne couvre encore — c'est ce qui rend visible ce qu'un nouveau scan créerait."""
	_require_admin(current_user)
	docs = _docs_animations()
	par_fichier = {}
	for d in docs:
		par_fichier.setdefault(str(d.get("fichier") or ""), []).append(str(d.get("_id") or ""))
	fichiers = []
	for f in _fichiers_effets():
		largeur, hauteur = _dimensions(os.path.join(EFFECTS_PATH, f))
		fichiers.append({"fichier": f, "largeur": largeur, "hauteur": hauteur,
						 "docs": par_fichier.get(f, [])})
	# ⚠️ Les docs partent BRUTS : le formulaire édite la valeur STOCKÉE. Les bases de décalage
	# sont publiées à côté pour que l'aperçu de scène montre la position réellement jouée,
	# sans que le client ait à recopier les constantes. `defauts_canaux` n'est qu'un RAPPEL en
	# lecture seule (la world-var se règle dans /admin) — relu à chaque appel, donc il suit un
	# réglage à chaud sans rechargement de page.
	return {"docs": sorted(docs, key=lambda d: str(d.get("_id") or "")), "fichiers": fichiers,
			"sons": _fichiers_sons(),
			"decalage_x_base": animations_util.DECALAGE_X_BASE,
			"decalage_y_base": animations_util.DECALAGE_Y_BASE,
			"defauts_canaux": animations_util.defauts_canaux()}


@animations_router.post("/admin/animations/scan")
async def scanner_animations(current_user: Annotated[dict, Depends(get_current_user)]):
	"""Crée un doc `animation:*` par fichier NOUVEAU — **feuilles d'effets ET sons**.

	Images : dimensions lues par Pillow, grille devinée. Sons : rien à deviner, le doc porte
	le seul `son` et se règle à l'oreille (une animation peut n'être QU'un son). Dans les
	deux cas `actif: false`.

	⚠️ **N'écrase JAMAIS un doc existant** : le scan est donc idempotent et relançable
	après tout ajout de fichier, sans jamais perdre une découpe réglée à la main. Un
	fichier déjà couvert par un doc (quel que soit l'id de ce doc) est « existant ».

	Rien n'est activé : `deviner_grille` ne fait que semer une hypothèse, qu'un humain
	confirme à l'aperçu animé de l'éditeur."""
	_require_admin(current_user)
	existants_docs = _docs_animations()
	# ⚠️ DEUX ensembles distincts, et c'est indispensable : un doc son-seul n'a pas de
	# `fichier`, un doc image n'a pas de `son`. Avec un seul ensemble, aucun son ne serait
	# jamais reconnu comme couvert et chaque scan recréerait toute la sonothèque.
	couverts = {str(d.get("fichier") or "") for d in existants_docs}
	couverts_sons = {str(d.get("son") or "") for d in existants_docs}
	ids_pris = {str(d.get("_id") or "") for d in existants_docs}

	# Deux fichiers peuvent produire le même slug (« Hit-Yellow.png » et « hit - yellow.png ») :
	# on descend les suffixes jusqu'à un id libre.
	def _id_libre(nom: str) -> str:
		for suffixe in "abcdefghijklmnopqrstuvwxyz":
			candidat = animations_util.slug_animation(nom, suffixe)
			if candidat not in ids_pris and get_doc(candidat) is None:
				return candidat
		return ""

	crees, existants, illisibles = [], [], []
	for fichier in _fichiers_effets():
		if fichier in couverts:
			existants.append(fichier)
			continue
		largeur, hauteur = _dimensions(os.path.join(EFFECTS_PATH, fichier))
		if largeur <= 0 or hauteur <= 0:
			illisibles.append(fichier)
			continue
		doc_id = _id_libre(fichier)
		if not doc_id:
			illisibles.append(fichier)
			continue
		colonnes, lignes, _devinee = animations_util.deviner_grille(fichier, largeur, hauteur)
		doc = {
			"_id": doc_id,
			"type": "animation",
			"nom": os.path.splitext(fichier)[0],
			"fichier": fichier,
			"largeur": largeur,
			"hauteur": hauteur,
			"colonnes": colonnes,
			"lignes": lignes,
			"sens_lignes": animations_util.SENS_DEFAUT,
			"sens_colonnes": animations_util.SENS_COLONNES_DEFAUT,
			"debut": 0,
			"fin": colonnes * lignes - 1,
			"duree_ms": animations_util.DUREE_DEFAUT_MS,
			"echelle": animations_util.ECHELLE_DEFAUT,
			"decalage_x": 0.0,
			"decalage_y": 0.0,
			"ancrage": animations_util.ANCRAGE_DEFAUT,
			# Trajectoire : semée NEUTRE. `depart_ancrage` vide = sprite posé, comme avant —
			# une feuille fraîchement scannée ne se met pas à voler toute seule.
			"depart_ancrage": animations_util.DEPART_ANCRAGE_DEFAUT,
			"depart_decalage_x": 0.0,
			"depart_decalage_y": 0.0,
			"duree_trajet_ms": 0,
			"arc": 0.0,
			"rotation": animations_util.ROTATION_DEFAUT,
			"rotation_auto": False,
			# Brouillon : rien n'est jamais actif sans confirmation humaine.
			"actif": False,
		}
		if save_doc(doc) is None:
			illisibles.append(fichier)
			continue
		ids_pris.add(doc_id)
		couverts.add(fichier)
		crees.append(doc_id)

	# ── Sons ──
	# Un doc par son NOUVEAU, SANS images : c'est la forme qu'attendent les canaux qui n'ont
	# rien à montrer (`miss`, `fumble`). Rien à deviner ici — pas de grille, pas de
	# dimensions, et les points de lecture se règlent à l'oreille dans l'éditeur.
	for son in _fichiers_sons():
		if son in couverts_sons:
			existants.append(son)
			continue
		doc_id = _id_libre(son)
		if not doc_id:
			illisibles.append(son)
			continue
		doc = {
			"_id": doc_id,
			"type": "animation",
			"nom": os.path.splitext(son)[0],
			"son": son,
			"son_debut_ms": 0,
			# 0 = jusqu'au bout du fichier : le serveur ne connaît pas la durée d'un son.
			"son_fin_ms": 0,
			"son_volume": animations_util.VOLUME_DEFAUT,
			# Brouillon : rien n'est jamais actif sans confirmation humaine — ici, sans
			# l'avoir ÉCOUTÉ.
			"actif": False,
		}
		if save_doc(doc) is None:
			illisibles.append(son)
			continue
		ids_pris.add(doc_id)
		couverts_sons.add(son)
		crees.append(doc_id)

	return {"crees": crees, "existants": existants, "illisibles": illisibles}


@animations_router.get("/api/admin/animations/liaisons")
async def liaisons(
	current_user: Annotated[dict, Depends(get_current_user)],
	doc_type: str = Query("", alias="type"),
):
	"""Docs d'un type liables, avec leur animation courante.

	⚠️ Requête PROJETÉE (`fields`) : lister les items sans projection rapatrierait toute
	la base d'objets pour n'en afficher que le nom."""
	_require_admin(current_user)
	t = (doc_type or "").strip()
	if t not in TYPES_LIABLES:
		raise HTTPException(status_code=400,
							detail=f"Type liable attendu parmi {', '.join(TYPES_LIABLES)}.")
	docs = find_docs({"type": t}, fields=["_id", "nom", "icon", "animation"]) or []
	return {"type": t, "docs": sorted(docs, key=lambda d: str(d.get("nom") or d.get("_id") or ""))}


@animations_router.post("/admin/animations/lier")
async def lier_animation(
	current_user: Annotated[dict, Depends(get_current_user)],
	payload: dict = Body(...),
):
	"""Pose (ou retire) le SEUL champ `animation` sur un doc de contenu.

	Fusion mono-champ : le doc est relu en base et réécrit tel quel à un champ près —
	à l'opposé du PUT complet d'`admin_import_bulk`, qui obligerait à reproduire le
	document entier pour ne changer qu'une liaison."""
	_require_admin(current_user)
	doc_id = str(payload.get("doc_id") or "").strip()
	animation = str(payload.get("animation") or "").strip()
	if not doc_id:
		raise HTTPException(status_code=400, detail="Champ 'doc_id' requis.")
	doc = get_doc(doc_id)
	if not doc:
		raise HTTPException(status_code=404, detail="Document introuvable.")
	if animation:
		doc["animation"] = animation
	else:
		doc.pop("animation", None)
	if save_doc(doc) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — rechargez et réessayez.")
	return {"saved": True, "_id": doc_id, "animation": animation}
