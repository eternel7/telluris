"""Grille d'une cité lue par MATIÈRES (pur, sans dépendance) — 0, 1 et 5 d'abord, nav ensuite.

POURQUOI : la lecture par couleur moyenne de case (`grille_image`) confond la pierre claire d'un
rempart avec une rue claire et terne. Son tracé des rues ouvre alors le chemin de ronde, la
moitié éclairée des tours, les flancs rocheux d'une colline — et l'enceinte n'est fermée que
par des murs nav. Ici, chaque SOUS-CASE (quelques pixels) reçoit une matière, et la case se
décide sur la part de chacune. Règle de l'Auteur (22/10/2026) :
  1. d'abord les cases : pierre, toits, roche → 0 ; herbe, terre → 1 ; eau → 5 ;
  2. une rivière coupée par une teinte proche de la sienne est une rivière : on la recoud ;
  3. les nav ne CORRIGENT qu'un rempart trop fin pour faire une case pleine, entre le dedans
     et le dehors — jamais un mur devant une case à 0, jamais au milieu d'un pré.
  Le chemin de ronde est pour les soldats : jamais un passage.

Matières (couleur Lab moyenne de la sous-case + écart-type de sa clarté, la « texture ») :
  vegetation · eau · pierre (claire et texturée : joints des moellons) · terre (claire, jaune,
  lisse : rue, terre battue) · roche (couleur de terre mais texturée : falaise, éboulis) ·
  sombre (toits, ombres, colombages, encre) · autre.
  ⚠️ L'ombre bleutée d'une tour ou d'un toit d'ardoise a la couleur de l'eau : une tache d'eau
  n'est gardée que si la VÉGÉTATION en borde la plus grande part (`eau_bord_vegetal`).

Seuils dans `REGLES_MATIERES`, calibrés sur towns/camelot_capital.jpg (illustration peinte à
dominante chaude) ; la clarté L va de 0 à 100, a et b sont les axes vert-rouge et bleu-jaune.
"""

LAB_REF = (0.9505, 1.0, 1.089)
_LIN = [((c / 255 + 0.055) / 1.055) ** 2.4 if c / 255 > 0.04045 else c / 255 / 12.92
	for c in range(256)]

VEGETATION, EAU, PIERRE, TERRE, ROCHE, SOMBRE, AUTRE = (
	"vegetation", "eau", "pierre", "terre", "roche", "sombre", "autre")
MATIERES = (VEGETATION, EAU, PIERRE, TERRE, ROCHE, SOMBRE, AUTRE)
PRATICABLES = (VEGETATION, TERRE)
PLEINES = (PIERRE, ROCHE, SOMBRE)

REGLES_MATIERES = {
	"sous_case": 4,              # px par côté de sous-case
	"veg_a_max": -3.0,           # a* < : vert
	"veg_b_min": 12.0,           # b* > : pas un gris bleuté
	"eau_b_max": 12.0,           # b* < : bleu ou gris froid
	"eau_l_min": 35.0,           # plus clair que l'encre
	"sombre_l_max": 45.0,        # toits, ombres, colombages
	"pierre_l_min": 62.0,        # pierre éclairée…
	"texture_min": 4.5,          # …texturée (joints) ; en dessous, surface lisse
	"terre_l_min": 52.0,
	"terre_b_min": 22.0,
	"terre_a_min": -3.0,
	"eau_bord_vegetal": 0.55,    # part du pourtour d'une tache d'eau bordée de végétation
	"eau_taille_min": 6,         # sous-cases : en dessous, un reflet
	# Case : parts des matières parmi ses sous-cases.
	"case_eau": 0.40,
	"case_praticable": 0.55,
	"case_pleine_max": 0.30,
	# Corrections d'une grille proposée (`corriger`).
	"case_pierre": 0.30,         # part de pierre qui ferme une case (rempart, tour)
	"case_toit": 0.75,           # part de sombre…
	"toit_ecart_max": 7.0,       # …UNIE : un toit ; bigarrée (> ce seuil) : une foule
	"case_franche": 0.85,        # herbe + terre qui rouvre une case hors de l'enceinte…
	"case_franche_pleine_max": 0.05,  # …sans pierre, roche ni sombre
	# Cité à enceinte déclarée (`proposer_cite`).
	"dedans_uni_ecart": 7.0,     # au dedans, case UNIE (écart <)…
	"dedans_uni_sol": 0.5,       # …d'herbe, terre ou roche, hors rue tracée : talus, falaise
	"tour_part": 0.6,            # pierre + ombre + autre d'une case du dehors collée au rempart
	"marge_pierre": 6.0,         # coût de creuser une case de pierre (`relier_zones`)
	"marge_toit": 4.0,           # … un toit
	# Rivière : trou maximal recousu (cases) et écart de teinte toléré sur le trou.
	"riviere_trou_max": 4,
	"riviere_ecart_b": 10.0,
}


