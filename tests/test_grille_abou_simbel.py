"""dev/grille_abou_simbel.py — grille dessinée d'Abou Simbel : une seule zone praticable, la
terrasse franchie par le seul escalier, le pont muré par ses parapets, l'eau reprise hors les
murs seulement."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import grille_abou_simbel as gas  # noqa: E402
from utils import grille_image  # noqa: E402

W, H = gas.DIMS["x"], gas.DIMS["y"]

# Points relevés sur l'image : porte du temple, esplanade, avenue de la haute ville, marché,
# nécropole, basse ville est, cour de la porte, tablier du pont, route de la rive (sortie).
POINTS = {"temple": (25, 13), "esplanade": (25, 19), "haute_ville": (25, 30), "marche": (25, 44),
	"necropole": (9, 50), "basse_ville_est": (40, 50), "cour": (25, 58), "pont": (30, 64),
	"route": (48, 80)}


def _grille(valeur=grille_image.TERRAIN_EAU):
	return gas.grille([[valeur] * W for _ in range(H)])


def test_une_seule_zone_qui_porte_tous_les_quartiers():
	cells, nav = _grille()
	zone, tailles = grille_image.zones(cells, nav)
	assert len(tailles) == 1
	assert all(cells[y][x] == 1 and zone[y][x] == 0 for x, y in POINTS.values())


def test_la_terrasse_ne_se_franchit_que_par_l_escalier():
	cells, nav = _grille()
	(x0, y0, x1, y1) = next(o for o in gas.OUVERTURES if o == (24, 37, 26, 41))
	for y in range(y0, y1 + 1):
		for x in range(x0, x1 + 1):
			cells[y][x] = 0
	zone, _ = grille_image.zones(cells, nav)
	(hx, hy), (mx, my) = POINTS["haute_ville"], POINTS["marche"]
	assert zone[hy][hx] != zone[my][mx]


def test_parapets_du_pont():
	"""Aucun pas du tablier vers l'eau ; le tablier rejoint la cour et la route."""
	cells, nav = _grille()
	pont = gas._cases_polygone(gas.PONT)
	for x, y in pont:
		for dx in (-1, 0, 1):
			for dy in (-1, 0, 1):
				nx, ny = x + dx, y + dy
				if (dx or dy) and 0 <= nx < W and 0 <= ny < H and cells[ny][nx] == grille_image.TERRAIN_EAU:
					assert not grille_image.nav_autorise(nav, x, y, dx, dy), (x, y, dx, dy)


def test_eau_reprise_hors_les_murs_seulement():
	cells, _ = _grille()
	enceinte = gas._cases_polygone(gas.ENCEINTE)
	assert all(cells[y][x] != grille_image.TERRAIN_EAU for x, y in enceinte)
	assert any(v == grille_image.TERRAIN_EAU for ligne in cells for v in ligne)
	# Sans eau proposée, rien d'autre que le relevé : 0 et 1.
	sec, _ = _grille(grille_image.TERRAIN_LIBRE)
	assert {v for ligne in sec for v in ligne} == {0, 1}


def test_taille_d_image_differente_refusee():
	with pytest.raises(ValueError):
		gas.grille([[1] * 88 for _ in range(48)])
