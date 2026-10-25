# tests/test_combat_orientation.py
#
# Ligne de vue pour TOUT coup (une allonge de mêlée ne frappe pas à travers un mur) et
# interdiction de frapper dans son dos : devant et les cases directement à gauche/droite
# se frappent, dès une rangée en arrière il faut pivoter (`combat._dans_le_dos`).
# Joueur : son `facing` (0 = Nord, action `tourner`). Monstre : son `cap`, qui suit la
# marche ; l'IA pivote d'un quart de tour (une case de déplacement) avant de frapper.

import pytest

from utils import combat as combat_mod
from utils.combat import _dans_le_dos, _run_monster_turn, resolve_action
from _fixtures_magie import combat, joueur, monstre, sort

# Fouet : mêlée (`ranged` False) à deux cases.
FOUET = [{"mode": "cac", "portee": 2, "ranged": False, "toucher": "cc", "degats": "degats_cc"}]


@pytest.fixture(autouse=True)
def _des_fixes(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)


def _attaque(cible_xy, mur=None, **joueur_extra):
	"""Le joueur (3, 5), orienté au Nord, frappe un loup posé en `cible_xy`."""
	j = joueur(attaque_profils=FOUET, **joueur_extra)
	loup = monstre(x=cible_xy[0], y=cible_xy[1])
	doc = combat([j], [loup])
	if mur:
		doc["grid"]["cells"][mur[1]][mur[0]] = 0
	return doc, j, loup


# ── Ligne de vue en mêlée ────────────────────────────────────────────────────────

def test_un_fouet_ne_frappe_pas_a_travers_un_mur():
	doc, _, loup = _attaque((3, 3), mur=(3, 4))
	res = resolve_action(doc, "attaquer", cible_id=loup["id"])
	assert res.get("error") == "Ligne de vue obstruée."
	assert loup["currentPV"] == loup["pv_max"]


def test_un_fouet_frappe_a_deux_cases_sans_mur():
	doc, _, loup = _attaque((3, 3))
	res = resolve_action(doc, "attaquer", cible_id=loup["id"])
	assert "error" not in res, res


def test_le_ciblage_automatique_ignore_la_cible_derriere_un_mur():
	doc, _, loup = _attaque((3, 3), mur=(3, 4))
	assert "error" in resolve_action(doc, "attaquer")


# ── Le dos ───────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("xy", [(3, 6), (4, 6), (2, 6), (3, 7)])
def test_on_ne_frappe_pas_dans_son_dos(xy):
	doc, _, loup = _attaque(xy)
	res = resolve_action(doc, "attaquer", cible_id=loup["id"])
	assert res.get("error") == "Cible dans votre dos : pivotez d'abord."


@pytest.mark.parametrize("xy", [(4, 5), (2, 5), (4, 4), (3, 4), (5, 5)])
def test_devant_et_sur_les_cotes_on_frappe(xy):
	doc, _, loup = _attaque(xy)
	res = resolve_action(doc, "attaquer", cible_id=loup["id"])
	assert "error" not in res, res


def test_apres_un_quart_de_tour_la_cible_passe_sur_le_cote():
	doc, j, loup = _attaque((3, 6))
	assert "error" not in resolve_action(doc, "tourner", sens=1)
	assert j["facing"] == 90
	res = resolve_action(doc, "attaquer", cible_id=loup["id"])
	assert "error" not in res, res


def test_un_sort_offensif_ne_part_pas_dans_le_dos():
	doc, _, loup = _attaque((3, 7))
	res = resolve_action(doc, "sort", cible_id=loup["id"],
						 sort=sort(cible="ennemi", portee=4, effets={"degats": "1D6"}))
	assert res.get("error") == "Cible dans votre dos : pivotez d'abord."


def test_un_soin_sur_un_allie_dans_le_dos_reste_permis():
	soigneur = joueur(0)
	blesse = joueur(1, x=3, y=6, nom="Bruna", pv=100)
	blesse["currentPV"] = 50
	doc = combat([soigneur, blesse], [monstre(x=10, y=1)])
	res = resolve_action(doc, "sort", cible_id=blesse["id"],
						 sort=sort(cible="allie", portee=1, effets={"pv": 10}))
	assert "error" not in res, res
	assert blesse["currentPV"] == 60


def test_dos_d_un_grand_jeton_mesure_sur_son_emprise():
	"""2x2 orienté au Nord en (5, 5)-(6, 6) : le côté de sa rangée arrière (y 6) n'est
	pas dans son dos, la rangée d'en dessous (y 7) l'est."""
	bete = {"id": "monstre_0", "pos": {"x": 5, "y": 5}, "cap": "haut",
			"jeton": {"largeur": 2, "profondeur": 2, "forme": "ellipse"}}
	assert not _dans_le_dos(bete, {"pos": {"x": 7, "y": 6}})
	assert not _dans_le_dos(bete, {"pos": {"x": 4, "y": 6}})
	assert _dans_le_dos(bete, {"pos": {"x": 5, "y": 7}})


# ── IA des monstres ──────────────────────────────────────────────────────────────

def _tour_du_loup(loup_xy, cap, joueur_xy=(3, 5), mur=None):
	j = joueur(x=joueur_xy[0], y=joueur_xy[1])
	loup = monstre(x=loup_xy[0], y=loup_xy[1], cap=cap)
	doc = combat([j], [loup])
	doc["acteur_courant_index"] = 1
	if mur:
		doc["grid"]["cells"][mur[1]][mur[0]] = 0
	return doc, j, loup


def test_un_monstre_pivote_avant_de_frapper_dans_son_dos():
	doc, j, loup = _tour_du_loup((3, 4), "haut")   # le joueur est juste derrière lui
	_run_monster_turn(doc, loup, combat_mod.get_combat_grid(doc))
	assert loup["cap"] in ("gauche", "droite")
	assert loup["pos"] == {"x": 3, "y": 4}, "un pivot n'est pas un pas"
	assert any("pivote" in e["texte"] for e in doc["log"])
	assert any(e.get("acteur") == loup["nom"] and e["kind"] in ("hit", "crit", "miss", "fumble")
			   for e in doc["log"])


def test_sans_budget_de_deplacement_un_monstre_ne_frappe_pas_dans_son_dos():
	doc, j, loup = _tour_du_loup((3, 4), "haut")
	loup["deplacement"] = 0
	_run_monster_turn(doc, loup, combat_mod.get_combat_grid(doc))
	assert j["currentPV"] == j["pv_max"]
	assert not any(e.get("acteur") == loup["nom"] and e["kind"] in ("hit", "crit", "miss")
				   for e in doc["log"])


def test_un_monstre_a_allonge_contourne_le_mur_au_lieu_de_frapper_a_travers():
	doc, j, loup = _tour_du_loup((3, 3), "bas", mur=(3, 4))
	loup["portee"] = 2
	_run_monster_turn(doc, loup, combat_mod.get_combat_grid(doc))
	assert loup["pos"] != {"x": 3, "y": 3}, "il avance au lieu de frapper à travers le mur"


def test_le_cap_d_un_monstre_sans_jeton_suit_sa_marche():
	doc, j, loup = _tour_du_loup((9, 5), "haut")
	assert not loup.get("jeton")
	_run_monster_turn(doc, loup, combat_mod.get_combat_grid(doc))
	assert loup["cap"] == "gauche"
