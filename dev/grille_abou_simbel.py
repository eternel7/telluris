"""Grille DESSINÉE d'Abou Simbel (`towns/abou_simbel_capital.jpg`, 800 × 1306 px → 50 × 82
cases de 16 px), bibliothèque de `gen_villes_pays.py`.

POURQUOI À LA MAIN : la carte est une vue CAVALIÈRE — façades, faces de murs et de terrasse
dessinées en hauteur. La proposition de `gen_grille_image` y lit des murs dans chaque ombre
(la haute ville éclate en poches) et coupe le pont. Seule l'EAU y est fiable : elle est reprise
de la proposition (`cells == 5` hors de l'enceinte), tout le reste est relevé sur l'image
quadrillée, en coordonnées de case (flottants : le centre d'une case est `x + 0,5`).

LECTURE DE LA CARTE (du haut vers le bas) :
  · falaise et Grand Temple : 0, sauf la porte du temple (x 25-26) et la porte de la falaise
    gardée par deux statues (x 13) — futurs sous-lieux ;
  · esplanade au pied des quatre colosses (socles et blocs tombés à 0) ;
  · haute ville : quatre îlots de palais, puis une rangée de demeures, rues entre eux ;
  · face de la TERRASSE (bande à 0, `FACE_HAUT` → `FACE_BAS`) que seul franchit le grand
    ESCALIER (x 24-26) ;
  · basse ville : place du marché (étals à 0), nécropole à gauche (tombeaux, allées),
    quartier de maisons à droite ;
  · châtelet de la porte (deux tours, passage x 24-26), cour devant les Anubis ;
  · PONT (tablier ouvert, parapets murés par `nav` : on n'en saute pas dans le Nil), tour de
    tête de pont, route murée de la rive sud-est ;
  · hors les murs : Nil à 5, berges et désert à 0 — inatteignables à pied (la route murée
    est la seule sortie), elles feraient des zones isolées.

`nav` : parapets du pont, puis `grille_image.fermer_coins` (aucun pas diagonal à travers un
angle de maison ou de mur).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import grille_image  # noqa: E402

DIMS = {"x": 50, "y": 82}

# Contour EXTÉRIEUR de l'enceinte (tours comprises), en partant de la tour nord-ouest.
ENCEINTE = (
	(9, 15), (3, 25), (1.5, 30), (1, 39), (1, 44), (2, 46), (3, 50), (3.5, 62), (7, 63),
	(10, 67.5), (15, 69), (20, 70.5), (23.5, 71.5), (26.5, 71.5), (28.5, 62), (31, 67.5),
	(35, 68.5), (40, 66.5), (44, 63), (47, 59), (47.5, 51), (49.5, 44), (49.5, 39), (48, 30),
	(47.5, 25), (45.5, 21), (41.5, 15.5))

# Intérieur de la cité, de l'esplanade au mur intérieur qui ferme la basse ville.
INTERIEUR = (
	(11.5, 18), (38.5, 18), (41.5, 21.5), (43.5, 25.5), (44.5, 30), (45, 35), (45, 51),
	(41, 55), (8, 55), (5, 51), (4.5, 45), (4.5, 35), (5.5, 30), (7, 25), (9, 21))

# Face de la terrasse : le haut (bord de la haute ville) et le pied (sol de la basse ville),
# polylignes en x croissant. Entre les deux : la face du mur, à 0.
FACE_HAUT = ((4.5, 44.5), (10, 42.5), (15, 39.7), (20, 38.7), (23.1, 37.5), (27.2, 37.5),
	(31.2, 38.7), (34.4, 40.3), (39, 42.2), (45.6, 43.4))
FACE_BAS = ((4.5, 46.5), (10, 45.5), (15, 43), (20, 41.5), (23.1, 41.5), (27.2, 41.5),
	(31.2, 40.5), (34.4, 42), (39, 44), (45.6, 45))

# Bâti et obstacles : rectangles de cases (x0, y0, x1, y1) INCLUS, posés à 0.
BATI = (
	# Esplanade : socles des colosses, blocs tombés, obélisque de l'avenue.
	(17, 18, 23, 18), (27, 18, 33, 18), (18, 19, 21, 19), (24, 21, 24, 22),
	# Haute ville, rangée des palais.
	(11, 21, 16, 26), (19, 22, 23, 29), (27, 22, 33, 30), (36, 22, 43, 29),
	# Pavillon à coupole et demeures de l'ouest.
	(7, 27, 11, 33), (5, 35, 9, 38), (10, 37, 11, 38), (5, 40, 11, 43),
	# Haute ville, rangée des demeures.
	(15, 31, 16, 32), (13, 33, 18, 37), (20, 31, 24, 36), (19, 35, 21, 37), (27, 32, 30, 36),
	(32, 32, 35, 37),
	# Maisons de l'est.
	(37, 30, 44, 35), (38, 38, 44, 42),
	# Étals du marché.
	(18, 42, 18, 42), (21, 42, 21, 42), (23, 44, 23, 44), (28, 43, 28, 43), (30, 41, 30, 41),
	(32, 42, 32, 42), (34, 43, 34, 43),
	# Basse ville est.
	(35, 45, 38, 49), (39, 45, 42, 49), (43, 45, 44, 48), (36, 51, 41, 53),
	# Nécropole : tout le quartier, les allées sont rouvertes par OUVERTURES.
	(5, 46, 16, 54),
	# Châtelet : tours et corps de porte.
	(17, 46, 21, 59), (29, 46, 33, 59), (22, 48, 28, 56))

# Rouvert à 1 APRÈS le bâti et la face de la terrasse.
OUVERTURES = (
	(25, 12, 26, 17),          # porte du Grand Temple
	(13, 18, 13, 18),          # porte de la falaise, entre ses deux gardiens
	(24, 37, 26, 41),          # grand escalier
	(24, 48, 26, 56),          # passage de la porte
	(6, 46, 16, 47),           # allée de la nécropole
	(9, 48, 9, 54), (13, 48, 13, 54), (10, 53, 12, 53),  # allées entre les tombeaux
	(22, 57, 28, 59),          # cour devant la porte, entre les Anubis
)

# Tablier du pont, de la cour de la porte à la tête de pont.
PONT = ((26, 60), (28.5, 60), (29, 62.5), (33.75, 66.25), (37.8, 69.4), (41.6, 71.9), (42, 73),
	(39.5, 74), (35.6, 71.25), (31.25, 68), (28.1, 65), (26, 62.5))

# Route murée de la rive sud-est (la sortie de la cité).
ROUTE = ((39.5, 72), (42, 72), (45, 75.5), (50, 77), (50, 82), (44, 82), (39.5, 76))

# Tours de la tête de pont et étal de la route.
BATI_RIVE = ((36, 74, 39, 81), (42, 69, 44, 75), (46, 75, 47, 76))

# Arches et piles du pont, sous le tablier : 0 (l'image les lit comme de la berge).
ARCHES = ((26, 63), (28, 65), (31.25, 68), (35.6, 71.25), (36, 74), (36, 80), (33, 80), (30, 76),
	(27, 73), (26, 71.5))


def dans_polygone(px, py, poly) -> bool:
	"""Point dans le polygone (règle pair-impair)."""
	dedans = False
	n = len(poly)
	for i in range(n):
		(x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
		if (y1 > py) != (y2 > py) and px < x1 + (py - y1) * (x2 - x1) / (y2 - y1):
			dedans = not dedans
	return dedans


def interpoler(polyligne, x) -> float:
	"""y de la polyligne (x croissant) en `x`, prolongée à plat hors de ses bornes."""
	if x <= polyligne[0][0]:
		return polyligne[0][1]
	for (x1, y1), (x2, y2) in zip(polyligne, polyligne[1:]):
		if x <= x2:
			return y1 + (y2 - y1) * (x - x1) / (x2 - x1)
	return polyligne[-1][1]


def _cases_polygone(poly):
	return {(x, y) for y in range(DIMS["y"]) for x in range(DIMS["x"])
		if dans_polygone(x + 0.5, y + 0.5, poly)}


def _cases_rects(rects):
	return {(x, y) for x0, y0, x1, y1 in rects for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)}


def cases_face():
	"""Cases de la face de la terrasse (centre strictement entre haut et pied)."""
	return {(x, y) for y in range(DIMS["y"]) for x in range(DIMS["x"])
		if interpoler(FACE_HAUT, x + 0.5) < y + 0.5 < interpoler(FACE_BAS, x + 0.5)}


def grille(cells_proposees):
	"""`(cells, nav)` d'Abou Simbel ; `cells_proposees` = la proposition de `gen_grille_image`
	sur l'image (seule son eau, `5`, est reprise, hors de l'enceinte)."""
	W, H = DIMS["x"], DIMS["y"]
	if len(cells_proposees) != H or any(len(ligne) != W for ligne in cells_proposees):
		raise ValueError(f"grille d'Abou Simbel relevée sur {W} × {H} cases : l'image a changé de taille")
	enceinte = _cases_polygone(ENCEINTE)
	pont = _cases_polygone(PONT)
	route = _cases_polygone(ROUTE) - _cases_rects(BATI_RIVE)
	cells = [[0] * W for _ in range(H)]
	for y in range(H):
		for x in range(W):
			if (x, y) in enceinte:
				continue
			if cells_proposees[y][x] == grille_image.TERRAIN_EAU:
				cells[y][x] = grille_image.TERRAIN_EAU
	for x, y in _cases_rects(BATI_RIVE) | _cases_polygone(ARCHES):
		cells[y][x] = 0
	ouvert = (_cases_polygone(INTERIEUR) - _cases_rects(BATI) - cases_face()) | _cases_rects(OUVERTURES)
	for x, y in ouvert | pont | route:
		cells[y][x] = grille_image.TERRAIN_LIBRE

	nav = {}
	# Parapets : du tablier, on ne passe qu'à la cour de la porte ou à la route.
	accueil = pont | route | _cases_rects(OUVERTURES[-1:])
	for x, y in sorted(pont):
		for dx in (-1, 0, 1):
			for dy in (-1, 0, 1):
				nx, ny = x + dx, y + dy
				if (dx or dy) and 0 <= nx < W and 0 <= ny < H and (nx, ny) not in accueil \
						and cells[ny][nx] != 0:
					grille_image.interdire(nav, x, y, dx, dy)
	grille_image.fermer_coins(cells, nav)
	return cells, nav
