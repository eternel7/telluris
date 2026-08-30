# tests/test_effets_equipement.py
#
# Effets PERMANENTS conférés par un objet PORTÉ — `regen_pv`/`regen_pm`/`esquive` du champ
# `effets` d'un doc `item:*` qui n'est ni une arme ni un consommable (le focus magique et
# son `regen_pm` en sont le cas d'école).
#
# Deux trous fermés ici, aux deux bouts de la même chaîne :
#   1. `recompute_equipment_bonus` ne lisait pas du tout `effets` → ces clés étaient de la
#      donnée MORTE sur un objet équipé, y compris au tour de monde ;
#   2. `_tick_effets_combat` ne cumulait que les `effets_actifs` → même alimentée, la régén
#      n'aurait jamais joué pendant un combat, le seul moment où elle compte vraiment.
#
# ⚠️ Ces clés se déclarent dans `effets`, jamais dans `bonus` — qui ne porte que des
# CARACTÉRISTIQUES. Un `bonus:{esquive:…}` est inerte, et c'est épinglé ici (§4).
#
# Logique pure : `get_doc` est monkeypatché sur un catalogue en mémoire, aucun accès DB.

import pytest

from utils import characters as characters_mod
from utils import combat as combat_mod
from utils.characters import recompute_equipment_bonus, sync_equipment_bonus
from utils.combat import build_joueur_snapshot, _tick_effets_combat, _empiler_effet_combat
from utils.consommables import caracts_avec_buffs, esquive_bonus, regen_bonus


# ── Fixtures ─────────────────────────────────────────────────────────────────────

FOCUS = {  # l'objet du rapport : porté, ni arme ni consommable
	"_id": "item:focus_magique", "type": "item", "nom": "Focus magique", "icon": "🔮",
	"categorie": "catalyseur", "slots": ["main_gauche"], "poids": 0.3,
	"bonus_pm": 3, "effets": {"regen_pm": 1},
}

AMULETTE = {  # seconde source portée : les permanents s'ADDITIONNENT entre eux
	"_id": "item:amulette_vie", "type": "item", "nom": "Amulette de vie", "icon": "📿",
	"categorie": "bijou", "slots": ["cou"], "poids": 0.1,
	"effets": {"regen_pv": 2, "esquive": 3},
}

CAPE_FAUTIVE = {  # authoring fautif : `esquive` n'est pas une caractéristique
	"_id": "item:cape_fautive", "type": "item", "nom": "Cape mal écrite", "icon": "🧥",
	"categorie": "armure", "slots": ["epaules"], "poids": 1.0,
	"bonus": {"esquive": 5},
}

BOLAS = {  # arme : son `effets` vise l'ENNEMI à l'impact, jamais son porteur
	"_id": "item:Bolas", "type": "item", "nom": "Bolas", "categorie": "arme",
	"slots": ["main_droite"], "poids": 0.8, "tags": ["jet"], "portee": 3,
	"cible": "ennemi", "effets": {"buffs": {"V": -2}, "regen_pv": 9, "esquive": 7, "duree": 2},
}

POTION = {  # consommable : son `effets` s'applique à l'ingestion
	"_id": "item:remede", "type": "item", "nom": "Remède", "categorie": "consommable",
	"slots": [], "poids": 0.2, "effets": {"pv": 15, "duree": 5, "regen_pv": 3},
}

CATALOGUE = {d["_id"]: d for d in (FOCUS, AMULETTE, BOLAS, POTION, CAPE_FAUTIVE)}


@pytest.fixture(autouse=True)
def _items_en_memoire(monkeypatch):
	monkeypatch.setattr(characters_mod, "get_doc", lambda i: CATALOGUE.get(i))
	monkeypatch.setattr(combat_mod, "get_doc", lambda i: CATALOGUE.get(i))


