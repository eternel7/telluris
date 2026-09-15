# tests/_fixtures_magie.py
#
# Fixtures PARTAGÉES par les huit fichiers de test des trois notions du temps magique
# (incantation, entretien, concentration) et des effets qui les accompagnent (drain,
# dégâts aux PM, coût en PV, saut, lien de vie).
#
# Même style que tests/test_combat_zone.py — snapshots RÉELS construits par le moteur
# (`build_joueur_snapshot` / `build_monster_snapshot`), aucun accès base. Un module à part
# plutôt qu'un copier-coller par fichier : ces huit tests éprouvent une seule mécanique
# vue sous huit angles, et huit copies des mêmes fixtures dériveraient à la première
# évolution du snapshot.
#
# ⚠️ Pas de `test_` dans le nom : pytest ne le collecte pas, il est seulement importé.

from utils.combat import build_joueur_snapshot, build_monster_snapshot
from utils.sorts import normaliser_sort


def character(**overrides):
	char = {
		"_id": "character:test_1", "nom": "Frida", "voc": "mage", "race": "humain",
		"caracteristiques_current": {"V": 5, "F": 40, "R": 30, "Ag": 40,
									 "Vol": 60, "Int": 60, "Cha": 20, "Ch": 20},
		"vocations_niveaux": {"mage": 1},
		"currentPV": 100, "currentPM": 60,
		"inventaire": [], "slots": {},
	}
	char.update(overrides)
	return char


def espece(**overrides):
	esp = {
		"_id": "espece:loup", "nom": "Loup", "tags": [],
		"base_attributes": {c: {"min": v, "max": v} for c, v in
							(("V", 4), ("F", 30), ("R", 30), ("Ag", 40),
							 ("Vol", 20), ("Int", 10), ("Cha", 10), ("Ch", 10))},
	}
	esp.update(overrides)
	return esp


def monstre(idx=0, x=6, y=5, pv=200, **overrides):
	m = build_monster_snapshot(espece(), None, idx)
	m["pos"] = {"x": x, "y": y}
	m["nom"] = f"Loup {idx}"
	m["currentPV"] = m["pv_max"] = pv
	m.update(overrides)
	return m


def joueur(idx=0, x=3, y=5, nom="Frida", pm=60, pv=100, **overrides):
	j = build_joueur_snapshot(character(_id=f"character:test_{idx}", nom=nom), idx)
	j["pos"] = {"x": x, "y": y}
	j["vivant"] = True
	# On n'éprouve jamais le TOUCHER dans ces fichiers : il a ses propres tests.
	j["cc"] = j["cd"] = j["toucher_magique"] = 200
	j["currentPM"] = j["pm_max"] = pm
	j["currentPV"] = j["pv_max"] = pv
	j.update(overrides)
	return j


def combat(joueurs, monstres=None, cells=None, dims=(12, 9)):
	monstres = monstres if monstres is not None else [monstre()]
	w, h = dims
	return {
		"_id": "combat:test", "type": "combat", "status": "active", "tour": 1, "log": [],
		"character_id": "character:test_0",
		"ordre_initiative": [j["id"] for j in joueurs if j.get("jouable") is not False]
							+ [m["id"] for m in monstres],
		"acteur_courant_index": 0,
		"joueurs": list(joueurs), "monstres": list(monstres),
		"grid": {"dims": {"x": w, "y": h},
				 "cells": cells or [[1] * w for _ in range(h)], "nav": {}},
	}


def sort(cout_pm=10, **champs):
	"""Couple `{doc, effets}` tel que routers/combat.py l'injecte dans resolve_action."""
	doc = {"_id": "sort:essai", "type": "sort", "vocation": "mage", "nom": "Sort d'essai",
		   "icon": "🔮", "cout_pm": max(1, cout_pm), "cible": "soi", "portee": 1,
		   "effets": {}, **champs}
	norm = normaliser_sort(doc)
	# Après normalisation : un doc `sort:*` exige cout_pm > 0, mais le moteur accepte 0.
	norm["cout_pm"] = cout_pm
	return {"doc": norm, "effets": norm["effets"], "composants_engages": [],
			"poids_consommes": 0}


def textes(combat_doc):
	"""Les lignes de journal, pour affirmer sur ce que le joueur LIT."""
	return [e["texte"] for e in combat_doc.get("log") or []]
