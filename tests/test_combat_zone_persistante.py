# tests/test_combat_zone_persistante.py
#
# ZONES PERSISTANTES (Mur de feu) : toute capacité OFFENSIVE MAINTENUE à ZONE laisse ses
# cases actives tant que la concentration est payée — aucun champ ne le déclare, c'est dérivé
# du doc. QUICONQUE s'y trouve brûle (monstres, alliés, lanceur) : en y commençant son tour,
# à CHAQUE pas dans la zone, et à l'arrivée d'un saut. Lanceur à terre ⇒ zone inerte ;
# rupture de la concentration ⇒ le feu s'éteint (`_rompre_concentration`).

import pytest

from utils import combat as combat_mod
from utils.combat import (
	_monster_step_toward, _reset_turn_budget, _rompre_concentration, _run_monster_turn,
	get_combat_grid, resolve_action,
)
from _fixtures_magie import combat, sort, textes
from _fixtures_magie import joueur as _joueur_fixture
from _fixtures_magie import monstre as _monstre_fixture


# Dés fixés : 7 à chaque jet de dégâts (2D6), jets de toucher au milieu.
DEGATS = 7

# Le mage en (3,5) vise le loup en (8,5) : rectangle 1×3 ancré sur la cible, perpendiculaire
# à l'axe lanceur→cible — les cases (8,4), (8,5), (8,6).
MUR = dict(cout_pm=5, maintien=3, cible="ennemi", portee=6, nom="Mur de feu", icon="🔥",
		   effets={"degats": "2D6", "buffs": {"Ag": -10}, "duree": 2},
		   zone={"forme": "rectangle", "origine": "cible", "orientation": "cible",
				 "longueur": 1, "largeur": 3, "decalage": 0})
CASES_MUR = [[8, 4], [8, 5], [8, 6]]


@pytest.fixture(autouse=True)
def _des_fixes(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)
	monkeypatch.setattr(combat_mod, "roll_dice", lambda notation: DEGATS)


# Les fixtures forcent les PV (200 / 100) ; le premier recalcul des dérivées — le débuff
# −10 Ag que pose chaque brûlure — les re-clamperait, et la perte se lirait comme des
# dégâts. On part donc de PV COHÉRENTS avec les caractéristiques.
def monstre(**kw):
	m = _monstre_fixture(**kw)
	combat_mod._refresh_snapshot_stats(m)
	return m


def joueur(**kw):
	j = _joueur_fixture(**kw)
	combat_mod._refresh_snapshot_stats(j)
	return j


def _lancer_mur(doc, **champs):
	return resolve_action(doc, "sort", cible_id="monstre_0", sort=sort(**{**MUR, **champs}))


def _ecarter(m):
	"""La cible désignée quitte la scène : ses cases se libèrent pour les autres."""
	m["vivant"] = False
	m["currentPV"] = 0


# ── Pose : dérivée de « offensif + zone + maintien » ────────────────────────────

def test_le_mur_reste_sur_la_grille_avec_ses_cases_figees():
	mage = joueur(pm=60)
	doc = combat([mage], [monstre(x=8, y=5)])
	res = _lancer_mur(doc)

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
	_lancer_mur(doc)
	_lancer_mur(doc)
	assert len(doc["zones_persistantes"]) == 1


@pytest.mark.parametrize("champs", [
	{"maintien": 0},   # sans maintien : un seul coup au lancement, comme avant
	{"zone": None},    # sans zone : mono-cible, rien à laisser sur la grille
])
def test_pas_de_mur_sans_zone_ni_sans_maintien(champs):
	doc = combat([joueur(pm=60)], [monstre(x=8, y=5)])
	_lancer_mur(doc, **champs)
	assert not doc.get("zones_persistantes")


def test_un_soutien_de_zone_maintenu_ne_laisse_pas_de_mur():
	"""Limité à l'OFFENSIF : un soutien maintenu garde son buff posé sur les corps."""
	mage = joueur(pm=60)
	ami = joueur(idx=1, x=4, y=5, nom="Brun")
	doc = combat([mage, ami], [monstre(x=10, y=5)])
	resolve_action(doc, "sort", cible_id=ami["id"], sort=sort(
		cout_pm=5, maintien=2, cible="allie", portee=3, effets={"buffs": {"F": 5}},
		zone={"forme": "carre", "origine": "cible", "rayon": 1}))
	assert not doc.get("zones_persistantes")


