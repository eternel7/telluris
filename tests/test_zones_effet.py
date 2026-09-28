# tests/test_zones_effet.py
# Géométrie des zones d'effet (utils/zones_effet.py) : normalisation du bloc `zone`,
# les quatre formes, l'ancre, l'orientation, et le filtrage par terrain / ligne de vue.
#
# Les quatre figures de référence du système sont verrouillées telles quelles (souffle,
# boule de feu, balayage d'épée, tourbillon) : ce sont elles qui décrivent le contrat, et
# `dev/test_zones_effet_client.js` rejoue EXACTEMENT les mêmes cas côté client.

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.zones_effet import (  # noqa: E402
	ANGLE_DEFAUT, RAYON_MAX, ancre_de, axe_de, axe_facing, cases_effet, cases_zone,
	est_orientee, normaliser_zone,
)


# ── Normalisation ────────────────────────────────────────────────────────────────

def test_zone_absente_ou_inconnue_rend_none():
	# Aucune zone ⇒ la capacité touche la seule case de sa cible (comportement d'avant).
	assert normaliser_zone(None) is None
	assert normaliser_zone({}) is None
	assert normaliser_zone({"forme": "triangle"}) is None
	assert normaliser_zone("cercle") is None


def test_normalisation_toutes_les_cles_presentes():
	z = normaliser_zone({"forme": "CERCLE", "rayon": 3})
	assert z["forme"] == "cercle"
	assert z["origine"] == "cible"
	assert z["orientation"] == "cible"
	assert z["rayon"] == 3
	# Les clés des autres formes existent quand même : le client n'a aucun repli à gérer.
	assert z["longueur"] == 1 and z["largeur"] == 1
	assert z["decalage"] == 0 and z["angle"] == ANGLE_DEFAUT


def test_normalisation_valeurs_hors_contrat():
	z = normaliser_zone({"forme": "cone", "origine": "ailleurs", "orientation": "lune",
						 "longueur": 999, "angle": 0})
	assert z["origine"] == "cible"        # valeur inconnue ⇒ défaut
	assert z["orientation"] == "cible"
	assert z["longueur"] == 12            # borné
	assert z["angle"] == 1                # borné par le bas, jamais 0


def test_rayon_absent_vaut_un_mais_rayon_zero_est_respecte():
	assert normaliser_zone({"forme": "carre"})["rayon"] == 1
	assert normaliser_zone({"forme": "carre", "rayon": 0})["rayon"] == 0
	assert normaliser_zone({"forme": "carre", "rayon": 99})["rayon"] == RAYON_MAX


def test_est_orientee():
	assert est_orientee(normaliser_zone({"forme": "cone"})) is True
	assert est_orientee(normaliser_zone({"forme": "rectangle"})) is True
	assert est_orientee(normaliser_zone({"forme": "cercle"})) is False
	assert est_orientee(normaliser_zone({"forme": "carre"})) is False


# ── Ancre et axe ─────────────────────────────────────────────────────────────────

def test_ancre_suit_origine():
	assert ancre_de(normaliser_zone({"forme": "cercle"}), (5, 5), (7, 3)) == (7, 3)
	zl = normaliser_zone({"forme": "cercle", "origine": "lanceur"})
	assert ancre_de(zl, (5, 5), (7, 3)) == (5, 5)


def test_axe_vers_la_cible_ramene_au_huitieme_de_tour():
	z = normaliser_zone({"forme": "cone"})
	assert axe_de(z, (5, 5), (5, 1)) == (0, -1)    # plein nord
	assert axe_de(z, (5, 5), (9, 5)) == (1, 0)     # plein est
	assert axe_de(z, (5, 5), (8, 2)) == (1, -1)    # diagonale
	# Une cible presque alignée retombe sur la direction cardinale la plus proche.
	assert axe_de(z, (5, 5), (10, 4)) == (1, 0)


def test_axe_facing_et_replis():
	assert axe_facing(0) == (0, -1)
	assert axe_facing(90) == (1, 0)
	assert axe_facing(180) == (0, 1)
	assert axe_facing(270) == (-1, 0)
	assert axe_facing(45) == (0, -1)      # hors des quarts ⇒ nord
	assert axe_facing(None) == (0, -1)
	z = normaliser_zone({"forme": "cone", "orientation": "facing"})
	assert axe_de(z, (5, 5), (9, 5), facing=180) == (0, 1)
	# Cible posée SUR le lanceur : aucun axe à lire, on retombe sur le facing.
	zc = normaliser_zone({"forme": "cone"})
	assert axe_de(zc, (5, 5), (5, 5), facing=90) == (1, 0)


