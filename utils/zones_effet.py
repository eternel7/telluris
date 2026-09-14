# utils/zones_effet.py
# Zones d'effet des sorts et des compétences : la GÉOMÉTRIE, et rien d'autre.
#
# Un doc `sort:*` / `competence:*` peut porter un bloc `zone` qui décrit la forme
# touchée par la capacité. Sans ce bloc, la capacité touche EXACTEMENT la case de la
# cible désignée — le comportement d'avant, à la lettre (aucune migration, cf.
# CLAUDE.md Conventions §4).
#
# Le quadrillage est fait de CARRÉS. Une zone se lit donc en trois temps :
#   1. une case d'ANCRE      (`origine` : la case du lanceur, ou celle de la cible visée) ;
#   2. une ORIENTATION       (`orientation` : l'axe lanceur → cible, ou le `facing` du
#                             lanceur) — les formes non orientées l'ignorent ;
#   3. une FORME             (`forme` + ses dimensions), posée sur l'ancre selon l'axe.
#
# Les quatre formes couvrent les figures demandées :
#   • `cercle`    — disque EUCLIDIEN de `rayon` autour de l'ancre (boule de feu) ;
#   • `carre`     — disque de CHEBYSHEV de `rayon` : les 8 cases autour + l'ancre à
#                   rayon 1 (tourbillon de lames du barbare) ;
#   • `rectangle` — `longueur` cases de profondeur × `largeur` cases de front, posé
#                   le long de l'axe à partir de `decalage` (coup d'épée qui balaie les
#                   trois cases DEVANT : longueur 1, largeur 3, decalage 1) ;
#   • `cone`      — secteur angulaire d'ouverture `angle` et de `longueur` anneaux le
#                   long de l'axe (souffle de feu).
#
# ⚠️ `decalage` compte à partir de l'ANCRE INCLUSE : 0 = la zone commence sur la case
# d'ancre, 1 = elle commence une case plus loin le long de l'axe. Une forme orientée
# ancrée sur le LANCEUR s'écrit donc avec `decalage: 1` — sans quoi son premier anneau
# est la case du lanceur lui-même (inoffensive, aucun monstre n'y tient, mais l'aperçu
# la peindrait). Une forme ancrée sur la CIBLE garde `decalage: 0`, faute de quoi la
# cible désignée serait la seule à ne PAS être touchée.
#
# Module PUR : aucune lecture de base, aucune connaissance de la grille de combat. Les
# prédicats de terrain et de ligne de vue sont INJECTÉS par l'appelant (`cases_effet`) —
# ils vivent dans `utils/combat.py` (`_passable`, `_line_of_sight`), qui importe ce
# module ; les faire venir ici créerait un cycle.
#
# ⚠️ MIROIR CLIENT : `templates/scripts/zones_effet.js` rejoue cette géométrie pour
# l'APERÇU des cases touchées pendant le ciblage. La vérité reste ici (le serveur
# résout les dégâts) ; `dev/test_zones_effet_client.js` vérifie que les deux s'accordent
# sur les mêmes cas que `tests/test_zones_effet.py`.

import math

from utils.consommables import _as_int

# Formes reconnues. Une `forme` absente ou inconnue ⇒ pas de zone (`normaliser_zone`
# rend None) ⇒ la capacité touche la seule case de sa cible, comme avant.
FORMES = ("cercle", "carre", "rectangle", "cone")

# Case d'ancre de la zone.
#   `cible`   → la case de la cible désignée (boule de feu qui explose sur l'ennemi) ;
#   `lanceur` → la case du lanceur (tourbillon, balayage d'épée, souffle).
ORIGINES = ("cible", "lanceur")
ORIGINE_DEFAUT = "cible"

# Source de l'axe des formes orientées (rectangle, cone).
#   `cible`  → l'axe lanceur → cible désignée, ramené au huitième de tour le plus proche.
#              C'est le DÉFAUT : le joueur vise, la zone part dans cette direction.
#   `facing` → l'orientation du lanceur (0/90/180/270, cf. l'action `tourner`). Utile
#              pour une capacité qui balaie « devant soi » sans rien désigner.
# ⚠️ Seuls les JOUEURS portent un `facing` (build_joueur_snapshot) ; un monstre n'en a
# pas. `axe_de` retombe donc sur l'axe vers la cible quand le facing est absent.
ORIENTATIONS = ("cible", "facing")
ORIENTATION_DEFAUT = "cible"

# Ouverture par défaut d'un cône, en degrés (ouverture TOTALE, pas le demi-angle) : 90°
# donne la figure classique sur quadrillage carré — 3 cases au premier anneau, 5 au
# deuxième, 7 au troisième.
ANGLE_DEFAUT = 90

# Bornes de la DONNÉE. Elles ne protègent pas d'un auteur maladroit mais d'un doc qui
# ferait balayer toute la carte (ou tourner la boucle pour rien) : la plus grande carte
# de combat tient largement dans ces valeurs.
RAYON_MAX = 8
LONGUEUR_MAX = 12
LARGEUR_MAX = 12
DECALAGE_MAX = 12

