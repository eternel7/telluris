# tests/test_armes_effets.py
#
# Effets à durée portés par une ARME (champ `effets` d'un doc `item:*`) : appliqués à
# l'IMPACT sur ce que le coup touche. Les bolas entravent les jambes (`buffs:{V:-2}`),
# donc réduisent le DÉPLACEMENT réel de la cible.
#
# Miroir de tests/test_combat_debuffs.py (part « sur cible » d'un sort) : mêmes fixtures.
# Seul écart, assumé : `_weapon_attacks` lit les docs d'items → `get_doc` est monkeypatché
# sur un dictionnaire d'items en mémoire, aucun accès DB.

import pytest

from utils import combat as combat_mod
from utils import sorts as sorts_mod
from utils.combat import build_joueur_snapshot, build_monster_snapshot, resolve_action


# ── Fixtures ─────────────────────────────────────────────────────────────────────

BOLAS = {
	"_id": "item:Bolas", "type": "item", "nom": "Bolas", "categorie": "arme",
	"slots": ["main_droite"], "poids": 0.8, "tags": ["jet"], "portee": 3,
	"bonus_cd": 5, "bonus_degats": 1, "bonus_degats_dice": 4,
	"cible": "ennemi", "effets": {"buffs": {"V": -2}, "duree": 2},
}

MASSUE = {  # arme ordinaire : aucun bloc `effets`
	"_id": "item:Rungu", "type": "item", "nom": "Rungu", "categorie": "arme",
	"slots": ["main_droite"], "poids": 1.0, "tags": ["jet"], "portee": 2,
	"bonus_degats": 4, "bonus_degats_dice": 4,
}


@pytest.fixture(autouse=True)
def _items_en_memoire(monkeypatch):
	"""`_weapon_attacks` fait un get_doc par slot — on le sert depuis un dict."""
	catalogue = {d["_id"]: d for d in (BOLAS, MASSUE)}
	monkeypatch.setattr(combat_mod, "get_doc", lambda i: catalogue.get(i))


def _character(arme=None, **overrides):
	char = {
		"_id": "character:test_1", "nom": "Frida", "voc": "chasseur", "race": "humain",
		"caracteristiques_current": {"V": 5, "F": 40, "R": 30, "Ag": 40,
									 "Vol": 40, "Int": 30, "Cha": 20, "Ch": 20},
		"vocations_niveaux": {"chasseur": 1},
		"currentPV": 100, "currentPM": 40,
		"inventaire": [], "slots": {"main_droite": arme} if arme else {},
	}
	char.update(overrides)
	return char


def _espece(**overrides):
	base = {
		"_id": "espece:loup", "nom": "Loup", "tags": [],
		"base_attributes": {c: {"min": v, "max": v} for c, v in
							(("V", 6), ("F", 30), ("R", 30), ("Ag", 40),
							 ("Vol", 20), ("Int", 10), ("Cha", 10), ("Ch", 10))},
	}
	base.update(overrides)
	return base


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


def _scene(arme="item:Bolas", distance=2):
	joueur = build_joueur_snapshot(_character(arme))
	monstre = build_monster_snapshot(_espece(), None, 0)
	monstre["pos"] = {"x": 3, "y": 5 - distance}
	return _combat(joueur, [monstre]), joueur, monstre


def _touche(monkeypatch):
	"""Jet à 50 : hors fenêtre de critique (≤5 / ≥96), sous un seuil large."""
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)


def _rate(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 95)


def _attaquer(doc, joueur, monstre):
	return resolve_action(doc, "attaquer", cible_id=monstre["id"], mode="jet")


# ── V est enfin exprimable dans un bloc `effets` ─────────────────────────────────

def test_v_survit_a_la_normalisation():
	# C'est l'invariant qui ouvre la feature : tant que _bonus_dict jetait V, une entrave
	# était écrite en base et normalisée à néant — donnée présente, mécanique absente.
	eff = sorts_mod.effets_de_sort({"effets": {"buffs": {"V": -2}, "duree": 2}})
	assert eff["buffs"] == {"V": -2}
	assert sorts_mod.part_durative(eff)


def test_cible_d_arme_est_whitelistee():
	assert sorts_mod.effets_d_arme(BOLAS)[1] == "ennemi"
	assert sorts_mod.effets_d_arme({"effets": {}, "cible": "soi"})[1] == "soi"
	# `allie` n'a pas de sens pour un coup porté → retombe sur `ennemi`, pas sur un
	# troisième comportement silencieux.
	assert sorts_mod.effets_d_arme({"effets": {}, "cible": "allie"})[1] == "ennemi"
	assert sorts_mod.effets_d_arme({"effets": {}, "cible": "n_importe_quoi"})[1] == "ennemi"


# ── Le profil d'attaque emporte l'effet ──────────────────────────────────────────

