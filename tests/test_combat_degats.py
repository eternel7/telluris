# tests/test_combat_degats.py
# `combat.calculer_degats` — SOURCE UNIQUE des dégâts d'un coup qui touche, traversée par
# les cinq sites qui frappent (monstre, arme du joueur, sort, compétence, duel du
# simulateur) et par les deux qui estiment (score du simulateur, offense des potentiels).
# Ces tests épinglent la RÈGLE ; les tests de combat épinglent son usage en situation.

from utils import combat, potentiel, simulateur


def _des(valeur):
	"""Évaluateur de dés figé — la formule se teste sans aléa."""
	return lambda notation: valeur


ATTAQUANT = {"nom": "Attaquant", "caracts_base": {"F": 40, "R": 30}}
DEFENSEUR = {"nom": "Défenseur", "pa": 3, "caracts_base": {"F": 20, "R": 50}}


# ── La règle ─────────────────────────────────────────────────────────────────────────

def test_martial_soustrait_les_pa():
	assert combat.calculer_degats(ATTAQUANT, DEFENSEUR, "1D6", 1, "cc", _des(10)) == 7
	assert combat.calculer_degats(ATTAQUANT, DEFENSEUR, "1D6", 1, "cd", _des(10)) == 7


def test_magie_ignore_les_pa():
	"""L'armure physique n'arrête pas la magie : la pm_def a déjà joué dans le seuil."""
	assert combat.calculer_degats(ATTAQUANT, DEFENSEUR, "2D6", 1, "magique", _des(10)) == 10


def test_critique_double_les_des_avant_les_pa():
	"""⚠️ (dés × 2) − PA, et non (dés − PA) × 2 : le critique double le coup, pas la
	pénétration d'armure."""
	assert combat.calculer_degats(ATTAQUANT, DEFENSEUR, "1D6", 2, "cc", _des(10)) == 17
	assert combat.calculer_degats(ATTAQUANT, DEFENSEUR, "1D6", 2, "cc", _des(10)) != (10 - 3) * 2


def test_plancher_a_1_quand_l_armure_depasse_les_des():
	mur = {"nom": "Mur", "pa": 99, "caracts_base": {}}
	assert combat.calculer_degats(ATTAQUANT, mur, "1D4", 1, "cc", _des(2)) == 1


def test_defenseur_sans_pa_ne_plante_pas():
	"""Snapshot d'avant une feature, ou dict d'étalon minimal : `.get` partout."""
	assert combat.calculer_degats(ATTAQUANT, {}, "1D6", 1, "cc", _des(6)) == 6


# ── L'injection de l'évaluateur de dés ───────────────────────────────────────────────

def test_des_fn_defaut_joue_le_coup():
	"""Sans `des_fn`, c'est `roll_dice` : un entier dans la fourchette du dé."""
	for _ in range(20):
		dmg = combat.calculer_degats(ATTAQUANT, {"pa": 0}, "1D6", 1, "cc")
		assert isinstance(dmg, int) and 1 <= dmg <= 6


def test_le_defaut_est_resolu_a_l_appel_pas_a_la_definition(monkeypatch):
	"""⚠️ Piège verrouillé : avec `des_fn=roll_dice` en valeur par défaut du paramètre,
	la référence serait figée à la définition du module et les nombreux tests qui
	monkeypatchent `roll_dice` ne l'atteindraient plus — ils verraient les vrais dés
	tomber. Le défaut doit donc être résolu DANS le corps."""
	monkeypatch.setattr(combat, "roll_dice", lambda notation: 100)
	assert combat.calculer_degats(ATTAQUANT, DEFENSEUR, "1D6", 1, "cc") == 97


def test_des_fn_moyenne_donne_l_esperance_de_la_meme_formule():
	# E("2D6") = 7 ; PA 3 → 4.0.
	assert combat.calculer_degats(ATTAQUANT, DEFENSEUR, "2D6", 1, "cc",
								  des_fn=simulateur.moyenne_de_des) == 4.0
	# ⚠️ Le plancher vaut AUSSI pour l'espérance : E("1D6") = 3.5, moins 3 de PA, il
	# resterait 0.5 — un coup qui touche fait toujours au moins 1.
	assert combat.calculer_degats(ATTAQUANT, DEFENSEUR, "1D6", 1, "cc",
								  des_fn=simulateur.moyenne_de_des) == 1