# Axe monde d'un `facing`. ⚠️ Même convention que le client : l'écran regarde vers
# `(0, -1)` (la flèche ↑ du pavé porte `data-sdy="-1"`), et `facing` fait tourner le
# MONDE sous un joueur qui reste face au haut — `rot(x, y, 90) = (-y, x)`, comme dans
# `combat_telluris.html`. Un facing hors des quatre quarts retombe sur le Nord.
AXE_FACING = {0: (0, -1), 90: (1, 0), 180: (0, 1), 270: (-1, 0)}

# Les huit directions, dans l'ordre trigonométrique à partir de l'Est — c'est l'ordre
# qu'indexe l'arrondi de `atan2` dans `_axe_unitaire`.
DIRECTIONS_8 = ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1))


def _borne(valeur, mini: int, maxi: int) -> int:
	return max(mini, min(maxi, _as_int(valeur)))


def _champ(raw: dict, cle: str, defaut: int, mini: int, maxi: int) -> int:
	"""Entier borné du bloc brut, `defaut` si la clé est absente (et non si elle vaut 0 :
	un auteur qui écrit `rayon: 0` a le droit d'obtenir une zone d'une seule case)."""
	valeur = raw.get(cle)
	return _borne(defaut if valeur is None else valeur, mini, maxi)


def normaliser_zone(raw) -> dict | None:
	"""Vue normalisée d'un bloc `zone`, ou None si le doc n'en décrit pas une.

	Rend None — donc « capacité mono-case, comportement d'avant » — pour un bloc absent,
	vide, ou dont la `forme` n'est pas reconnue. Sinon TOUTES les clés sont présentes
	(même celles qui ne servent pas à la forme retenue) : le client reçoit cette vue
	telle quelle et n'a aucun repli à gérer, exactement comme pour `_bonus_dict`.
	"""
	raw = raw or {}
	if not isinstance(raw, dict):
		return None
	forme = str(raw.get("forme") or "").strip().lower()
	if forme not in FORMES:
		return None
	origine = str(raw.get("origine") or ORIGINE_DEFAUT).strip().lower()
	if origine not in ORIGINES:
		origine = ORIGINE_DEFAUT
	orientation = str(raw.get("orientation") or ORIENTATION_DEFAUT).strip().lower()
	if orientation not in ORIENTATIONS:
		orientation = ORIENTATION_DEFAUT
	# Un rayon absent vaut 1 et non 0 : une zone de rayon 0 ne touche que sa case
	# d'ancre, soit un sort de zone qui n'en est pas un — un piège silencieux.
	return {
		"forme": forme,
		"origine": origine,
		"orientation": orientation,
		"rayon": _champ(raw, "rayon", 1, 0, RAYON_MAX),
		"longueur": _champ(raw, "longueur", 1, 1, LONGUEUR_MAX),
		"largeur": _champ(raw, "largeur", 1, 1, LARGEUR_MAX),
		"decalage": _champ(raw, "decalage", 0, 0, DECALAGE_MAX),
		"angle": _champ(raw, "angle", ANGLE_DEFAUT, 1, 360),
	}


def est_orientee(zone: dict) -> bool:
	"""La forme dépend-elle d'un axe ? (rectangle et cône oui, cercle et carré non.)"""
	return (zone or {}).get("forme") in ("rectangle", "cone")


def _axe_unitaire(dx: int, dy: int) -> tuple | None:
	"""Vecteur (dx, dy) ramené à l'une des 8 directions, ou None s'il est nul.

	Arrondi au huitième de tour le plus proche : chaque direction couvre 45°, et les
	frontières exactes (22,5°) tombent du côté que choisit `round` — sans conséquence,
	les deux directions voisines sont également défendables à cet endroit.
	"""
	if dx == 0 and dy == 0:
		return None
	k = int(round(math.atan2(dy, dx) / (math.pi / 4))) % 8
	return DIRECTIONS_8[k]


def axe_facing(facing) -> tuple:
	"""Axe monde du `facing` d'un acteur (0/90/180/270). Défaut : le Nord de la carte."""
	try:
		quart = int(facing or 0) % 360
	except (TypeError, ValueError):
		quart = 0
	return AXE_FACING.get(quart, AXE_FACING[0])


def ancre_de(zone: dict, lanceur: tuple, cible: tuple) -> tuple:
	"""Case sur laquelle la forme est posée (cf. `origine`)."""
	return tuple(lanceur) if (zone or {}).get("origine") == "lanceur" else tuple(cible)