# ── Début de tour ───────────────────────────────────────────────────────────────

def test_un_monstre_qui_commence_son_tour_dans_le_mur_brule():
	mage = joueur(pm=60)
	loup = monstre(x=8, y=5)
	doc = combat([mage], [loup])
	_lancer_mur(doc)
	apres_lancement = loup["currentPV"]

	for tour in (2, 3):
		doc["tour"] = tour
		_reset_turn_budget(loup, doc)
		assert loup["currentPV"] == apres_lancement - DEGATS * (tour - 1)
	assert any("brûle dans Mur de feu" in t for t in textes(doc))


def test_hors_du_mur_rien_ne_brule():
	loup, ours = monstre(x=8, y=5), monstre(idx=1, x=10, y=5)
	doc = combat([joueur(pm=60)], [loup, ours])
	_lancer_mur(doc)
	pv = ours["currentPV"]
	_reset_turn_budget(ours, doc)
	assert ours["currentPV"] == pv


def test_un_allie_qui_commence_son_tour_dans_le_mur_brule():
	"""Le mur n'a pas de camp. Présent au LANCEMENT, l'allié n'est pas touché par l'impact
	(ciblage offensif = monstres) : il brûle à son propre tour."""
	mage = joueur(pm=60)
	ami = joueur(idx=1, x=8, y=4, nom="Brun")
	doc = combat([mage, ami], [monstre(x=8, y=5)])
	pv = ami["currentPV"]
	_lancer_mur(doc)
	assert ami["currentPV"] == pv, "l'impact du lancement ne vise que les monstres"

	_reset_turn_budget(ami, doc)
	assert ami["currentPV"] == pv - DEGATS


def test_un_allie_tombe_dans_le_mur_passe_par_la_cascade_de_ko():
	mage = joueur(pm=60)
	ami = joueur(idx=1, x=8, y=4, nom="Brun")
	doc = combat([mage, ami], [monstre(x=8, y=5)])
	_lancer_mur(doc)
	ami["currentPV"] = DEGATS - 1
	_reset_turn_budget(ami, doc)
	assert ami["currentPV"] == 0
	assert any("Brun est à terre" in t for t in textes(doc))
	assert doc["status"] == "active", "le mage tient encore debout"


def test_un_grand_jeton_brule_des_qu_une_case_de_son_emprise_est_dans_le_mur():
	loup = monstre(x=8, y=5)
	# 2×2 en (9,3) : couvre (9..10, 3..4) — hors du mur ; décalé en (7,3) il en mord (8,4).
	geant = monstre(idx=1, x=9, y=3, jeton={"largeur": 2, "profondeur": 2})
	doc = combat([joueur(pm=60)], [loup, geant])
	_lancer_mur(doc)
	pv = geant["currentPV"]
	_reset_turn_budget(geant, doc)
	assert geant["currentPV"] == pv

	geant["pos"] = {"x": 7, "y": 3}
	_reset_turn_budget(geant, doc)
	assert geant["currentPV"] == pv - DEGATS


# ── Déplacement : une brûlure À CHAQUE PAS dans la zone ─────────────────────────

def test_un_monstre_brule_a_chaque_pas_dans_le_mur():
	mage = joueur(pm=60)
	cible, loup = monstre(x=8, y=5), monstre(idx=1, x=9, y=5)
	doc = combat([mage], [cible, loup])
	_lancer_mur(doc)
	_ecarter(cible)
	grid = get_combat_grid(doc)

	_reset_turn_budget(loup, doc)
	pv = loup["currentPV"]
	assert _monster_step_toward(doc, loup, mage, grid)
	assert [loup["pos"]["x"], loup["pos"]["y"]] in CASES_MUR
	assert loup["currentPV"] == pv - DEGATS

	# Au tour suivant, toujours dedans : il brûle en commençant son tour.
	_reset_turn_budget(loup, doc)
	assert loup["currentPV"] == pv - 2 * DEGATS


