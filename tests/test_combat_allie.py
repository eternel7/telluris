# tests/test_combat_allie.py
#
# Ciblage ALLIÉ (`cible: "allie"`) : soigner ou buffer un COMPAGNON ou une MONTURE en
# plein combat. Troisième valeur de `cible` après `soi` et `ennemi`, partagée par les
# sorts et les compétences — les deux branches passent par le même chokepoint
# `_lancer_sur_allie`, sans jet de toucher (un allié ne se défend pas).
#
# Logique pure : aucun accès DB (`slots` vide → _weapon_attacks ne lit aucun item).

import pytest

from utils import combat as combat_mod
from utils.combat import build_joueur_snapshot, resolve_action, _reset_turn_budget
from utils.sorts import CIBLES, normaliser_sort
from utils.competences import normaliser_competence


# ── Fixtures ─────────────────────────────────────────────────────────────────────

def _character(nom="Frida", **overrides):
	char = {
		"_id": "character:test_1", "nom": nom, "voc": "pretre", "race": "humain",
		"caracteristiques_current": {"V": 5, "F": 40, "R": 30, "Ag": 40,
									 "Vol": 40, "Int": 60, "Cha": 20, "Ch": 20},
		"vocations_niveaux": {"pretre": 1},
		"currentPV": 100, "currentPM": 40,
		"inventaire": [], "slots": {},
	}
	char.update(overrides)
	return char


def _groupe(pv_compagnon=30, monture=False):
	"""Lanceur en (3,5), allié adjacent en (3,4)."""
	lanceur = build_joueur_snapshot(_character("Frida"), joueur_index=0)
	lanceur["pos"] = {"x": 3, "y": 5}
	lanceur["vivant"] = True

	allie = build_joueur_snapshot(_character("Borin"), joueur_index=1)
	allie["pos"] = {"x": 3, "y": 4}
	allie["vivant"] = True
	allie["currentPV"] = pv_compagnon
	if monture:
		allie["nom"] = "Mule"
		allie["est_monture"] = True
		allie["jouable"] = False
		allie["deplacement"] = 0
	return lanceur, allie


def _combat(joueurs, monstres=None):
	monstres = monstres or []
	# Une monture ne figure jamais dans l'ordre d'initiative (elle ne joue pas).
	ordre = [j["id"] for j in joueurs if not j.get("est_monture")] + [m["id"] for m in monstres]
	return {
		"_id": "combat:test", "type": "combat", "status": "active", "tour": 1, "log": [],
		"ordre_initiative": ordre, "acteur_courant_index": 0,
		"joueurs": joueurs, "monstres": monstres,
		"grid": {"dims": {"x": 9, "y": 9},
				 "cells": [[1] * 9 for _ in range(9)], "nav": {}},
	}


def _sort(cible="allie", portee=1, cout_pm=0, nom="Revigore", **effets):
	doc = {"_id": "sort:revigore", "nom": nom, "icon": "✨", "cible": cible,
		   "cout_pm": cout_pm, "portee": portee, "effets": effets}
	return {"doc": doc, "effets": effets}


# ── La cible « allie » existe et traverse la normalisation ───────────────────────

def test_allie_est_une_cible_valide():
	assert "allie" in CIBLES
	vue = normaliser_sort({"_id": "sort:x", "type": "sort", "nom": "X", "vocation": "pretre",
						   "cout_pm": 5, "cible": "allie"})
	assert vue["cible"] == "allie"


def test_une_cible_inconnue_retombe_sur_soi():
	# Garde-fou : une faute de frappe dans un doc ne doit pas créer un troisième
	# comportement silencieux (ni planter la branche de résolution).
	vue = normaliser_sort({"_id": "sort:x", "type": "sort", "nom": "X", "vocation": "pretre",
						   "cout_pm": 5, "cible": "amis"})
	assert vue["cible"] == "soi"


def test_les_competences_partagent_la_meme_liste():
	vue = normaliser_competence({"_id": "competence:x", "type": "competence", "nom": "X",
								 "vocation": "pretre", "mode": "active", "cible": "allie"})
	assert vue["cible"] == "allie"


