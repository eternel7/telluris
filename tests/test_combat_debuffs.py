# tests/test_combat_debuffs.py
#
# Effets à durée sur une CIBLE ENNEMIE : un sort/une compétence offensif dont les effets
# portent une part durative (buffs négatifs, régén, esquive) l'empile sur le snapshot du
# MONSTRE touché, qui la subit, la décrémente à SES tours et la voit expirer.
#
# Miroir exact de tests/test_combat_effets.py (part « sur soi ») — mêmes fixtures, aucun
# accès DB : `slots` vide côté joueur, monstre bâti par build_monster_snapshot.

import pytest

from utils import combat as combat_mod
from utils.combat import (
	build_joueur_snapshot, build_monster_snapshot, resolve_action,
	_reset_turn_budget, _refresh_snapshot_stats,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────────

def _character(**overrides):
	char = {
		"_id": "character:test_1", "nom": "Frida", "voc": "elementaliste", "race": "humain",
		"caracteristiques_current": {"V": 5, "F": 40, "R": 30, "Ag": 40,
									 "Vol": 40, "Int": 60, "Cha": 20, "Ch": 20},
		"vocations_niveaux": {"elementaliste": 1},
		"currentPV": 100, "currentPM": 40,
		"inventaire": [], "slots": {},
	}
	char.update(overrides)
	return char


def _espece(**overrides):
	base = {
		"_id": "espece:loup", "nom": "Loup", "tags": [],
		"base_attributes": {c: {"min": v, "max": v} for c, v in
							(("V", 4), ("F", 30), ("R", 30), ("Ag", 40),
							 ("Vol", 20), ("Int", 10), ("Cha", 10), ("Ch", 10))},
	}
	base.update(overrides)
	return base


def _monstre(idx=0, **overrides):
	m = build_monster_snapshot(_espece(), None, idx)
	m["pos"] = {"x": 3, "y": 4}
	m.update(overrides)
	return m


def _combat(joueur, monstres):
	joueur["pos"] = {"x": 3, "y": 5}   # adjacent au monstre : portée 1 suffit
	joueur["vivant"] = True
	return {
		"_id": "combat:test", "type": "combat", "status": "active", "tour": 1, "log": [],
		"ordre_initiative": ["joueur_0"] + [m["id"] for m in monstres],
		"acteur_courant_index": 0,
		"joueurs": [joueur], "monstres": monstres,
		"grid": {"dims": {"x": 7, "y": 7},
				 "cells": [[1] * 7 for _ in range(7)], "nav": {}},
	}


def _sort(nom="Éclat de givre", cible="ennemi", portee=1, cout_pm=0, **effets):
	"""Couple (doc, effets) tel que le router l'injecte dans resolve_action."""
	doc = {"_id": "sort:givre", "nom": nom, "icon": "❄️", "cible": cible,
		   "cout_pm": cout_pm, "portee": portee, "effets": effets}
	return {"doc": doc, "effets": effets}


def _touche_toujours(monkeypatch):
	"""Jet à 50 : au-dessus de la fenêtre de critique (≤5 / ≥96), sous un seuil large."""
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)


def _rate_toujours(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 95)


# ── Le monstre est recalculable ──────────────────────────────────────────────────

def test_snapshot_monstre_porte_de_quoi_se_recalculer():
	# Sans caracts_base, _refresh_snapshot_stats sort sans rien toucher : un debuff
	# posé sur un monstre serait inerte. C'est l'invariant qui ouvre toute la feature.
	m = _monstre()
	assert m["caracts_base"]["Ag"] == 40
	assert m["effets_actifs"] == []
	assert m["esquive_base"] == 0


def test_refresh_sur_monstre_neuf_ne_change_rien():
	# Le recalcul doit coïncider avec la dérivation d'origine, sinon le seul fait de
	# poser puis retirer un effet déplacerait les stats du monstre.
	m = _monstre()
	avant = {k: m[k] for k in ("cc", "pa", "pv_max", "initiative", "deplacement", "ag")}
	_refresh_snapshot_stats(m)
	assert {k: m[k] for k in avant} == avant


# ── Pose du debuff ───────────────────────────────────────────────────────────────

def test_sort_offensif_pose_sa_part_durative_sur_la_cible(monkeypatch):
	_touche_toujours(monkeypatch)
	snap, m = build_joueur_snapshot(_character()), _monstre()
	combat = _combat(snap, [m])
	ag_avant = m["ag"]

	res = resolve_action(combat, "sort", cible_id="monstre_0",
						 sort=_sort(degats="1D4", buffs={"Ag": -10}, duree=2))

	assert "error" not in res and res["hit"] is True
	assert res["effet_cible"]["restants"] == 2
	assert [e["nom"] for e in m["effets_actifs"]] == ["Éclat de givre"]
	assert m["ag"] == ag_avant - 10