def test_le_joueur_brule_a_chaque_pas_le_long_du_mur():
	mage = joueur(pm=60, x=7, y=4)
	cible = monstre(x=8, y=5)
	doc = combat([mage], [cible, monstre(idx=1, x=11, y=8)])
	# Lancé depuis (3,5) pour poser le mur en (8,4..6), puis le mage s'en approche.
	mage["pos"] = {"x": 3, "y": 5}
	_lancer_mur(doc)
	_ecarter(cible)
	mage["pos"] = {"x": 7, "y": 4}
	_reset_turn_budget(mage, doc)
	pv = mage["currentPV"]

	assert not resolve_action(doc, "deplacer", dx=1, dy=0).get("error")   # → (8,4)
	assert mage["currentPV"] == pv - DEGATS
	assert not resolve_action(doc, "deplacer", dx=0, dy=1).get("error")   # → (8,5)
	assert mage["currentPV"] == pv - 2 * DEGATS, "chaque pas dans la zone brûle"
	assert not resolve_action(doc, "deplacer", dx=-1, dy=0).get("error")  # → (7,5), dehors
	assert mage["currentPV"] == pv - 2 * DEGATS


def test_tomber_dans_le_mur_en_marchant_passe_la_main():
	mage = joueur(pm=60)
	ami = joueur(idx=1, x=1, y=1, nom="Brun")
	cible = monstre(x=8, y=5)
	doc = combat([mage, ami], [cible, monstre(idx=1, x=11, y=8)])
	_lancer_mur(doc)
	_ecarter(cible)
	mage["pos"] = {"x": 7, "y": 4}
	mage["currentPV"] = DEGATS

	resolve_action(doc, "deplacer", dx=1, dy=0)
	assert mage["currentPV"] == 0
	actif = doc["ordre_initiative"][doc["acteur_courant_index"]]
	assert actif != mage["id"], "un joueur à terre ne garde pas la main"


def test_atterrir_d_un_saut_dans_le_mur_brule():
	mage = joueur(pm=60)
	cible = monstre(x=8, y=5)
	doc = combat([mage], [cible, monstre(idx=1, x=11, y=8)])
	_lancer_mur(doc)
	_ecarter(cible)
	pv = mage["currentPV"]
	res = resolve_action(doc, "sort", dx=8, dy=4, sort=sort(
		cout_pm=2, _id="sort:saut", nom="Saut", cible="soi", effets={"saut": 6}))
	assert not res.get("error")
	assert mage["pos"] == {"x": 8, "y": 4}
	assert mage["currentPV"] == pv - DEGATS


def test_un_monstre_tue_par_le_mur_ne_joue_pas_et_la_victoire_tombe():
	mage = joueur(pm=60)
	loup = monstre(x=8, y=5)
	doc = combat([mage], [loup])
	_lancer_mur(doc)
	loup["currentPV"] = DEGATS - 1
	pv_mage = mage["currentPV"]

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
	_lancer_mur(doc)
	_rompre_concentration(doc, mage, mage["concentrations"][0], "Le mur s'éteint.")
	assert doc["zones_persistantes"] == []

	pv = loup["currentPV"]
	_reset_turn_budget(loup, doc)
	assert loup["currentPV"] == pv


def test_le_defaut_de_pm_eteint_le_mur():
	mage = joueur(pm=60)
	doc = combat([mage], [monstre(x=8, y=5)])
	_lancer_mur(doc)
	mage["currentPM"] = 0
	_reset_turn_budget(mage, doc)
	assert doc["zones_persistantes"] == []


def test_relacher_le_sort_eteint_le_mur():
	mage = joueur(pm=60)
	doc = combat([mage], [monstre(x=8, y=5)])
	_lancer_mur(doc)
	res = resolve_action(doc, "interrompre", cible_id="sort:essai")
	assert not res.get("error")
	assert doc["zones_persistantes"] == []


def test_lanceur_a_terre_le_mur_est_inerte():
	mage = joueur(pm=60)
	loup = monstre(x=8, y=5)
	doc = combat([mage], [loup])
	_lancer_mur(doc)
	mage["currentPV"] = 0
	pv = loup["currentPV"]
	_reset_turn_budget(loup, doc)
	assert loup["currentPV"] == pv