def lab(rgb):
	"""(L, a, b) d'un pixel sRGB."""
	r, g, b = (_LIN[int(v)] for v in rgb[:3])
	x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / LAB_REF[0]
	y = (0.2126 * r + 0.7152 * g + 0.0722 * b) / LAB_REF[1]
	z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / LAB_REF[2]

	def f(t):
		return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
	fx, fy, fz = f(x), f(y), f(z)
	return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def sous_cases(pixels, largeur, hauteur, k):
	"""Grille de sous-cases k×k px : [(L, a, b, texture)] par ligne. `pixels` = liste plate
	de (r, g, b) ligne à ligne (Pillow `getdata`). Le bord qui ne fait pas k px est ignoré."""
	sc_l, sc_h = largeur // k, hauteur // k
	cache = {}
	grille = []
	for sy in range(sc_h):
		ligne = []
		for sx in range(sc_l):
			sl = sa = sb = sl2 = 0.0
			for dy in range(k):
				base = (sy * k + dy) * largeur + sx * k
				for dx in range(k):
					px = pixels[base + dx]
					v = cache.get(px)
					if v is None:
						v = cache[px] = lab(px)
					sl += v[0]
					sa += v[1]
					sb += v[2]
					sl2 += v[0] * v[0]
			n = k * k
			moy = sl / n
			ligne.append((moy, sa / n, sb / n, max(0.0, sl2 / n - moy * moy) ** 0.5))
		grille.append(ligne)
	return grille


def classer(sc, regles=None) -> str:
	"""Matière d'une sous-case (L, a, b, texture)."""
	r = {**REGLES_MATIERES, **(regles or {})}
	L, a, b, tex = sc
	if a < r["veg_a_max"] and b > r["veg_b_min"]:
		return VEGETATION
	if b < r["eau_b_max"] and L > r["eau_l_min"]:
		return EAU
	if L < r["sombre_l_max"]:
		return SOMBRE
	terreuse = L >= r["terre_l_min"] and b >= r["terre_b_min"] and a > r["terre_a_min"]
	if terreuse:
		return ROCHE if tex > r["texture_min"] else TERRE
	if L >= r["pierre_l_min"] and tex > r["texture_min"]:
		return PIERRE
	return AUTRE


def _composantes(masque):
	"""Composantes 4-connexes des cellules vraies d'une matrice booléenne."""
	h, w = len(masque), len(masque[0])
	vues, sortie = set(), []
	for y in range(h):
		for x in range(w):
			if masque[y][x] and (x, y) not in vues:
				pile, comp = [(x, y)], []
				vues.add((x, y))
				while pile:
					cx, cy = pile.pop()
					comp.append((cx, cy))
					for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
						if 0 <= nx < w and 0 <= ny < h and masque[ny][nx] and (nx, ny) not in vues:
							vues.add((nx, ny))
							pile.append((nx, ny))
				sortie.append(comp)
	return sortie


def matieres(grille_sc, regles=None):
	"""Matrice des matières des sous-cases, eau VALIDÉE par son bord végétal."""
	r = {**REGLES_MATIERES, **(regles or {})}
	mat = [[classer(sc, r) for sc in ligne] for ligne in grille_sc]
	h, w = len(mat), len(mat[0])
	for comp in _composantes([[m == EAU for m in ligne] for ligne in mat]):
		dedans = set(comp)
		bord = [mat[ny][nx] for x, y in comp
			for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
			if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in dedans]
		vegetal = sum(1 for m in bord if m == VEGETATION) / max(1, len(bord))
		if len(comp) < r["eau_taille_min"] or vegetal < r["eau_bord_vegetal"]:
			for x, y in comp:
				mat[y][x] = SOMBRE
	return mat


