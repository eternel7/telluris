"""Échange de place avec un allié NON JOUABLE (utils/combat.py, action `deplacer`).

Une monture et une personne escortée vivent dans `joueurs` (donc ciblables), mais elles
sont `jouable: False` et `deplacement: 0` : elles n'ont ni tour ni budget de déplacement.
Comptées comme occupants par `_occupied_set`, elles ENFERMAIENT le joueur pour tout le
combat dès qu'elles se posaient dans un couloir. Le pas devient donc une PERMUTATION —
refusée si l'un des deux ne peut pas tenir sur la case de l'autre (falaise vs vol).

Tests purs : docs à la main, aucune DB (seul `random` est neutralisé, comme dans
tests/test_combat_journal_etat.py, dont les fixtures sont reprises).
"""
import pytest

from utils import combat as combat_mod
from utils.lieux import VALID_MOVES


def _bit(dx, dy):
	"""Bit d'INTERDICTION de la direction (dx,dy) — dérivé, jamais recopié."""
	return next(b for b, x, y, _op in VALID_MOVES if (x, y) == (dx, dy))


def _character(nom="Frida", cid="character:test_1"):
	return {
		"_id": cid, "nom": nom, "voc": "guerrier", "race": "humain",
		"caracteristiques_current": {"V": 5, "F": 40, "R": 30, "Ag": 40,
									 "Vol": 30, "Int": 20, "Cha": 20, "Ch": 20},
		"vocations_niveaux": {"guerrier": 1},
		"currentPV": 100, "currentPM": 20, "inventaire": [], "slots": {},
	}


def _espece():
	return {"_id": "espece:loup", "nom": "Loup", "tags": [],
			"base_attributes": {c: {"min": v, "max": v} for c, v in
								(("V", 4), ("F", 30), ("R", 30), ("Ag", 40),
								 ("Vol", 20), ("Int", 10), ("Cha", 10), ("Ch", 10))}}


def _joueur(monkeypatch, index=0, nom="Frida", **champs):
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)
	snap = combat_mod.build_joueur_snapshot(
		_character(nom, f"character:test_{index + 1}"), index)
	snap["vivant"] = True
	snap.update(champs)
	return snap


def _hors_tour(monkeypatch, index, nom="Âne", **champs):
	"""Snapshot d'un acteur NON JOUABLE : monture par défaut, immobile et hors initiative."""
	snap = _joueur(monkeypatch, index, nom)
	snap.update({"jouable": False, "est_monture": True,
				 "deplacement": 0, "deplacement_base": 0})
	snap.update(champs)
	return snap


def _combat(joueurs, monstres=(), cells=None, nav=None):
	"""Grille 7×7 entièrement praticable par défaut ; chaque acteur doit porter sa `pos`."""
	return {
		"_id": "combat:test", "type": "combat", "status": "active", "tour": 1, "log": [],
		"ordre_initiative": ["joueur_0"] + [m["id"] for m in monstres],
		"acteur_courant_index": 0,
		"joueurs": list(joueurs), "monstres": list(monstres),
		"grid": {"dims": {"x": 7, "y": 7},
				 "cells": cells if cells is not None else [[1] * 7 for _ in range(7)],
				 "nav": nav or {}},
	}


def _monstre(monkeypatch, x, y):
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)
	m = combat_mod.build_monster_snapshot(_espece(), None, 0)
	m["pos"] = {"x": x, "y": y}
	return m


def _falaises(*cases):
	cells = [[1] * 7 for _ in range(7)]
	for x, y in cases:
		cells[y][x] = combat_mod.TERRAIN_FALAISE
	return cells


# ── L'échange lui-même ───────────────────────────────────────────────────────────

def test_echange_avec_une_monture(monkeypatch):
	"""Le pas vers la case d'une monture PERMUTE les deux acteurs."""
	joueur = _joueur(monkeypatch, 0, pos={"x": 3, "y": 5})
	ane = _hors_tour(monkeypatch, 1, pos={"x": 4, "y": 5})
	combat = _combat([joueur, ane])

	res = combat_mod.resolve_action(combat, "deplacer", dx=1, dy=0)

	assert res == {"moved": True, "pos": {"x": 4, "y": 5}}
	assert joueur["pos"] == {"x": 4, "y": 5}
	assert ane["pos"] == {"x": 3, "y": 5}
	assert joueur["cells_moved"] == 1