# ── Les quatre figures de référence ──────────────────────────────────────────────

def test_boule_de_feu_cercle_euclidien_sur_la_cible():
	z = normaliser_zone({"forme": "cercle", "rayon": 2})
	cases = cases_zone(z, (5, 5), (5, 3))
	assert len(cases) == 13                      # disque euclidien de rayon 2
	assert (5, 3) in cases                       # la cible désignée, au centre
	assert (5, 1) in cases and (3, 3) in cases   # les pointes cardinales
	assert (4, 2) in cases                       # la diagonale proche (dist √2)
	assert (3, 1) not in cases                   # le coin (dist 2√2) reste dehors


def test_tourbillon_carre_de_chebyshev_autour_de_soi():
	z = normaliser_zone({"forme": "carre", "origine": "lanceur", "rayon": 1})
	cases = cases_zone(z, (5, 5), (5, 4))
	assert len(cases) == 9                       # les 8 cases autour + la sienne
	assert set(cases) == {(x, y) for x in (4, 5, 6) for y in (4, 5, 6)}


def test_cercle_et_carre_de_rayon_1_sont_deux_figures_distinctes():
	# C'est la raison d'être des deux formes : le tourbillon veut les 8 cases, la
	# nappe de gel veut la croix.
	croix = cases_zone(normaliser_zone({"forme": "cercle", "rayon": 1}), (0, 0), (0, 0))
	carre = cases_zone(normaliser_zone({"forme": "carre", "rayon": 1}), (0, 0), (0, 0))
	assert len(croix) == 5 and len(carre) == 9
	assert (1, 1) in carre and (1, 1) not in croix


def test_coup_d_epee_les_trois_cases_devant():
	z = normaliser_zone({"forme": "rectangle", "origine": "lanceur",
						 "longueur": 1, "largeur": 3, "decalage": 1})
	cases = cases_zone(z, (5, 5), (5, 4))        # ennemi désigné plein nord
	assert set(cases) == {(4, 4), (5, 4), (6, 4)}


def test_coup_d_epee_en_diagonale_balaie_une_bande_en_biais():
	z = normaliser_zone({"forme": "rectangle", "origine": "lanceur",
						 "longueur": 1, "largeur": 3, "decalage": 1})
	cases = cases_zone(z, (5, 5), (6, 4))        # ennemi en haut à droite
	# Perpendiculaire diagonale : une vraie bande en biais, pas un escalier.
	assert set(cases) == {(5, 3), (6, 4), (7, 5)}


def test_souffle_de_feu_cone_de_90_degres():
	z = normaliser_zone({"forme": "cone", "origine": "lanceur",
						 "longueur": 3, "decalage": 1})
	cases = cases_zone(z, (5, 5), (5, 3))        # souffle vers le nord
	assert len(cases) == 3 + 5 + 7               # un anneau qui s'élargit de 2 par cran
	assert set(c for c in cases if c[1] == 4) == {(4, 4), (5, 4), (6, 4)}
	assert set(c for c in cases if c[1] == 3) == {(3, 3), (4, 3), (5, 3), (6, 3), (7, 3)}
	assert (5, 5) not in cases                   # `decalage: 1` épargne le lanceur


def test_cone_l_ouverture_pilote_la_largeur():
	base = {"forme": "cone", "origine": "lanceur", "longueur": 2, "decalage": 1}
	etroit = cases_zone(normaliser_zone({**base, "angle": 20}), (5, 5), (5, 3))
	large = cases_zone(normaliser_zone({**base, "angle": 180}), (5, 5), (5, 3))
	assert set(etroit) == {(5, 4), (5, 3)}       # un simple rayon
	assert len(large) > len(cases_zone(normaliser_zone(base), (5, 5), (5, 3)))