def parts_par_case(mat, cols, rows):
	"""{matière: part} de chaque case : la grille de sous-cases est répartie sur cols×rows."""
	h, w = len(mat), len(mat[0])
	sortie = []
	for y in range(rows):
		ligne = []
		y0, y1 = y * h // rows, max(y * h // rows + 1, (y + 1) * h // rows)
		for x in range(cols):
			x0, x1 = x * w // cols, max(x * w // cols + 1, (x + 1) * w // cols)
			compte = {}
			for sy in range(y0, y1):
				for sx in range(x0, x1):
					m = mat[sy][sx]
					compte[m] = compte.get(m, 0) + 1
			n = sum(compte.values())
			ligne.append({m: c / n for m, c in compte.items()})
		sortie.append(ligne)
	return sortie


def lecture(grille_sc, cols, rows, regles=None):
	"""Ce que dit l'image de chaque case : `{parts, ecart, b}` — parts des matières, écart-type
	de la clarté ENTRE ses sous-cases (un toit est uni, une place noire de monde est bigarrée),
	teinte b* moyenne (pour juger un trou de rivière)."""
	mat = matieres(grille_sc, regles)
	parts = parts_par_case(mat, cols, rows)
	h, w = len(grille_sc), len(grille_sc[0])
	sortie = []
	for y in range(rows):
		ligne = []
		y0, y1 = y * h // rows, max(y * h // rows + 1, (y + 1) * h // rows)
		for x in range(cols):
			x0, x1 = x * w // cols, max(x * w // cols + 1, (x + 1) * w // cols)
			ls = [grille_sc[sy][sx][0] for sy in range(y0, y1) for sx in range(x0, x1)]
			bs = [grille_sc[sy][sx][2] for sy in range(y0, y1) for sx in range(x0, x1)]
			moy = sum(ls) / len(ls)
			ligne.append({"parts": parts[y][x], "b": sum(bs) / len(bs),
				"ecart": (sum((v - moy) ** 2 for v in ls) / len(ls)) ** 0.5})
		sortie.append(ligne)
	return sortie


def corriger(cells, lect, masque=None, regles=None) -> dict:
	"""Corrige une grille proposée (`grille_image.proposer`, après le tracé des rues et AVANT
	la fermeture de l'enceinte) par ce que disent les matières. Mute `cells` ; renvoie les
	comptes. Le tracé des rues reste la source des passages entre les maisons (une place noire
	de monde ne se lit pas à la couleur) ; les matières ne font que :
	- poser l'eau (5) là où elle est, et retirer le 5 là où il n'y en a pas ;
	- fermer (0) la PIERRE (rempart, tour, chemin de ronde : réservé aux soldats) ;
	- fermer (0) un TOIT : case sombre et UNIE (`toit_ecart_max`) ;
	- rouvrir (1) la terre franche et l'herbe pure, HORS de l'enceinte et de ses abords
	  (bourg, prés) — jamais au dedans, où le rempart doit tenir."""
	r = {**REGLES_MATIERES, **(regles or {})}
	rows, cols = len(cells), len(cells[0])

	def pres_enceinte(x, y):
		return masque and any(0 <= x + dx < cols and 0 <= y + dy < rows and masque[y + dy][x + dx]
			for dx in (-1, 0, 1) for dy in (-1, 0, 1))
	comptes = {"eau": 0, "pierre": 0, "toit": 0, "rouvertes": 0}
	for y in range(rows):
		for x in range(cols):
			c = lect[y][x]
			p = c["parts"]
			eau = p.get(EAU, 0)
			praticable = sum(p.get(m, 0) for m in PRATICABLES)
			if eau >= r["case_eau"]:
				comptes["eau"] += cells[y][x] != 5
				cells[y][x] = 5
				continue
			if cells[y][x] == 5:
				cells[y][x] = 1 if praticable >= r["case_praticable"] else 0
			if cells[y][x] == 1 and p.get(PIERRE, 0) >= r["case_pierre"]:
				cells[y][x] = 0
				comptes["pierre"] += 1
			elif cells[y][x] == 1 and p.get(SOMBRE, 0) >= r["case_toit"] and c["ecart"] <= r["toit_ecart_max"]:
				cells[y][x] = 0
				comptes["toit"] += 1
			elif (cells[y][x] == 0 and praticable >= r["case_franche"]
					and sum(p.get(m, 0) for m in PLEINES) <= r["case_franche_pleine_max"]
					and not pres_enceinte(x, y)):
				cells[y][x] = 1
				comptes["rouvertes"] += 1
	return comptes


