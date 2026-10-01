"""dev/gen_villes_images.py — un lieu de ville par carte de `towns/` qu'aucun lieu ne cite.

Partie pure seulement (`villes_a_creer`, `poser_grille`) : la grille elle-même vient de
`gen_grille_image.proposer_pour_image` (Pillow), testée par `test_grille_image.py`. Verrouille
ce qu'un import PUT COMPLET rendrait silencieux : une ville réémise écraserait sa grille
retouchée, un `_id` réutilisé écraserait un autre lieu.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev.gen_villes_images import (COTE_CASE_DEFAUT, PAYS_FRANCE, cote_case, poser_grille,
	villes_a_creer)

# Les tailles réelles des cartes (en pixels) ; la base a deux villes à cases de 16 px.
TAILLES = {
	"auxerre_start_city.png": (1376, 768),
	"paris_capital.png": (1408, 768),
	"chartres_city.png": (1408, 768),
	"lutecia_capital.png": (1408, 768),
	"akureyri_start_city.png": (1024, 1024),
	"rome_capital.png": (1408, 768),
	"reykjavík_capital.png": (1408, 768),
	"auberge_europe01.png": (1408, 768),
}
COTE = 16
BASE = [
	{"_id": "lieu:france", "type": "lieu", "categorie": "pays"},
	{"_id": "lieu:auxerre", "categorie": "ville", "image": "auxerre_start_city.png",
		"dimensions": {"x": 1376 // COTE, "y": 768 // COTE}},
	{"_id": "lieu:lutecia", "categorie": "ville", "image": "paris_capital.png",
		"dimensions": {"x": 1408 // COTE, "y": 768 // COTE}},
]


def _par_id(docs):
	return {d["_id"]: d for d in docs}


def test_cote_relu_sur_les_villes_en_base():
	assert cote_case(BASE, TAILLES.get) == COTE
	# Des villes à cases de 32 px ⇒ des cartes neuves à cases de 32 px.
	grosses = [dict(d, dimensions={"x": d["dimensions"]["x"] // 2, "y": d["dimensions"]["y"] // 2})
		if "dimensions" in d else d for d in BASE]
	assert cote_case(grosses, TAILLES.get) == COTE * 2
	assert cote_case([], TAILLES.get) == COTE_CASE_DEFAUT


def test_seules_les_cartes_de_ville_non_citees():
	docs, refus = villes_a_creer(list(TAILLES), BASE, TAILLES.get)
	ids = set(_par_id(docs))
	assert not refus
	# auxerre / paris : déjà cités ; auberge : pas une carte de ville.
	assert ids == {"lieu:chartres", "lieu:lutecia_capital", "lieu:akureyri", "lieu:rome",
		"lieu:reykjavik"}


def test_cases_carrees_a_la_taille_de_la_base():
	docs = _par_id(villes_a_creer(list(TAILLES), BASE, TAILLES.get)[0])
	for doc in docs.values():
		l, h = TAILLES[doc["image"]]
		assert doc["dimensions"] == {"x": round(l / COTE), "y": round(h / COTE)}
	assert docs["lieu:akureyri"]["dimensions"]["x"] == docs["lieu:akureyri"]["dimensions"]["y"]


def test_forme_du_doc():
	docs = _par_id(villes_a_creer(list(TAILLES), BASE, TAILLES.get)[0])
	rome, chartres = docs["lieu:rome"], docs["lieu:chartres"]
	assert rome["type"] == "lieu" and rome["categorie"] == "ville" and rome["tags"] == []
	assert rome["sous_categorie"] == "capitale" and "lieu_parent" not in rome
	assert chartres["sous_categorie"] == "ville" and chartres["lieu_parent"] == PAYS_FRANCE
	assert docs["lieu:akureyri"]["sous_categorie"] == "ville"  # _start_city, pas _city seul
	assert docs["lieu:reykjavik"]["label"] == "Reykjavík"


def test_slug_pris_retombe_sur_le_nom_complet():
	"""`lieu:lutecia` existe (sur paris_capital.png) : lutecia_capital.png devient un lieu
	DISTINCT plutôt que de l'écraser."""
	doc = _par_id(villes_a_creer(list(TAILLES), BASE, TAILLES.get)[0])["lieu:lutecia_capital"]
	assert doc["image"] == "lutecia_capital.png" and doc["lieu_parent"] == PAYS_FRANCE


def test_id_entierement_pris_refuse_le_lot():
	base = BASE + [{"_id": "lieu:rome"}, {"_id": "lieu:rome_capital"}]
	docs, refus = villes_a_creer(list(TAILLES), base, TAILLES.get)
	assert refus and "rome_capital.png" in refus[0]


def test_sans_pays_pas_de_parent():
	base = [d for d in BASE if d["_id"] != PAYS_FRANCE]
	docs = _par_id(villes_a_creer(list(TAILLES), base, TAILLES.get)[0])
	assert "lieu_parent" not in docs["lieu:chartres"]


def test_rejeu_apres_import_ne_cree_rien():
	docs, _ = villes_a_creer(list(TAILLES), BASE, TAILLES.get)
	assert villes_a_creer(list(TAILLES), BASE + docs, TAILLES.get) == ([], [])


def test_image_illisible_refusee():
	docs, refus = villes_a_creer(["lyon_city.png"], BASE, TAILLES.get)
	assert not docs and "illisible" in refus[0]


def test_grille_posee_apres_dimensions():
	doc = villes_a_creer(["rome_capital.png"], BASE, TAILLES.get)[0][0]
	sortant = poser_grille(doc, {"cells": [[1]], "nav": {"0,0": 1}})
	cles = list(sortant)
	assert cles[cles.index("dimensions") + 1: cles.index("dimensions") + 3] == ["cells", "nav"]
	assert sortant["cells"] == [[1]] and sortant["nav"] == {"0,0": 1}
