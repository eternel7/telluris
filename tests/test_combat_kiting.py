# tests/test_combat_kiting.py
#
# IA de distance d'un monstre humanoïde armé : garde ses distances s'il est équipé à
# distance (tir/jet) et que le joueur s'est trop approché, approche sinon — inchangé
# pour un monstre non-humanoïde ou mêlée. Fixtures reprises de tests/test_combat_jetons.py
# (get_doc/random neutralisés, aucune dépendance DB).

from utils import combat as combat_mod
from utils import characters as characters_mod


ARC = {
	"_id": "item:Arc_court", "type": "item", "nom": "Arc court", "categorie": "arme",
	"slots": ["main_droite"], "tags": ["tir"], "portee": 4, "deux_mains": True,
}
HALLEBARDE = {
	"_id": "item:Hallebarde", "type": "item", "nom": "Hallebarde", "categorie": "arme",
	"slots": ["main_droite"], "tags": [], "portee": 2, "deux_mains": True,
}
CATALOGUE = {d["_id"]: d for d in (ARC, HALLEBARDE)}


def _equiper(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "random", lambda: 0.0)
	monkeypatch.setattr(combat_mod.random, "shuffle", lambda l: None)
	monkeypatch.setattr(combat_mod.random, "choice", lambda opts: opts[0])
	monkeypatch.setattr(combat_mod, "get_doc", lambda i: CATALOGUE.get(i))
	monkeypatch.setattr(characters_mod, "get_doc", lambda i: CATALOGUE.get(i))


def _espece(tags=("humanoide",), items=(), v=6, jeton=None):
	e = {
		"_id": "espece:test", "nom": "Cobaye", "tags": list(tags), "items": list(items),
		"base_attributes": {
			"V": {"min": v, "max": v}, "F": {"min": 24, "max": 24},
			"R": {"min": 20, "max": 20}, "Ag": {"min": 40, "max": 40},
			"Vol": {"min": 10, "max": 10}, "Int": {"min": 10, "max": 10},
			"Cha": {"min": 10, "max": 10}, "Ch": {"min": 10, "max": 10},
		},
	}
	if jeton:
		e["jeton"] = jeton
	return e


def _monstre(x, y, espece_doc, idx=0):
	m = combat_mod.build_monster_snapshot(espece_doc, None, idx)
	m["pos"] = {"x": x, "y": y}
	m["vivant"] = True
	return m


def _character(nom="Frida"):
	return {
		"_id": f"character:{nom}", "user_id": "user:test", "nom": nom, "voc": "guerrier",
		"race": "humain",
		"caracteristiques_current": {"V": 5, "F": 30, "R": 30, "Ag": 30,
									 "Vol": 20, "Int": 20, "Cha": 20, "Ch": 20},
		"vocations_niveaux": {"guerrier": 1},
		"currentPV": 100, "currentPM": 20, "inventaire": [], "slots": {},
	}


def _joueur(monkeypatch, pos, index=0):
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)
	snap = combat_mod.build_joueur_snapshot(_character(f"J{index}"), index)
	snap["vivant"] = True
	snap["pos"] = pos
	return snap


def _combat(joueurs, monstres, w=21, h=21):
	return {
		"_id": "combat:test", "type": "combat", "status": "active", "tour": 1, "log": [],
		"ordre_initiative": [j["id"] for j in joueurs] + [m["id"] for m in monstres],
		"acteur_courant_index": 0,
		"joueurs": list(joueurs), "monstres": list(monstres),
		"grid": {"dims": {"x": w, "y": h}, "cells": [[1] * w for _ in range(h)], "nav": {}},
	}


# ── Kiting : archer humanoïde 1x1 ────────────────────────────────────────────────

def test_monstre_archer_recule_si_trop_proche(monkeypatch):
	_equiper(monkeypatch)
	archer = _monstre(11, 10, _espece(items=[ARC["_id"]]))
	joueur = _joueur(monkeypatch, {"x": 10, "y": 10})
	combat = _combat([joueur], [archer])
	grid = combat_mod.get_combat_grid(combat)
	avant = combat_mod._cheby(archer, joueur)

	combat_mod._run_monster_turn(combat, archer, grid)

	assert avant == 1
	assert combat_mod._cheby(archer, joueur) > avant
	assert archer["cells_moved"] > 0


def test_monstre_archer_tient_sa_position_a_bonne_distance(monkeypatch):
	_equiper(monkeypatch)
	archer = _monstre(14, 10, _espece(items=[ARC["_id"]]))   # portée 4, distance 4 pile
	joueur = _joueur(monkeypatch, {"x": 10, "y": 10})
	combat = _combat([joueur], [archer])
	grid = combat_mod.get_combat_grid(combat)

	assert combat_mod._cheby(archer, joueur) == 4
	combat_mod._run_monster_turn(combat, archer, grid)

	assert archer["cells_moved"] == 0
	assert any(e["kind"] in ("hit", "crit", "miss", "fumble") for e in combat["log"])