def test_le_debuff_pese_reellement_sur_les_derivees_de_la_cible(monkeypatch):
	_touche_toujours(monkeypatch)
	snap, m = build_joueur_snapshot(_character()), _monstre()
	combat = _combat(snap, [m])
	avant = {k: m[k] for k in ("cc", "initiative", "ag")}

	resolve_action(combat, "sort", cible_id="monstre_0",
				   sort=_sort(degats="1D4", buffs={"Ag": -20}, duree=2))

	# cc = (F + Ag*3)//4 et initiative = (Ag + V*20)//3 : les deux baissent.
	assert m["ag"] < avant["ag"]
	assert m["cc"] < avant["cc"]
	assert m["initiative"] < avant["initiative"]


def test_un_sort_de_pur_debuff_est_lancable(monkeypatch):
	# Sans dégâts du tout : le sort n'est plus refusé, il touche et pose son effet.
	_touche_toujours(monkeypatch)
	snap, m = build_joueur_snapshot(_character()), _monstre()
	combat = _combat(snap, [m])
	pv_avant = m["currentPV"]

	res = resolve_action(combat, "sort", cible_id="monstre_0",
						 sort=_sort(buffs={"Ag": -10}, duree=3))

	assert "error" not in res
	assert res["dmg"] == 0 and m["currentPV"] == pv_avant   # touche sans blesser
	assert m["effets_actifs"][0]["restants"] == 3


def test_un_debuff_de_F_ou_de_R_rogne_les_PV_par_le_re_clamp(monkeypatch):
	# Conséquence ASSUMÉE (et déjà vraie pour les joueurs) : pv_max = R*3 + F, donc
	# affaiblir R ou F abaisse le plafond et re-clampe les PV courants. Un debuff de
	# constitution fait donc mal — le documenter ici évite de le « corriger » plus tard.
	_touche_toujours(monkeypatch)
	snap, m = build_joueur_snapshot(_character()), _monstre()
	combat = _combat(snap, [m])
	pv_avant = m["currentPV"]

	resolve_action(combat, "sort", cible_id="monstre_0",
				   sort=_sort(buffs={"F": -10}, duree=3))

	assert m["currentPV"] < pv_avant


def test_sort_sans_degats_ni_duree_reste_refuse():
	snap, m = build_joueur_snapshot(_character()), _monstre()
	combat = _combat(snap, [m])
	res = resolve_action(combat, "sort", cible_id="monstre_0", sort=_sort())
	assert "error" in res


def test_competence_offensive_pose_sa_part_durative(monkeypatch):
	_touche_toujours(monkeypatch)
	snap, m = build_joueur_snapshot(_character()), _monstre()
	combat = _combat(snap, [m])

	res = resolve_action(combat, "competence", cible_id="monstre_0", competence={
		"nom": "Entrave", "icon": "🪢", "cible": "ennemi", "jet": "magique",
		"cout_pm": 0, "portee": 1,
		"effets": {"degats": "1D4", "buffs": {"Ag": -10}, "duree": 2}})

	assert "error" not in res and res["hit"] is True
	assert [e["nom"] for e in m["effets_actifs"]] == ["Entrave"]


# ── Ce qui NE pose PAS le debuff ─────────────────────────────────────────────────

def test_un_sort_qui_rate_ne_debuffe_personne(monkeypatch):
	_rate_toujours(monkeypatch)
	snap, m = build_joueur_snapshot(_character()), _monstre()
	combat = _combat(snap, [m])

	res = resolve_action(combat, "sort", cible_id="monstre_0",
						 sort=_sort(degats="1D4", buffs={"Ag": -10}, duree=2))

	assert res["hit"] is False
	assert m["effets_actifs"] == []


def test_une_cible_abattue_par_le_coup_n_est_pas_debuffee(monkeypatch):
	_touche_toujours(monkeypatch)
	snap = build_joueur_snapshot(_character())
	m = _monstre(currentPV=1)
	combat = _combat(snap, [m])

	resolve_action(combat, "sort", cible_id="monstre_0",
				   sort=_sort(degats="4D6", buffs={"Ag": -10}, duree=2))

	assert m["vivant"] is False
	assert m["effets_actifs"] == []


# ── Durée : elle compte en tours de la CIBLE ─────────────────────────────────────

def test_le_debuff_se_decremente_aux_tours_de_la_cible(monkeypatch):
	_touche_toujours(monkeypatch)
	snap, m = build_joueur_snapshot(_character()), _monstre()
	combat = _combat(snap, [m])
	ag_nu = m["ag"]

	resolve_action(combat, "sort", cible_id="monstre_0",
				   sort=_sort(buffs={"Ag": -10}, duree=2))

	# Tour de pose épargné par le tick (pose_tour == tour courant) : l'effet sert
	# pleinement au premier tour du monstre.
	_reset_turn_budget(m, combat)
	assert m["effets_actifs"][0]["restants"] == 2
	assert m["ag"] == ag_nu - 10

	combat["tour"] = 2
	_reset_turn_budget(m, combat)
	assert m["effets_actifs"][0]["restants"] == 1

	combat["tour"] = 3
	_reset_turn_budget(m, combat)
	assert m["effets_actifs"] == []
	assert m["ag"] == ag_nu          # les dérivées reviennent à la normale


