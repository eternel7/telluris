"""`dev/gen_quais_manche.py` — zones de quai, un capitaine par zone.

1. Zone neuve : lieu + capitaine + route dont seul le départ change, connexions vers ce lieu.
2. Zone d'origine : seul le portrait du capitaine change (PNJ et entrée `pnj` du lieu) ;
   `quai01` n'est réécrit que s'il change de case.
3. Case ≠ 1, case isolée, case prise ou `_id` volé ⇒ refus.
4. Numérotation dans l'ordre du pourtour, `quai01` à 1 ; zones du vrai découpage contiguës.
"""

from dev import gen_quais_manche as g


def _docs(cells, autres=()):
	return [
		{"_id": "lieu:port", "type": "lieu", "cells": cells},
		{"_id": "lieu:port_quais", "type": "lieu", "label": "Les quais", "image": "q.jpg",
		 "categorie": "quai", "lieu_parent": "lieu:port",
		 "pnj": [{"character": "pnj:capitaine_port", "portrait": "vieux.jpg", "probabilite": 1}]},
		{"_id": "pnj:capitaine_port", "type": "pnj", "portrait": "vieux.jpg",
		 "vocation": "guerrier", "services": {"traversee": {"route": "traversee:port_ile"}}},
		{"_id": "traversee:port_ile", "type": "traversee", "depart": {"lieu": "lieu:port_quais"},
		 "arrivee": {"lieu": "lieu:ile_quais", "pos": [0, 0]}},
		{"_id": "link:quai01_to_port", "type": "connection",
		 "nodes": [{"lieu": "lieu:port", "pos": [0, 0]}, {"lieu": "lieu:port_quais", "pos": [0, 0]}]},
		*autres]


def _ports(monkeypatch, origine, neuve):
	monkeypatch.setattr(g, "PORTRAITS", {"pnj:capitaine_port": "neuf.jpg"})
	monkeypatch.setattr(g, "PORTS", ({"cite": "lieu:port", "quai01": origine[0],
									   "route": "traversee:port_ile", "zones": (
		{"zone": None, "cases": origine},
		{"zone": "est", "label": "Les quais est",
		 "cases": neuve, "capitaine": {"nom": "Ana", "race": "elfe", "sexe": "f",
									   "description": "d", "dialogue": {}}})},))


def test_zone_neuve_et_zone_d_origine(monkeypatch):
	_ports(monkeypatch, ((0, 0),), ((2, 0),))
	docs = _docs([[1, 1, 1]])
	sortants, refus = g.construire(docs)
	assert refus == []
	par_id = {d["_id"]: d for d in sortants}
	assert "link:quai01_to_port" not in {d["_id"] for d in g.a_emettre(docs, sortants)[0]}
	assert par_id["pnj:capitaine_port"]["portrait"] == "neuf.jpg"
	assert par_id["lieu:port_quais"]["pnj"][0]["portrait"] == "neuf.jpg"
	route = par_id["traversee:port_est_ile"]
	assert route["depart"] == {"lieu": "lieu:port_quais_est"}
	assert route["arrivee"] == {"lieu": "lieu:ile_quais", "pos": [0, 0]}
	cap = par_id["pnj:capitaine_port_est"]
	assert cap["services"]["traversee"]["route"] == "traversee:port_est_ile"
	assert cap["portrait"] == "capitaine_elfe_f_port01.jpg"
	assert par_id["lieu:port_quais_est"]["pnj"][0]["character"] == "pnj:capitaine_port_est"
	assert par_id["link:quai02_to_port"]["nodes"] == [
		{"lieu": "lieu:port", "pos": [2, 0]}, {"lieu": "lieu:port_quais_est", "pos": [0, 0]}]


def test_case_bloquee_isolee_prise_ou_id_vole(monkeypatch):
	_ports(monkeypatch, ((0, 0),), ((1, 0), (2, 0)))
	assert len(g.construire(_docs([[1, 0, 1]]))[1]) == 2   # (1,0) = 0, (2,0) isolée
	prise = {"_id": "link:autre", "type": "connection",
			 "nodes": [{"lieu": "lieu:port", "pos": [2, 0]}, {"lieu": "lieu:x", "pos": [0, 0]}]}
	volee = {"_id": "link:quai02_to_port", "type": "connection",
			 "nodes": [{"lieu": "lieu:port", "pos": [9, 9]}, {"lieu": "lieu:x", "pos": [0, 0]}]}
	refus = g.construire(_docs([[1, 1, 1]], (prise, volee)))[1]
	assert any("déjà prise par link:autre" in r for r in refus)
	assert any("_id déjà pris" in r for r in refus)


def test_quai01_repose_sur_sa_case(monkeypatch):
	_ports(monkeypatch, ((1, 0),), ((2, 0),))
	docs = _docs([[1, 1, 1]])
	par_id = {d["_id"]: d for d in g.a_emettre(docs, g.construire(docs)[0])[0]}
	assert par_id["link:quai01_to_port"]["nodes"][0] == {"lieu": "lieu:port", "pos": [1, 0]}


def test_numerotation_et_zones_contigues():
	for port in g.PORTS:
		nums = [nn for zone in g.numeroter(port) for nn, _ in zone]
		assert sorted(nums) == list(range(1, len(nums) + 1)), port["cite"]
		origine = next(z for z in port["zones"] if z["zone"] is None)
		assert tuple(port["quai01"]) in map(tuple, origine["cases"])
		cases = [c for z in port["zones"] for c in z["cases"]]
		assert len(set(cases)) == len(cases)
		for z in port["zones"]:
			assert len(z["cases"]) >= 3, (port["cite"], z["zone"])
			for a, b in zip(z["cases"], z["cases"][1:]):   # voisines le long du quai
				assert max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= 3, (a, b)
