"""Géométrie des jetons de taille variable (utils/jetons.py) — tests purs.

Emprise selon le cap, distance entre emprises, case la plus proche, pas avec pivot et A* sur
les états (ancre, cap). Les cas d'emprise, de distance, de case proche et de centre sont
rejoués À L'IDENTIQUE côté client par dev/test_jetons_client.js : les deux fichiers se lisent
en vis-à-vis.
"""
from utils import jetons


def _acteur(x, y, taille=None, forme=None, cap=None):
	acteur = {"pos": {"x": x, "y": y}}
	jeton = jetons.normaliser_jeton({"taille": taille, "forme": forme}) if (taille or forme) else None
	if jeton:
		acteur["jeton"] = jeton
	if cap:
		acteur["cap"] = cap
	return acteur


def _ouvert(w, h):
	return lambda x, y: 0 <= x < w and 0 <= y < h


def _dragon(x=2, y=2, cap="bas"):
	return _acteur(x, y, "3x2", "triangle", cap)


# ── Normalisation ────────────────────────────────────────────────────────────────

def test_absent_ou_1x1_rond_vaut_none():
	"""Aucune migration : sans gabarit ni forme, l'acteur reste le 1x1 rond d'avant."""
	assert jetons.normaliser_jeton(None) is None
	assert jetons.normaliser_jeton({}) is None
	assert jetons.normaliser_jeton({"taille": "1x1"}) is None
	assert jetons.normaliser_jeton("3x2") is None


def test_gabarit_normalise_et_forme_par_defaut():
	assert jetons.normaliser_jeton({"taille": "3x2"}) == {
		"largeur": 3, "profondeur": 2, "forme": "ellipse"}
	assert jetons.normaliser_jeton({"taille": "2×2", "forme": "TRIANGLE"}) == {
		"largeur": 2, "profondeur": 2, "forme": "triangle"}


def test_taille_inconnue_retombe_en_1x1():
	assert jetons.normaliser_jeton({"taille": "4x4"}) is None
	# Une forme seule est gardée : elle change le dessin d'un acteur d'une case.
	assert jetons.normaliser_jeton({"taille": "4x4", "forme": "triangle"}) == {
		"largeur": 1, "profondeur": 1, "forme": "triangle"}
	assert jetons.normaliser_jeton({"taille": "2x2", "forme": "etoile"})["forme"] == "ellipse"


def test_jeton_espece():
	assert jetons.jeton_espece({"jeton": {"taille": "1x2"}})["profondeur"] == 2
	assert jetons.jeton_espece({"nom": "Loup"}) is None
	assert jetons.jeton_espece(None) is None


# ── Emprise ──────────────────────────────────────────────────────────────────────

def test_emprise_suit_le_cap():
	"""La PROFONDEUR suit la marche : un dragon qui avance vers la droite est 2 de large sur
	3 de haut (ses ailes en travers)."""
	assert jetons.emprise(_dragon(cap="bas")) == (2, 2, 3, 2)
	assert jetons.emprise(_dragon(cap="haut")) == (2, 2, 3, 2)
	assert jetons.emprise(_dragon(cap="droite")) == (2, 2, 2, 3)
	assert jetons.emprise(_dragon(cap="gauche")) == (2, 2, 2, 3)
	assert jetons.emprise({"pos": {"x": 2, "y": 2}, "jeton": {"largeur": 3, "profondeur": 2}}) \
		== (2, 2, 3, 2), "cap absent ⇒ bas"
	assert jetons.emprise(_acteur(2, 2)) == (2, 2, 1, 1)


def test_cases_et_couvre():
	dragon = _dragon()
	assert jetons.cases_emprise(dragon) == [(2, 2), (3, 2), (4, 2), (2, 3), (3, 3), (4, 3)]
	assert jetons.couvre(dragon, 4, 3) is True
	assert jetons.couvre(dragon, 5, 3) is False
	assert jetons.est_grand(dragon) is True
	assert jetons.est_grand(_acteur(0, 0, forme="triangle")) is False