def test_expiration_journalisee(monkeypatch):
	_touche_toujours(monkeypatch)
	snap, m = build_joueur_snapshot(_character()), _monstre()
	combat = _combat(snap, [m])
	resolve_action(combat, "sort", cible_id="monstre_0",
				   sort=_sort(buffs={"Ag": -10}, duree=1))
	combat["tour"] = 2
	_reset_turn_budget(m, combat)
	assert any("se dissipe" in e["texte"] for e in combat["log"])


def test_la_pose_est_journalisee(monkeypatch):
	_touche_toujours(monkeypatch)
	snap, m = build_joueur_snapshot(_character()), _monstre()
	combat = _combat(snap, [m])
	resolve_action(combat, "sort", cible_id="monstre_0",
				   sort=_sort(buffs={"Ag": -10}, duree=2))
	assert any("subit" in e["texte"] and "tour(s)" in e["texte"] for e in combat["log"])


# ── Garde-fous ───────────────────────────────────────────────────────────────────

def test_un_debuff_de_R_extreme_ne_tue_pas_la_cible(monkeypatch):
	# pv_max est planché à 1 : sans ce plancher, le re-clamp mettrait currentPV à 0
	# sans lever `vivant` — un cadavre debout qui bloquerait le combat.
	_touche_toujours(monkeypatch)
	snap, m = build_joueur_snapshot(_character()), _monstre()
	combat = _combat(snap, [m])

	resolve_action(combat, "sort", cible_id="monstre_0",
				   sort=_sort(buffs={"R": -999, "F": -999}, duree=2))

	assert m["pv_max"] >= 1
	assert m["currentPV"] >= 1 and m["vivant"] is True


def test_le_debuff_ne_touche_pas_actions_max(monkeypatch):
	# Même exclusion que pour les joueurs : actions_restantes est RECALCULÉ depuis
	# actions_max − Σ compteurs. Un actions_max mouvant offrirait des tours gratuits.
	_touche_toujours(monkeypatch)
	snap, m = build_joueur_snapshot(_character()), _monstre()
	combat = _combat(snap, [m])
	avant = m["actions_max"]

	resolve_action(combat, "sort", cible_id="monstre_0",
				   sort=_sort(buffs={"Ag": -40, "V": -3}, duree=2))

	assert m["actions_max"] == avant


def test_debuff_sur_une_monture_ne_la_remet_pas_en_marche():
	# Une monture est ciblable (elle vit dans `joueurs`) mais immobilisée à 0 case.
	# Le recalcul déclenché par un effet ne doit pas lui rendre son déplacement.
	monture = build_joueur_snapshot(_character())
	monture["est_monture"] = True
	monture["jouable"] = False
	monture["deplacement"] = 0
	combat_mod._empiler_effet_combat(
		monture, {"nom": "Cri", "icon": "📣"}, {"buffs": {"V": -1}, "duree": 2}, 1)
	assert monture["deplacement"] == 0


# ── Non-cumul (cf. utils/consommables : poser_effet / cumul_effets) ───────────────

def test_relancer_le_meme_debuff_ne_l_empile_pas(monkeypatch):
	# Une source = une entrée, sur la cible comme sur soi : re-lancer le même sort
	# rafraîchit le debuff au lieu d'en ajouter un second qui doublerait le malus.
	_touche_toujours(monkeypatch)
	snap, m = build_joueur_snapshot(_character()), _monstre()
	combat = _combat(snap, [m])
	ag_avant = m["ag"]

	resolve_action(combat, "sort", cible_id="monstre_0",
				   sort=_sort(buffs={"Ag": -10}, duree=2))
	assert m["ag"] == ag_avant - 10

	_reset_turn_budget(snap, combat)          # nouveau tour du joueur, budget rendu
	resolve_action(combat, "sort", cible_id="monstre_0",
				   sort=_sort(buffs={"Ag": -10}, duree=2))

	assert len(m["effets_actifs"]) == 1
	assert m["effets_actifs"][0]["restants"] == 2
	assert m["ag"] == ag_avant - 10           # PAS -20


def test_deux_debuffs_differents_ne_se_cumulent_pas_sur_la_meme_caract(monkeypatch):
	# Deux sorts distincts coexistent, mais seul le PIRE malus s'applique.
	_touche_toujours(monkeypatch)
	snap, m = build_joueur_snapshot(_character()), _monstre()
	combat = _combat(snap, [m])
	ag_avant = m["ag"]

	resolve_action(combat, "sort", cible_id="monstre_0",
				   sort=_sort(nom="Givre", buffs={"Ag": -10}, duree=2))
	_reset_turn_budget(snap, combat)
	resolve_action(combat, "sort", cible_id="monstre_0",
				   sort={"doc": {"_id": "sort:vase", "nom": "Vase", "icon": "🪣",
								 "cible": "ennemi", "cout_pm": 0, "portee": 1,
								 "effets": {"buffs": {"Ag": -4}, "duree": 5}},
						 "effets": {"buffs": {"Ag": -4}, "duree": 5}})

	assert len(m["effets_actifs"]) == 2
	assert m["ag"] == ag_avant - 10           # le pire, pas -14
