"""Images des livres (Auteur, 22/11/2026) — dossier `templates/resources/livres/`, mount `/livres`.

Deux usages du MÊME dossier :
- une image déposée à la RACINE devient un objet achetable, une **planche** : `carte_…` →
  une carte 🗺️, tout autre nom → une œuvre 🖼️. Le nom vient du fichier (soulignés et tirets
  → espaces, première lettre en capitale, casse et accents du fichier gardés :
  `carte_de_la_Beauce.jpg` → « Carte de la Beauce »). Aucun import : le doc `item:planche_*`
  est créé au premier tirage par un magasin de la famille du scriptorium
  (`scriptorium.recettes_planches`), puis jamais retouché ;
- un SOUS-DOSSIER nommé comme l'id d'un livre sans « item: » (`livres/ouvrage_critias/`) porte
  les illustrations de ce livre, montrées dans l'ordre des noms de fichier.

Les images d'un livre sont résolues À LA LECTURE (`images_de`, appelé par
`characters.resolve_item_ref`) : déposer ou retirer un fichier suffit. Listages mémoïsés
`_TTL` secondes (le dossier vit souvent sur un partage réseau).

⚠️ Un nom de sous-dossier n'est jamais tiré d'une saisie : il vient d'un id d'item, et seuls
les caractères `[A-Za-z0-9_.-]` sont admis (pas de `..`, pas de séparateur)."""

import os
import re
import time
import unicodedata
from urllib.parse import quote

RACINE = os.path.join("templates", "resources", "livres")
URL = "/livres"
EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")
PREFIXE_PLANCHE = "planche_"
SOUS_CATEGORIE_PLANCHE = "planche"

_TTL = 30.0
_cache: dict = {}
_RE_SOUS_DOSSIER = re.compile(r"^[A-Za-z0-9_.\-]+$")


def reset_cache() -> None:
	_cache.clear()


def _lister(chemin: str) -> list:
	"""Fichiers image de `chemin` (pas récursif), triés ; [] si le dossier manque."""
	now = time.time()
	memo = _cache.get(chemin)
	if memo is not None and now - memo[0] < _TTL:
		return memo[1]
	try:
		with os.scandir(chemin) as it:
			fichiers = sorted(e.name for e in it
							  if e.is_file() and e.name.lower().endswith(EXTENSIONS) and not e.name.startswith("."))
	except OSError:
		fichiers = []
	_cache[chemin] = (now, fichiers)
	return fichiers


def planches(racine: str = RACINE) -> list:
	"""Images déposées à la racine : chacune est une planche achetable."""
	return _lister(racine)


def illustrations(sous_dossier: str, racine: str = RACINE) -> list:
	"""Images du sous-dossier d'un livre ; [] pour un nom non admis."""
	if not sous_dossier or ".." in sous_dossier or not _RE_SOUS_DOSSIER.match(sous_dossier):
		return []
	return _lister(os.path.join(racine, sous_dossier))


def url(*parties: str) -> str:
	return URL + "/" + "/".join(quote(p) for p in parties)


def _tige(fichier: str) -> str:
	return os.path.splitext(fichier)[0]


def genre_planche(fichier: str) -> str:
	return "carte" if _tige(fichier).lower().startswith("carte") else "oeuvre"


_RE_ELISION = re.compile(r"\b([dDlLjJmMnNsStTcC]|[qQ]u)\s+(?=\w)")


def nom_planche(fichier: str) -> str:
	"""Nom lisible : soulignés et tirets → espaces, élision rétablie (un fichier ne porte pas
	toujours d'apostrophe : `vision_d_Atlantis` → « Vision d'Atlantis »), première lettre en
	capitale, le reste tel que dans le fichier."""
	nom = re.sub(r"[_\-]+", " ", _tige(fichier)).strip()
	nom = _RE_ELISION.sub(lambda m: m.group(1) + "'", nom)
	return (nom[:1].upper() + nom[1:]) if nom else fichier


def slug_planche(fichier: str) -> str:
	ascii_ = unicodedata.normalize("NFKD", _tige(fichier)).encode("ascii", "ignore").decode()
	return re.sub(r"[^a-z0-9]+", "_", ascii_.lower()).strip("_") or "sans_nom"


def item_id_planche(fichier: str) -> str:
	return f"item:{PREFIXE_PLANCHE}{slug_planche(fichier)}"


def doc_planche(fichier: str) -> dict:
	"""Doc item d'une planche, figé à sa création (jamais recalculé ensuite)."""
	carte = genre_planche(fichier) == "carte"
	nom = nom_planche(fichier)
	return {
		"_id": item_id_planche(fichier), "type": "item", "nom": nom,
		"icon": "🗺️" if carte else "🖼️",
		"categorie": "livre", "sous_categorie": SOUS_CATEGORIE_PLANCHE,
		"slots": [], "poids": 0.1, "rarete": "peu_commun",
		"planche": {"fichier": fichier, "genre": genre_planche(fichier)},
		"description": (f"Une carte : {nom}." if carte else f"Une œuvre : {nom}."),
	}


def images_de(item_doc: dict | None, racine: str = RACINE) -> list:
	"""[{url}] d'un livre : l'image d'une planche (si le fichier est toujours là), puis les
	illustrations du sous-dossier nommé comme son id. [] pour tout autre objet."""
	if not item_doc or item_doc.get("categorie") != "livre":
		return []
	out = []
	fichier = ((item_doc.get("planche") or {}).get("fichier"))
	if fichier:
		# Même tige, extension libre : une image reconvertie (`.jpg` → `.webp`) garde sa planche.
		present = planches(racine)
		trouve = fichier if fichier in present else next(
			(f for f in present if _tige(f) == _tige(fichier)), None)
		if trouve:
			out.append({"url": url(trouve)})
	item_id = item_doc.get("item") or item_doc.get("_id") or ""
	sous = item_id[len("item:"):] if item_id.startswith("item:") else item_id
	out.extend({"url": url(sous, f)} for f in illustrations(sous, racine))
	return out
