"""Grilles NETTOYÉES des 12 cartes de pays d'Europe orientale et du Nord (pur).

POURQUOI : le profil `pays` (`grille_image.masque_eau`) lit l'eau à la FROIDEUR des couleurs
(vert + bleu contre rouge). Sur ces cartes, les forêts vert sombre, les neiges, la Volga élargie
et les marais du Pripiat passent pour de la mer : la côte murée traversait la Suède, coupait la
chaîne du Caucase, les Alpes, l'Oural. Ici l'eau se lit par CROISSANCE DE RÉGION depuis des
GRAINES posées à la main dans chaque mer et chaque grand lac (`EAUX`) : une case rejoint l'eau
de sa graine quand sa couleur reste à `tolerance` de celle de la graine. La mer d'une carte est
uniforme ; une forêt, une neige, une rive n'ont pas sa couleur.

Règles de l'Auteur gardées (profil `pays`) : `cells` à 1 sauf le cadre décoratif (lu comme le
profil le lit), la côte SEULE murée en `nav` (`murer_barrieres`, mêmes diagonales), les fleuves
jamais — la Volga, large de plusieurs cases sur `volga_oural`, est un fleuve : non semée.
Une terre de moins de `ILE_MIN` cases cernée d'eau (navire, monstre marin, banquise dessinés)
redevient de l'eau.
"""

ILE_MIN = 6
# Bleu moins rouge, plancher d'une case d'eau : la mer grise de la Baltique est à ≈ 0, le
# parchemin et la steppe à -40 et moins, une forêt sombre à -30.
BLEU_MIN = -8
# Distance au cadre (cases) en deçà de laquelle l'eau est prolongée jusqu'à lui.
CADRE_PROCHE = 3
VOISINS4 = ((1, 0), (-1, 0), (0, 1), (0, -1))

# Carte → {"graines": ((x, y), …), "tolerance": distance RGB}. Une carte sans graine (Moscovie,
# Germanie du Sud : ni mer ni grand lac) n'a aucun mur.
EAUX = {
	"scandinavie_meridionale": {"tolerance": 30, "graines": (
		(12, 20), (14, 38), (35, 34), (60, 30), (60, 8), (75, 21), (48, 42), (43, 25), (46, 29))},
	"laponie": {"tolerance": 40, "graines": (
		(30, 5), (70, 8), (8, 20), (34, 39), (80, 24), (70, 33))},
	"germanie_du_sud": {"tolerance": 30, "graines": ()},
	"baltique_orientale": {"tolerance": 34, "graines": (
		(10, 25), (5, 20), (20, 6), (45, 6), (18, 16), (72, 6), (53, 16))},
	"pologne_ruthenie": {"tolerance": 34, "graines": ((8, 4), (24, 4))},
	"balkans": {"tolerance": 40, "graines": (
		(10, 30), (50, 25), (60, 38), (30, 40), (72, 13), (75, 6))},
	"steppe_pontique": {"tolerance": 40, "graines": ((25, 38), (60, 30), (60, 39), (40, 41), (45, 40), (55, 41))},
	"moscovie": {"tolerance": 30, "graines": ()},
	"grand_nord": {"tolerance": 40, "graines": ((40, 8), (70, 10), (8, 22), (40, 18))},
	"volga_oural": {"tolerance": 30, "graines": ()},
	"basse_volga": {"tolerance": 40, "graines": ((70, 38), (80, 32))},
	"caucase": {"tolerance": 40, "graines": ((10, 20), (25, 30), (8, 28), (75, 10), (80, 25))},
}


def _rgb(c):
	return c[0], c[1], c[2]


def _dist(a, b):
	return sum((u - v) ** 2 for u, v in zip(_rgb(a), _rgb(b))) ** 0.5


def _reference(couleurs, W, H, x, y):
	"""Couleur moyenne des cases BLEUTÉES du 3×3 autour de la graine (bruit de la peinture
	lissé, sans la rive voisine)."""
	somme, n = [0.0, 0.0, 0.0], 0
	for dy in (-1, 0, 1):
		for dx in (-1, 0, 1):
			nx, ny = x + dx, y + dy
			if 0 <= nx < W and 0 <= ny < H and bleutee(couleurs[ny * W + nx]):
				for i, v in enumerate(_rgb(couleurs[ny * W + nx])):
					somme[i] += v
				n += 1
	return tuple(v / n for v in somme)


def bleutee(c):
	"""Une case d'eau n'est jamais rougeâtre : parchemin, steppe, forêt (bleu bas) exclus d'office.
	Garde-fou de la croissance — une graine posée sur la terre n'inonde rien."""
	r, _, b = _rgb(c)
	return b - r >= BLEU_MIN


