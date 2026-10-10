"""dev/gen_plaine_europeenne.py — plaine européenne, Bruges, Aix-la-Chapelle et leurs connexions.

Partie pure seulement : les grilles viennent de `gen_grille_image.proposer_pour_image` (Pillow),
testé par `test_grille_image.py`. Verrouille ce qu'un import PUT COMPLET rendrait silencieux :
une plaine réémise écraserait ses murs retouchés, une porte hors de la zone principale serait
inatteignable sans erreur.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_plaine_europeenne as gpe  # noqa: E402

TAILLES = {gpe.IMAGE_PLAINE: (1408, 768), **{nom: (1408, 768) for nom in gpe.IMAGES_CITES}}
BASE = [
	{"_id": "lieu:france", "type": "lieu", "categorie": "pays", "image": "france.png",
		"dimensions": {"x": 88, "y": 48}},
]


def _grille(cols, rows, valeur=1):
	return [[valeur] * cols for _ in range(rows)]


def test_trois_lieux_cites_rattachees_a_la_plaine():
	plaine, cites, refus = gpe.lieux_a_creer(BASE, TAILLES.get)
	assert refus == []
	assert plaine["_id"] == gpe.PLAINE and plaine["categorie"] == "pays"
	assert {c["_id"] for c in cites} == set(gpe.POSITIONS_PLAINE)
	assert all(c["lieu_parent"] == gpe.PLAINE and c["categorie"] == "ville" for c in cites)
	assert {c["_id"]: c["label"] for c in cites}["lieu:aix_la_chapelle"] == "Aix-la-Chapelle"


def test_plaine_deja_en_base_rien_a_creer():
	docs = BASE + [{"_id": gpe.PLAINE, "type": "lieu", "image": gpe.IMAGE_PLAINE}]
	assert gpe.lieux_a_creer(docs, TAILLES.get) == (None, [], [])


def test_cite_deja_prise_refuse_le_lot():
	docs = BASE + [{"_id": "lieu:bruges", "type": "lieu", "image": "bruges_city.jpg"}]
	plaine, cites, refus = gpe.lieux_a_creer(docs, TAILLES.get)
	assert plaine is None and cites == [] and any("lieu:bruges" in r for r in refus)


def test_zone_principale_suit_la_marche():
	cells = _grille(5, 3)
	for y in range(3):
		cells[y][2] = 0  # colonne pleine : deux zones, 6 cases à gauche contre 6 à droite
	cells[0][3] = 0
	principale = gpe.zone_principale(cells, {})
	assert principale == {(x, y) for x in (0, 1) for y in range(3)}


def test_france_rangee_nord_vers_la_limite_sud_de_la_plaine():
	plaine = _grille(88, 48)
	for x in range(88):
		plaine[47][x] = 0  # cadre du bas : la limite sud accessible est la rangée 46
	principale = gpe.zone_principale(plaine, {})
	france = {"_id": gpe.FRANCE, "cells": _grille(88, 48)}
	docs, refus = gpe.connexions_france(france, principale)
	assert refus == [] and len(docs) == len(gpe.PASSAGES_FRANCE)
	for doc, (x_fr, x_pl) in zip(docs, gpe.PASSAGES_FRANCE):
		fr, pl = doc["nodes"]
		assert fr == {"lieu": gpe.FRANCE, "pos": [x_fr, gpe.FRANCE_Y]}
		assert pl == {"lieu": gpe.PLAINE, "pos": [x_pl, 46]}
		assert doc["type"] == "connection" and doc["metadata"]["status"] == "ouvert"


def test_france_case_inaccessible_refusee():
	x_fr = gpe.PASSAGES_FRANCE[0][0]
	cells = _grille(88, 48)
	cells[gpe.FRANCE_Y][x_fr] = 0
	_, refus = gpe.connexions_france({"cells": cells}, gpe.zone_principale(_grille(88, 48), {}))
	assert len(refus) == 1 and f"[{x_fr}, {gpe.FRANCE_Y}]" in refus[0]


def test_sorties_de_cite_dans_la_zone_principale_et_cases_plaine_distinctes():
	cite = _grille(88, 48)
	for y in range(48):
		for x in range(88):
			if x < 3 or y < 3:
				cite[y][x] = 0  # cadre : la sortie ouest se replie sur la colonne 3
	principale_cite = gpe.zone_principale(cite, {})
	principale_plaine = gpe.zone_principale(_grille(88, 48), {})
	for cite_id, sorties in gpe.SORTIES_CITES.items():
		docs, refus = gpe.connexions_cite(cite_id, principale_cite, principale_plaine)
		assert refus == [] and len(docs) == len(sorties)
		poses_plaine = [tuple(d["nodes"][0]["pos"]) for d in docs]
		assert len(set(poses_plaine)) == len(poses_plaine)
		assert poses_plaine[0] == gpe.POSITIONS_PLAINE[cite_id]
		for d in docs:
			assert tuple(d["nodes"][1]["pos"]) in principale_cite
			assert d["nodes"][1]["lieu"] == cite_id


def test_cite_hors_zone_principale_de_la_plaine_refusee():
	plaine = _grille(88, 48)
	x, y = gpe.POSITIONS_PLAINE["lieu:bruges"]
	plaine[y][x] = 0
	docs, refus = gpe.connexions_cite("lieu:bruges", gpe.zone_principale(_grille(88, 48), {}),
		gpe.zone_principale(plaine, {}))
	assert docs == [] and len(refus) == 1


def test_ids_deja_pris():
	sortants = [{"_id": "link:france_to_plaine_europeenne_01"}, {"_id": "lieu:neuf"}]
	assert gpe.ids_deja_pris([{"_id": "link:france_to_plaine_europeenne_01"}], sortants) == [
		"link:france_to_plaine_europeenne_01"]