def _character(slots=None, **overrides):
	char = {
		"_id": "character:test_1", "nom": "Frida", "voc": "mage", "race": "humain",
		"caracteristiques_current": {"V": 5, "F": 40, "R": 30, "Ag": 40,
									 "Vol": 40, "Int": 40, "Cha": 20, "Ch": 20},
		"vocations_niveaux": {"mage": 1},
		"currentPV": 100, "currentPM": 40,
		"inventaire": [], "slots": dict(slots or {}),
	}
	char.update(overrides)
	return char


def _combat(joueur):
	joueur.setdefault("pos", {"x": 3, "y": 5})
	joueur.setdefault("vivant", True)
	return {
		"_id": "combat:test", "type": "combat", "status": "active", "tour": 1, "log": [],
		"ordre_initiative": ["joueur_0"], "acteur_courant_index": 0,
		"joueurs": [joueur], "monstres": [],
		"grid": {"dims": {"x": 7, "y": 7},
				 "cells": [[1] * 7 for _ in range(7)], "nav": {}},
	}


# ── 1. L'agrégat d'équipement lit `effets` ───────────────────────────────────────

def test_objet_porte_alimente_la_regen_de_l_equipement():
	bonus = recompute_equipment_bonus({"main_gauche": "item:focus_magique"})
	assert bonus.regen_pm == 1
	assert bonus.regen_pv == 0


def test_deux_objets_portes_s_additionnent():
	# Les sources PERMANENTES s'additionnent (le non-cumul ne joue qu'entre effets à durée).
	bonus = recompute_equipment_bonus({
		"main_gauche": "item:focus_magique", "cou": "item:amulette_vie",
	})
	assert (bonus.regen_pv, bonus.regen_pm) == (2, 1)


def test_une_arme_ne_donne_jamais_sa_regen_a_son_porteur():
	# Le `effets` d'une arme vise la CIBLE (utils/sorts.effets_d_arme) : le replier ici
	# donnerait au porteur de bolas un −2 en V permanent ET 9 PV par tour.
	bonus = recompute_equipment_bonus({"main_droite": "item:Bolas"})
	assert (bonus.regen_pv, bonus.regen_pm) == (0, 0)
	assert "V" not in bonus.buffs


def test_un_consommable_equipe_ne_donne_pas_sa_regen():
	# Aucun slot ne l'accepte en jeu, mais un doc bricolé ne doit pas ouvrir de canal :
	# l'effet d'une potion s'applique à l'ingestion, pas au portage.
	bonus = recompute_equipment_bonus({"ceinture": "item:remede"})
	assert (bonus.regen_pv, bonus.regen_pm) == (0, 0)


# ── 2. Le tour de MONDE en profite (via le chokepoint regen_bonus) ───────────────

def test_regen_bonus_replie_l_objet_porte():
	char = _character(slots={"main_gauche": "item:focus_magique"})
	sync_equipment_bonus(char)
	assert regen_bonus(char) == (0, 1)


def test_regen_bonus_additionne_objet_porte_et_effet_a_duree():
	char = _character(
		slots={"main_gauche": "item:focus_magique"},
		effets_actifs=[{"nom": "Encens", "icon": "🕯", "buffs": {},
						"regen_pv": 0, "regen_pm": 2, "esquive": 0, "restants": 3}],
	)
	sync_equipment_bonus(char)
	assert regen_bonus(char) == (0, 3)


# ── 3. Le tour de COMBAT en profite — c'est la demande ───────────────────────────

def test_le_snapshot_porte_la_part_permanente_seule():
	char = _character(
		slots={"main_gauche": "item:focus_magique"},
		effets_actifs=[{"nom": "Encens", "icon": "🕯", "buffs": {},
						"regen_pv": 0, "regen_pm": 2, "esquive": 0, "restants": 3}],
	)
	snap = build_joueur_snapshot(char)
	# `regen_pm_base` = l'objet SEUL : l'effet à durée vit dans `effets_actifs` et varie.
	assert snap["regen_pm_base"] == 1
	assert snap["regen_pv_base"] == 0


