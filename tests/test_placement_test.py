# tests/test_placement_test.py
#
# `GET /api/lieu/{id}/placement_test` (utils/lieux.py) — où le jeton du mode « test de
# déplacement » de l'éditeur de carte naît-il ?
#
# CE QUI EST FIGÉ ICI : l'endpoint ne réimplémente RIEN. Il rebâtit le `grid` exactement
# comme `create_combat_doc` et délègue à `combat._place_actors`. Le test le vérifie par ses
# CONSÉQUENCES — le joueur tombe sur du terrain EXACTEMENT 1, dans les bornes de `cells`,
# les monstres sur du `_walkable` et dans SA région — parce que ce sont ces propriétés-là
# que le mode test promet à l'admin. Une règle recopiée en JS les perdrait en silence.
#
# ⚠️ Le placement est ALÉATOIRE (mode centre/bordure tiré à pile ou face, ordre mélangé dans
# chaque palier de distance) : chaque cas tourne plusieurs fois, sinon un défaut sur une
# branche sur deux passerait une fois sur deux.

import asyncio

import pytest
from fastapi import HTTPException

from utils import combat, lieux

ADMIN = {"admin": 1, "_id": "user:a@b.c"}
PASSANT = {"admin": 0, "_id": "user:x@y.z"}


def _appeler(monkeypatch, doc, monstres=0, user=ADMIN):
	monkeypatch.setattr(lieux, "get_doc", lambda _id: doc)
	return asyncio.run(lieux.get_placement_test(None, user, "lieu:test", monstres=monstres))


def _lieu(cells, nav=None):
	return {
		"_id": "lieu:test",
		"dimensions": {"x": len(cells[0]), "y": len(cells)},
		"cells": [list(l) for l in cells],
		"nav": nav or {},
	}


# Grille 12×10 : une bande de terrain difficile (2) au milieu, une falaise (3), un mur (0).
GRILLE = [[1] * 12 for _ in range(10)]
for _x in range(12):
	GRILLE[4][_x] = 2
GRILLE[4][6] = 3
GRILLE[0][0] = 0


def test_le_jeton_tombe_sur_du_terrain_EXACTEMENT_1(monkeypatch):
	# ⚠️ Pas `>= 1` : le joueur ne se pose que sur du sol normal (`_is_type1`), le `>= 1`
	# étant réservé aux monstres. Confondre les deux ferait naître le jeton sur du terrain
	# difficile, où l'exploration refuse justement d'aller.
	doc = _lieu(GRILLE)
	for _ in range(30):
		pos = _appeler(monkeypatch, doc)["pos"]
		assert doc["cells"][pos["y"]][pos["x"]] == 1, f"posé sur du terrain {doc['cells'][pos['y']][pos['x']]}"


def test_le_jeton_reste_dans_les_bornes_de_cells(monkeypatch):
	# Bornes en comptes de cases (0..dim-1). Le garde serveur de `move_character`, lui, teste
	# `<= dimensions.x` — borne inclusive : un jeton posé sur `dim` serait hors image.
	doc = _lieu(GRILLE)
	for _ in range(30):
		pos = _appeler(monkeypatch, doc)["pos"]
		assert 0 <= pos["x"] < 12 and 0 <= pos["y"] < 10


def test_une_grille_SANS_AUCUN_1_reste_exploitable(monkeypatch):
	# Repli de `_place_actors` (`_first_passable_cells`) : mieux vaut un jeton sur du terrain
	# difficile qu'un 500 sur la carte même qu'on est venu réparer.
	cells = [[2] * 5 for _ in range(5)]
	pos = _appeler(monkeypatch, _lieu(cells))["pos"]
	assert 0 <= pos["x"] < 5 and 0 <= pos["y"] < 5


def test_un_lieu_sans_dimensions_rend_400_et_pas_500(monkeypatch):
	# Sans garde, `grid["dims"]` lèverait un KeyError — une erreur serveur là où le vrai
	# message est « ce lieu n'a pas de grille ».
	doc = {"_id": "lieu:boutique", "cells": [[1, 1], [1, 1]]}
	with pytest.raises(HTTPException) as e:
		_appeler(monkeypatch, doc)
	assert e.value.status_code == 400


def test_un_lieu_sans_cells_rend_400(monkeypatch):
	doc = {"_id": "lieu:boutique", "dimensions": {"x": 2, "y": 2}}
	with pytest.raises(HTTPException) as e:
		_appeler(monkeypatch, doc)
	assert e.value.status_code == 400


def test_un_lieu_introuvable_rend_404(monkeypatch):
	with pytest.raises(HTTPException) as e:
		_appeler(monkeypatch, None)
	assert e.value.status_code == 404


def test_un_non_admin_est_refuse(monkeypatch):
	with pytest.raises(HTTPException) as e:
		_appeler(monkeypatch, _lieu(GRILLE), user=PASSANT)
	assert e.value.status_code == 400


def test_les_monstres_sont_distincts_walkable_et_dans_la_region_du_joueur(monkeypatch):
	# ⚠️ C'EST LE CAS QUI EXERCE LA VRAIE RÈGLE. Avec `monstres: []`, `need` vaut 1 et la
	# région d'une case type 1 la contient toujours : la boucle de candidats casse sur le
	# premier et l'étape 4 (dispersion) ne tourne jamais. À N > 0 seulement, on éprouve
	# « la région est-elle assez grande ? » et « les monstres joignent-ils le joueur ? ».
	doc = _lieu(GRILLE)
	for _ in range(20):
		rep = _appeler(monkeypatch, doc, monstres=4)
		joueur = rep["pos"]
		assert len(rep["monstres"]) == 4
		cases = {(joueur["x"], joueur["y"])} | {(m["x"], m["y"]) for m in rep["monstres"]}
		assert len(cases) == 5, "deux acteurs sur la même case"
		region = combat._reachable_region(
			doc["cells"], doc["dimensions"], doc["nav"], (joueur["x"], joueur["y"]))
		for m in rep["monstres"]:
			assert combat._walkable(doc["cells"], m["x"], m["y"]), "monstre sur une case infranchissable"
			assert (m["x"], m["y"]) in region, "monstre injoignable depuis le joueur"


def test_le_nombre_de_monstres_est_borne(monkeypatch):
	# Une valeur venue de la barre d'URL ne doit pas pouvoir demander mille flood fills.
	rep = _appeler(monkeypatch, _lieu(GRILLE), monstres=999)
	assert len(rep["monstres"]) == 20
	assert _appeler(monkeypatch, _lieu(GRILLE), monstres=-3)["monstres"] == []


def test_nav_est_respecte_le_jeton_ne_nait_pas_dans_une_enclave_trop_petite(monkeypatch):
	# Une case type 1 murée de toutes parts par `nav` a une région de taille 1 : elle ne peut
	# pas loger le joueur ET ses deux monstres, donc `_place_actors` doit passer son chemin.
	cells = [[1] * 8 for _ in range(8)]
	nav = {"0,0": 255}   # toutes les directions interdites depuis (0,0)
	doc = _lieu(cells, nav)
	for _ in range(20):
		pos = _appeler(monkeypatch, doc, monstres=2)["pos"]
		assert (pos["x"], pos["y"]) != (0, 0), "jeton né dans une enclave d'une seule case"
