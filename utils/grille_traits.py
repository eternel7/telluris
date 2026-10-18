"""Grille d'une carte dessinée À L'ENCRE, lue par ses TRAITS (pur, sans Pillow).

POURQUOI : `grille_image` classe chaque case par sa couleur moyenne ; sur une cité dessinée
à l'encre, un toit clair passe pour une rue et une ruelle ombrée pour un toit. Ici une rue
est ce qui reste CLAIR et BEIGE entre les traits noirs, lu au PIXEL :

  · pixel de rue (`pixel_de_rue`) = ni encre (gris ≥ `SEUIL_ENCRE`) ni pierre grise
    (saturation HLS ≥ `SATURATION_RUE`) ;
  · on ne garde que ses régions 4-connexes d'au moins `AIRE_RUE` pixels (`masque_rues`) —
    une face de toit coupée par ses hachures est plus petite ;
  · case praticable si elle porte `PIXELS_CASE` pixels de rue ; entre deux cases praticables
    voisines, mur `nav` si aucun chemin de pixels de rue ne les relie DANS leur fenêtre
    (`relies`) : UN TRAIT NOIR EST UNE LIMITE (`grille_traits`).

Optionnel : une ENCEINTE (polygone en cases posé sur la crête du mur). Son anneau de bord
(`anneau_et_interieur`) est le rempart — une case intérieure n'a que des voisines
intérieures, aucun pas n'en sort — et seule la partie intérieure est relue.

Réglages mesurés sur `calais_city.jpg` (1408×768, 16 px la case) : traits ~2 px gris < 60 ;
rue grise 150-190, saturée 0,19-0,27 ; pierre des murs et du château 0,12-0,14 ; herbe 0,19.

Utilisé par `dev/gen_grille_traits.py` (toute ville) et `dev/gen_calais_remparts.py`.
"""

from utils import grille_image

SEUIL_ENCRE = 80
SATURATION_RUE = 0.14
AIRE_RUE = 300          # px
PIXELS_CASE = 10        # px de rue pour une case de 16×16


def pixel_de_rue(r, g, b, seuil=SEUIL_ENCRE, saturation=SATURATION_RUE) -> bool:
	"""Ni encre (gris ITU-R 601, celui de Pillow `L`, ≥ `seuil`) ni pierre grise
	(saturation HLS ≥ `saturation`)."""
	if (r * 299 + g * 587 + b * 114) // 1000 < seuil:
		return False
	mx, mn = max(r, g, b), min(r, g, b)
	if mx == mn:
		return False
	somme = mx + mn
	return (mx - mn) / (somme if somme < 255 else 510 - somme) >= saturation


def masque_rues(libre, largeur, hauteur, aire=AIRE_RUE) -> bytearray:
	"""Pixels `libre` (suite de booléens, ligne par ligne) dont la région 4-connexe fait au
	moins `aire` pixels : 1, sinon 0."""
	total = largeur * hauteur
	rue = bytearray(total)
	vu = bytearray(total)
	for depart in range(total):
		if not libre[depart] or vu[depart]:
			continue
		vu[depart] = 1
		region, pile = [], [depart]
		while pile:
			i = pile.pop()
			region.append(i)
			x = i % largeur
			for j in (i - largeur, i + largeur, i - 1 if x else -1, i + 1 if x + 1 < largeur else -1):
				if 0 <= j < total and libre[j] and not vu[j]:
					vu[j] = 1
					pile.append(j)
		if len(region) >= aire:
			for i in region:
				rue[i] = 1
	return rue