def test_decalage_repousse_la_forme_le_long_de_l_axe():
	z = normaliser_zone({"forme": "rectangle", "origine": "lanceur",
						 "longueur": 2, "largeur": 1, "decalage": 2})
	assert cases_zone(z, (5, 5), (5, 4)) == [(5, 2), (5, 3)]
	# decalage 0 ⇒ la forme commence SUR l'ancre (ici le lanceur lui-même).
	z0 = normaliser_zone({"forme": "rectangle", "origine": "lanceur",
						  "longueur": 2, "largeur": 1})
	assert (5, 5) in cases_zone(z0, (5, 5), (5, 4))


def test_forme_orientee_ancree_sur_la_cible_couvre_la_cible():
	# `decalage: 0` + `origine: "cible"` : la cible désignée est la première case du mur.
	z = normaliser_zone({"forme": "rectangle", "longueur": 1, "largeur": 5})
	cases = cases_zone(z, (5, 5), (5, 2))
	assert set(cases) == {(3, 2), (4, 2), (5, 2), (6, 2), (7, 2)}


def test_largeur_paire_deborde_a_droite():
	# Cas limite ASSUMÉ : une largeur paire ne peut pas être centrée sur une case.
	z = normaliser_zone({"forme": "rectangle", "origine": "lanceur",
						 "longueur": 1, "largeur": 2, "decalage": 1})
	assert cases_zone(z, (5, 5), (5, 4)) == [(5, 4), (6, 4)]


def test_ordre_de_sortie_deterministe_et_sans_doublon():
	z = normaliser_zone({"forme": "carre", "rayon": 1})
	cases = cases_zone(z, (0, 0), (0, 0))
	assert cases == sorted(set(cases), key=lambda c: (c[1], c[0]))


# ── Filtrage par la carte (cases_effet) ──────────────────────────────────────────

# Grille 7×5, un mur vertical en x=4 sauf une ouverture en y=2.
#        x= 0  1  2  3  4  5  6
CELLS = [
	[1, 1, 1, 1, 0, 1, 1],   # y=0
	[1, 1, 1, 1, 0, 1, 1],   # y=1
	[1, 1, 1, 1, 1, 1, 1],   # y=2
	[1, 1, 1, 1, 0, 1, 1],   # y=3
	[1, 1, 1, 1, 0, 1, 1],   # y=4
]


def _praticable(x, y):
	return 0 <= y < len(CELLS) and 0 <= x < len(CELLS[y]) and CELLS[y][x] >= 1


def _vue(x0, y0, x1, y1):
	# Bresenham réduit : une case INTERMÉDIAIRE impraticable coupe la vue.
	dx, dy = abs(x1 - x0), abs(y1 - y0)
	sx = 1 if x0 < x1 else -1
	sy = 1 if y0 < y1 else -1
	err, x, y = dx - dy, x0, y0
	while True:
		if (x, y) not in ((x0, y0), (x1, y1)) and not _praticable(x, y):
			return False
		if (x, y) == (x1, y1):
			return True
		e2 = 2 * err
		if e2 > -dy:
			err -= dy
			x += sx
		if e2 < dx:
			err += dx
			y += sy


def test_cases_effet_sans_predicat_rend_la_geometrie_brute():
	z = normaliser_zone({"forme": "carre", "rayon": 1})
	assert cases_effet(z, (2, 2), (2, 2)) == cases_zone(z, (2, 2), (2, 2))


def test_cases_effet_ecarte_les_murs():
	z = normaliser_zone({"forme": "carre", "rayon": 1})
	cases = cases_effet(z, (2, 2), (3, 1), praticable=_praticable)
	assert (4, 0) not in cases and (4, 1) not in cases   # le mur
	assert (4, 2) in cases                               # l'ouverture


def test_cases_effet_ne_contourne_pas_un_angle():
	# Explosion sur (3, 2) : (5, 0) est derrière le mur, invisible depuis l'ancre.
	z = normaliser_zone({"forme": "carre", "rayon": 2})
	cases = cases_effet(z, (0, 2), (3, 2), praticable=_praticable, vue=_vue)
	assert (5, 2) in cases        # dans l'axe de l'ouverture
	assert (5, 0) not in cases    # à l'abri derrière le mur
	assert (3, 2) in cases        # l'ancre, jamais écartée par la ligne de vue


def test_cases_effet_l_ancre_survit_meme_sans_ligne_de_vue():
	z = normaliser_zone({"forme": "cercle", "rayon": 0})
	assert cases_effet(z, (0, 0), (6, 4), praticable=_praticable, vue=_vue) == [(6, 4)]
