# utils/jetons.py
# Jetons de TAILLE VARIABLE en combat : l'EMPRISE d'un acteur sur la grille, et rien d'autre.
#
# Un doc `espece:*` peut porter `jeton: {"taille": "LxP", "forme": ...}`. Sans ce champ,
# l'acteur tient sur UNE case et se dessine en rond — le comportement d'avant, à la lettre
# (aucune migration, cf. CLAUDE.md Conventions §4).
#
#   • `L` = LARGEUR, en travers de la marche ; `P` = PROFONDEUR, dans le sens de la marche.
#     Un cheval est 1x2, une envergure d'archange 2x1, un dragon 3x2 (3 cases d'ailes sur
#     2 de corps).
#   • `forme` (ellipse / rectangle / triangle) n'habille que le DESSIN : les cases occupées
#     sont toujours le rectangle plein.
#
# Sur un snapshot de combat, le bloc est normalisé en `jeton: {largeur, profondeur, forme}`
# et complété par `cap` (haut/bas/gauche/droite, repère MONDE) : la direction de marche.
# L'emprise PIVOTE avec la marche — cap horizontal ⇒ `w = P`, `h = L` ; cap vertical ⇒
# `w = L`, `h = P`. `pos` est le coin haut-gauche (x min, y min) de l'emprise : pour un 1x1,
# rien ne change.
#
# Module PUR : ni base, ni grille. Terrain (`praticable`), cases prises (`bloque`) et masques
# (`nav_ok`) sont INJECTÉS par `utils/combat.py`, qui importe ce module.
#
# ⚠️ MIROIR CLIENT : `templates/scripts/jetons.js` rejoue l'emprise, la distance et la case la
# plus proche (pas le pathfinding : seul le serveur déplace un grand acteur).
# `dev/test_jetons_client.js` vérifie les mêmes cas que `tests/test_jetons.py`.

import heapq

# Gabarits admis (largeur, profondeur). Une taille inconnue ⇒ 1x1 : on ne devine pas.
TAILLES_JETON = {"1x1": (1, 1), "2x1": (2, 1), "1x2": (1, 2), "2x2": (2, 2), "3x2": (3, 2)}
FORMES_JETON = ("ellipse", "rectangle", "triangle")
FORME_DEFAUT = "ellipse"
DIMENSION_MAX = 3

# Cap = direction de marche, repère MONDE (y croît vers le bas, comme `cells[y][x]`).
CAPS = {"haut": (0, -1), "bas": (0, 1), "gauche": (-1, 0), "droite": (1, 0)}
CAP_DEFAUT = "bas"

# Les huit pas d'un acteur, dans un ordre fixe (déterminisme de l'A* à coût égal).
PAS_8 = ((0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1))

# Garde-fou de l'A* : au-delà, la cible est tenue pour injoignable ce tour-ci. La plus grande
# carte de combat compte quelques centaines de cases, soit ×4 caps.
EXPANSIONS_MAX = 6000


def normaliser_jeton(raw) -> dict | None:
	"""Vue normalisée d'un bloc `jeton` d'espèce, ou None = 1x1 rond (comportement d'avant).

	Une forme sans gabarit (1x1 triangle) est gardée : elle change le dessin. Un gabarit sans
	forme prend `ellipse`."""
	if not isinstance(raw, dict):
		return None
	taille = str(raw.get("taille") or "").strip().lower().replace("×", "x")
	largeur, profondeur = TAILLES_JETON.get(taille, (1, 1))
	forme = str(raw.get("forme") or "").strip().lower()
	if forme not in FORMES_JETON:
		forme = ""
	if largeur * profondeur == 1 and not forme:
		return None
	return {"largeur": largeur, "profondeur": profondeur, "forme": forme or FORME_DEFAUT}


def jeton_espece(espece) -> dict | None:
	"""Le jeton normalisé d'un doc `espece:*` (None si absent ou doc manquant)."""
	return normaliser_jeton((espece or {}).get("jeton"))


def _dimension(valeur) -> int:
	try:
		return max(1, min(DIMENSION_MAX, int(valeur)))
	except (TypeError, ValueError):
		return 1


def dims_jeton(acteur) -> tuple:
	"""(largeur, profondeur) du jeton d'un snapshot — (1, 1) sans jeton."""
	jeton = (acteur or {}).get("jeton")
	if not isinstance(jeton, dict):
		return (1, 1)
	return (_dimension(jeton.get("largeur")), _dimension(jeton.get("profondeur")))


def est_grand(acteur) -> bool:
	"""L'acteur occupe-t-il plus d'une case ?"""
	largeur, profondeur = dims_jeton(acteur)
	return largeur * profondeur > 1


