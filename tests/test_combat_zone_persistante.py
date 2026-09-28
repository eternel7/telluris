# tests/test_combat_zone_persistante.py
#
# ZONES PERSISTANTES (Mur de feu) : une capacité offensive MAINTENUE dont la zone porte
# `persistante: true` laisse ses cases EN FEU tant que la concentration est payée. Un
# MONSTRE y brûle au plus une fois par tour qui lui est propre : en y commençant son tour,
# ou en y entrant pendant qu'il marche. Aucun tir ami ; lanceur à terre ⇒ zone inerte ;
# rupture de la concentration ⇒ le feu s'éteint (`_rompre_concentration`).

import pytest

from utils import combat as combat_mod
from utils.combat import (
	_bruler_zones, _monster_step_toward, _reset_turn_budget, _rompre_concentration,
	_run_monster_turn, get_combat_grid, resolve_action,
)
from _fixtures_magie import combat, joueur, sort, textes
from _fixtures_magie import monstre as _monstre_fixture


# Dés fixés : 7 à chaque jet de dégâts (2D6), jets de toucher au milieu.
DEGATS = 7

# Le mage en (3,5) vise le loup en (8,5) : rectangle 1×3 ancré sur la cible, perpendiculaire
# à l'axe lanceur→cible — les cases (8,4), (8,5), (8,6).
MUR = dict(cout_pm=5, maintien=3, cible="ennemi", portee=6, nom="Mur de feu", icon="🔥",
		   effets={"degats": "2D6", "buffs": {"Ag": -10}, "duree": 2},
		   zone={"forme": "rectangle", "origine": "cible", "orientation": "cible",
				 "longueur": 1, "largeur": 3, "decalage": 0, "persistante": True})
CASES_MUR = [[8, 4], [8, 5], [8, 6]]


@pytest.fixture(autouse=True)
def _des_fixes(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)
	monkeypatch.setattr(combat_mod, "roll_dice", lambda notation: DEGATS)


def monstre(**kw):
	"""Monstre de fixture aux PV COHÉRENTS avec ses caractéristiques : la fixture force 200 PV,
	que le premier recalcul des dérivées (le débuff −10 Ag du mur) re-clamperait — la perte
	se lirait alors comme une brûlure."""
	m = _monstre_fixture(**kw)
	combat_mod._refresh_snapshot_stats(m)
	return m


def _lancer_mur(mage, doc, **champs):
	return resolve_action(doc, "sort", cible_id="monstre_0", sort=sort(**{**MUR, **champs}))


# ── Pose ────────────────────────────────────────────────────────────────────────

def test_le_mur_reste_sur_la_grille_avec_ses_cases_figees():
	mage = joueur(pm=60)
	doc = combat([mage], [monstre(x=8, y=5)])
	res = _lancer_mur(mage, doc)

	zones = doc["zones_persistantes"]
	assert len(zones) == 1
	assert zones[0]["cases"] == CASES_MUR
	assert zones[0]["lanceur_id"] == mage["id"]
	assert res["zone_persistante"]["cases"] == CASES_MUR

	# Le lanceur bouge : le mur, lui, ne le suit pas.
	mage["pos"] = {"x": 2, "y": 2}
	assert doc["zones_persistantes"][0]["cases"] == CASES_MUR


def test_relancer_le_meme_sort_remplace_le_mur():
	mage = joueur(pm=60)
	doc = combat([mage], [monstre(x=8, y=5)])
	_lancer_mur(mage, doc)
	_lancer_mur(mage, doc)
	assert len(doc["zones_persistantes"]) == 1


@pytest.mark.parametrize("champs", [
	# Sans `persistante` : comportement d'avant, un seul coup au lancement.
	{"zone": {**MUR["zone"], "persistante": False}},
	# Sans maintien : rien ne dirait quand le mur s'éteint — il n'est donc pas posé.
	{"maintien": 0},
])
def test_pas_de_mur_sans_persistante_ni_sans_maintien(champs):
	mage = joueur(pm=60)
	doc = combat([mage], [monstre(x=8, y=5)])
	_lancer_mur(mage, doc, **champs)
	assert not doc.get("zones_persistantes")


# ── Début de tour ───────────────────────────────────────────────────────────────

def test_un_monstre_qui_commence_son_tour_dans_le_mur_brule():
	mage = joueur(pm=60)
	loup = monstre(x=8, y=5)
	doc = combat([mage], [loup])
	_lancer_mur(mage, doc)
	apres_lancement = loup["currentPV"]

	for tour in (2, 3):
		doc["tour"] = tour
		_reset_turn_budget(loup, doc)
		assert loup["currentPV"] == apres_lancement - DEGATS * (tour - 1)
	assert any("brûle dans Mur de feu" in t for t in textes(doc))


def test_hors_du_mur_rien_ne_brule():
	mage = joueur(pm=60)
	loup, ours = monstre(x=8, y=5), monstre(idx=1, x=10, y=5)
	doc = combat([mage], [loup, ours])
	_lancer_mur(mage, doc)
	pv = ours["currentPV"]
	_reset_turn_budget(ours, doc)
	assert ours["currentPV"] == pv


