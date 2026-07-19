# tests/test_sorts_jet.py
#
# Jet de toucher d'un sort porté par la DONNÉE (`jet`: cc / cd / magique), miroir du
# contrat déjà en place pour les compétences. Un sort de CONTACT (« au toucher ») exige
# de poser la main : jet martial contre la défense physique, PA soustraits.
#
# ⚠️ Le DÉFAUT diffère entre les deux familles, et c'est l'invariant de rétro-compat :
# un sort sans champ `jet` reste `magique`, une compétence sans champ reste `cc`.

import pytest

from utils import combat as combat_mod
from utils.combat import (
	build_joueur_snapshot, build_monster_snapshot, resolve_action,
	_defense_physique, _hit_threshold, _magic_hit_threshold,
)
from utils.sorts import JETS, normaliser_sort
from utils.competences import normaliser_competence


# ── Fixtures (identiques à test_combat_debuffs.py) ───────────────────────────────

def _character(**overrides):
	char = {
		"_id": "character:test_1", "nom": "Frida", "voc": "templier", "race": "humain",
		"caracteristiques_current": {"V": 5, "F": 40, "R": 30, "Ag": 40,
									 "Vol": 40, "Int": 60, "Cha": 20, "Ch": 20},
		"vocations_niveaux": {"templier": 1},
		"currentPV": 100, "currentPM": 40,
		"inventaire": [], "slots": {},
	}
	char.update(overrides)
	return char


def _espece():
	return {"_id": "espece:loup", "nom": "Loup", "tags": [],
			"base_attributes": {c: {"min": v, "max": v} for c, v in
								(("V", 4), ("F", 30), ("R", 30), ("Ag", 40),
								 ("Vol", 20), ("Int", 10), ("Cha", 10), ("Ch", 10))}}


def _monstre(**overrides):
	m = build_monster_snapshot(_espece(), None, 0)
	m["pos"] = {"x": 3, "y": 4}
	m.update(overrides)
	return m


def _combat(joueur, monstres):
	joueur["pos"] = {"x": 3, "y": 5}
	joueur["vivant"] = True
	return {
		"_id": "combat:test", "type": "combat", "status": "active", "tour": 1, "log": [],
		"ordre_initiative": ["joueur_0"] + [m["id"] for m in monstres],
		"acteur_courant_index": 0,
		"joueurs": [joueur], "monstres": monstres,
		"grid": {"dims": {"x": 7, "y": 7},
				 "cells": [[1] * 7 for _ in range(7)], "nav": {}},
	}


def _sort(jet=None, portee=1, **effets):
	doc = {"_id": "sort:contact", "nom": "Main de venin", "icon": "🐍",
		   "cible": "ennemi", "cout_pm": 0, "portee": portee, "effets": effets}
	if jet is not None:
		doc["jet"] = jet
	return {"doc": doc, "effets": effets}


# ── Normalisation : le défaut, c'est tout l'enjeu de rétro-compat ────────────────

def test_un_sort_sans_champ_jet_reste_magique():
	# INVARIANT : tous les sorts déjà en base n'ont pas ce champ. S'ils basculaient en
	# martial, chaque sort du jeu changerait de stat de résolution sans qu'on le demande.
	vue = normaliser_sort({"_id": "sort:x", "type": "sort", "nom": "X",
						   "vocation": "mage", "cout_pm": 5})
	assert vue["jet"] == "magique"


def test_une_competence_sans_champ_jet_reste_martiale():
	# Le défaut OPPOSÉ, sur la même liste de valeurs : c'est voulu, pas une incohérence.
	vue = normaliser_competence({"_id": "competence:x", "type": "competence", "nom": "X",
								 "vocation": "guerrier", "mode": "active"})
	assert vue["jet"] == "cc"


@pytest.mark.parametrize("brut", ["cc", "cd", "magique"])
def test_les_jets_valides_traversent(brut):
	vue = normaliser_sort({"_id": "sort:x", "type": "sort", "nom": "X",
						   "vocation": "mage", "cout_pm": 5, "jet": brut})
	assert vue["jet"] == brut and brut in JETS


def test_un_jet_inconnu_retombe_sur_le_defaut():
	vue = normaliser_sort({"_id": "sort:x", "type": "sort", "nom": "X",
						   "vocation": "mage", "cout_pm": 5, "jet": "psychique"})
	assert vue["jet"] == "magique"


