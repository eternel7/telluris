"""Accord grammatical du nom d'une espèce (pur) : article, contraction, pronom.

Les titres et descriptions de quêtes GÉNÉRÉS citent une espèce (« Traquer le Vipère »,
« La tête du Harpie »). Le nom seul ne dit ni son genre ni son élision : le doc `espece:*`
porte donc, en option :
	- `genre` : "m" | "f" (absent ⇒ masculin, comportement d'avant : aucune migration) ;
	- `pluriel` : true pour un nom de groupe (« Fauves », « Rapaces ») → les / des / ces ;
	- `nom_propre` : true pour un être unique (« Apep ») → aucun article ;
	- `h_aspire` : true pour un « h » aspiré (« la Harpie ») — tout autre « h » s'élide.

L'élision (« l'Ane », « de l'Hydre ») se lit sur la première lettre du nom, accents ignorés.
Les poser est le travail de `dev/gen_genres_especes.py`.
"""

import unicodedata

FORMES = ("le", "du", "un", "ce")

_VOYELLES = "aeiouy"


def nom_de(espece_doc: dict | None) -> str:
	"""Nom affichable : `nom`, sinon le slug de l'`_id`."""
	doc = espece_doc or {}
	return doc.get("nom") or (doc.get("_id") or "").split(":", 1)[-1]


def est_feminin(espece_doc: dict | None) -> bool:
	return (espece_doc or {}).get("genre") == "f"


def est_pluriel(espece_doc: dict | None) -> bool:
	return bool((espece_doc or {}).get("pluriel"))


def est_propre(espece_doc: dict | None) -> bool:
	return bool((espece_doc or {}).get("nom_propre"))


def elide(espece_doc: dict | None) -> bool:
	"""Le nom commence-t-il par une voyelle ou un « h » muet ?"""
	nom = nom_de(espece_doc)
	initiale = unicodedata.normalize("NFD", nom.strip()).encode("ascii", "ignore").decode()[:1].lower()
	if initiale == "h":
		return not (espece_doc or {}).get("h_aspire")
	return bool(initiale) and initiale in _VOYELLES


def groupe(espece_doc: dict | None, forme: str) -> str:
	"""Nom précédé de son déterminant : `le` (« le Loup », « la Harpie », « l'Hydre », « les
	Fauves »), `du` (« du Loup », « de la Harpie », « de l'Hydre »), `un` (« un Loup », « une
	Harpie »), `ce` (« ce Loup », « cet Ours », « cette Harpie »). Un nom propre n'a pas
	d'article (« Apep ») mais sa contraction s'élide (« d'Apep », « de Cupidon »)."""
	if forme not in FORMES:
		raise ValueError(f"forme inconnue : {forme!r}")
	nom = nom_de(espece_doc)
	el = elide(espece_doc)
	if est_propre(espece_doc):
		if forme == "du":
			return ("d'" if el else "de ") + nom
		return nom
	if est_pluriel(espece_doc):
		return {"le": "les ", "du": "des ", "un": "des ", "ce": "ces "}[forme] + nom
	fem = est_feminin(espece_doc)
	if forme == "le":
		prefixe = "l'" if el else ("la " if fem else "le ")
	elif forme == "du":
		prefixe = "de l'" if el else ("de la " if fem else "du ")
	elif forme == "un":
		prefixe = "une " if fem else "un "
	else:
		prefixe = "cette " if fem else ("cet " if el else "ce ")
	return prefixe + nom


def pronom(espece_doc: dict | None) -> str:
	"""Pronom complément d'objet : « le » / « la » / « les » (« abattez-la »)."""
	if est_pluriel(espece_doc):
		return "les"
	return "la" if est_feminin(espece_doc) else "le"


def sujet(espece_doc: dict | None) -> str:
	"""Pronom sujet : « il » / « elle » / « ils »."""
	if est_pluriel(espece_doc):
		return "ils"
	return "elle" if est_feminin(espece_doc) else "il"


def majuscule(texte: str) -> str:
	"""Première lettre en capitale, le reste intact (`str.capitalize` abaisserait « Loup »)."""
	return texte[:1].upper() + texte[1:]
