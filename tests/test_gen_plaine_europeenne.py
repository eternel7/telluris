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
	return {"_id": gpe.FRANCE, "type": "lieu", "categorie": "pays", "image": "france.png",
		"dimensions": {"x": 88, "y": 48}, "cells": _grille(), "nav": {}}


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
	cells = _grille(5, 5)
	assert gpe.fermer(cells, cases) == 4 and gpe.fermer(cells, cases) == 0
	assert cells[3][1] == 0 and cells[2][1] == 1


def test_trois_lieux_neufs_frontiere_posee_et_cites_rattachees():
	lieux, liens, refus, propositions = gpe.construire([_france()], TAILLES.get, _proposer, _france())
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
	lieux, liens, _, _ = gpe.construire([_france()], TAILLES.get, _proposer, _france())
	plaine = next(d for d in lieux if d["_id"] == gpe.PLAINE)
	par_id = {l["_id"]: l for l in liens}
	for i, (cible_fr, cible_pl) in enumerate(gpe.PASSAGES_PLAINE, start=1):
		fr, pl = par_id[f"link:france_to_plaine_europeenne_{i:02d}"]["nodes"]
		assert fr == {"lieu": gpe.FRANCE, "pos": list(cible_fr)}
		x, y = pl["pos"]
		assert pl["lieu"] == gpe.PLAINE and plaine["cells"][y][x] == 1
		assert plaine["cells"][y + 1][x] == 0  # la case au sud est déjà la France, fermée


def test_lieux_deja_en_base_relus_et_non_reproposes():
	plaine = {"_id": gpe.PLAINE, "_rev": "3-x", "type": "lieu", "image": gpe.IMAGE_PLAINE,
		"categorie": "pays", "dimensions": {"x": 88, "y": 48}, "cells": _grille(), "nav": {},
		"zone_influences": ["retouche"]}
	cites = [{"_id": c, "type": "lieu", "image": f"{c.split(':')[1]}_city.jpg",
		"dimensions": {"x": 88, "y": 48}, "cells": _grille(), "nav": {}, "lieu_parent": gpe.PLAINE}
		for c in gpe.POSITIONS_PLAINE]
	lieux, _, refus, propositions = gpe.construire([_france(), plaine] + cites, TAILLES.get,
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
