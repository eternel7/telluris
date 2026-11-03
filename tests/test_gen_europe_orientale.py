"""dev/gen_europe_orientale.py + dev/grilles_europe_orientale.py — grilles nettoyées des 12 cartes
d'Europe du Nord et de l'Est, et passages entre cartes.

Parties pures seulement : la grille d'image (Pillow) n'est pas rejouée ici. Verrouille ce qui
rendrait la carte injouable sans bruit : une graine posée sur la terre qui inonde la carte, une
bande de parchemin qui relie deux rives le long du cadre, un passage posé sur la mer.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_europe_orientale as geo_gen  # noqa: E402
from dev import grilles_europe_orientale as geo  # noqa: E402

MER = (40, 80, 140)
TERRE = (150, 130, 90)


def _image(motif):
	"""`motif` : lignes de « ~ » (mer), « . » (terre), « # » (cadre). → (couleurs, W, H, cadre)."""
	H, W = len(motif), len(motif[0])
	couleurs = [MER if c == "~" else TERRE for ligne in motif for c in ligne]
	cadre = [[c == "#" for c in ligne] for ligne in motif]
	return couleurs, W, H, cadre


def test_graine_sur_la_terre_n_inonde_rien():
	couleurs, W, H, cadre = _image(["#######", "#..~~.#", "#..~~.#", "#######"])
	assert geo.graines_invalides(couleurs, W, [(1, 1), (3, 1)], cadre) == [(1, 1)]
	eau = geo.eau_par_graines(couleurs, W, H, [(1, 1)], 40, cadre)
	assert not any(v for ligne in eau for v in ligne)


def test_mer_lue_depuis_sa_graine_sans_deborder_sur_la_terre():
	couleurs, W, H, cadre = _image(["############", "#~~~.......#", "#~~~.......#", "############"])
	eau = geo.eau_par_graines(couleurs, W, H, [(1, 1)], 40, cadre)
	assert eau[1][1] and eau[2][3] and not eau[1][6] and not eau[1][0]


def test_bande_de_parchemin_contre_le_cadre_rendue_a_la_mer():
	"""Deux cases de terre entre la mer et le cadre : sans prolongement, elles relieraient
	les deux rives en longeant le bord."""
	assert geo.CADRE_PROCHE >= 2
	couleurs, W, H, cadre = _image([
		"###################",
		"#.......~~~.......#",
		"#.......~~~.......#",
		"#.......~~~.......#",
		"#.......~~~.......#",
		"#.......~~~.......#",
		"#.......~~~.......#",
		"#.......~~~.......#",
		"###################",
	])
	couleurs = list(couleurs)
	# Les deux rangées du haut, côté mer, peintes en parchemin clair.
	for y in (1, 2):
		for x in range(8, 11):
			couleurs[y * W + x] = TERRE
	eau = geo.eau_par_graines(couleurs, W, H, [(9, 6)], 40, cadre)
	assert all(eau[y][x] for y in (1, 2) for x in range(8, 11))
	assert not eau[4][4] and not eau[4][14]


def test_grille_nettoyee_mure_la_cote_et_garde_le_cadre():
	from utils import grille_image
	couleurs, W, H, cadre = _image(["#" * 17] + ["#.......~.......#"] * 9 + ["#" * 17])
	cells = [[0 if c else 1 for c in ligne] for ligne in cadre]
	g = geo.grille_nettoyee(cells, couleurs, W, H, [(8, 5)], 40,
		grille_image.murer_barrieres, grille_image.zones)
	assert g["cells"] == cells
	assert "7,5" in g["nav"] and "9,5" in g["nav"]
	assert len(g["zones_isolees"]) == 1


def test_postes_une_case_sur_deux_le_long_de_la_ligne_la_plus_longue():
	assert geo_gen.nombre_postes(((0, 0), (20, 0)), ((0, 0), (8, 0))) == 10
	assert geo_gen.nombre_postes(((0, 0), (0, 1)), ((0, 0), (0, 1))) == 1


def test_liens_poses_sur_la_terre_et_abandonnes_sur_l_eau():
	zone_a = {(x, 0) for x in range(0, 11)}
	# Sur B, la terre s'arrête à x = 4 : au-delà, les postes tomberaient sur la mer.
	zone_b = {(x, 5) for x in range(0, 5)}
	libelles = {"lieu:a": "A", "lieu:b": "B"}
	docs, abandonnes = geo_gen.liens_frontiere("Gué", "a", ((0, 0), (10, 0)), zone_a,
		"b", ((0, 5), (10, 5)), zone_b, libelles)
	assert abandonnes and docs
	for d in docs:
		(na, nb) = d["nodes"]
		assert tuple(na["pos"]) in zone_a and tuple(nb["pos"]) in zone_b
		assert math.dist(nb["pos"], (nb["pos"][0], 5)) <= geo_gen.ECART_MAX
	assert docs[0]["_id"] == "link:a_to_b_01"
	assert docs[0]["nodes"][0]["label"] == "Gué 1 — A"
	assert len({tuple(map(tuple, (n["pos"] for n in d["nodes"]))) for d in docs}) == len(docs)


def test_specification_coherente():
	"""Chaque frontière relie deux cartes connues, ses lignes restent dans la grille (86×48 pour
	les cartes neuves, 88×48 pour celles en jeu), chaque carte neuve a ses graines et son ancre."""
	en_jeu = {"france", "plaine_europeenne", "pannonie", "roumanie"}
	for nom, a, ligne_a, b, ligne_b in geo_gen.FRONTIERES:
		for slug, ligne in ((a, ligne_a), (b, ligne_b)):
			assert slug in geo_gen.CARTES or slug in en_jeu, (nom, slug)
			w = 86 if slug in geo_gen.CARTES else 88
			assert all(0 <= x < w and 0 <= y < 48 for x, y in ligne), (nom, slug)
	assert set(geo_gen.CARTES) == set(geo.EAUX) == set(geo_gen.ANCRES)
	ids = [f"{a}_to_{b}" for _, a, _, b, _ in geo_gen.FRONTIERES]
	assert len(ids) == len(set(ids))


def test_construire_n_emet_que_le_delta():
	"""Cartes neuves absentes du dump : créées ; rejeu avec le lot importé : plus rien."""
	def carte(slug):
		W = 88 if slug in ("france", "plaine_europeenne", "pannonie", "roumanie") else 86
		return {"_id": f"lieu:{slug}", "type": "lieu", "label": slug,
			"cells": [[1] * W for _ in range(48)], "nav": {}}

	dump = [carte(s) for s in ("france", "plaine_europeenne", "pannonie", "roumanie")]
	lieux, liens, suppr, rapport = geo_gen.construire(dump, carte)
	assert len(lieux) == len(geo_gen.CARTES) and liens and not suppr
	lieux2, liens2, suppr2, _ = geo_gen.construire(dump + lieux + liens, carte)
	assert lieux2 == [] and liens2 == [] and suppr2 == []
	# Un lien de frontière en base que le lot ne produit plus part en suppression.
	perime = {"_id": "link:moscovie_to_volga_oural_99", "type": "connection", "nodes": []}
	_, _, suppr3, _ = geo_gen.construire(dump + lieux + liens + [perime], carte)
	assert suppr3 == [{"_id": perime["_id"], "_deleted": True}]