def cases(parts, regles=None):
	"""0 / 1 / 5 de chaque case d'après la part de ses matières."""
	r = {**REGLES_MATIERES, **(regles or {})}
	sortie = []
	for ligne in parts:
		out = []
		for p in ligne:
			eau = p.get(EAU, 0)
			praticable = sum(p.get(m, 0) for m in PRATICABLES)
			pleine = sum(p.get(m, 0) for m in PLEINES)
			if eau >= r["case_eau"]:
				out.append(5)
			elif praticable >= r["case_praticable"] and pleine <= r["case_pleine_max"]:
				out.append(1)
			else:
				out.append(0)
		sortie.append(out)
	return sortie


def b_moyen_par_case(grille_sc, cols, rows):
	"""b* moyen de chaque case (teinte bleu-jaune), pour juger un trou de rivière."""
	h, w = len(grille_sc), len(grille_sc[0])
	sortie = []
	for y in range(rows):
		ligne = []
		y0, y1 = y * h // rows, max(y * h // rows + 1, (y + 1) * h // rows)
		for x in range(cols):
			x0, x1 = x * w // cols, max(x * w // cols + 1, (x + 1) * w // cols)
			vals = [grille_sc[sy][sx][2] for sy in range(y0, y1) for sx in range(x0, x1)]
			ligne.append(sum(vals) / len(vals))
		sortie.append(ligne)
	return sortie


def _ligne(a, b):
	"""Cases d'un segment (Bresenham), extrémités comprises."""
	(x0, y0), (x1, y1) = a, b
	dx, dy = abs(x1 - x0), -abs(y1 - y0)
	sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
	err, out = dx + dy, []
	while True:
		out.append((x0, y0))
		if (x0, y0) == (x1, y1):
			return out
		e2 = 2 * err
		if e2 >= dy:
			err += dy
			x0 += sx
		if e2 <= dx:
			err += dx
			y0 += sy


def recoudre_rivieres(cells, b_case, regles=None) -> list:
	"""Recoud deux étendues d'eau séparées par un trou court dont la teinte reste proche de
	celle de l'eau (Auteur : « les nuances de couleur sont faibles entre le point d'arrêt et le
	point de recommencement, c'est sûrement qu'en réalité il y a vraiment une rivière »).
	Mute `cells` ; renvoie les cases passées à 5."""
	r = {**REGLES_MATIERES, **(regles or {})}
	rows, cols = len(cells), len(cells[0])
	comps = _composantes([[v == 5 for v in ligne] for ligne in cells])
	if len(comps) < 2:
		return []
	b_eau = sum(b_case[y][x] for comp in comps for x, y in comp) / sum(len(c) for c in comps)
	trou_max = r["riviere_trou_max"]
	recousues = []
	for i in range(len(comps)):
		for j in range(i + 1, len(comps)):
			meilleur = None
			for a in comps[i]:
				for b in comps[j]:
					d = max(abs(a[0] - b[0]), abs(a[1] - b[1]))
					if d <= trou_max + 1 and (meilleur is None or d < meilleur[0]):
						meilleur = (d, a, b)
			if meilleur is None:
				continue
			trou = [c for c in _ligne(meilleur[1], meilleur[2]) if cells[c[1]][c[0]] != 5]
			if trou and all(abs(b_case[y][x] - b_eau) <= r["riviere_ecart_b"] for x, y in trou):
				for x, y in trou:
					cells[y][x] = 5
				recousues += trou
	return recousues


def poser_ponts(cells, parts) -> list:
	"""Un pont est une case non praticable, sans pierre, qui a de l'eau sur deux côtés opposés
	et de la terre ferme sur les deux autres : elle redevient praticable. Renvoie les cases."""
	rows, cols = len(cells), len(cells[0])

	def v(x, y):
		return cells[y][x] if 0 <= x < cols and 0 <= y < rows else None
	ponts = []
	for y in range(rows):
		for x in range(cols):
			if cells[y][x] != 0 or parts[y][x].get(PIERRE, 0) > 0.2:
				continue
			for (ax, ay), (bx, by) in (((0, -1), (0, 1)), ((-1, 0), (1, 0)),
					((-1, -1), (1, 1)), ((1, -1), (-1, 1))):
				eau = v(x + ax, y + ay) == 5 and v(x + bx, y + by) == 5
				# Terre ferme dans l'axe perpendiculaire.
				px, py = -ay, ax
				qx, qy = ay, -ax
				terre = v(x + px, y + py) == 1 or v(x + qx, y + qy) == 1
				if eau and terre:
					ponts.append((x, y))
					break
	for x, y in ponts:
		cells[y][x] = 1
	return ponts


