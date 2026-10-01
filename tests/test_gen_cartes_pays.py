"""dev/gen_cartes_pays.py — un lieu de pays par carte de `maps/` qu'aucun lieu ne cite.

Partie pure seulement (`cartes_a_creer`) : la grille vient de
`gen_grille_image.proposer_pour_image` (Pillow) au profil `pays`, testé par
`test_grille_image.py`. Verrouille ce qu'un import PUT COMPLET rendrait silencieux : une carte
réémise écraserait ses murs retouchés (celle de `lieu:france` est peinte à la main), un `_id`
réutilisé écraserait un autre lieu.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev.gen_cartes_pays import CARTES, CATEGORIE, cartes_a_creer  # noqa: E402
from dev.gen_villes_images import COTE_CASE_DEFAUT  # noqa: E402

TAILLES = {
	"france.png": (1408, 768),
	"angleterre.png": (1408, 768),
	"islande.png": (1264, 848),
	"world.png": (1408, 768),
	"world_globe1.png": (757, 735),
	"hameau.png": (1264, 848),
}
COTE = 16
BASE = [
	{"_id": "lieu:france", "type": "lieu", "categorie": "pays", "image": "france.png",
		"dimensions": {"x": 1408 // COTE, "y": 768 // COTE}},
	{"_id": "lieu:auxerre", "categorie": "ville", "image": "auxerre_start_city.png",
		"dimensions": {"x": 1376 // (COTE * 2), "y": 768 // (COTE * 2)}},
]


def _par_id(docs):
	return {d["_id"]: d for d in docs}


def test_seules_les_cartes_de_la_liste_blanche_non_citees():
	docs, refus = cartes_a_creer(list(TAILLES), BASE, TAILLES.get)
	assert not refus
	# france : déjà citée ; globe et hameau : hors liste blanche.
	assert set(_par_id(docs)) == {"lieu:angleterre", "lieu:islande", "lieu:world"}
	assert "world_globe1.png" not in CARTES and "hameau.png" not in CARTES


def test_cote_relu_sur_les_pays_pas_sur_les_villes():
	"""Auxerre est à cases de 32 px dans cette base : seul le pays compte."""
	docs = _par_id(cartes_a_creer(list(TAILLES), BASE, TAILLES.get)[0])
	for doc in docs.values():
		l, h = TAILLES[doc["image"]]
		assert doc["dimensions"] == {"x": round(l / COTE), "y": round(h / COTE)}
	sans_pays = [d for d in BASE if d["categorie"] != CATEGORIE]
	docs = _par_id(cartes_a_creer(["angleterre.png"], sans_pays, TAILLES.get)[0])
	assert docs["lieu:angleterre"]["dimensions"]["x"] == round(1408 / COTE_CASE_DEFAUT)


def test_forme_du_doc():
	doc = _par_id(cartes_a_creer(list(TAILLES), BASE, TAILLES.get)[0])["lieu:world"]
	label, sous_categorie = CARTES["world.png"]
	assert doc["type"] == "lieu" and doc["categorie"] == CATEGORIE and doc["tags"] == []
	assert doc["label"] == label and doc["sous_categorie"] == sous_categorie
	assert doc["image"] == "world.png" and "lieu_parent" not in doc


def test_id_pris_refuse_le_lot():
	base = BASE + [{"_id": "lieu:islande", "image": "autre.png"}]
	docs, refus = cartes_a_creer(list(TAILLES), base, TAILLES.get)
	assert refus and "islande.png" in refus[0]


def test_rejeu_apres_import_ne_cree_rien():
	docs, _ = cartes_a_creer(list(TAILLES), BASE, TAILLES.get)
	assert cartes_a_creer(list(TAILLES), BASE + docs, TAILLES.get) == ([], [])


def test_image_illisible_refusee():
	docs, refus = cartes_a_creer(["italie.png"], BASE, TAILLES.get)
	assert not docs and "illisible" in refus[0]