def bornes(pixels, cases) -> list:
	"""Limites en pixels des `cases` colonnes (ou lignes) : la case i couvre
	[b[i], b[i + 1]). Une image dont la taille n'est pas un multiple tombe juste quand même."""
	return [i * pixels // cases for i in range(cases + 1)]


def relies(rue, largeur, bx, by, a, b) -> bool:
	"""Des pixels de rue relient-ils les cases voisines `a` et `b` SANS sortir de leur
	fenêtre (2 cases, ou le carré 2×2 d'un pas diagonal) ? Un trait noir les sépare sinon."""
	x0, x1 = bx[min(a[0], b[0])], bx[max(a[0], b[0]) + 1]
	y0, y1 = by[min(a[1], b[1])], by[max(a[1], b[1]) + 1]
	bx0, bx1, by0, by1 = bx[b[0]], bx[b[0] + 1], by[b[1]], by[b[1] + 1]
	pile = [(px, py) for py in range(by[a[1]], by[a[1] + 1])
			for px in range(bx[a[0]], bx[a[0] + 1]) if rue[py * largeur + px]]
	vus = set(pile)
	while pile:
		px, py = pile.pop()
		if bx0 <= px < bx1 and by0 <= py < by1:
			return True
		for q in ((px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)):
			if x0 <= q[0] < x1 and y0 <= q[1] < y1 and q not in vus and rue[q[1] * largeur + q[0]]:
				vus.add(q)
				pile.append(q)
	return False


def grille_traits(cells, nav, rue, largeur, hauteur, cases, pixels_case=None) -> int:
	"""Mute `cells`/`nav` sur `cases` (ensemble de (x, y)) : case à 1 si elle porte assez de
	pixels de rue (`pixels_case`, défaut `PIXELS_CASE` ramené à l'aire de la case), sinon 0 —
	l'eau (5) reste ; ses murs nav repartent de zéro, un mur est posé entre deux cases
	praticables que `relies` ne joint pas. Rend le nombre de murs posés."""
	cols, rows = len(cells[0]), len(cells)
	bx, by = bornes(largeur, cols), bornes(hauteur, rows)
	if pixels_case is None:
		pixels_case = max(1, round(PIXELS_CASE * (largeur / cols) * (hauteur / rows) / 256))
	for (x, y) in cases:
		nav.pop(f"{x},{y}", None)
		if cells[y][x] == grille_image.TERRAIN_EAU:
			continue
		compte = sum(rue[py * largeur + px] for py in range(by[y], by[y + 1])
					 for px in range(bx[x], bx[x + 1]))
		cells[y][x] = 1 if compte >= pixels_case else 0
	poses = 0
	for (x, y) in sorted(cases):
		if cells[y][x] != 1:
			continue
		for dx, dy in ((1, 0), (0, 1), (1, 1), (-1, 1)):
			v = (x + dx, y + dy)
			if v in cases and cells[v[1]][v[0]] == 1 and not relies(rue, largeur, bx, by, (x, y), v):
				grille_image.interdire(nav, x, y, dx, dy)
				poses += 1
	return poses


# ── Enceinte ───────────────────────────────────────────────────────────────────────────────
def dans_polygone(poly, x, y) -> bool:
	"""Le CENTRE de la case (x, y) est-il dans `poly` ? (parité des croisements)"""
	px, py = x + .5, y + .5
	poly = [tuple(p) for p in poly]
	dedans = False
	for (ax, ay), (bx, by) in zip(poly, poly[1:] + poly[:1]):
		if (ay > py) != (by > py) and px < ax + (py - ay) * (bx - ax) / (by - ay):
			dedans = not dedans
	return dedans


def anneau_et_interieur(poly, cols, rows):
	"""(anneau, intérieur) des cases de l'enceinte : l'anneau a une voisine (8) hors du
	polygone — c'est le rempart —, l'intérieur n'a que des voisines dedans."""
	dedans = {(x, y) for y in range(rows) for x in range(cols) if dans_polygone(poly, x, y)}
	interieur = {(x, y) for (x, y) in dedans
				 if all((x + dx, y + dy) in dedans for dx in (-1, 0, 1) for dy in (-1, 0, 1))}
	return dedans - interieur, interieur


def fermer_anneau(cells, nav, anneau) -> int:
	"""Mute : chaque case de l'anneau à 0 (l'eau reste), ses murs nav retirés (inutiles sur
	une case fermée). Rend le nombre de cases fermées."""
	fermees = 0
	for x, y in anneau:
		nav.pop(f"{x},{y}", None)
		if cells[y][x] not in (0, grille_image.TERRAIN_EAU):
			cells[y][x] = 0
			fermees += 1
	return fermees


def ouvrir_passages(cells, nav, passages) -> None:
	"""Mute : chaque passage (suite de cases voisines) à 1, murs nav levés sur ses pas,
	orthogonaux ou diagonaux, dans les deux sens."""
	for chemin in passages:
		chemin = [tuple(c) for c in chemin]
		for x, y in chemin:
			cells[y][x] = 1
		for a, b in zip(chemin, chemin[1:]):
			for p, q in ((a, b), (b, a)):
				bit, _op = grille_image._BIT[(q[0] - p[0], q[1] - p[1])]
				cle = f"{p[0]},{p[1]}"
				reste = int(nav.get(cle, 0) or 0) & ~bit
				if reste:
					nav[cle] = reste
				else:
					nav.pop(cle, None)
