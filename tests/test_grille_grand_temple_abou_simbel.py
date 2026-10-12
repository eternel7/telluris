"""dev/grille_grand_temple_abou_simbel.py — grille dessinée de l'intérieur du Grand Temple :
une seule zone praticable, chaque salle jointe depuis l'entrée."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import grille_grand_temple_abou_simbel as gt  # noqa: E402
from utils import grille_image  # noqa: E402


def test_dimensions():
	cells, _ = gt.grille()
	assert len(cells) == gt.DIMS["y"] and all(len(l) == gt.DIMS["x"] for l in cells)


def test_chaque_salle_jointe_depuis_l_entree():
	cells, nav = gt.grille()
	zone, tailles = grille_image.zones(cells, nav)
	ex, ey = gt.ENTREE
	assert cells[ey][ex] == 1 and len(tailles) == 1
	for nom, poly in gt.SALLES.items():
		libres = [(x, y) for x, y in gt.cases_salle(poly) if cells[y][x] == 1]
		assert libres and all(zone[y][x] == zone[ey][ex] for x, y in libres), nom


def test_estrade_des_trones_et_bassins():
	cells, _ = gt.grille()
	x0, y0, x1, y1 = gt.OBSTACLES[-1]
	assert all(cells[y][x] == 0 for y in range(y0, y1 + 1) for x in range(x0, x1 + 1))
	assert sum(v == grille_image.TERRAIN_EAU for l in cells for v in l) > 0