def test_aucun_tir_ami_un_allie_traverse_le_mur_indemne():
	mage = joueur(pm=60)
	ami = joueur(idx=1, x=8, y=4, nom="Brun")
	doc = combat([mage, ami], [monstre(x=8, y=5)])
	_lancer_mur(mage, doc)
	pv = ami["currentPV"]
	_reset_turn_budget(ami, doc)
	assert ami["currentPV"] == pv


def test_un_grand_jeton_brule_des_qu_une_case_de_son_emprise_est_dans_le_mur():
	mage = joueur(pm=60)
	loup = monstre(x=8, y=5)
	# 2×2 en (9,3) : couvre (9..10, 3..4) — hors du mur ; décalé en (7,3) il en mord (8,4).
	geant = monstre(idx=1, x=9, y=3, jeton={"largeur": 2, "profondeur": 2})
	doc = combat([mage], [loup, geant])
	_lancer_mur(mage, doc)
	pv = geant["currentPV"]
	_reset_turn_budget(geant, doc)
	assert geant["currentPV"] == pv

	geant["pos"] = {"x": 7, "y": 3}
	doc["tour"] = 2
	_reset_turn_budget(geant, doc)
	assert geant["currentPV"] == pv - DEGATS


# ── Traversée ───────────────────────────────────────────────────────────────────

def test_un_monstre_qui_entre_dans_le_mur_en_marchant_brule_une_fois_par_tour():
	mage = joueur(pm=60)
	cible, loup = monstre(x=8, y=5), monstre(idx=1, x=9, y=5)
	doc = combat([mage], [cible, loup])
	_lancer_mur(mage, doc)
	# La cible désignée s'écarte du chemin : le loup va passer par (8,5).
	cible["vivant"] = False
	cible["currentPV"] = 0
	grid = get_combat_grid(doc)

	doc["tour"] = 2
	_reset_turn_budget(loup, doc)
	pv = loup["currentPV"]
	assert _monster_step_toward(doc, loup, mage, grid)
	assert [loup["pos"]["x"], loup["pos"]["y"]] in CASES_MUR
	assert loup["currentPV"] == pv - DEGATS

	# Un second pas DANS le même mur, le même tour : pas de seconde brûlure.
	loup["pos"] = {"x": 8, "y": 4}
	_bruler_zones(doc, loup)
	assert loup["currentPV"] == pv - DEGATS

	# Au tour suivant, toujours dedans : il brûle de nouveau.
	doc["tour"] = 3
	_reset_turn_budget(loup, doc)
	assert loup["currentPV"] == pv - 2 * DEGATS


def test_un_monstre_tue_par_le_mur_ne_joue_pas_et_la_victoire_tombe():
	mage = joueur(pm=60)
	loup = monstre(x=8, y=5)
	doc = combat([mage], [loup])
	_lancer_mur(mage, doc)
	loup["currentPV"] = DEGATS - 1
	pv_mage = mage["currentPV"]

	doc["tour"] = 2
	doc["acteur_courant_index"] = doc["ordre_initiative"].index(loup["id"])
	_run_monster_turn(doc, loup, get_combat_grid(doc))

	assert loup["vivant"] is False
	assert doc["status"] == "victoire"
	assert mage["currentPV"] == pv_mage, "un monstre mort ne frappe pas"
	assert any("périt dans Mur de feu" in t for t in textes(doc))


# ── Extinction ──────────────────────────────────────────────────────────────────

def test_rompre_la_concentration_eteint_le_mur():
	mage = joueur(pm=60)
	loup = monstre(x=8, y=5)
	doc = combat([mage], [loup])
	_lancer_mur(mage, doc)
	_rompre_concentration(doc, mage, mage["concentrations"][0], "Le mur s'éteint.")
	assert doc["zones_persistantes"] == []

	pv = loup["currentPV"]
	doc["tour"] = 2
	_reset_turn_budget(loup, doc)
	assert loup["currentPV"] == pv


def test_le_defaut_de_pm_eteint_le_mur():
	mage = joueur(pm=60)
	doc = combat([mage], [monstre(x=8, y=5)])
	_lancer_mur(mage, doc)
	mage["currentPM"] = 0
	doc["tour"] = 2
	_reset_turn_budget(mage, doc)
	assert doc["zones_persistantes"] == []


def test_relacher_le_sort_eteint_le_mur():
	mage = joueur(pm=60)
	doc = combat([mage], [monstre(x=8, y=5)])
	_lancer_mur(mage, doc)
	res = resolve_action(doc, "interrompre", cible_id="sort:essai")
	assert not res.get("error")
	assert doc["zones_persistantes"] == []


def test_lanceur_a_terre_le_mur_est_inerte():
	mage = joueur(pm=60)
	loup = monstre(x=8, y=5)
	doc = combat([mage], [loup])
	_lancer_mur(mage, doc)
	mage["currentPV"] = 0
	pv = loup["currentPV"]
	doc["tour"] = 2
	_reset_turn_budget(loup, doc)
	assert loup["currentPV"] == pv