def test_l_objet_porte_regenere_a_chaque_tour_SANS_aucun_effet_actif():
	# Le cœur du défaut : `_tick_effets_combat` sortait en tête sur `not actifs`.
	char = _character(slots={"main_gauche": "item:focus_magique"}, currentPM=0)
	snap = build_joueur_snapshot(char)
	combat = _combat(snap)
	_tick_effets_combat(combat, snap)
	assert snap["currentPM"] == 1
	combat["tour"] = 2
	_tick_effets_combat(combat, snap)
	assert snap["currentPM"] == 2


def test_en_combat_le_permanent_s_ajoute_au_meilleur_effet_a_duree():
	# Même arithmétique que `regen_bonus` : permanents additifs, non-cumul entre effets.
	char = _character(slots={"main_gauche": "item:focus_magique"}, currentPM=0)
	snap = build_joueur_snapshot(char)
	combat = _combat(snap)
	_empiler_effet_combat(snap, {"nom": "Encens", "icon": "🕯"},
						  {"regen_pm": 2, "duree": 5}, tour=0)
	_empiler_effet_combat(snap, {"nom": "Bougie", "icon": "🕯"},
						  {"regen_pm": 3, "duree": 5}, tour=0)
	_tick_effets_combat(combat, snap)
	assert snap["currentPM"] == 4   # 1 (objet) + max(2, 3), et non 1 + 2 + 3


def test_la_regen_de_combat_est_clampee_au_maximum():
	char = _character(slots={"main_gauche": "item:focus_magique"})
	snap = build_joueur_snapshot(char)
	snap["currentPM"] = snap["pm_max"]
	combat = _combat(snap)
	_tick_effets_combat(combat, snap)
	assert snap["currentPM"] == snap["pm_max"]


def test_un_combat_deja_en_base_ne_regenere_pas_et_ne_casse_pas():
	# Aucune migration : un snapshot d'avant la feature n'a pas les champs `regen_*_base`.
	snap = build_joueur_snapshot(_character(currentPM=0))
	snap.pop("regen_pv_base", None)
	snap.pop("regen_pm_base", None)
	combat = _combat(snap)
	_tick_effets_combat(combat, snap)
	assert snap["currentPM"] == 0


# ── 4. Esquive : même canal `effets`, JAMAIS `bonus` ─────────────────────────────

def test_objet_porte_alimente_l_esquive():
	bonus = recompute_equipment_bonus({"cou": "item:amulette_vie"})
	assert bonus.esquive == 3


def test_esquive_dans_bonus_reste_inerte():
	# `bonus` ne porte que des CARACTÉRISTIQUES : `caracts_avec_buffs` écarte toute clé
	# absente de `caracteristiques_current`. Le canal de l'esquive est `effets`, et lui
	# seul — ce test épingle que l'autre écriture ne fait rien, plutôt qu'un demi-effet.
	char = _character(slots={"epaules": "item:cape_fautive"})
	sync_equipment_bonus(char)
	assert esquive_bonus(char) == 0
	assert char["caracteristiques_current"]["Ag"] == caracts_avec_buffs(char)["Ag"]


def test_esquive_bonus_replie_l_objet_porte():
	char = _character(slots={"cou": "item:amulette_vie"})
	sync_equipment_bonus(char)
	assert esquive_bonus(char) == 3


def test_esquive_permanente_et_effet_a_duree_s_additionnent():
	# Permanents additifs, non-cumul (max) entre effets à durée — comme la régén.
	char = _character(
		slots={"cou": "item:amulette_vie"},
		effets_actifs=[{"nom": "Danse", "icon": "💨", "buffs": {},
						"regen_pv": 0, "regen_pm": 0, "esquive": 4, "restants": 3}],
	)
	sync_equipment_bonus(char)
	assert esquive_bonus(char) == 7


def test_le_snapshot_de_combat_porte_l_esquive_de_l_objet():
	char = _character(slots={"cou": "item:amulette_vie"})
	snap = build_joueur_snapshot(char)
	assert snap["esquive_base"] == 3
	assert snap["esquive"] == 3


def test_une_arme_ne_donne_jamais_son_esquive():
	bonus = recompute_equipment_bonus({"main_droite": "item:Bolas"})
	assert bonus.esquive == 0
