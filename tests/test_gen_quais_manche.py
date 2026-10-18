"""`dev/gen_quais_manche.py` — accès supplémentaires aux quais de la traversée.

1. Une case praticable reliée à `quai01` donne une connexion de la forme de `quai01`.
2. Case ≠ 1, case isolée, case déjà prise ou `_id` volé ⇒ refus.
"""

from dev import gen_quais_manche as g


def _docs(cells, autres=()):
	return [{"_id": "lieu:port", "type": "lieu", "cells": cells},
			{"_id": "lieu:port_quais", "type": "lieu"}, *autres]


def _quais(monkeypatch, cases):
	monkeypatch.setattr(g, "QUAIS", ({"cite": "lieu:port", "quai": "lieu:port_quais",
									   "existant": (0, 0), "cases": cases},))


def test_une_case_reliee_donne_la_forme_de_quai01(monkeypatch):
	_quais(monkeypatch, ((2, 0),))
	sortants, refus = g.construire(_docs([[1, 1, 1]]))
	assert refus == []
	assert sortants == [{"_id": "link:quai02_to_port", "type": "connection",
						 "nodes": [{"lieu": "lieu:port", "pos": [2, 0]},
								   {"lieu": "lieu:port_quais", "pos": [0, 0]}],
						 "metadata": g.META}]


def test_case_bloquee_isolee_prise_ou_id_vole(monkeypatch):
	_quais(monkeypatch, ((1, 0), (2, 0)))
	assert len(g.construire(_docs([[1, 0, 1]]))[1]) == 2   # (1,0) = 0, (2,0) isolée
	prise = {"_id": "link:autre", "type": "connection",
			 "nodes": [{"lieu": "lieu:port", "pos": [2, 0]}, {"lieu": "lieu:x", "pos": [0, 0]}]}
	volee = {"_id": "link:quai02_to_port", "type": "connection",
			 "nodes": [{"lieu": "lieu:port", "pos": [9, 9]}, {"lieu": "lieu:x", "pos": [0, 0]}]}
	refus = g.construire(_docs([[1, 1, 1]], (prise, volee)))[1]
	assert any("déjà prise par link:autre" in r for r in refus)
	assert any("_id déjà pris" in r for r in refus)