# ── Ancrage : le moteur et le simulateur frappent pareil ─────────────────────────────

def test_le_simulateur_et_le_moteur_partagent_la_formule(monkeypatch):
	"""La garantie que ce chokepoint existe pour donner : un coup joué en jeu et le même
	coup simulé rendent le MÊME nombre. On piège la formule elle-même — si un site la
	recopiait au lieu de l'appeler, il échapperait au piège et le test tomberait."""
	appels = []

	def _mouchard(att, dfn, notation, mult=1, jet="cc", des_fn=None):
		appels.append((notation, mult, jet))
		return 42

	monkeypatch.setattr(combat, "calculer_degats", _mouchard)
	monkeypatch.setattr(combat, "_resoudre_jet", lambda a, d, s: {
		"roll": 50, "seuil": s, "touche": True, "critique": False,
		"fumble": False, "mult_degats": 1})

	# 1. Attaque de monstre (moteur).
	attaquant = {"id": "monstre_0", "nom": "Loup", "cc": 40, "ch": 0, "degats_cc": "1D6",
				 "actions_max": 2, "actions_restantes": 2, "attaques": 0, "deplacement": 3,
				 "cells_moved": 0, "penalites": 0, "pos": {"x": 0, "y": 0}}
	defenseur = {"id": "joueur_0", "nom": "Héros", "ag": 30, "esquive": 0, "ch": 0,
				 "pa": 3, "currentPV": 100, "pv_max": 100, "pos": {"x": 1, "y": 0}}
	doc = {"tour": 1, "log": []}
	combat._do_attack_on(doc, attaquant, defenseur)
	assert defenseur["currentPV"] == 58        # 100 − 42, la valeur du mouchard
	assert appels[0] == ("1D6", 1, "cc")

	# 2. Le même coup dans le simulateur.
	acteur = simulateur._normaliser_snapshot({
		"id": "a", "nom": "Loup", "cc": 40, "ch": 0, "degats_cc": "1D6", "pa": 0,
		"actions_max": 2, "actions_restantes": 2, "attaques": 0, "deplacement": 3,
		"cells_moved": 0, "penalites": 0, "currentPV": 50, "pv_max": 50,
		"caracts_base": {}, "effets_actifs": [], "pos": {"x": 0, "y": 0}})
	cible = simulateur._normaliser_snapshot({
		"id": "b", "nom": "Héros", "ag": 30, "esquive": 0, "ch": 0, "pa": 3,
		"currentPV": 100, "pv_max": 100, "actions_max": 1, "actions_restantes": 1,
		"caracts_base": {}, "effets_actifs": [], "pos": {"x": 1, "y": 0}})
	option = {"kind": "arme", "label": "Griffes", "jet": "cc", "notation": "1D6",
			  "cout_pm": 0, "ranged": False, "compteur": "attaques", "source": {}}
	simulateur._executer_attaque(acteur, cible, option,
								 {"distance": 1, "pseudo": {"tour": 1, "log": []}})
	assert cible["currentPV"] == 58            # même formule, même nombre
	assert appels[1] == ("1D6", 1, "cc")


def test_les_potentiels_passent_par_la_formule(monkeypatch):
	"""L'offense affichée par l'écran doit suivre un changement de formule."""
	vu = []
	monkeypatch.setattr(combat, "calculer_degats",
						lambda att, dfn, notation, mult=1, jet="cc", des_fn=None: (
							vu.append(jet) or 8.0))
	snapshot = {"actions_max": 1, "pm_max": 0, "pv_max": 100, "pa": 0, "ag": 40,
				"esquive": 0, "cc": 50, "cd": 0, "toucher_magique": 0, "degats_cc": "1D6",
				"attaque_profils": [{"mode": "cac", "portee": 1, "ranged": False,
									 "toucher": "cc", "degats": "degats_cc",
									 "label": "Épée"}]}
	res = potentiel.potentiel_combat(snapshot, {"sorts": [], "competences": []})
	assert vu == ["cc"]
	# seuil = 50 + 50 − 40 = 60 → 0.6 × 8.0 × 1 action = 4.8
	assert res["offense"] == 4.8