def test_echange_avec_une_personne_escortee(monkeypatch):
	"""C'est `jouable`, et non `est_monture`, qui décide : un protégé s'échange aussi."""
	joueur = _joueur(monkeypatch, 0, pos={"x": 3, "y": 5})
	protege = _hors_tour(monkeypatch, 1, nom="Aloïs", pos={"x": 3, "y": 4},
						 est_monture=False, est_protege=True)
	combat = _combat([joueur, protege])

	assert combat_mod.resolve_action(combat, "deplacer", dx=0, dy=-1)["moved"] is True
	assert joueur["pos"] == {"x": 3, "y": 4}
	assert protege["pos"] == {"x": 3, "y": 5}


def test_lechange_est_soumis_au_budget_de_deplacement(monkeypatch):
	"""Il coûte un pas comme les autres : budget épuisé, il est refusé."""
	joueur = _joueur(monkeypatch, 0, pos={"x": 3, "y": 5})
	joueur["cells_moved"] = joueur["deplacement"]
	ane = _hors_tour(monkeypatch, 1, pos={"x": 4, "y": 5})
	combat = _combat([joueur, ane])

	assert combat_mod.resolve_action(combat, "deplacer", dx=1, dy=0) == {
		"error": "Budget de déplacement épuisé."}
	assert joueur["pos"] == {"x": 3, "y": 5}
	assert ane["pos"] == {"x": 4, "y": 5}


def test_le_journal_nomme_les_deux_acteurs(monkeypatch):
	"""⚠️ L'échangé DOIT être dans `etat` : absent, son jeton suivrait l'état final tout de
	suite pendant que celui du joueur attend la révélation — les corps se dissocieraient."""
	joueur = _joueur(monkeypatch, 0, pos={"x": 3, "y": 5})
	ane = _hors_tour(monkeypatch, 1, pos={"x": 4, "y": 5})
	combat = _combat([joueur, ane])

	combat_mod.resolve_action(combat, "deplacer", dx=1, dy=0)
	ligne = next(e for e in combat["log"] if e["kind"] == "move")

	assert "échange sa place avec Âne" in ligne["texte"]
	assert ligne["etat"]["joueur_0"]["pos"] == {"x": 4, "y": 5}
	assert ligne["etat"]["joueur_1"]["pos"] == {"x": 3, "y": 5}
	# COPIE : le snapshot garde son dict d'un pas à l'autre.
	ane["pos"]["x"] = 99
	assert ligne["etat"]["joueur_1"]["pos"]["x"] != 99


# ── Qui NE s'échange pas ─────────────────────────────────────────────────────────

def test_un_monstre_bloque_toujours(monkeypatch):
	joueur = _joueur(monkeypatch, 0, pos={"x": 3, "y": 5})
	loup = _monstre(monkeypatch, 4, 5)
	combat = _combat([joueur], [loup])

	assert combat_mod.resolve_action(combat, "deplacer", dx=1, dy=0) == {
		"error": "Case occupée."}
	assert joueur["pos"] == {"x": 3, "y": 5}
	assert loup["pos"] == {"x": 4, "y": 5}


def test_un_compagnon_jouable_bloque_toujours(monkeypatch):
	"""⚠️ Un joueur ordinaire n'a PAS la clé `jouable` : le test doit être `is False`, sinon
	tout le groupe deviendrait échangeable. Un compagnon a son propre tour pour s'écarter."""
	joueur = _joueur(monkeypatch, 0, pos={"x": 3, "y": 5})
	compagnon = _joueur(monkeypatch, 1, nom="Borin", pos={"x": 4, "y": 5})
	combat = _combat([joueur, compagnon])

	assert "jouable" not in compagnon
	assert combat_mod.resolve_action(combat, "deplacer", dx=1, dy=0) == {
		"error": "Case occupée."}
	assert compagnon["pos"] == {"x": 4, "y": 5}


def test_un_allie_a_terre_noccupe_rien(monkeypatch):
	"""Cohérent avec `_occupied_set` : à 0 PV la case est libre, c'est un pas ordinaire."""
	joueur = _joueur(monkeypatch, 0, pos={"x": 3, "y": 5})
	ane = _hors_tour(monkeypatch, 1, pos={"x": 4, "y": 5}, currentPV=0)
	combat = _combat([joueur, ane])

	assert combat_mod.resolve_action(combat, "deplacer", dx=1, dy=0)["moved"] is True
	assert joueur["pos"] == {"x": 4, "y": 5}
	assert ane["pos"] == {"x": 4, "y": 5}      # elle n'a pas bougé
	assert "se déplace" in next(e for e in combat["log"] if e["kind"] == "move")["texte"]