def test_distance_1x1_egale_lancien_cheby():
	for (ax, ay, bx, by) in ((0, 0, 3, 1), (5, 5, 5, 5), (2, 7, 0, 0), (1, 1, 2, 2)):
		assert jetons.distance(_acteur(ax, ay), _acteur(bx, by)) == max(abs(ax - bx), abs(ay - by))


def test_distance_entre_emprises():
	"""Dragon 3x2 en (2,2), cases x 2..4 × y 2..3 : il se touche par n'importe quel bord."""
	dragon = _dragon()
	assert jetons.distance(dragon, _acteur(5, 4)) == 1
	assert jetons.distance(_acteur(5, 4), dragon) == 1
	assert jetons.distance(dragon, _acteur(6, 2)) == 2
	assert jetons.distance(dragon, _acteur(3, 3)) == 0
	assert jetons.distance(dragon, _acteur(1, 1)) == 1
	assert jetons.distance(dragon, _acteur(0, 5)) == 2
	assert jetons.distance(dragon, _acteur(5, 1, "2x2")) == 1, "deux grands jetons au contact"
	assert jetons.distance(dragon, _acteur(6, 1, "2x2")) == 2


def test_case_proche_et_centre():
	dragon = _dragon()
	assert jetons.case_proche(dragon, 0, 0) == (2, 2)
	assert jetons.case_proche(dragon, 3, 10) == (3, 3)
	assert jetons.case_proche(dragon, 9, 2) == (4, 2)
	assert jetons.case_proche(_acteur(5, 5), 0, 0) == (5, 5)
	assert jetons.centre(dragon) == (3.0, 2.5)
	assert jetons.centre(_acteur(4, 1)) == (4.0, 1.0)


def test_cap_vers():
	a = _acteur(0, 0)
	assert jetons.cap_vers(a, _acteur(5, 1)) == "droite"
	assert jetons.cap_vers(a, _acteur(-3, -1)) == "gauche"
	assert jetons.cap_vers(a, _acteur(1, 4)) == "bas"
	assert jetons.cap_vers(a, _acteur(0, -2)) == "haut"
	assert jetons.cap_vers(a, _acteur(2, 2)) == "droite", "égalité ⇒ horizontal"
	assert jetons.cap_vers(_acteur(0, 0, cap="haut"), _acteur(0, 0)) == "haut", "aucun écart"


# ── Un pas ───────────────────────────────────────────────────────────────────────

def test_translation_dun_carre_prend_le_cap_du_pas():
	carre = _acteur(1, 1, "2x2")
	assert jetons.pas_jeton(carre, 1, 0, set(), _ouvert(7, 7)) == ({"x": 2, "y": 1}, "droite")


def test_pas_diagonal_garde_le_cap():
	assert jetons.pas_jeton(_dragon(1, 1), 1, 1, set(), _ouvert(7, 7)) == ({"x": 2, "y": 2}, "bas")


def test_pivot_le_bord_avant_avance_dune_case():
	"""Dragon bas en (1,1) (x 1..3, y 1..2) qui part à droite : il pivote, son bord avant passe
	de x=3 à x=4, et il reste centré en travers (arrondi vers le bas)."""
	etat = jetons.pas_jeton(_dragon(1, 1), 1, 0, set(), _ouvert(7, 7))
	assert etat == ({"x": 3, "y": 0}, "droite")
	pivote = {"pos": etat[0], "jeton": _dragon()["jeton"], "cap": etat[1]}
	assert jetons.emprise(pivote) == (3, 0, 2, 3)


def test_pivot_arrondi_vers_le_haut_si_le_bas_est_pris():
	assert jetons.pas_jeton(_dragon(1, 1), 1, 0, {(3, 0)}, _ouvert(7, 7)) == (
		{"x": 3, "y": 1}, "droite")


