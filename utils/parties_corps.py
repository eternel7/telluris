# utils/parties_corps.py
# PARTIES DU CORPS des plus grands jetons de combat (4x3, 5x4, 2x5) — module PUR.
#
# Le découpage est DÉRIVÉ de l'emprise et du cap (utils/jetons.py) : rien n'est écrit par
# espèce, rien n'est stocké (aucune migration, CLAUDE.md Conventions §4).
#   • AILES  : les deux colonnes extérieures, en travers de la marche — seulement pour une
#              espèce qui vole (`vol_espece` du snapshot) et large d'au moins 3 cases ;
#   • TÊTE   : la rangée de l'AVANT (dans le sens du cap), hors ailes ;
#   • QUEUE  : la rangée de l'ARRIÈRE, hors ailes ;
#   • FLANCS : tout le reste.
# Exemple, dragon 4x3 cap bas : 6 cases d'ailes, 2 de tête, 2 de queue, 2 de flancs.
#
# Effets (branchés dans utils/combat.py) :
#   1. la partie FRAPPÉE est celle de l'emprise la plus proche de l'attaquant — elle remplace
#      le d100 de localisation et module les PA du monstre (`MULT_PA`, lu par `pa_de_zone`) ;
#   2. les dégâts reçus aux AILES s'additionnent : au-delà de `SEUIL_AILES` × PV max, le
#      monstre perd le vol d'espèce jusqu'à la fin du combat (`ailes_brisees`) ;
#   3. ses zones d'effet partent de la case de TÊTE la plus proche de la cible ;
#   4. une cible dans son dos et au contact de sa QUEUE est frappée sans pivot, à
#      `COUP_DE_QUEUE_FACTEUR` des dégâts.

from utils import jetons

# Gabarits (largeur, profondeur) dotés de parties : les boss géants seulement.
GABARITS_A_PARTIES = frozenset({(4, 3), (5, 4), (2, 5)})
LARGEUR_MIN_AILES = 3

TETE, QUEUE, AILES, FLANCS = "corps_tete", "corps_queue", "corps_ailes", "corps_flancs"
PARTIES = (TETE, QUEUE, AILES, FLANCS)

# Multiplicateur des PA du monstre selon la partie touchée (choix de l'auteur).
MULT_PA = {TETE: 1.5, QUEUE: 1.0, FLANCS: 0.75, AILES: 0.5}
LIBELLES = {TETE: "à la tête", QUEUE: "à la queue", FLANCS: "au flanc", AILES: "à l'aile"}

SEUIL_AILES = 0.25            # part des PV max encaissée aux ailes qui brise le vol
COUP_DE_QUEUE_FACTEUR = 0.75  # dégâts d'un coup de queue, en remplacement de l'attaque


def a_des_parties(acteur) -> bool:
	return jetons.dims_jeton(acteur) in GABARITS_A_PARTIES


def a_des_ailes(acteur) -> bool:
	return bool((acteur or {}).get("vol_espece")) and jetons.dims_jeton(acteur)[0] >= LARGEUR_MIN_AILES


def _indices(acteur, x: int, y: int) -> tuple:
	"""(travers, profondeur) d'une case de l'emprise ; profondeur = P−1 à l'AVANT."""
	x0, y0, w, h = jetons.emprise(acteur)
	cap = jetons.cap_de(acteur)
	if cap == "bas":
		return x - x0, y - y0
	if cap == "haut":
		return x - x0, (y0 + h - 1) - y
	if cap == "droite":
		return y - y0, x - x0
	return y - y0, (x0 + w - 1) - x


def partie_de_case(acteur, x: int, y: int) -> str | None:
	"""Partie du corps couvrant (x, y), ou None (case hors emprise, ou monstre sans parties)."""
	if not a_des_parties(acteur) or not jetons.couvre(acteur, x, y):
		return None
	largeur, profondeur = jetons.dims_jeton(acteur)
	travers, prof = _indices(acteur, x, y)
	if a_des_ailes(acteur) and travers in (0, largeur - 1):
		return AILES
	if prof == profondeur - 1:
		return TETE
	if prof == 0:
		return QUEUE
	return FLANCS


def parties(acteur) -> dict:
	"""{partie: [cases]} — vide sans parties. Cases triées par (y, x)."""
	out = {}
	if not a_des_parties(acteur):
		return out
	for (x, y) in jetons.cases_emprise(acteur):
		out.setdefault(partie_de_case(acteur, x, y), []).append((x, y))
	return out


def _plus_proche(cases: list, cible) -> tuple | None:
	"""Case de `cases` la plus proche de l'emprise de `cible` : Chebyshev, puis distance au
	centre de la cible, puis ordre (y, x) — déterministe."""
	if not cases:
		return None
	cx, cy = jetons.centre(cible)
	cibles = jetons.cases_emprise(cible)

	def cle(c):
		cheb = min(max(abs(c[0] - a), abs(c[1] - b)) for (a, b) in cibles)
		return (cheb, (c[0] - cx) ** 2 + (c[1] - cy) ** 2, c[1], c[0])
	return min(cases, key=cle)


def partie_visee(defenseur, attaquant) -> str | None:
	"""Partie du corps frappée par `attaquant` : celle de la case la plus proche de lui, au
	contact comme à distance. None ⇒ le d100 ordinaire s'applique."""
	if not a_des_parties(defenseur) or not (attaquant or {}).get("pos"):
		return None
	case = _plus_proche(jetons.cases_emprise(defenseur), attaquant)
	return partie_de_case(defenseur, *case) if case else None


def ancre_tete(lanceur, cible) -> tuple | None:
	"""Case de TÊTE la plus proche de `cible` : origine des zones d'effet du lanceur."""
	return _plus_proche(parties(lanceur).get(TETE, []), cible)


def queue_au_contact(monstre, cible) -> bool:
	"""Une case de QUEUE touche-t-elle l'emprise de `cible` (Chebyshev ≤ 1) ?"""
	queue = parties(monstre).get(QUEUE, [])
	return any(max(abs(qx - x), abs(qy - y)) <= 1
			   for (qx, qy) in queue for (x, y) in jetons.cases_emprise(cible))


def blesser_ailes(monstre: dict, degats: int) -> bool:
	"""Cumule des dégâts reçus aux ailes. Rend True quand CE coup brise le vol. Mute sans
	sauver. Le seuil se compte en PV RÉELLEMENT retirés (l'appelant passe l'écart de PV)."""
	if degats <= 0 or not a_des_ailes(monstre):
		return False
	monstre["degats_ailes"] = int(monstre.get("degats_ailes", 0) or 0) + int(degats)
	if monstre.get("ailes_brisees"):
		return False
	seuil = max(1, int(SEUIL_AILES * int(monstre.get("pv_max", 1) or 1)))
	if monstre["degats_ailes"] >= seuil:
		monstre["ailes_brisees"] = True
		return True
	return False