def axe_de(zone: dict, lanceur: tuple, cible: tuple, facing=0) -> tuple:
	"""Axe de la forme (cf. `orientation`).

	⚠️ Deux replis, dans cet ordre, et tous deux nécessaires :
	  • `orientation: "cible"` avec une cible posée SUR le lanceur (zone ancrée sur soi,
	    sans cible distincte) n'a pas d'axe : on retombe sur le facing ;
	  • une forme non orientée n'appelle jamais cette fonction, mais l'aperçu client s'en
	    sert pour dessiner une flèche — elle doit donc toujours rendre un vecteur valide.
	"""
	zone = zone or {}
	if zone.get("orientation") == "facing":
		return axe_facing(facing)
	axe = _axe_unitaire(int(cible[0]) - int(lanceur[0]), int(cible[1]) - int(lanceur[1]))
	return axe if axe is not None else axe_facing(facing)


def cases_zone(zone: dict, lanceur: tuple, cible: tuple, facing=0) -> list:
	"""Cases (x, y) couvertes par la forme, GÉOMÉTRIE PURE.

	Ni bornes de carte, ni terrain, ni ligne de vue : `cases_effet` s'en charge. Le
	résultat est trié par (y, x), donc déterministe et directement comparable en test.
	"""
	zone = zone or {}
	forme = zone.get("forme")
	if forme not in FORMES:
		return []
	ax, ay = ancre_de(zone, lanceur, cible)

	if forme in ("cercle", "carre"):
		rayon = int(zone.get("rayon", 1))
		cases = []
		for dy in range(-rayon, rayon + 1):
			for dx in range(-rayon, rayon + 1):
				# Chebyshev (carré plein) ou euclidien (disque). Sur un quadrillage
				# carré, `carre` rayon 1 = « toutes les cases autour », `cercle` rayon 1
				# = la croix : ce sont DEUX figures distinctes, pas deux écritures de la
				# même — d'où les deux formes.
				if forme == "carre" or dx * dx + dy * dy <= rayon * rayon:
					cases.append((ax + dx, ay + dy))
		return sorted(set(cases), key=lambda c: (c[1], c[0]))

	fx, fy = axe_de(zone, lanceur, cible, facing)
	debut = int(zone.get("decalage", 0))
	longueur = int(zone.get("longueur", 1))
	fin = debut + longueur - 1

	if forme == "rectangle":
		largeur = int(zone.get("largeur", 1))
		# Perpendiculaire directe à l'axe. Sur un axe DIAGONAL elle est diagonale elle
		# aussi : un balayage en biais couvre bien une bande en biais, pas un escalier.
		px, py = -fy, fx
		demi = (largeur - 1) // 2   # largeur paire ⇒ une case de plus à droite (assumé)
		cases = [(ax + i * fx + j * px, ay + i * fy + j * py)
				 for i in range(debut, fin + 1)
				 for j in range(-demi, largeur - demi)]
		return sorted(set(cases), key=lambda c: (c[1], c[0]))

	# Cône : anneaux de Chebyshev `debut..fin` autour de l'ancre, filtrés par l'angle au
	# vecteur d'axe. Le test se fait sur le cosinus (pas d'atan2 par case) avec une marge
	# de tolérance : un demi-angle de 45° doit accepter la diagonale exacte.
	cos_min = math.cos(math.radians(int(zone.get("angle", ANGLE_DEFAUT)) / 2.0)) - 1e-9
	norme_axe = math.hypot(fx, fy)
	cases = []
	for dy in range(-fin, fin + 1):
		for dx in range(-fin, fin + 1):
			d = max(abs(dx), abs(dy))
			if d < debut or d > fin:
				continue
			if d == 0:
				cases.append((ax, ay))   # l'ancre elle-même : aucun angle à mesurer
				continue
			if (dx * fx + dy * fy) / (math.hypot(dx, dy) * norme_axe) >= cos_min:
				cases.append((ax + dx, ay + dy))
	return sorted(set(cases), key=lambda c: (c[1], c[0]))


def cases_effet(zone: dict, lanceur: tuple, cible: tuple, facing=0,
				praticable=None, vue=None) -> list:
	"""Cases RÉELLEMENT touchées : la forme, moins ce que la carte lui retire.

	`praticable(x, y)` et `vue(x0, y0, x1, y1)` sont injectés — en combat ce sont
	`_passable` et `_line_of_sight`, qui vivent dans `utils/combat.py`.

	Deux filtres, et ils ne font pas le même travail :
	  • `praticable` écarte les murs : une explosion ne brûle pas l'intérieur d'un rocher ;
	  • `vue` écarte ce que l'ancre ne voit pas, donc ce qui est à l'abri DERRIÈRE un mur.
	    Sans lui, une boule de feu contournerait l'angle d'un couloir.
	L'ancre est exemptée du second (elle se voit elle-même), jamais du premier.
	"""
	ancre = ancre_de(zone, lanceur, cible)
	out = []
	for (x, y) in cases_zone(zone, lanceur, cible, facing):
		if praticable is not None and not praticable(x, y):
			continue
		if vue is not None and (x, y) != ancre and not vue(ancre[0], ancre[1], x, y):
			continue
		out.append((x, y))
	return out