def test_pivot_impossible_translation_sans_pivot():
	"""Aucun pivot ne tient : la bête se décale de côté, cap inchangé."""
	assert jetons.pas_jeton(_dragon(1, 1), 1, 0, {(4, 0), (4, 3)}, _ouvert(7, 7)) == (
		{"x": 2, "y": 1}, "bas")


def test_pivot_vers_le_haut():
	assert jetons.pas_jeton(_dragon(3, 3, "droite"), 0, -1, set(), _ouvert(9, 9)) == (
		{"x": 2, "y": 2}, "haut")


def test_pas_refuse_si_rien_ne_tient():
	assert jetons.pas_jeton(_acteur(0, 0, "2x2"), 1, 0, set(), _ouvert(2, 2)) is None
	assert jetons.pas_jeton(_acteur(0, 0), 1, 0, {(1, 0)}, _ouvert(5, 5)) is None


def test_nav_refuse_le_pas_dun_1x1():
	nav_ok = lambda x, y, dx, dy: not (x == 1 and y == 1 and (dx, dy) == (1, 0))
	assert jetons.pas_jeton(_acteur(1, 1), 1, 0, set(), _ouvert(5, 5), nav_ok) is None
	assert jetons.pas_jeton(_acteur(1, 1), 0, 1, set(), _ouvert(5, 5), nav_ok) == (
		{"x": 1, "y": 2}, "bas")


def test_nav_grand_jeton_de_proche_en_proche():
	"""Une case entrée peut être rejointe par une voisine de l'emprise ; un mur qui ferme
	TOUTE la colonne refuse le pas."""
	carre = _acteur(0, 0, "2x2")
	mur_partiel = lambda x, y, dx, dy: not (x == 1 and y == 0 and (dx, dy) == (1, 0))
	assert jetons.pas_jeton(carre, 1, 0, set(), _ouvert(5, 5), mur_partiel) is not None
	mur_plein = lambda x, y, dx, dy: not (x == 1 and dx == 1)
	assert jetons.pas_jeton(carre, 1, 0, set(), _ouvert(5, 5), mur_plein) is None


# ── A* ───────────────────────────────────────────────────────────────────────────

def _couloir(largeur):
	"""9×9 : deux rangées ouvertes en haut, puis un couloir vertical de `largeur` cases à x=3."""
	cells = [[1] * 9 for _ in range(2)] + [
		[1 if 3 <= x < 3 + largeur else 0 for x in range(9)] for _ in range(7)]
	return cells, (lambda x, y: 0 <= x < 9 and 0 <= y < 9 and cells[y][x] >= 1)


def _vers(cible, portee=1):
	return (lambda vue: jetons.distance(vue, cible) <= portee,
			lambda vue: max(0, jetons.distance(vue, cible) - portee))


def test_chemin_un_couloir_force_le_pivot():
	"""Un dragon de 3 cases d'envergure ne descend un couloir de 2 qu'en travers : l'A* doit
	trouver le pivot, puis le pas de côté qui garde le cap."""
	_, praticable = _couloir(2)
	cible = _acteur(3, 8)
	but, h = _vers(cible)
	chemin = jetons.chemin_jeton(_dragon(2, 0), but, h, {(3, 8)}, praticable)
	assert chemin is not None
	for etat in chemin:
		vue = jetons.vue_etat(_dragon(), etat)
		assert all(praticable(x, y) for (x, y) in jetons.cases_emprise(vue))
	assert any(etat[2] in ("gauche", "droite") for etat in chemin)
	assert but(jetons.vue_etat(_dragon(), chemin[-1]))


def test_chemin_couloir_trop_etroit():
	_, praticable = _couloir(1)
	but, h = _vers(_acteur(3, 8))
	assert jetons.chemin_jeton(_dragon(2, 0), but, h, {(3, 8)}, praticable) is None


def test_chemin_deja_au_but():
	but, h = _vers(_acteur(5, 2))
	assert jetons.chemin_jeton(_dragon(2, 2), but, h, set(), _ouvert(9, 9)) == [(2, 2, "bas")]
