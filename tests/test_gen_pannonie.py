"""dev/gen_pannonie.py — la Pannonie entre l'Italie et la Roumanie : frontières et liens.

Partie pure seulement (`proposer_fn` et `eau_fn` injectés). Verrouille ce qu'un import PUT
COMPLET rendrait silencieux : un faux rivage hors de l'Adriatique murerait la plaine, une mer
qui fuit laisserait marcher sur l'eau, une frontière ouverte laisserait passer sans connexion.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_pannonie as gpa  # noqa: E402
from dev.gen_plaine_europeenne import cases_frontiere  # noqa: E402

TAILLES = {gpa.IMAGE_PANNONIE: (1408, 768)}


def _grille(cols=88, rows=48, valeur=1):
	return [[valeur] * cols for _ in range(rows)]


def _italie():
	return {"_id": gpa.ITALIE, "label": "Italie", "dimensions": {"x": 88, "y": 48},
		"cells": _grille(), "nav": {}}


def _docs():
	return [{"_id": gpa.ROUMANIE, "_rev": "1-x", "type": "lieu", "label": "Roumanie",
		"dimensions": {"x": 88, "y": 48}, "cells": _grille(), "nav": {"40,40": 3}},
		{"_id": gpa.BUCAREST, "_rev": "402-x", "type": "lieu", "label": "Bucarest",
		"dimensions": {"x": 88, "y": 48}, "cells": _grille(), "nav": {}, "intro": {"titre": "t"}}]


# Un mur dans le cadre de l'Adriatique, un faux rivage dans la plaine hongroise.
MUR_ADRIATIQUE, FAUX_RIVAGE = "40,40", "50,15"
EAU = (40, 45)


def _proposer(doc, profil):
	return {"cells": _grille(), "nav": {MUR_ADRIATIQUE: 1, FAUX_RIVAGE: 16}, "rapport": {}}


def _eau(doc):
	eau = [[False] * 88 for _ in range(48)]
	eau[EAU[1]][EAU[0]] = True
	eau[15][50] = True  # la plaine hongroise lue comme de l'eau : hors du cadre, ignorée
	return eau


def _construire(docs=None):
	return gpa.construire(docs or _docs(), TAILLES.get, _proposer, _eau, _italie())


def test_pannonie_creee_faux_rivages_retires_adriatique_fermee():
	lieux, _, refus, propositions, _ = _construire()
	assert refus == [] and set(propositions) == {gpa.PANNONIE}
	pannonie = next(d for d in lieux if d["_id"] == gpa.PANNONIE)
	assert pannonie["label"] == "Pannonie" and pannonie["categorie"] == "pays"
	assert pannonie["nav"] == {MUR_ADRIATIQUE: 1}
	assert pannonie["cells"][EAU[1]][EAU[0]] == 0 and pannonie["cells"][15][50] == 1


def test_frontieres_de_la_pannonie_et_de_la_roumanie():
	lieux, _, _, _, _ = _construire()
	par_id = {d["_id"]: d for d in lieux}
	pannonie, roumanie = par_id[gpa.PANNONIE], par_id[gpa.ROUMANIE]
	for bandes, sens in ((gpa.FRONTIERE_PANNONIE_ITALIE, "ouest"),
			(gpa.FRONTIERE_PANNONIE_ROUMANIE, "est")):
		for x, y in cases_frontiere(bandes, sens, 88, 48):
			assert pannonie["cells"][y][x] == 0
	for bandes, sens in ((gpa.FRONTIERE_ROUMANIE_PANNONIE, "ouest"),
			(gpa.FRONTIERE_ROUMANIE_SERBIE, "sud")):
		for x, y in cases_frontiere(bandes, sens, 88, 48):
			assert roumanie["cells"][y][x] == 0
	assert "_rev" not in roumanie and roumanie["nav"] == {"40,40": 3}


def test_liens_italie_pannonie_roumanie_sur_les_frontieres():
	_, liens, refus, _, _ = _construire()
	assert refus == []
	par_id = {l["_id"]: l for l in liens}
	for prefixe, a, b, passages in (
			("link:italie_to_pannonie", gpa.ITALIE, gpa.PANNONIE, gpa.PASSAGES_ITALIE),
			("link:pannonie_to_roumanie", gpa.PANNONIE, gpa.ROUMANIE, gpa.PASSAGES_ROUMANIE)):
		assert sum(1 for i in par_id if i.startswith(prefixe + "_")) == len(passages)
		for i, nom in enumerate(passages, start=1):
			na, nb = par_id[f"{prefixe}_{i:02d}"]["nodes"]
			assert na["lieu"] == a and na["label"].startswith(f"{nom} — ")
			assert nb["lieu"] == b and nb["label"].startswith(f"{nom} — ")
	# Côté Italie, la frontière terrestre seule : jamais la côte adriatique.
	_, _, y_min, y_max = gpa.TERRE_ITALIE
	assert all(y_min <= l["nodes"][0]["pos"][1] <= y_max for i, l in par_id.items()
		if i.startswith("link:italie_to_pannonie_"))
	# Pannonie ↔ Roumanie : jamais au sud du Danube.
	assert all(n["pos"][1] <= gpa.DANUBE[3] for i, l in par_id.items()
		if i.startswith("link:pannonie_to_roumanie_") for n in l["nodes"])


def test_bucarest_posee_sur_la_roumanie():
	lieux, liens, refus, _, _ = _construire()
	assert refus == []
	bucarest = next(d for d in lieux if d["_id"] == gpa.BUCAREST)
	assert bucarest["lieu_parent"] == gpa.ROUMANIE and bucarest["intro"] == {"titre": "t"}
	assert "_rev" not in bucarest
	sorties = [l for l in liens if l["_id"].startswith("link:roumanie_to_bucarest_")]
	assert len(sorties) == len(gpa.SORTIES_BUCAREST)
	assert sorties[0]["nodes"][0]["pos"] == list(gpa.POSITION_BUCAREST)
	assert len({tuple(l["nodes"][0]["pos"]) for l in sorties}) == len(sorties)
	for l, (nom, (cible, _)) in zip(sorties, gpa.SORTIES_BUCAREST.items()):
		assert l["nodes"][1] == {"lieu": gpa.BUCAREST, "pos": list(cible),
			"label": gpa.libelle_sortie("Bucarest", nom)}


def test_sortie_de_bucarest_dans_l_exterieur_vise():
	docs = _docs()
	cells = docs[1]["cells"]
	# Un rempart plein en x 66 : la cible « sud » (64, 44) tombe à l'OUEST, son ancre (68, 34) à
	# l'EST. Sans l'ancre, la plus grande zone (l'ouest) garderait la cible telle quelle.
	mur = 66
	for y in range(48):
		cells[y][mur] = 0
	_, liens, refus, _, _ = _construire(docs)
	assert refus == []
	vus = set()
	for l in liens:
		if l["_id"].startswith("link:roumanie_to_bucarest_"):
			nom = l["_id"].rsplit("_to_bucarest_", 1)[1]
			x = l["nodes"][1]["pos"][0]
			assert (x > mur) == (gpa.SORTIES_BUCAREST[nom][1][0] > mur)
			vus.add(nom)
	assert vus == set(gpa.SORTIES_BUCAREST)


def test_pannonie_deja_en_base_relue_sans_reproposer():
	relue = {"_id": gpa.PANNONIE, "_rev": "2-y", "type": "lieu", "image": gpa.IMAGE_PANNONIE,
		"dimensions": {"x": 88, "y": 48}, "cells": _grille(), "nav": {"1,1": 255}}

	def interdit(*_):
		raise AssertionError("grille reproposée alors que la Pannonie est en base")

	lieux, _, refus, propositions, _ = gpa.construire(_docs() + [relue], TAILLES.get, interdit,
		interdit, _italie())
	assert refus == [] and propositions == {}
	pannonie = next(d for d in lieux if d["_id"] == gpa.PANNONIE)
	assert pannonie["nav"] == {"1,1": 255} and "_rev" not in pannonie


def test_roumanie_absente_refusee():
	assert gpa.construire([], TAILLES.get, _proposer, _eau, _italie())[2]
