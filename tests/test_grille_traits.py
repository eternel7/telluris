"""`utils/grille_traits` — la grille d'une carte à l'encre, lue par ses traits.

1. **Pixel de rue** : ni encre ni pierre grise ; seules les grandes régions comptent.
2. **Un trait noir est une limite** : deux cases que les pixels de rue ne relient pas dans
   leur fenêtre reçoivent un mur nav.
3. **L'anneau de l'enceinte isole l'intérieur** : aucune case intérieure ne touche le dehors.
4. **`gen_grille_traits.relire`** ne relit que l'intérieur de l'enceinte et ouvre les passages.
"""

from dev import gen_grille_traits
from utils import grille_image, grille_traits as gt


def test_pixel_de_rue_ni_encre_ni_pierre():
	assert gt.pixel_de_rue(191, 175, 145)            # pavé de la place de Calais (mesuré)
	assert not gt.pixel_de_rue(40, 35, 30)           # trait d'encre
	assert not gt.pixel_de_rue(143, 130, 112)        # pierre du mur nord (saturation 0,12)


def test_masque_rues_garde_les_grandes_regions():
	# 6×2 px : une région de 4 px à gauche, une de 2 px à droite, séparées par un trait.
	libre = [1, 1, 0, 0, 1, 1,
			 1, 1, 0, 0, 0, 0]
	assert list(gt.masque_rues(libre, 6, 2, aire=3)) == [1, 1, 0, 0, 0, 0,
														  1, 1, 0, 0, 0, 0]


def test_bornes_d_une_image_non_multiple():
	assert gt.bornes(10, 3) == [0, 3, 6, 10]


def _rue_deux_cases(trait):
	"""Deux cases de 4 px côte à côte (8×4 px), rue partout sauf la colonne 4 si `trait`."""
	return bytearray(0 if trait and x == 4 else 1 for y in range(4) for x in range(8))


def test_un_trait_noir_separe_deux_cases():
	bx, by = gt.bornes(8, 2), gt.bornes(4, 1)
	assert gt.relies(_rue_deux_cases(False), 8, bx, by, (0, 0), (1, 0))
	assert not gt.relies(_rue_deux_cases(True), 8, bx, by, (0, 0), (1, 0))


def test_grille_traits_pose_le_mur_sur_le_trait():
	cases = {(0, 0), (1, 0)}
	cells, nav = [[0, 0]], {}
	assert gt.grille_traits(cells, nav, _rue_deux_cases(True), 8, 4, cases, pixels_case=4) == 1
	assert cells == [[1, 1]] and not grille_image.nav_autorise(nav, 0, 0, 1, 0)
	cells, nav = [[0, 0]], {}
	assert gt.grille_traits(cells, nav, _rue_deux_cases(False), 8, 4, cases, pixels_case=4) == 0
	assert grille_image.nav_autorise(nav, 0, 0, 1, 0)


def test_l_eau_reste_de_l_eau():
	cells, nav = [[5, 0]], {}
	gt.grille_traits(cells, nav, _rue_deux_cases(False), 8, 4, {(0, 0), (1, 0)}, pixels_case=4)
	assert cells == [[5, 1]]


def test_l_anneau_de_l_enceinte_isole_l_interieur():
	anneau, interieur = gt.anneau_et_interieur(((0, 0), (5, 0), (5, 5), (0, 5)), 6, 6)
	assert interieur == {(x, y) for x in range(1, 4) for y in range(1, 4)}
	for (x, y) in interieur:
		for dx in (-1, 0, 1):
			for dy in (-1, 0, 1):
				assert (x + dx, y + dy) in anneau | interieur


def test_relire_ne_touche_que_l_interieur_et_ouvre_les_passages():
	# Carte 5×5 cases de 2 px, rue partout : le dehors (colonne 4, hors enceinte) garde sa
	# valeur, l'anneau ferme, l'intérieur passe à 1, le passage rouvre (0, 0).
	doc = {"_id": "lieu:test", "_rev": "1-a", "cells": [[3] * 5 for _ in range(5)], "nav": {}}
	masque = (bytearray([1] * 100), 10, 10)
	spec = {"enceinte": [[0, 0], [4, 0], [4, 4], [0, 4]], "passages": [[[0, 0]]]}
	sortant, rapport = gen_grille_traits.relire(doc, masque, spec)
	cells = sortant["cells"]
	assert "_rev" not in sortant and doc["cells"][0][0] == 3      # le doc relu n'est pas muté
	assert [cells[y][4] for y in range(5)] == [3] * 5               # dehors intact
	assert cells[1][1] == cells[2][2] == 1 and cells[0][1] == 0 and cells[0][0] == 1
	# Anneau = bord du carré 4×4 de l'enceinte, fermé AVANT que le passage ne rouvre (0, 0).
	assert rapport["anneau"] == len([1 for y in range(4) for x in range(4)
									 if x in (0, 3) or y in (0, 3)])
