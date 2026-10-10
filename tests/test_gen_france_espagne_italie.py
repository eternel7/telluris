"""dev/gen_france_espagne_italie.py — frontière des Pyrénées, liens France ↔ Espagne / Italie,
Rome posée sur l'Italie.

Partie pure seulement (`proposer_espagne_fn` injecté). Verrouille ce qu'un import PUT COMPLET
rendrait silencieux : une frontière ouverte laisserait passer sans connexion, un tour repris à
chaque rejeu effacerait les murs retouchés, Rome doit garder tout son doc.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_france_espagne_italie as gfei  # noqa: E402
from dev.gen_plaine_europeenne import cases_frontiere, zone_de  # noqa: E402


def _grille(cols=88, rows=48, valeur=1):
	return [[valeur] * cols for _ in range(rows)]


def _lieu(_id, **extra):
	return {"_id": _id, "_rev": "1-x", "type": "lieu", "dimensions": {"x": 88, "y": 48},
		"cells": _grille(), "nav": {}, **extra}


def _docs():
	return [_lieu(gfei.FRANCE, nav={"30,47": 56}, label="France"),
		_lieu(gfei.ESPAGNE, nav={"10,10": 255}, label="Espagne"), _lieu(gfei.ITALIE, label="Italie"),
		_lieu(gfei.ROME, label="Rome")]


def _proposer_tour(doc):
	# Le tour proposé : un mur de côte, plus des murs sur la France et sur les neiges.
	return {"cells": _grille(), "nav": {"20,20": 1, "60,2": 4, "60,10": 16}}


def test_frontieres_posees_des_deux_cotes():
	lieux, _, refus = gfei.construire(_docs(), _proposer_tour)
	assert refus == []
	par_id = {d["_id"]: d for d in lieux}
	france, espagne = par_id[gfei.FRANCE], par_id[gfei.ESPAGNE]
	for x, y in cases_frontiere(gfei.FRONTIERE_FRANCE, "sud", 88, 48):
		assert france["cells"][y][x] == 0
	for x, y in cases_frontiere(gfei.FRONTIERE_ESPAGNE, "nord", 88, 48):
		assert espagne["cells"][y][x] == 0
	assert france["nav"] == {"30,47": 56}  # murs peints de la France : aucun bit retiré


def test_tour_de_l_espagne_repris_murs_de_frontiere_et_de_neige_retires():
	lieux, _, _ = gfei.construire(_docs(), _proposer_tour)
	espagne = next(d for d in lieux if d["_id"] == gfei.ESPAGNE)
	assert espagne["nav"] == {"20,20": 1}  # l'ancien nav (10,10) est oublié


def test_tour_non_repris_si_la_frontiere_est_deja_posee():
	docs = _docs()
	espagne = docs[1]
	for x, y in cases_frontiere(gfei.FRONTIERE_ESPAGNE, "nord", 88, 48):
		espagne["cells"][y][x] = 0

	def interdit(doc):
		raise AssertionError("tour repris alors que la frontière est posée")

	lieux, _, refus = gfei.construire(docs, interdit)
	assert refus == []
	assert next(d for d in lieux if d["_id"] == gfei.ESPAGNE)["nav"] == {"10,10": 255}


def test_cols_des_pyrenees_de_part_et_d_autre_de_la_crete():
	_, liens, _ = gfei.construire(_docs(), _proposer_tour)
	par_id = {l["_id"]: l for l in liens}
	for i, (nom, cible_fr, cible_es) in enumerate(gfei.PASSAGES_ESPAGNE, start=1):
		fr, es = par_id[f"link:france_to_espagne_{i:02d}"]["nodes"]
		assert fr == {"lieu": gfei.FRANCE, "pos": list(cible_fr), "label": f"{nom} — France"}
		assert es == {"lieu": gfei.ESPAGNE, "pos": list(cible_es), "label": f"{nom} — Espagne"}
		assert fr["pos"][1] < 47  # avant la limite des murs nav de la France


def test_frontieres_alpines_et_balkaniques_de_l_italie():
	lieux, _, refus = gfei.construire(_docs(), _proposer_tour)
	assert refus == []
	par_id = {d["_id"]: d for d in lieux}
	france, italie = par_id[gfei.FRANCE], par_id[gfei.ITALIE]
	for x, y in cases_frontiere(gfei.FRONTIERE_FRANCE_ITALIE, "est", 88, 48):
		assert france["cells"][y][x] == 0
	assert france["cells"][44][82] == 1  # la Corse, au large, reste française
	for bandes, sens in ((gfei.FRONTIERE_ITALIE_FRANCE, "ouest"),
			(gfei.FRONTIERE_ITALIE_PANNONIE, "est"), (gfei.FRONTIERE_ITALIE_TYROL, "nord")):
		for x, y in cases_frontiere(bandes, sens, 88, 48):
			assert italie["cells"][y][x] == 0
	assert italie["cells"][gfei.ANCRE_ITALIE[1]][gfei.ANCRE_ITALIE[0]] == 1


def test_cols_des_alpes_de_part_et_d_autre_de_la_crete():
	_, liens, _ = gfei.construire(_docs(), _proposer_tour)
	par_id = {l["_id"]: l for l in liens}
	for i, (nom, cible_fr, cible_it) in enumerate(gfei.PASSAGES_ITALIE, start=1):
		fr, it = par_id[f"link:france_to_italie_{i:02d}"]["nodes"]
		assert fr == {"lieu": gfei.FRANCE, "pos": list(cible_fr), "label": f"{nom} — France"}
		assert it == {"lieu": gfei.ITALIE, "pos": list(cible_it), "label": f"{nom} — Italie"}


def test_rome_reste_atteignable_depuis_l_italie_bordee():
	_, liens, refus = gfei.construire(_docs(), _proposer_tour)
	assert refus == []
	assert sum(1 for l in liens if l["_id"].startswith("link:italie_to_rome_")) == len(gfei.SORTIES_ROME)


def test_rome_sorties_et_cases_italie_distinctes():
	docs, refus = gfei.connexions_rome(zone_de(_grille(), {}), zone_de(_grille(), {}))
	assert refus == [] and len(docs) == len(gfei.SORTIES_ROME)
	poses = [tuple(d["nodes"][0]["pos"]) for d in docs]
	assert poses[0] == gfei.POSITION_ROME and len(set(poses)) == len(poses)


def test_rome_rattachee_garde_tout_son_doc():
	rome = _lieu(gfei.ROME, label="Rome")
	doc = gfei.rome_rattachee(rome)
	assert "_rev" not in doc and doc["lieu_parent"] == gfei.ITALIE and doc["label"] == "Rome"
	assert "lieu_parent" not in rome


def test_lieu_manquant_refuse():
	lieux, liens, refus = gfei.construire(_docs()[:3], _proposer_tour)
	assert lieux == [] and liens == [] and gfei.ROME in refus[0]