def test_un_sort_d_allie_s_offre_des_DEUX_cotes():
	# Seul `ennemi` est exclu hors combat (pas de monstre à viser) : un sort d'allié se
	# lance aussi bien en exploration, la cible étant désignée par `cible_id`.
	from utils.sorts import sort_utilisable_combat, sort_utilisable_exploration
	vue = normaliser_sort({"_id": "sort:x", "type": "sort", "nom": "X", "vocation": "pretre",
						   "cout_pm": 5, "cible": "allie", "effets": {"pv": 10}})
	assert sort_utilisable_combat(vue) is True
	assert sort_utilisable_exploration(vue) is True


def test_un_sort_offensif_reste_exclu_de_l_exploration():
	from utils.sorts import sort_utilisable_exploration
	vue = normaliser_sort({"_id": "sort:x", "type": "sort", "nom": "X", "vocation": "mage",
						   "cout_pm": 5, "cible": "ennemi", "effets": {"degats": "1D6"}})
	assert sort_utilisable_exploration(vue) is False


# ── Soigner / buffer un compagnon ────────────────────────────────────────────────

def test_un_sort_de_soin_rend_des_PV_au_compagnon():
	lanceur, allie = _groupe(pv_compagnon=30)
	combat = _combat([lanceur, allie])

	res = resolve_action(combat, "sort", cible_id="joueur_1", sort=_sort(pv=12))

	assert "error" not in res
	assert allie["currentPV"] == 42
	assert lanceur["currentPV"] == 100    # le lanceur n'est pas soigné à sa place
	assert res["cible"] == "Borin"


def test_le_soin_est_clampe_au_maximum_du_compagnon():
	lanceur, allie = _groupe(pv_compagnon=30)
	allie["pv_max"] = 35
	combat = _combat([lanceur, allie])
	resolve_action(combat, "sort", cible_id="joueur_1", sort=_sort(pv=999))
	assert allie["currentPV"] == 35


def test_un_buff_lance_sur_un_compagnon_modifie_SES_derivees():
	lanceur, allie = _groupe()
	combat = _combat([lanceur, allie])
	cc_allie, cc_lanceur = allie["cc"], lanceur["cc"]

	resolve_action(combat, "sort", cible_id="joueur_1",
				   sort=_sort(nom="Bénédiction", buffs={"F": 20, "Ag": 20}, duree=3))

	assert allie["cc"] > cc_allie
	assert lanceur["cc"] == cc_lanceur     # ⚠️ le buff ne fuit pas sur le lanceur
	assert [e["restants"] for e in allie["effets_actifs"]] == [3]


def test_le_buff_se_decremente_aux_tours_du_COMPAGNON():
	lanceur, allie = _groupe()
	combat = _combat([lanceur, allie])
	resolve_action(combat, "sort", cible_id="joueur_1",
				   sort=_sort(buffs={"F": 20}, duree=2))

	_reset_turn_budget(allie, combat)          # tour de pose : épargné
	assert allie["effets_actifs"][0]["restants"] == 2
	combat["tour"] = 2
	_reset_turn_budget(allie, combat)
	assert allie["effets_actifs"][0]["restants"] == 1


def test_une_competence_d_allie_marche_pareil():
	lanceur, allie = _groupe(pv_compagnon=30)
	combat = _combat([lanceur, allie])
	res = resolve_action(combat, "competence", cible_id="joueur_1", competence={
		"nom": "Pansement", "icon": "🩹", "cible": "allie", "jet": "cc",
		"cout_pm": 0, "portee": 1, "effets": {"pv": 10}})
	assert "error" not in res and allie["currentPV"] == 40


# ── Les montures sont des alliés comme les autres ────────────────────────────────

def test_une_monture_peut_etre_soignee():
	lanceur, mule = _groupe(pv_compagnon=20, monture=True)
	combat = _combat([lanceur, mule])
	res = resolve_action(combat, "sort", cible_id="joueur_1", sort=_sort(pv=15))
	assert "error" not in res and mule["currentPV"] == 35