# ── Cité à enceinte DÉCLARÉE ────────────────────────────────────────────────────
# Le polygone de l'enceinte (cases, sur la CRÊTE du mur, comme `grille_traits`) est la seule
# donnée qu'on ne devine pas : la fermeture du bâti (`grille_image.detecter_enceinte`) avale
# les faubourgs collés au mur. Tout le reste se calcule.

def polygone_cases(poly) -> set:
	"""Cases du contour fermé d'un polygone (segments de Bresenham)."""
	cases_ = set()
	for i, a in enumerate(poly):
		cases_.update(_ligne(tuple(a), tuple(poly[(i + 1) % len(poly)])))
	return cases_


def dedans_polygone(poly, cols, rows) -> list:
	"""[y][x] vrai si le CENTRE de la case est dans le polygone (règle pair-impair)."""
	pts = [(x + 0.5, y + 0.5) for x, y in poly]
	sortie = []
	for y in range(rows):
		ligne = []
		for x in range(cols):
			px, py, dedans = x + 0.5, y + 0.5, False
			for i, (x1, y1) in enumerate(pts):
				x2, y2 = pts[(i + 1) % len(pts)]
				if (y1 > py) != (y2 > py) and px < (x2 - x1) * (py - y1) / (y2 - y1) + x1:
					dedans = not dedans
			ligne.append(dedans)
		sortie.append(ligne)
	return sortie


_VOISINS8 = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]


def _voisine_de(x, y, ensemble, cols, rows) -> bool:
	return any((x + dx, y + dy) in ensemble for dx, dy in _VOISINS8
		if 0 <= x + dx < cols and 0 <= y + dy < rows)


def marges(lect, regles=None) -> list:
	"""Coût de creuser chaque case pour `grille_image.relier_zones` : la pierre et les toits
	coûtent cher, une rue animée presque rien."""
	r = {**REGLES_MATIERES, **(regles or {})}
	sortie = []
	for ligne in lect:
		out = []
		for c in ligne:
			p = c["parts"]
			if p.get(PIERRE, 0) >= r["case_pierre"]:
				out.append(r["marge_pierre"])
			elif p.get(SOMBRE, 0) >= r["case_toit"] and c["ecart"] <= r["toit_ecart_max"]:
				out.append(r["marge_toit"])
			else:
				out.append(0.0)
		sortie.append(out)
	return sortie


