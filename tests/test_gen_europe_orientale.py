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


def test_georeferencement_retrouve_ses_reperes():
	"""La projection passe par chaque repère (résidus interpolés) et reste continue entre eux."""
	from dev import georeferencement_cartes as georef
	for lieu, reperes in georef.REPERES.items():
		for nom, ((lon, lat), (x, y)) in reperes.items():
			px, py = georef.vers_case(lieu, lon, lat)
			assert math.dist((px, py), (x, y)) < 0.01, (lieu, nom, (px, py), (x, y))
			# À un dixième de degré : à moins de 2 cases.
			assert math.dist(georef.vers_case(lieu, lon + 0.1, lat), (x, y)) < 2, (lieu, nom)


def test_paire_georeferencee_au_format_de_calage_cartes():
	from dev import calage_cartes
	from dev import georeferencement_cartes as georef
	reperes = georef.paire("lieu:roumanie", "lieu:balkans", (88, 48), (86, 48))
	assert len(reperes) == 16
	s, _, _ = calage_cartes.ajuster(reperes)
	assert 0.5 < s < 2.5


def test_specification_coherente():
	"""Chaque paire relie deux cartes géoréférencées et ancrées ; une paire au plus par couple."""
	from dev import georeferencement_cartes as georef
	from dev import gen_afrique as af
	for cfg in (geo_gen, af):
		vus = set()
		for foi, voisine, _ in cfg.PAIRES_CALEES:
			for s in (foi, voisine):
				assert f"lieu:{s}" in georef.REPERES and s in cfg.ANCRES, (cfg.__name__, s)
			assert frozenset((foi, voisine)) not in vus
			vus.add(frozenset((foi, voisine)))
		assert set(cfg.CARTES) == set(cfg.EAUX)
	# L'Égypte n'est jamais recalée : elle ne figure qu'en carte qui fait foi.
	assert all(v != "egypte" for _, v, _ in af.PAIRES_CALEES)


def test_bord_et_lignes_face():
	"""Deux cartes bord à bord : la frontière est le bord tourné vers l'autre, réduit à la portion
	en face de sa terre ; les passages vont d'un bout à l'autre à la même fraction."""
	ligne_a = [(x, 0) for x in range(10)]
	ligne_b = [(x, 5) for x in range(0, 20, 4)]
	libelles = {"lieu:a": "A", "lieu:b": "B"}
	docs, _ = geo_gen.liens_proportionnels("link:a_to_b", "lieu:a", ligne_a, "lieu:b", ligne_b,
		[f"P {k}" for k in range(1, 6)], libelles)
	assert [d["nodes"][0]["pos"] for d in docs] == [[0, 0], [2, 0], [4, 0], [6, 0], [8, 0]]
	assert docs[0]["nodes"][1]["pos"] == [0, 5] and docs[-1]["nodes"][1]["pos"][0] >= 12
	assert docs[0]["nodes"][0]["label"] == "P 1 — A"
	zone = {(x, y) for x in range(5) for y in range(5)} | {(5, 2)}
	# Le bord droit : la case (5, 2) qui avance, et les cases à `BORD_PROFONDEUR` d'elle.
	bord = geo_gen._bord(zone, "droite", lambda c: True)
	assert (5, 2) in bord and all(x >= 5 - geo_gen.BORD_PROFONDEUR for x, _ in bord)
	assert geo_gen.extremite({(0, 0), (1, 0), (9, 0)}) == (9, 0)


def test_afrique_aksoum_passe_sur_l_abyssinie():
	from dev import gen_afrique as af
	anciens = {f"link:afrique_du_nord_to_aksoum_{n}": {
		"_id": f"link:afrique_du_nord_to_aksoum_{n}", "type": "connection",
		"nodes": [{"lieu": "lieu:afrique_du_nord", "pos": [85, 45]},
			{"lieu": "lieu:aksoum", "pos": [i, 20], "label": f"Aksoum — {n}"}]}
		for i, n in enumerate(af.SORTIES_AKSOUM)}
	par_id = dict(anciens)
	par_id["lieu:aksoum"] = {"_id": "lieu:aksoum", "_rev": "2-x", "type": "lieu", "label": "Aksoum",
		"lieu_parent": "lieu:afrique_du_nord"}
	zone = {(x, y) for x in range(20, 45) for y in range(5, 25)}
	docs, suppr, _ = af.extras(par_id, {}, {"abyssinie": zone})
	par = {d["_id"]: d for d in docs}
	assert par["lieu:aksoum"]["lieu_parent"] == "lieu:abyssinie" and "_rev" not in par["lieu:aksoum"]
	for i, n in enumerate(af.SORTIES_AKSOUM):
		lien = par[f"link:abyssinie_to_aksoum_{n}"]
		assert lien["nodes"][0]["lieu"] == "lieu:abyssinie" and tuple(lien["nodes"][0]["pos"]) in zone
		assert lien["nodes"][1]["pos"] == [i, 20]
	assert {s["_id"] for s in suppr} == set(anciens)
	# Ses anciens liens ne protègent aucune case de l'Afrique du Nord au recalage.
	assert all(i.startswith(af.LIENS_REMPLACES) for i in anciens)