def test_buffer_une_monture_ne_la_remet_pas_en_marche():
	# Le recalcul des dérivées déclenché par l'effet ne doit pas lui rendre son
	# déplacement : elle reste immobilisée par conception.
	lanceur, mule = _groupe(monture=True)
	combat = _combat([lanceur, mule])
	resolve_action(combat, "sort", cible_id="joueur_1",
				   sort=_sort(buffs={"F": 20}, duree=2))
	assert mule["deplacement"] == 0


# ── Refus : ce qui n'est pas une cible valide ────────────────────────────────────

def test_un_allie_hors_de_portee_est_refuse_sans_couter_de_PM():
	lanceur, allie = _groupe()
	allie["pos"] = {"x": 8, "y": 8}
	combat = _combat([lanceur, allie])
	pm_avant, actions_avant = lanceur["currentPM"], lanceur["actions_restantes"]

	res = resolve_action(combat, "sort", cible_id="joueur_1", sort=_sort(cout_pm=9, pv=12))

	assert "error" in res
	assert lanceur["currentPM"] == pm_avant          # le sort n'est jamais parti
	assert lanceur["actions_restantes"] == actions_avant


def test_un_allie_a_terre_n_est_pas_visable():
	# Le soigner le remettrait en jeu : cela changerait la condition de défaite et
	# l'ordre du tour. Relever un compagnon mérite sa propre mécanique.
	lanceur, allie = _groupe(pv_compagnon=0)
	combat = _combat([lanceur, allie])
	res = resolve_action(combat, "sort", cible_id="joueur_1", sort=_sort(pv=12))
	assert "error" in res and allie["currentPV"] == 0


def test_sans_cible_designee_le_sort_est_refuse():
	lanceur, allie = _groupe()
	combat = _combat([lanceur, allie])
	res = resolve_action(combat, "sort", cible_id=None, sort=_sort(pv=12))
	assert "error" in res


def test_la_ligne_de_vue_est_exigee_au_dela_du_contact():
	lanceur, allie = _groupe()
	allie["pos"] = {"x": 3, "y": 2}
	combat = _combat([lanceur, allie])
	combat["grid"]["cells"][3][3] = 0        # mur entre les deux
	res = resolve_action(combat, "sort", cible_id="joueur_1", sort=_sort(portee=5, pv=12))
	assert "error" in res


def test_soigner_sous_le_feu_reste_possible():
	# ⚠️ Contrairement à un sort OFFENSIF à distance, l'entraide n'est PAS interdite
	# quand on est engagé au corps à corps : c'est exactement là qu'elle sert.
	lanceur, allie = _groupe(pv_compagnon=30)
	monstre = {"id": "monstre_0", "nom": "Loup", "vivant": True, "pos": {"x": 4, "y": 5},
			   "currentPV": 20, "pv_max": 20, "pa": 5, "ag": 30, "ch": 0, "cc": 50,
			   "degats_cc": "1D6", "pm_def": 30, "initiative": 5, "deplacement": 3,
			   "xp_reward": 5}
	combat = _combat([lanceur, allie], [monstre])
	res = resolve_action(combat, "sort", cible_id="joueur_1", sort=_sort(portee=4, pv=12))
	assert "error" not in res and allie["currentPV"] == 42


# ── Coût côté lanceur ────────────────────────────────────────────────────────────

def test_les_PM_et_l_action_sont_debites_au_LANCEUR():
	lanceur, allie = _groupe(pv_compagnon=30)
	combat = _combat([lanceur, allie])
	pm_avant, actions_avant = lanceur["currentPM"], lanceur["actions_restantes"]
	pm_allie = allie["currentPM"]

	resolve_action(combat, "sort", cible_id="joueur_1", sort=_sort(cout_pm=9, pv=12))

	assert lanceur["currentPM"] == pm_avant - 9
	assert lanceur["actions_restantes"] == actions_avant - 1
	assert allie["currentPM"] == pm_allie     # l'allié ne paie rien