def graines_invalides(couleurs, W, graines, cadre):
	"""Graines dans le cadre ou sur une case non bleutée : à déplacer."""
	return [(x, y) for x, y in graines if cadre[y][x] or not bleutee(couleurs[y * W + x])]


def eau_par_graines(couleurs, W, H, graines, tolerance, cadre):
	"""Masque [y][x] de l'eau : croissance 4-connexe depuis chaque graine (case bleutée, couleur
	à `tolerance` de la couleur de SA graine), jamais dans le `cadre` ; puis les terres de moins
	de `ILE_MIN` cases cernées d'eau, loin du bord, rendues à l'eau."""
	eau = [[False] * W for _ in range(H)]
	for gx, gy in graines:
		if cadre[gy][gx] or not bleutee(couleurs[gy * W + gx]):
			continue
		ref = _reference(couleurs, W, H, gx, gy)
		pile = [(gx, gy)]
		while pile:
			x, y = pile.pop()
			c = couleurs[y * W + x]
			if eau[y][x] or cadre[y][x] or not bleutee(c) or _dist(c, ref) > tolerance:
				continue
			eau[y][x] = True
			for dx, dy in VOISINS4:
				nx, ny = x + dx, y + dy
				if 0 <= nx < W and 0 <= ny < H and not eau[ny][nx]:
					pile.append((nx, ny))
	# Bande de parchemin entre la mer et le cadre (bord déchiré, filet clair) : la terre qu'elle
	# ferait relierait deux rives en longeant le bord. L'eau qui arrive à `CADRE_PROCHE` cases
	# du cadre, en ligne droite, est prolongée jusqu'à lui.
	prolonger = set()
	for y in range(H):
		for x in range(W):
			if not eau[y][x]:
				continue
			for dx, dy in VOISINS4:
				chemin = []
				for k in range(1, CADRE_PROCHE + 2):
					nx, ny = x + k * dx, y + k * dy
					if not (0 <= nx < W and 0 <= ny < H) or cadre[ny][nx]:
						prolonger.update(chemin)
						break
					if eau[ny][nx]:
						break
					chemin.append((nx, ny))
	for x, y in prolonger:
		eau[y][x] = True
	vu = [[False] * W for _ in range(H)]
	for y0 in range(H):
		for x0 in range(W):
			if eau[y0][x0] or cadre[y0][x0] or vu[y0][x0]:
				continue
			membres, pile, bord, contre_eau = [], [(x0, y0)], False, True
			vu[y0][x0] = True
			while pile:
				x, y = pile.pop()
				membres.append((x, y))
				for dx, dy in VOISINS4:
					nx, ny = x + dx, y + dy
					if not (0 <= nx < W and 0 <= ny < H):
						bord = True
						continue
					if cadre[ny][nx]:
						bord = True
					elif not eau[ny][nx] and not vu[ny][nx]:
						vu[ny][nx] = True
						pile.append((nx, ny))
			if len(membres) < ILE_MIN and not bord and contre_eau:
				for x, y in membres:
					eau[y][x] = True
	return eau


def grille_nettoyee(cells_cadre, couleurs, W, H, graines, tolerance, murer, zones_fn):
	"""`{cells, nav, eau, zones_isolees}` : `cells` = celles du profil (cadre à 0, reste à 1),
	nav = la côte de l'eau semée seule. `murer` = `grille_image.murer_barrieres`, `zones_fn` =
	`grille_image.zones` (injectés : module pur, sans Pillow)."""
	cadre = [[v == 0 for v in ligne] for ligne in cells_cadre]
	eau = eau_par_graines(couleurs, W, H, graines, tolerance, cadre)
	nav = {}
	murer(nav, eau, lambda x, y: not eau[y][x] and not cadre[y][x])
	terre = [[1 if not eau[y][x] and not cadre[y][x] else 0 for x in range(W)] for y in range(H)]
	zone, tailles = zones_fn(terre, nav)
	isolees = []
	if tailles:
		principale = max(range(len(tailles)), key=lambda z: (tailles[z], -z))
		vues = {principale}
		for y in range(H):
			for x in range(W):
				z = zone[y][x]
				if z != -1 and z not in vues:
					vues.add(z)
					isolees.append({"case": [x, y], "taille": tailles[z]})
	cells = [list(ligne) for ligne in cells_cadre]
	return {"cells": cells, "nav": nav, "eau": eau, "zones_isolees": isolees}
