"""dev/gen_plaine_europeenne.py — plaine européenne, Bruges, Aix-la-Chapelle, et les outils de
frontière partagés.

Partie pure seulement : les grilles viennent de `gen_grille_image.proposer_pour_image` (Pillow),
testé par `test_grille_image.py` ; ici `proposer_fn` est une grille uniforme. Verrouille ce qu'un
import PUT COMPLET rendrait silencieux : une plaine réémise écraserait ses murs retouchés, une
porte hors de la terre serait inatteignable sans erreur, une frontière ouverte laisserait
changer de carte sans connexion.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_plaine_europeenne as gpe  # noqa: E402

TAILLES = {gpe.IMAGE_PLAINE: (1408, 768), **{nom: (1408, 768) for nom in gpe.IMAGES_CITES}}


def _grille(cols=88, rows=48, valeur=1):
	return [[valeur] * cols for _ in range(rows)]


def _france():
	cells = _grille()
	cells[0] = [0] * 88  # le nord hors de la terre : la rangée 1 est la frontière
	return {"_id": gpe.FRANCE, "type": "lieu", "label": "France", "categorie": "pays", "image": "france.png",
		"dimensions": {"x": 88, "y": 48}, "cells": cells, "nav": {}}


def _proposer(doc, profil):
	return {"cells": _grille(doc["dimensions"]["x"], doc["dimensions"]["y"]), "nav": {}, "rapport": {}}


def test_zone_de_suit_l_ancre_puis_la_plus_grande():
	cells = _grille(6, 3)
	for y in range(3):
		cells[y][2] = 0  # colonne pleine : 6 cases à gauche, 9 à droite
	assert gpe.zone_de(cells, {}) == {(x, y) for x in (3, 4, 5) for y in range(3)}
	assert gpe.zone_de(cells, {}, (0, 0)) == {(x, y) for x in (0, 1) for y in range(3)}
	assert gpe.zone_de(cells, {}, (2, 0)) == set()


def test_cases_frontiere_et_fermer():
	cases = gpe.cases_frontiere(((1, 2, 3),), "sud", 5, 5)
	assert cases == {(x, y) for x in (1, 2) for y in (3, 4)}
	assert gpe.cases_frontiere(((0, 0, 1),), "nord", 5, 5) == {(0, 0), (0, 1)}
	assert gpe.cases_frontiere(((1, 1, 3),), "est", 5, 5) == {(3, 1), (4, 1)}
	assert gpe.cases_frontiere(((0, 1, 0),), "ouest", 5, 5) == {(0, 0), (0, 1)}
	cells = _grille(5, 5)
	assert gpe.fermer(cells, cases) == 4 and gpe.fermer(cells, cases) == 0
	assert cells[3][1] == 0 and cells[2][1] == 1


def test_trois_lieux_neufs_frontiere_posee_et_cites_rattachees():
	lieux, liens, refus, propositions, _ = gpe.construire([_france()], TAILLES.get, _proposer, _france())
	assert refus == []
	par_id = {d["_id"]: d for d in lieux}
	assert set(par_id) == {gpe.PLAINE} | set(gpe.POSITIONS_PLAINE) == set(propositions)
	assert all(par_id[c]["lieu_parent"] == gpe.PLAINE for c in gpe.POSITIONS_PLAINE)
	assert par_id["lieu:aix_la_chapelle"]["label"] == "Aix-la-Chapelle"
	cells = par_id[gpe.PLAINE]["cells"]
	for x, y in gpe.cases_frontiere(gpe.FRONTIERE_PLAINE, "sud", 88, 48):
		assert cells[y][x] == 0
	attendus = {f"link:france_to_plaine_europeenne_{i:02d}" for i in range(1, len(gpe.PASSAGES_PLAINE) + 1)}
	attendus |= {f"link:plaine_europeenne_to_{c.split(':')[1]}_{nom}"
		for c, sorties in gpe.SORTIES_CITES.items() for nom in sorties}
	assert {l["_id"] for l in liens} == attendus


def test_passage_france_plaine_juste_au_nord_de_la_frontiere():
	lieux, liens, _, _, _ = gpe.construire([_france()], TAILLES.get, _proposer, _france())
	plaine = next(d for d in lieux if d["_id"] == gpe.PLAINE)
	par_id = {l["_id"]: l for l in liens}
	for i, nom in enumerate(gpe.PASSAGES_PLAINE, start=1):
		fr, pl = par_id[f"link:france_to_plaine_europeenne_{i:02d}"]["nodes"]
		assert fr["lieu"] == gpe.FRANCE and fr["label"] == f"{nom} — France"
		assert fr["pos"][1] <= 2  # la rangée du nord de la France
		assert pl["label"] == f"{nom} — Plaine européenne"
		x, y = pl["pos"]
		assert pl["lieu"] == gpe.PLAINE and plaine["cells"][y][x] == 1
		# Une voisine est déjà la France, fermée (au sud, ou à l'ouest sur une marche de l'escalier).
		assert 0 in (plaine["cells"][y + 1][x], plaine["cells"][y][x - 1])


def test_passages_nommes_distincts_et_sorties_de_cite_libellees():
	noms = list(gpe.PASSAGES_PLAINE)
	assert len(set(noms)) == len(noms)
	_, liens, _, _, _ = gpe.construire([_france()], TAILLES.get, _proposer, _france())
	bruges = [l for l in liens if l["_id"].startswith("link:plaine_europeenne_to_bruges_")]
	assert {l["nodes"][1]["label"] for l in bruges} == {
		gpe.libelle_sortie("Bruges", nom) for nom in gpe.SORTIES_CITES["lieu:bruges"]}
	assert all("label" not in l["nodes"][0] for l in bruges)  # côté plaine : « Plaine européenne »


def test_lieux_deja_en_base_relus_et_non_reproposes():
	plaine = {"_id": gpe.PLAINE, "_rev": "3-x", "type": "lieu", "image": gpe.IMAGE_PLAINE,
		"categorie": "pays", "dimensions": {"x": 88, "y": 48}, "cells": _grille(), "nav": {},
		"zone_influences": ["retouche"]}
	cites = [{"_id": c, "type": "lieu", "image": f"{c.split(':')[1]}_city.jpg",
		"dimensions": {"x": 88, "y": 48}, "cells": _grille(), "nav": {}, "lieu_parent": gpe.PLAINE}
		for c in gpe.POSITIONS_PLAINE]
	lieux, _, refus, propositions, _ = gpe.construire([_france(), plaine] + cites, TAILLES.get,
		_proposer, _france())
	assert refus == [] and propositions == {}
	relue = next(d for d in lieux if d["_id"] == gpe.PLAINE)
	assert "_rev" not in relue and relue["zone_influences"] == ["retouche"]
	assert plaine["cells"][47][0] == 1  # le doc du dump n'est pas muté


def test_cite_hors_terre_de_la_plaine_refusee():
	zone = gpe.zone_de(_grille(), {})
	zone.discard(gpe.POSITIONS_PLAINE["lieu:bruges"])
	docs, refus = gpe.connexions_cite("lieu:bruges", gpe.zone_de(_grille(), {}), zone)
	assert docs == [] and len(refus) == 1


def test_lien_vise_ramene_dans_la_zone():
	zone = {(5, 5), (9, 9)}
	doc, refus = gpe.lien_vise("link:x", "lieu:a", zone, (4, 4), "lieu:b", zone, (10, 10))
	assert refus is None and [n["pos"] for n in doc["nodes"]] == [[5, 5], [9, 9]]
	doc, refus = gpe.lien_vise("link:x", "lieu:a", set(), (4, 4), "lieu:b", zone, (10, 10))
	assert doc is None and "lieu:a" in refus


def test_ligne_frontiere_suit_l_escalier_d_une_bande():
	# Bande « sud » en escalier : y ≥ 3 pour x ≤ 2, y ≥ 4 pour x ≥ 3 ; tout le reste est terre.
	au_dela = gpe.cases_frontiere(((0, 2, 3), (3, 5, 4)), "sud", 6, 6)
	zone = {(x, y) for x in range(6) for y in range(6)} - au_dela
	assert gpe.ligne_frontiere(zone, au_dela, (0, 0)) == [
		(0, 2), (1, 2), (2, 2), (3, 3), (4, 3), (5, 3)]
	assert gpe.ligne_frontiere(zone, au_dela, (9, 0))[0] == (5, 3)  # parcourue depuis l'autre bout
	assert gpe.ligne_frontiere(zone, au_dela, (0, 0), (2, 4, 0, 9)) == [(2, 2), (3, 3), (4, 3)]
	assert gpe.ligne_frontiere(set(), au_dela, (0, 0)) == []


def test_postes_une_case_sur_deux():
	ligne = list(range(7))
	assert gpe.postes(ligne, 4) == [0, 2, 4, 6]  # compte juste : une case sur deux, exactement
	plus = gpe.postes(ligne, 6)  # côté court : une case porte deux liens, aucune impaire
	assert len(plus) == 6 and set(plus) == {0, 2, 4, 6} and plus == sorted(plus)
	assert gpe.postes(ligne, 1) == [0] and gpe.postes([], 3) == []


def test_liens_frontiere_nommes_et_compte_verifie():
	ligne_a = [(x, 0) for x in range(5)]   # 3 postes
	ligne_b = [(x, 9) for x in range(3)]   # 2 postes : l'un porte deux liens
	libelles = {"lieu:a": "A", "lieu:b": "B"}
	docs, refus, avert = gpe.liens_frontiere("link:a_to_b", "lieu:a", ligne_a, "lieu:b", ligne_b,
		("Col 1", "Col 2", "Col 3"), libelles)
	assert refus == [] and avert == []
	assert [d["_id"] for d in docs] == ["link:a_to_b_01", "link:a_to_b_02", "link:a_to_b_03"]
	assert [d["nodes"][0]["pos"] for d in docs] == [[0, 0], [2, 0], [4, 0]]
	assert {tuple(d["nodes"][1]["pos"]) for d in docs} == {(0, 9), (2, 9)}
	assert docs[1]["nodes"] == [{"lieu": "lieu:a", "pos": [2, 0], "label": "Col 2 — A"},
		{"lieu": "lieu:b", "pos": [docs[1]["nodes"][1]["pos"][0], 9], "label": "Col 2 — B"}]
	_, _, avert = gpe.liens_frontiere("link:a_to_b", "lieu:a", ligne_a, "lieu:b", ligne_b,
		("Col 1", "Col 2"), libelles)
	assert len(avert) == 1  # la grille a bougé : la liste de noms est à revoir
	assert gpe.liens_frontiere("link:a_to_b", "lieu:a", [], "lieu:b", ligne_b, ("Col 1",), libelles)[1]