def cap_de(acteur) -> str:
	cap = (acteur or {}).get("cap")
	return cap if cap in CAPS else CAP_DEFAUT


def dims_orientees(largeur: int, profondeur: int, cap: str) -> tuple:
	"""(w, h) monde d'un gabarit selon son cap : la profondeur suit la marche."""
	if cap in ("gauche", "droite"):
		return (profondeur, largeur)
	return (largeur, profondeur)


def emprise(acteur) -> tuple:
	"""(x0, y0, w, h) : le rectangle occupé, coin haut-gauche = `pos`."""
	pos = (acteur or {}).get("pos") or {}
	largeur, profondeur = dims_jeton(acteur)
	w, h = dims_orientees(largeur, profondeur, cap_de(acteur))
	return (int(pos.get("x", 0)), int(pos.get("y", 0)), w, h)


def cases_rect(x0: int, y0: int, w: int, h: int) -> list:
	"""Cases d'un rectangle, triées par (y, x)."""
	return [(x, y) for y in range(y0, y0 + h) for x in range(x0, x0 + w)]


def cases_emprise(acteur) -> list:
	return cases_rect(*emprise(acteur))


def couvre(acteur, x: int, y: int) -> bool:
	x0, y0, w, h = emprise(acteur)
	return x0 <= x < x0 + w and y0 <= y < y0 + h


def _ecart(a0: int, aw: int, b0: int, bw: int) -> int:
	return max(0, b0 - (a0 + aw - 1), a0 - (b0 + bw - 1))


def distance(a, b) -> int:
	"""Distance de Chebyshev entre deux EMPRISES : le plus grand écart libre sur un axe.
	0 = elles se chevauchent, 1 = elles se touchent. Deux 1x1 ⇒ exactement l'ancien `_cheby`."""
	ax, ay, aw, ah = emprise(a)
	bx, by, bw, bh = emprise(b)
	return max(_ecart(ax, aw, bx, bw), _ecart(ay, ah, by, bh))


def case_proche(acteur, x: int, y: int) -> tuple:
	"""La case de l'emprise la plus proche de (x, y) — le point, borné au rectangle. Sert
	d'ANCRE à une zone d'effet posée sur un grand acteur."""
	x0, y0, w, h = emprise(acteur)
	return (max(x0, min(x0 + w - 1, int(x))), max(y0, min(y0 + h - 1, int(y))))


def centre(acteur) -> tuple:
	"""Centre géométrique de l'emprise (demi-cases possibles)."""
	x0, y0, w, h = emprise(acteur)
	return (x0 + (w - 1) / 2, y0 + (h - 1) / 2)


def cap_vers(acteur, cible) -> str:
	"""Cap qui fait face à `cible` : l'axe dominant entre les deux centres, horizontal à
	égalité. Aucun écart ⇒ le cap actuel de l'acteur."""
	ax, ay = centre(acteur)
	bx, by = centre(cible)
	dx, dy = bx - ax, by - ay
	if dx == 0 and dy == 0:
		return cap_de(acteur)
	if abs(dx) >= abs(dy):
		return "droite" if dx > 0 else "gauche"
	return "bas" if dy > 0 else "haut"


def _cap_du_pas(dx: int, dy: int) -> str | None:
	for cap, vecteur in CAPS.items():
		if vecteur == (dx, dy):
			return cap
	return None


def _candidats_pas(acteur, dx: int, dy: int) -> list:
	"""États (x0, y0, cap) à essayer, dans l'ordre, pour UN pas (dx, dy).

	Pas CARDINAL qui change l'axe d'un gabarit non carré : d'abord le PIVOT — le bord avant
	avance d'une case dans le sens du pas, et l'emprise reste centrée sur l'ancienne en
	travers (arrondi vers le bas, puis vers le haut) —, sinon la translation SANS pivot (la
	bête se décale de côté, cap inchangé). Autre pas cardinal : translation, cap du pas.
	Pas DIAGONAL : translation, cap inchangé."""
	x0, y0, w, h = emprise(acteur)
	cap = cap_de(acteur)
	largeur, profondeur = dims_jeton(acteur)
	nouveau = _cap_du_pas(dx, dy)
	if nouveau is None:
		return [(x0 + dx, y0 + dy, cap)]
	nw, nh = dims_orientees(largeur, profondeur, nouveau)
	if (nw, nh) == (w, h):
		return [(x0 + dx, y0 + dy, nouveau)]
	pivots = []
	if dx != 0:
		nx0 = x0 + w - nw + 1 if dx > 0 else x0 - 1
		bas, haut = (2 * y0 + h - nh) // 2, -((-(2 * y0 + h - nh)) // 2)
		pivots = [(nx0, bas, nouveau)] + ([(nx0, haut, nouveau)] if haut != bas else [])
	else:
		ny0 = y0 + h - nh + 1 if dy > 0 else y0 - 1
		bas, haut = (2 * x0 + w - nw) // 2, -((-(2 * x0 + w - nw)) // 2)
		pivots = [(bas, ny0, nouveau)] + ([(haut, ny0, nouveau)] if haut != bas else [])
	return pivots + [(x0 + dx, y0 + dy, cap)]