# ── Résolution : la stat qui décide change ───────────────────────────────────────

def test_un_sort_de_contact_se_resout_sous_le_cc(monkeypatch):
	# Cible à pm_def écrasante mais Ag médiocre : un sort magique la manque, le même
	# sort en `jet: "cc"` la touche. C'est tout l'intérêt du « au toucher ».
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)
	m_stats = dict(pm_def=200, ag=10)

	magique = build_joueur_snapshot(_character())
	cible_m = _monstre(**m_stats)
	res_m = resolve_action(_combat(magique, [cible_m]), "sort", cible_id="monstre_0",
						   sort=_sort(degats="1D4"))

	martial = build_joueur_snapshot(_character())
	cible_c = _monstre(**m_stats)
	res_c = resolve_action(_combat(martial, [cible_c]), "sort", cible_id="monstre_0",
						   sort=_sort(jet="cc", degats="1D4"))

	assert res_m["hit"] is False   # pm_def 200 → seuil planché à 5
	assert res_c["hit"] is True    # cc 40 vs Ag 10 → seuil 80


def test_le_sort_martial_soustrait_les_PA(monkeypatch):
	# Contrepartie assumée : contourner la pm_def se paie en armure.
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 10)
	monkeypatch.setattr(combat_mod, "roll_dice", lambda n: 20)

	magique = build_joueur_snapshot(_character())
	cible_m = _monstre(pa=7)
	res_m = resolve_action(_combat(magique, [cible_m]), "sort", cible_id="monstre_0",
						   sort=_sort(degats="4D6"))

	martial = build_joueur_snapshot(_character())
	cible_c = _monstre(pa=7)
	res_c = resolve_action(_combat(martial, [cible_c]), "sort", cible_id="monstre_0",
						   sort=_sort(jet="cc", degats="4D6"))

	assert res_m["dmg"] == 20
	assert res_c["dmg"] == 13


def test_le_sort_martial_pose_quand_meme_sa_part_durative(monkeypatch):
	# Le mode de jet ne change QUE la résolution du toucher : le debuff suit.
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)
	snap, m = build_joueur_snapshot(_character()), _monstre(ag=10)
	resolve_action(_combat(snap, [m]), "sort", cible_id="monstre_0",
				   sort=_sort(jet="cc", degats="1D4", buffs={"F": -10}, duree=2))
	assert [e["restants"] for e in m["effets_actifs"]] == [2]


def test_jet_cd_utilise_la_capacite_de_tir(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)
	snap = build_joueur_snapshot(_character())
	m = _monstre(ag=10, pm_def=200)
	res = resolve_action(_combat(snap, [m]), "sort", cible_id="monstre_0",
						 sort=_sort(jet="cd", degats="1D4"))
	assert res["hit"] is True


# ── Défense physique : une seule définition pour les trois sites ─────────────────

def test_la_defense_physique_additionne_ag_et_esquive():
	assert _defense_physique({"ag": 30, "esquive": 12}) == 42
	assert _defense_physique({"ag": 30}) == 30
	assert _defense_physique({}) == 0


def test_l_esquive_de_la_cible_compte_face_a_un_sort_de_contact(monkeypatch):
	# Régression : les compétences ne lisaient que l'Ag, donc un buff d'esquive sur un
	# monstre était ignoré par elles et respecté par les armes. Les trois sites passent
	# désormais par _defense_physique.
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)

	nu = build_joueur_snapshot(_character())
	cible_nue = _monstre(ag=10)
	assert resolve_action(_combat(nu, [cible_nue]), "sort", cible_id="monstre_0",
						  sort=_sort(jet="cc", degats="1D4"))["hit"] is True

	pare = build_joueur_snapshot(_character())
	cible_esquive = _monstre(ag=10, esquive=90)
	assert resolve_action(_combat(pare, [cible_esquive]), "sort", cible_id="monstre_0",
						  sort=_sort(jet="cc", degats="1D4"))["hit"] is False


def test_l_esquive_ne_protege_pas_contre_un_sort_magique(monkeypatch):
	# L'esquive n'a rien à faire dans un jet magique : il passe par la pm_def.
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)
	snap = build_joueur_snapshot(_character())
	m = _monstre(pm_def=10, esquive=90)
	assert resolve_action(_combat(snap, [m]), "sort", cible_id="monstre_0",
						  sort=_sort(degats="1D4"))["hit"] is True