# ── La règle demandée : chacun doit tenir sur la case de l'autre ─────────────────

def test_refus_si_lallie_ne_peut_tenir_sur_la_case_du_joueur(monkeypatch):
	"""Joueur VOLANT sur une falaise : la monture ne peut pas l'y remplacer."""
	joueur = _joueur(monkeypatch, 0, pos={"x": 3, "y": 5}, volant=True)
	ane = _hors_tour(monkeypatch, 1, pos={"x": 4, "y": 5})
	combat = _combat([joueur, ane], cells=_falaises((3, 5)))

	assert combat_mod.resolve_action(combat, "deplacer", dx=1, dy=0) == {
		"error": "Âne ne peut pas tenir sur votre case."}
	assert joueur["pos"] == {"x": 3, "y": 5}
	assert ane["pos"] == {"x": 4, "y": 5}
	assert joueur["cells_moved"] == 0


def test_echange_accepte_si_les_deux_volent(monkeypatch):
	joueur = _joueur(monkeypatch, 0, pos={"x": 3, "y": 5}, volant=True)
	ane = _hors_tour(monkeypatch, 1, pos={"x": 4, "y": 5}, volant=True)
	combat = _combat([joueur, ane], cells=_falaises((3, 5)))

	assert combat_mod.resolve_action(combat, "deplacer", dx=1, dy=0)["moved"] is True
	assert ane["pos"] == {"x": 3, "y": 5}


def test_refus_si_le_joueur_ne_peut_tenir_sur_la_case_de_lallie(monkeypatch):
	"""L'autre sens est rendu par la garde ALLER, déjà en place — pas de doublon."""
	joueur = _joueur(monkeypatch, 0, pos={"x": 3, "y": 5})
	ane = _hors_tour(monkeypatch, 1, pos={"x": 4, "y": 5}, volant=True)
	combat = _combat([joueur, ane], cells=_falaises((4, 5)))

	assert combat_mod.resolve_action(combat, "deplacer", dx=1, dy=0) == {
		"error": "Terrain infranchissable."}
	assert ane["pos"] == {"x": 4, "y": 5}


def test_echange_soumis_a_nav(monkeypatch):
	"""Un mur nav entre les deux cases refuse l'échange comme il refuse le pas.
	⚠️ Un seul contrôle : `get_final_mask` est bidirectionnel, la direction retour suit."""
	joueur = _joueur(monkeypatch, 0, pos={"x": 3, "y": 5})
	ane = _hors_tour(monkeypatch, 1, pos={"x": 4, "y": 5})
	combat = _combat([joueur, ane], nav={"3,5": _bit(1, 0)})

	assert combat_mod.resolve_action(combat, "deplacer", dx=1, dy=0) == {
		"error": "Direction bloquée."}
	assert ane["pos"] == {"x": 4, "y": 5}


# ── Les prédicats purs ───────────────────────────────────────────────────────────

def test_echange_possible_est_symetrique():
	cells = _falaises((1, 1))
	sol = {"pos": {"x": 0, "y": 0}}
	falaise_volant = {"pos": {"x": 1, "y": 1}, "volant": True}
	assert combat_mod._echange_possible(cells, sol, falaise_volant) is False
	assert combat_mod._echange_possible(cells, falaise_volant, sol) is False


def test_echange_possible_deux_volants_sur_falaise():
	cells = _falaises((1, 1), (2, 2))
	a = {"pos": {"x": 1, "y": 1}, "volant": True}
	b = {"pos": {"x": 2, "y": 2}, "volant": True}
	assert combat_mod._echange_possible(cells, a, b) is True


def test_allie_echangeable_ne_voit_que_les_non_jouables(monkeypatch):
	joueur = _joueur(monkeypatch, 0, pos={"x": 3, "y": 5})
	compagnon = _joueur(monkeypatch, 1, nom="Borin", pos={"x": 4, "y": 5})
	ane = _hors_tour(monkeypatch, 2, pos={"x": 2, "y": 5})
	combat = _combat([joueur, compagnon, ane])

	assert combat_mod._allie_echangeable(combat, 4, 5) is None
	assert combat_mod._allie_echangeable(combat, 3, 5) is None
	assert combat_mod._allie_echangeable(combat, 2, 5) is ane
	assert combat_mod._allie_echangeable(combat, 0, 0) is None