def proposer_cite(cells, rues, lect, enceinte, pleins=(), cadre=None, regles=None,
		regles_grille=None, chemins=()) -> dict:
	"""Grille d'une cité à enceinte déclarée, à partir de la proposition de `grille_image`
	(SANS enceinte devinée, sans nav, sans passages : `cells` et la liste `rues` du tracé).

	1. matières (`corriger`, avec l'enceinte comme garde) : eau, pierre, toits, terre franche
	   hors les murs ;
	2. au dedans, une étendue UNIE d'herbe, de terre ou de roche qui n'est pas une rue tracée
	   passe à 0 : talus, falaise, jardin (une rue est bigarrée, une place animée aussi) ;
	3. `pleins` (polygones déclarés : monuments qui sont des LIEUX, pas des toits où marcher ;
	   reliefs — une pente se lit comme une place, mi-herbe mi-ombre) → 0, puis `chemins`
	   (lignes brisées déclarées : la rampe qui monte au fort) → 1 ;
	4. le REMPART : la ligne du polygone, et une case vers l'intérieur — dans une vue
	   cavalière, c'est le chemin de ronde, réservé aux soldats ; une case du dehors collée au
	   rempart et faite de pierre ou d'ombre (la tour) aussi ;
	5. îlots reliés côté par côté (`grille_image.relier_zones`, coût des matières), jamais à
	   travers le rempart ni le cadre ;
	6. nav : SEULEMENT un pas qui enjambe la ligne du rempart entre deux cases praticables
	   (en diagonale, le mur est trop fin pour une case pleine) — un seul côté, celui du dedans ;
	7. rivière recousue, ponts rouverts.
	Ne mute pas `cells`. Rend `{cells, nav, dedans, anneau, rapport}`."""
	from utils import grille_image
	from utils.lieux import VALID_MOVES
	r = {**REGLES_MATIERES, **(regles or {})}
	rows, cols = len(cells), len(cells[0])
	cells = [list(ligne) for ligne in cells]
	rues = {tuple(c) for c in (rues or [])}
	dedans = dedans_polygone(enceinte, cols, rows)
	rapport = {"matieres": corriger(cells, lect, dedans, regles)}

	epures = 0
	for y in range(rows):
		for x in range(cols):
			c = lect[y][x]
			p = c["parts"]
			sol = p.get(VEGETATION, 0) + p.get(TERRE, 0) + p.get(ROCHE, 0)
			if (dedans[y][x] and cells[y][x] == 1 and (x, y) not in rues
					and c["ecart"] < r["dedans_uni_ecart"] and sol >= r["dedans_uni_sol"]):
				cells[y][x] = 0
				epures += 1
	rapport["talus"] = epures

	pleines = 0
	for poly in pleins:
		masque = dedans_polygone(poly, cols, rows)
		for x, y in polygone_cases(poly):
			if 0 <= x < cols and 0 <= y < rows:
				masque[y][x] = True
		for y in range(rows):
			for x in range(cols):
				if masque[y][x] and cells[y][x] != 0:
					cells[y][x] = 0
					pleines += 1
	rapport["monuments"] = pleines
	ouverts = set()
	for trace in chemins:
		for i in range(len(trace) - 1):
			ouverts.update(_ligne(tuple(trace[i]), tuple(trace[i + 1])))
	for x, y in ouverts:
		if 0 <= x < cols and 0 <= y < rows:
			cells[y][x] = 1
	rapport["chemins"] = len(ouverts)

	anneau = {(x, y) for x, y in polygone_cases(enceinte) if 0 <= x < cols and 0 <= y < rows}
	ronde = {(x, y) for y in range(rows) for x in range(cols)
		if dedans[y][x] and (x, y) not in anneau and _voisine_de(x, y, anneau, cols, rows)}
	tours = set()
	for y in range(rows):
		for x in range(cols):
			if dedans[y][x] or (x, y) in anneau or not _voisine_de(x, y, anneau, cols, rows):
				continue
			p = lect[y][x]["parts"]
			if p.get(PIERRE, 0) + p.get(SOMBRE, 0) + p.get(AUTRE, 0) >= r["tour_part"]:
				tours.add((x, y))
	for x, y in anneau | ronde | tours:
		cells[y][x] = 0
	rapport["rempart"] = {"anneau": len(anneau), "chemin_de_ronde": len(ronde), "tours": len(tours)}

	interdites = [[(x, y) in anneau or (x, y) in ronde or bool(cadre and cadre[y][x])
		for x in range(cols)] for y in range(rows)]
	cotes = [[1 if dedans[y][x] else 0 for x in range(cols)] for y in range(rows)]
	cells, _nav, relie = grille_image.relier_zones(cells, {}, marges(lect, regles), cotes,
		grille_image.regles_de("ville", regles_grille), murs_nav=False, interdites=interdites)
	rapport["passages"] = len(relie["passages"])
	rapport["poches_effacees"] = relie["poches_effacees"]
	rapport["zones_isolees"] = relie["zones_isolees"]

	nav = {}
	for y in range(rows):
		for x in range(cols):
			if not dedans[y][x] or cells[y][x] < 1:
				continue
			for bit, dx, dy, _op in VALID_MOVES:
				nx, ny = x + dx, y + dy
				if 0 <= nx < cols and 0 <= ny < rows and cells[ny][nx] >= 1 and not dedans[ny][nx]:
					nav[f"{x},{y}"] = nav.get(f"{x},{y}", 0) | bit
	rapport["nav"] = sum(bin(v).count("1") for v in nav.values())

	b_case = [[c["b"] for c in ligne] for ligne in lect]
	parts = [[c["parts"] for c in ligne] for ligne in lect]
	rapport["riviere_recousue"] = recoudre_rivieres(cells, b_case, regles)
	rapport["ponts"] = poser_ponts(cells, parts)
	if cadre:
		for y in range(rows):
			for x in range(cols):
				if cadre[y][x]:
					cells[y][x] = 0
	return {"cells": cells, "nav": nav, "dedans": dedans, "anneau": anneau | ronde,
		"rapport": rapport}