def _emprise_valide(anciennes: list, rect: tuple, bloque, praticable, nav_ok) -> bool:
	"""Le rectangle tient-il ? Toutes ses cases praticables et libres, et chaque case ENTRÉE
	reliée à l'ancienne emprise par des pas `nav_ok`, de proche en proche à l'intérieur de
	l'union ancienne ∪ nouvelle emprise."""
	nouvelles = cases_rect(*rect)
	for (x, y) in nouvelles:
		if not praticable(x, y) or (x, y) in bloque:
			return False
	if nav_ok is None:
		return True
	atteintes = set(anciennes)
	a_joindre = [c for c in nouvelles if c not in atteintes]
	progres = True
	while a_joindre and progres:
		progres = False
		restantes = []
		for (x, y) in a_joindre:
			if any(max(abs(x - ox), abs(y - oy)) == 1 and nav_ok(ox, oy, x - ox, y - oy)
				   for (ox, oy) in atteintes):
				atteintes.add((x, y))
				progres = True
			else:
				restantes.append((x, y))
		a_joindre = restantes
	return not a_joindre


def pas_jeton(acteur, dx: int, dy: int, bloque, praticable, nav_ok=None) -> tuple | None:
	"""Nouvel état ({"x", "y"}, cap) après UN pas (dx, dy), ou None si rien ne tient.

	`bloque` : cases prises par les AUTRES acteurs. `praticable(x, y)` : bornes + terrain.
	`nav_ok(x, y, dx, dy)` : masques de la carte (None = aucun)."""
	anciennes = cases_emprise(acteur)
	largeur, profondeur = dims_jeton(acteur)
	for (nx0, ny0, cap) in _candidats_pas(acteur, dx, dy):
		w, h = dims_orientees(largeur, profondeur, cap)
		if _emprise_valide(anciennes, (nx0, ny0, w, h), bloque, praticable, nav_ok):
			return {"x": nx0, "y": ny0}, cap
	return None


def vue_etat(acteur, etat: tuple) -> dict:
	"""Pseudo-acteur (pos, jeton, cap) pour un état (x0, y0, cap) — ce que lisent les
	fonctions de géométrie."""
	return {"pos": {"x": etat[0], "y": etat[1]}, "jeton": (acteur or {}).get("jeton"),
			"cap": etat[2]}


def chemin_jeton(acteur, but, heuristique, bloque, praticable, nav_ok=None) -> list | None:
	"""A* sur les états (x0, y0, cap), coût 1 par pas (pivot compris).

	`but(vue)` et `heuristique(vue)` reçoivent un pseudo-acteur (`vue_etat`). Avec
	`but = distance ≤ portée` et `heuristique = max(0, distance − portée)`, l'heuristique est
	admissible : un pas, pivot compris, ne réduit l'écart que d'une case par axe.
	Rend la liste des états du départ au but inclus, ou None."""
	pos = (acteur or {}).get("pos") or {}
	depart = (int(pos.get("x", 0)), int(pos.get("y", 0)), cap_de(acteur))
	ouverts = [(heuristique(vue_etat(acteur, depart)), 0, 0, depart)]
	parents = {depart: None}
	couts = {depart: 0}
	fermes = set()
	compteur = 0
	while ouverts and len(fermes) < EXPANSIONS_MAX:
		_, cout, _, courant = heapq.heappop(ouverts)
		if courant in fermes:
			continue
		vue = vue_etat(acteur, courant)
		if but(vue):
			chemin = []
			while courant is not None:
				chemin.append(courant)
				courant = parents[courant]
			return chemin[::-1]
		fermes.add(courant)
		for dx, dy in PAS_8:
			pas = pas_jeton(vue, dx, dy, bloque, praticable, nav_ok)
			if pas is None:
				continue
			suivant = (pas[0]["x"], pas[0]["y"], pas[1])
			if suivant in fermes or cout + 1 >= couts.get(suivant, cout + 2):
				continue
			couts[suivant] = cout + 1
			parents[suivant] = courant
			compteur += 1
			heapq.heappush(ouverts, (cout + 1 + heuristique(vue_etat(acteur, suivant)),
									 cout + 1, compteur, suivant))
	return None