def test_le_profil_porte_l_effet_de_l_arme():
	joueur = build_joueur_snapshot(_character("item:Bolas"))
	profil = next(p for p in joueur["attaque_profils"] if p["mode"] == "jet")
	assert profil["effets"]["buffs"] == {"V": -2}
	assert profil["effets_cible"] == "ennemi"
	# Identité ancrée sur l'_id de l'arme (deux docs peuvent partager un `nom`).
	assert profil["effets_source_id"] == "item:Bolas"


def test_arme_ordinaire_ne_porte_aucun_effet():
	joueur = build_joueur_snapshot(_character("item:Rungu"))
	profil = next(p for p in joueur["attaque_profils"] if p["mode"] == "jet")
	assert "effets" not in profil and "effets_cible" not in profil


def test_effets_sans_duree_ne_sont_pas_portes(monkeypatch):
	# part_durative exige une duree > 0 : sans elle, il n'y a rien à empiler et la clé
	# ne doit pas exister (sinon _appliquer_effet_arme testerait à chaque coup).
	sans_duree = dict(BOLAS, _id="item:Sans_duree", effets={"buffs": {"V": -2}})
	monkeypatch.setattr(combat_mod, "get_doc", lambda i: {"item:Sans_duree": sans_duree}.get(i))
	joueur = build_joueur_snapshot(_character("item:Sans_duree"))
	assert "effets" not in next(p for p in joueur["attaque_profils"] if p["mode"] == "jet")


# ── Application à l'impact ───────────────────────────────────────────────────────

def test_touche_pose_l_effet_sur_la_cible(monkeypatch):
	_touche(monkeypatch)
	doc, joueur, monstre = _scene()
	res = _attaquer(doc, joueur, monstre)
	assert res["hit"] is True
	assert [e["source_id"] for e in monstre["effets_actifs"]] == ["item:Bolas"]
	assert monstre["effets_actifs"][0]["buffs"] == {"V": -2}
	assert monstre["effets_actifs"][0]["restants"] == 2
	assert res["effet_arme"]["nom"] == "Bolas"


def test_l_entrave_reduit_vraiment_le_deplacement(monkeypatch):
	# Le cœur de la feature : sans cette assertion, l'effet serait posé et décoratif.
	_touche(monkeypatch)
	doc, joueur, monstre = _scene()
	avant = monstre["deplacement"]
	_attaquer(doc, joueur, monstre)
	assert monstre["deplacement"] < avant
	assert monstre["deplacement"] >= 1   # plancher : une cible entravée avance toujours


def test_rate_ne_pose_rien(monkeypatch):
	_rate(monkeypatch)
	doc, joueur, monstre = _scene()
	assert _attaquer(doc, joueur, monstre)["hit"] is False
	assert monstre["effets_actifs"] == []


def test_cible_abattue_n_est_pas_entravee(monkeypatch):
	_touche(monkeypatch)
	doc, joueur, monstre = _scene()
	monstre["currentPV"] = 1          # le coup l'achève
	_attaquer(doc, joueur, monstre)
	assert monstre["vivant"] is False
	assert monstre["effets_actifs"] == []   # on ne ralentit pas un cadavre


def test_deux_coups_relancent_au_lieu_d_empiler(monkeypatch):
	# Non-cumul : une source = une entrée. Sans l'identité par _id, une arme frappant
	# trois fois cumulerait -6 en V et clouerait sa cible sur place.
	_touche(monkeypatch)
	doc, joueur, monstre = _scene()
	_attaquer(doc, joueur, monstre)
	dep_un_coup = monstre["deplacement"]
	joueur["attaques"] = 0            # rend une action pour rejouer
	combat_mod._refresh_actions(joueur)
	_attaquer(doc, joueur, monstre)
	assert len(monstre["effets_actifs"]) == 1
	assert monstre["effets_actifs"][0]["buffs"] == {"V": -2}
	assert monstre["deplacement"] == dep_un_coup


def test_cible_soi_pose_sur_l_attaquant(monkeypatch):
	_touche(monkeypatch)
	arme = dict(BOLAS, _id="item:Lame_avide", nom="Lame avide", cible="soi",
				effets={"buffs": {"Ag": 5}, "duree": 3})
	monkeypatch.setattr(combat_mod, "get_doc", lambda i: {"item:Lame_avide": arme}.get(i))
	joueur = build_joueur_snapshot(_character("item:Lame_avide"))
	monstre = build_monster_snapshot(_espece(), None, 0)
	monstre["pos"] = {"x": 3, "y": 3}
	doc = _combat(joueur, [monstre])
	_touche(monkeypatch)
	_attaquer(doc, joueur, monstre)
	assert [e["source_id"] for e in joueur["effets_actifs"]] == ["item:Lame_avide"]
	assert monstre["effets_actifs"] == []


def test_un_combat_deja_en_base_ne_change_pas(monkeypatch):
	# Profil figé d'avant la feature (aucune clé `effets`) : rien ne se déclenche.
	_touche(monkeypatch)
	doc, joueur, monstre = _scene()
	for p in joueur["attaque_profils"]:
		p.pop("effets", None)
	_attaquer(doc, joueur, monstre)
	assert monstre["effets_actifs"] == []