def test_monstre_archer_approche_si_hors_de_portee(monkeypatch):
	_equiper(monkeypatch)
	archer = _monstre(20, 10, _espece(items=[ARC["_id"]]))   # portée 4, distance 10
	joueur = _joueur(monkeypatch, {"x": 10, "y": 10})
	combat = _combat([joueur], [archer])
	grid = combat_mod.get_combat_grid(combat)
	avant = combat_mod._cheby(archer, joueur)

	combat_mod._run_monster_turn(combat, archer, grid)

	assert combat_mod._cheby(archer, joueur) < avant
	ligne = next(e for e in combat["log"] if e["kind"] == "move")
	assert "avance vers" in ligne["texte"]


def test_monstre_corps_a_corps_comportement_inchange(monkeypatch):
	"""Une arme d'hast (portée 2, `ranged=False`) approche jusqu'à SA portée réelle,
	exactement comme le repli mains nues approchait jusqu'à 1."""
	_equiper(monkeypatch)
	guerrier = _monstre(15, 10, _espece(items=[HALLEBARDE["_id"]]))
	joueur = _joueur(monkeypatch, {"x": 10, "y": 10})
	combat = _combat([joueur], [guerrier])
	grid = combat_mod.get_combat_grid(combat)

	combat_mod._run_monster_turn(combat, guerrier, grid)

	assert combat_mod._cheby(guerrier, joueur) == 2
	assert guerrier["portee"] == 2


def test_monstre_non_humanoide_ia_inchangee(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)
	loup = _monstre(15, 10, _espece(tags=["predateur"]))
	joueur = _joueur(monkeypatch, {"x": 10, "y": 10})
	combat = _combat([joueur], [loup])
	grid = combat_mod.get_combat_grid(combat)

	assert "attaque_profils" not in loup
	combat_mod._run_monster_turn(combat, loup, grid)

	assert combat_mod._cheby(loup, joueur) == 1   # a foncé au contact, comme avant


# ── Chasse (prédateur/proie sous furtivité) ──────────────────────────────────────

def test_chasse_ou_erre_predateur_arme_a_distance_recule(monkeypatch):
	_equiper(monkeypatch)
	predateur_espece = _espece(tags=["humanoide", "predateur"], items=[ARC["_id"]])
	predateur = _monstre(11, 10, predateur_espece, idx=0)
	proie_espece = _espece(tags=["proie"], items=[])
	proie = _monstre(10, 10, proie_espece, idx=1)
	combat = _combat([], [predateur, proie])
	grid = combat_mod.get_combat_grid(combat)

	combat_mod._chasse_ou_erre(combat, predateur, grid)

	assert combat_mod._cheby(predateur, proie) > 1


# ── Invocation humanoïde ──────────────────────────────────────────────────────────

def test_invocation_humanoide_garde_son_profil_darme(monkeypatch):
	_equiper(monkeypatch)
	e = _espece(items=[ARC["_id"]])
	snap = combat_mod.build_invocation_snapshot(e, None, 0, duree=3)
	assert any(a.get("mode") == "tir" for a in snap["attaque_profils"])


def test_invocation_non_humanoide_reste_en_melee_forcee(monkeypatch):
	e = _espece(tags=["predateur"])
	snap = combat_mod.build_invocation_snapshot(e, None, 0, duree=3)
	assert snap["attaque_profils"] == [{
		"mode": "cac", "portee": snap.get("portee", 1), "ranged": False,
		"toucher": "cc", "degats": "degats_cc",
		"label": e.get("nom", "Griffes"), "animation": "",
	}]


# ── Grand jeton : le repli d'un humanoïde de grande taille ───────────────────────

def test_monster_step_away_grand_jeton(monkeypatch):
	_equiper(monkeypatch)
	e = _espece(items=[ARC["_id"]], jeton={"taille": "2x2", "forme": "rectangle"})
	archer = _monstre(11, 10, e)
	archer["cap"] = "gauche"
	joueur = _joueur(monkeypatch, {"x": 10, "y": 10})
	combat = _combat([joueur], [archer])
	grid = combat_mod.get_combat_grid(combat)
	profil = combat_mod._profil_arme_monstre(archer)
	avant = combat_mod.jetons.distance(archer, joueur)

	moved = combat_mod._monster_step_away(combat, archer, joueur, grid, profil["portee"])

	assert moved is True
	assert combat_mod.jetons.distance(archer, joueur) > avant
