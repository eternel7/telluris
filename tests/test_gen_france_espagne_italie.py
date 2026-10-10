"""dev/gen_france_espagne_italie.py — liens France ↔ Espagne / Italie, Rome posée sur l'Italie.

Partie pure seulement. Verrouille ce qu'un import PUT COMPLET rendrait silencieux : une porte
hors de la zone principale serait inatteignable sans erreur, un lien réémis écraserait sa
retouche, et Rome doit garder tout son doc en recevant son parent.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_france_espagne_italie as gfei  # noqa: E402
from dev.gen_plaine_europeenne import zone_principale  # noqa: E402


def _grille(cols=88, rows=48, valeur=1):
	return [[valeur] * cols for _ in range(rows)]


def _principale(cells=None):
	return zone_principale(cells or _grille(), {})


def test_case_au_bord_dans_les_quatre_sens():
	p = {(3, 1), (3, 5), (3, 9), (0, 4), (6, 4)}
	assert gfei.case_au_bord(p, colonne=3, vers="nord") == (3, 1)
	assert gfei.case_au_bord(p, colonne=3, vers="sud") == (3, 9)
	assert gfei.case_au_bord(p, rangee=4, vers="ouest") == (0, 4)
	assert gfei.case_au_bord(p, rangee=4, vers="est") == (6, 4)
	assert gfei.case_au_bord(p, colonne=3, vers="nord", borne=2) == (3, 5)
	assert gfei.case_au_bord(p, colonne=7, vers="nord") is None


def test_france_sud_vers_espagne_cases_fixees():
	docs, refus = gfei.connexions_pays(_principale(), _principale(), gfei.ESPAGNE,
		gfei.PASSAGES_ESPAGNE, "sud")
	assert refus == [] and len(docs) == len(gfei.PASSAGES_ESPAGNE)
	for doc, (x_fr, pos_es) in zip(docs, gfei.PASSAGES_ESPAGNE):
		fr, es = doc["nodes"]
		assert fr == {"lieu": gfei.FRANCE, "pos": [x_fr, gfei.FRANCE_Y_SUD]}
		assert es == {"lieu": gfei.ESPAGNE, "pos": list(pos_es)}


def test_case_fixee_hors_zone_principale_refusee():
	cells = _grille()
	x, y = gfei.PASSAGES_ESPAGNE[0][1]
	cells[y][x] = 0
	docs, refus = gfei.connexions_pays(_principale(), _principale(cells), gfei.ESPAGNE,
		gfei.PASSAGES_ESPAGNE, "sud")
	assert len(docs) == len(gfei.PASSAGES_ESPAGNE) - 1 and len(refus) == 1


def test_france_est_vers_la_limite_ouest_de_l_italie():
	italie = _grille()
	for y in range(48):
		italie[y][0] = italie[y][1] = 0  # cadre : la limite ouest accessible est la colonne 2
	docs, refus = gfei.connexions_pays(_principale(), _principale(italie), gfei.ITALIE,
		gfei.PASSAGES_ITALIE, "est", "ouest")
	assert refus == [] and len(docs) == len(gfei.PASSAGES_ITALIE)
	for doc, (y_fr, y_it) in zip(docs, gfei.PASSAGES_ITALIE):
		fr, it = doc["nodes"]
		assert fr["pos"] == [gfei.FRANCE_X_EST, y_fr] and it["pos"] == [2, y_it]


def test_case_france_hors_zone_principale_refusee():
	france = _grille()
	france[gfei.FRANCE_Y_SUD][gfei.PASSAGES_ESPAGNE[0][0]] = 0
	_, refus = gfei.connexions_pays(_principale(france), _principale(), gfei.ESPAGNE,
		gfei.PASSAGES_ESPAGNE, "sud")
	assert len(refus) == 1 and gfei.FRANCE in refus[0]


def test_rome_sorties_et_cases_italie_distinctes():
	docs, refus = gfei.connexions_rome(_principale(), _principale())
	assert refus == [] and len(docs) == len(gfei.SORTIES_ROME)
	poses = [tuple(d["nodes"][0]["pos"]) for d in docs]
	assert poses[0] == gfei.POSITION_ROME and len(set(poses)) == len(poses)
	assert all(d["nodes"][1]["lieu"] == gfei.ROME for d in docs)


def test_rome_rattachee_garde_tout_son_doc():
	rome = {"_id": gfei.ROME, "_rev": "1-x", "cells": [[1]], "nav": {"0,0": 1}, "label": "Rome"}
	doc = gfei.rome_rattachee(rome)
	assert doc == {"_id": gfei.ROME, "cells": [[1]], "nav": {"0,0": 1}, "label": "Rome",
		"lieu_parent": gfei.ITALIE}
	assert gfei.rome_rattachee(doc) is None


def test_a_ecrire_rejeu():
	liens = [{"_id": "link:a"}, {"_id": "link:b"}]
	rome = {"_id": gfei.ROME}
	assert gfei.a_ecrire([], liens, rome) == ([rome] + liens, [])
	assert gfei.a_ecrire([{"_id": "link:a"}, {"_id": "link:b"}], liens, None) == ([], [])
	sortants, refus = gfei.a_ecrire([{"_id": "link:a"}], liens, None)
	assert sortants == [] and refus == ["link:a : `_id` déjà pris"]
