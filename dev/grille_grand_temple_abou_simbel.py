"""Grille DESSINÉE de l'intérieur du Grand Temple d'Abou Simbel
(`towns/grand_temple_abou_simbel.jpg`, 1408 × 768 px → 88 × 48 cases de 16 px), bibliothèque
de `gen_villes_pays.py`.

POURQUOI À LA MAIN : la carte est une COUPE — salles éclairées reliées par des galeries et des
escaliers dans la roche sombre. La proposition de `gen_grille_image` (profil catacombes) lit
les salles mais perd les galeries, trop sombres : une vingtaine d'îlots. Tout est relevé sur
l'image quadrillée, en coordonnées de case (flottants : le centre d'une case est `x + 0,5`).

LECTURE DE LA CARTE :
  · en HAUT, la salle hypostyle — l'ENTRÉE du temple (`ENTREE`, sa porte du fond) ; trois
    descentes sous ses colonnes ;
  · à gauche, la galerie des tombeaux royaux, le tombeau du bord, puis le dédale des chambres
    (cinq rangs, escaliers entre eux) et la chambre aux sarcophages du bas ;
  · au centre bas, la SALLE DU TRÔNE (estrade des deux trônes à 0), ouverte à gauche sur le
    dédale et à droite sur la galerie basse ;
  · à droite, la chapelle haute, la grotte aux cristaux, le sanctuaire et ses chambres, la
    galerie basse des momies, le sanctuaire du bas ; deux bassins (5).

`nav` : `grille_image.fermer_coins` (aucun pas diagonal à travers un angle de roche).
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev.grille_abou_simbel import dans_polygone  # noqa: E402
from utils import grille_image  # noqa: E402

DIMS = {"x": 88, "y": 48}

# Case du fond de la salle hypostyle : là où l'on entre depuis l'esplanade.
ENTREE = (44, 9)

# Salles : polygones de sol.
SALLES = {
	"salle_hypostyle": ((31, 11.5), (37, 11), (42, 8.5), (46, 8.5), (51, 11), (57, 11.5),
		(57.5, 14.5), (30.5, 14.5)),
	"galerie_des_tombeaux": ((2, 19.5), (8, 18), (14, 16), (20, 14), (28, 13), (29.5, 15.5),
		(22, 16.5), (16, 18.5), (10, 20.5), (4, 22.5), (2, 22.5)),
	"tombeau_du_bord": ((2, 26.5), (10, 26), (10.5, 29.5), (2.5, 30)),
	"chambres_rang_1": ((20, 21.5), (43, 21.5), (43, 24.5), (20, 24.5)),
	"chambres_rang_2": ((15, 26), (35, 26), (35, 28.5), (15, 28.5)),
	"chambres_rang_3": ((10, 30.5), (30, 30.5), (30, 34), (10, 34)),
	"chambres_rang_4": ((14, 36.5), (26, 36.5), (26, 40), (14, 40)),
	"chambres_rang_5": ((18, 42.5), (25, 42.5), (25, 46.5), (18, 46.5)),
	"chambre_aux_sarcophages": ((1.5, 40), (12, 40), (12, 46), (1.5, 46)),
	"trone_parvis": ((33, 39), (56, 39), (56, 48), (33, 48)),
	"trone_bas_cote_ouest": ((33, 33), (39, 33), (39, 39), (33, 39)),
	"trone_bas_cote_est": ((51, 33), (56, 33), (56, 39), (51, 39)),
	"chapelle_haute": ((61, 10), (69, 10), (69, 13), (61, 13)),
	"grotte_aux_cristaux": ((73, 10.5), (80, 10.5), (80, 12.5), (73, 12.5)),
	"sanctuaire_haut": ((79, 19.5), (83, 19.5), (83, 22), (79, 22)),
	"chambre_a_la_lampe": ((70.5, 16), (75, 16), (75, 18), (70.5, 18)),
	"galerie_haute": ((43, 24), (66, 24), (66, 26.5), (43, 26.5)),
	"chambre_a_la_colonne": ((55, 26.5), (60.5, 26.5), (60.5, 30), (55, 30)),
	"grotte_des_pretres": ((57.5, 30), (69.5, 30), (69.5, 33.5), (57.5, 33.5)),
	"chambre_au_pupitre": ((58, 33.5), (64, 33.5), (64, 36.5), (58, 36.5)),
	"chambre_a_l_arche": ((71.5, 31), (78, 31), (78, 34), (71.5, 34)),
	"chambre_au_coffre": ((78.5, 33), (84.5, 33), (84.5, 35.5), (78.5, 35.5)),
	"tombeau_haut_est": ((77, 26), (86, 26), (86, 30), (77, 30)),
	"grotte_aux_arches": ((57, 38.5), (65, 38.5), (65, 41), (57, 41)),
	"galerie_des_momies": ((70.5, 42), (78, 42), (78, 45), (70.5, 45)),
	"sanctuaire_bas": ((78, 41), (85, 41), (85, 45.5), (78, 45.5)),
}

# Galeries et escaliers : polylignes, demi-largeur en cases.
GALERIES = {
	"hypostyle_vers_tombeaux": (((37, 14.5), (33, 16.5), (29, 15)), 0.9),
	"hypostyle_vers_chambres": (((40, 14.5), (40, 18), (41, 22)), 0.9),
	"hypostyle_vers_l_est": (((44, 14), (44, 16.5), (50, 17.5), (58, 17.5), (62, 15.5),
		(66, 14.5), (70.5, 14.5)), 0.9),
	"chapelle_escalier_ouest": (((62, 12.5), (61.5, 14.5), (62, 15.5)), 0.8),
	"chapelle_escalier_est": (((68.5, 12.5), (70.5, 14.5)), 0.8),
	"cristaux_escalier": (((73.5, 12), (72.5, 14.5), (70.5, 14.5)), 0.8),
	"vers_le_sanctuaire_haut": (((70.5, 14.5), (73, 15), (76, 15.5), (77, 17.5), (78, 20),
		(79.5, 21)), 0.8),
	"vers_la_chambre_a_la_lampe": (((73, 15), (72.5, 16.5)), 0.8),
	"descente_est": (((63, 16), (63.5, 20), (64, 24.5)), 0.8),
	"escalier_du_bassin": (((50, 18), (52, 21), (54, 24.5)), 0.8),
	"sanctuaire_vers_tombeau_est": (((80, 21.5), (77, 23), (75, 25.5), (78, 27)), 0.8),
	"galerie_haute_vers_tombeau_est": (((65.5, 25.5), (70, 26.5), (74, 26), (78, 27)), 0.8),
	"tombeaux_vers_chambres": (((12, 20.5), (14, 24), (16, 26.5)), 0.8),
	"tombeaux_vers_tombeau_du_bord": (((4, 22), (5, 26.5)), 0.8),
	"chambres_rang_1_vers_2": (((32, 24), (32.5, 26.5)), 0.8),
	"chambres_rang_2_vers_3": (((21.5, 28), (21.5, 30.5)), 0.8),
	"rampe_du_tombeau_du_bord": (((5.5, 29.5), (5.5, 33), (10, 35.5), (11, 33.5)), 0.8),
	"rampe_vers_les_sarcophages": (((8, 35), (8, 40.5)), 0.8),
	"chambres_vers_le_trone": (((29, 33), (30, 36), (33.5, 37.5)), 0.8),
	"chambres_rang_4_vers_le_trone": (((25.5, 38), (28, 38), (33.5, 38)), 0.8),
	"chambres_rang_4_vers_5": (((26, 39.5), (28, 43), (24.5, 44)), 0.8),
	"chambres_rang_4_vers_sarcophages": (((15, 39.5), (13, 42.5), (11.5, 43)), 0.8),
	"trone_vers_l_est": (((55.5, 40), (60, 40), (71, 40.5), (73, 40), (75, 42.5), (78, 43)), 0.9),
	"escalier_des_pretres": (((65, 40), (65.5, 36), (64, 33)), 0.8),
	"escalier_a_la_torche": (((71, 40), (71, 36.5), (71, 34), (73, 32.5)), 0.8),
	"grand_escalier_est": (((73, 40), (76.5, 37.5), (80, 35)), 0.8),
	"grotte_vers_colonne": (((59, 30.5), (59.5, 27)), 0.8),
	"grotte_vers_arche": (((69, 31.5), (72, 32)), 0.8),
}

# Obstacles posés à 0 après les salles : colonnes de la salle hypostyle, estrade des trônes.
OBSTACLES = ((37, 12, 38, 12), (50, 12, 51, 12), (40, 10, 40, 10), (48, 10, 48, 10),
	(40, 36, 49, 38))

# Bassins (5), posés après tout le reste.
BASSINS = (((45, 20), (50, 20), (50, 22), (45, 22)), ((60, 42), (70, 42), (70, 45), (60, 45)))


def _distance_segment(px, py, a, b) -> float:
	(ax, ay), (bx, by) = a, b
	dx, dy = bx - ax, by - ay
	t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
	return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def cases_salle(poly):
	return {(x, y) for y in range(DIMS["y"]) for x in range(DIMS["x"])
		if dans_polygone(x + 0.5, y + 0.5, poly)}


def cases_galerie(points, demi_largeur):
	return {(x, y) for y in range(DIMS["y"]) for x in range(DIMS["x"])
		if any(_distance_segment(x + 0.5, y + 0.5, a, b) <= demi_largeur
			for a, b in zip(points, points[1:]))}


def grille():
	"""`(cells, nav)` de l'intérieur du Grand Temple."""
	W, H = DIMS["x"], DIMS["y"]
	cells = [[0] * W for _ in range(H)]
	ouvert = set()
	for poly in SALLES.values():
		ouvert |= cases_salle(poly)
	for points, demi in GALERIES.values():
		ouvert |= cases_galerie(points, demi)
	for x, y in ouvert:
		cells[y][x] = grille_image.TERRAIN_LIBRE
	for x0, y0, x1, y1 in OBSTACLES:
		for y in range(y0, y1 + 1):
			for x in range(x0, x1 + 1):
				cells[y][x] = 0
	for poly in BASSINS:
		for x, y in cases_salle(poly):
			cells[y][x] = grille_image.TERRAIN_EAU
	nav = {}
	grille_image.fermer_coins(cells, nav)
	return cells, nav
