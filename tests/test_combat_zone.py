# tests/test_combat_zone.py
#
# ZONES D'EFFET en combat : un sort ou une compétence porteur d'un bloc `zone`
# (utils/zones_effet.py) frappe TOUS les monstres pris dans la forme, pas seulement la
# cible désignée. La géométrie elle-même est verrouillée par tests/test_zones_effet.py ;
# ici on éprouve ce que le moteur en fait — cibles retenues, un jet et une localisation
# PAR victime, un seul débit de PM/action, le fumble de la seule cible désignée, et
# l'absence totale de tir ami.
#
# Mêmes fixtures que tests/test_combat_debuffs.py, aucun accès DB.

import pytest

from utils import combat as combat_mod
from utils.combat import build_joueur_snapshot, build_monster_snapshot, resolve_action
from utils.competences import normaliser_competence
from utils.sorts import normaliser_sort


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


def _espece():
	return {
		"_id": "espece:loup", "nom": "Loup", "tags": [],
		"base_attributes": {c: {"min": v, "max": v} for c, v in
							(("V", 4), ("F", 30), ("R", 30), ("Ag", 40),
							 ("Vol", 20), ("Int", 10), ("Cha", 10), ("Ch", 10))},
	}


def _monstre(idx, x, y):
	m = build_monster_snapshot(_espece(), None, idx)
	m["pos"] = {"x": x, "y": y}
	m["nom"] = f"Loup {idx}"
	m["currentPV"] = m["pv_max"] = 200   # personne ne meurt : on compte les touches
	return m


def _combat(joueur, monstres, cells=None):
	joueur["pos"] = {"x": 3, "y": 5}
	joueur["vivant"] = True
	return {
		"_id": "combat:test", "type": "combat", "status": "active", "tour": 1, "log": [],
		"ordre_initiative": ["joueur_0"] + [m["id"] for m in monstres],
		"acteur_courant_index": 0,
		"joueurs": [joueur], "monstres": monstres,
		"grid": {"dims": {"x": 7, "y": 7},
				 "cells": cells or [[1] * 7 for _ in range(7)], "nav": {}},
	}


def _sort_zone(zone=None, portee=1, cout_pm=0, degats="1D6", **extra):
	"""Couple (doc normalisé, effets) tel que le router l'injecte dans resolve_action."""
	doc = {"_id": "sort:nappe", "type": "sort", "vocation": "elementaliste",
		   "nom": "Nappe de feu", "icon": "🔥", "cible": "ennemi", "cout_pm": max(1, cout_pm),
		   "portee": portee, "effets": {"degats": degats}, "zone": zone, **extra}
	norm = normaliser_sort(doc)
	norm["cout_pm"] = cout_pm            # après normalisation : un sort exige cout_pm > 0
	return {"doc": norm, "effets": norm["effets"]}


def _comp_zone(zone=None, degats="1D6", portee=1):
	return normaliser_competence({
		"_id": "competence:tourbillon", "type": "competence", "vocation": "barbare",
		"nom": "Tourbillon de lames", "mode": "active", "cible": "ennemi", "jet": "cc",
		"cout_pm": 0, "portee": portee, "effets": {"degats": degats}, "zone": zone,
	})


def _joueur():
	j = build_joueur_snapshot(_character(), 0)
	j["cc"] = j["cd"] = 200              # on ne teste pas le toucher, on teste la zone
	j["toucher_magique"] = 200
	return j


@pytest.fixture(autouse=True)
def _des_fixes(monkeypatch):
	"""Jet à 50 : hors fenêtre de critique, et sous un seuil large ⇒ tout touche."""
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)


# ── Sans zone : rien n'a changé ──────────────────────────────────────────────────

def test_sans_zone_une_seule_cible_et_payload_inchange():
	m0, m1 = _monstre(0, 3, 4), _monstre(1, 4, 4)
	doc = _combat(_joueur(), [m0, m1])
	res = resolve_action(doc, "sort", m0["id"], sort=_sort_zone())
	assert res["hit"] is True
	assert res["cible"] == "Loup 0"
	# `cibles` n'apparaît QUE pour une zone à plusieurs victimes : le client garde
	# exactement le payload qu'il lisait avant.
	assert "cibles" not in res
	assert m1["currentPV"] == m1["pv_max"]


# ── Les quatre figures, en combat ────────────────────────────────────────────────

def test_boule_de_feu_touche_tout_le_disque():
	# Explosion de rayon 2 sur le loup du milieu : les trois sont dedans.
	m0, m1, m2 = _monstre(0, 3, 2), _monstre(1, 4, 2), _monstre(2, 3, 1)
	loin = _monstre(3, 0, 0)
	doc = _combat(_joueur(), [m0, m1, m2, loin])
	res = resolve_action(doc, "sort", m0["id"],
						 sort=_sort_zone({"forme": "cercle", "rayon": 2}, portee=4))
	assert len(res["cibles"]) == 3
	assert [c["cible"] for c in res["cibles"]] == ["Loup 0", "Loup 1", "Loup 2"]
	assert all(m["currentPV"] < m["pv_max"] for m in (m0, m1, m2))
	assert loin["currentPV"] == loin["pv_max"]


def test_tourbillon_touche_les_huit_cases_autour_du_lanceur():
	# Joueur en (3, 5). Deux loups au contact, un troisième à deux cases.
	m0, m1, m2 = _monstre(0, 3, 4), _monstre(1, 2, 6), _monstre(2, 3, 2)
	doc = _combat(_joueur(), [m0, m1, m2])
	comp = _comp_zone({"forme": "carre", "origine": "lanceur", "rayon": 1})
	res = resolve_action(doc, "competence", m0["id"], competence=comp)
	assert {c["cible"] for c in res["cibles"]} == {"Loup 0", "Loup 1"}
	assert m2["currentPV"] == m2["pv_max"]


def test_coup_d_epee_ne_touche_que_les_trois_cases_devant():
	# Joueur en (3, 5), ennemi désigné plein nord ⇒ bande (2,4) (3,4) (4,4).
	m0, m1, m2 = _monstre(0, 3, 4), _monstre(1, 4, 4), _monstre(2, 4, 5)
	doc = _combat(_joueur(), [m0, m1, m2])
	comp = _comp_zone({"forme": "rectangle", "origine": "lanceur",
					   "longueur": 1, "largeur": 3, "decalage": 1})
	res = resolve_action(doc, "competence", m0["id"], competence=comp)
	assert {c["cible"] for c in res["cibles"]} == {"Loup 0", "Loup 1"}
	assert m2["currentPV"] == m2["pv_max"]      # de côté, pas devant


def test_souffle_de_feu_s_elargit_avec_la_distance():
	# Cône de 3 vers le nord depuis (3, 5) : (3,4) au premier anneau, (1,2) au troisième.
	m0, m1 = _monstre(0, 3, 4), _monstre(1, 1, 2)
	dos = _monstre(2, 3, 6)
	doc = _combat(_joueur(), [m0, m1, dos])
	res = resolve_action(doc, "sort", m0["id"], sort=_sort_zone(
		{"forme": "cone", "origine": "lanceur", "longueur": 3, "decalage": 1}))
	assert {c["cible"] for c in res["cibles"]} == {"Loup 0", "Loup 1"}
	assert dos["currentPV"] == dos["pv_max"]    # dans le dos du souffleur


# ── Ce que la zone ne change pas ─────────────────────────────────────────────────

def test_un_seul_debit_de_pm_et_une_seule_action_pour_toute_la_zone():
	m0, m1, m2 = _monstre(0, 3, 4), _monstre(1, 2, 4), _monstre(2, 4, 4)
	j = _joueur()
	pm_avant, actions_avant = j["currentPM"], j["actions_restantes"]
	doc = _combat(j, [m0, m1, m2])
	res = resolve_action(doc, "sort", m0["id"], sort=_sort_zone(
		{"forme": "carre", "origine": "lanceur", "rayon": 1}, cout_pm=7))
	assert len(res["cibles"]) == 3
	assert j["currentPM"] == pm_avant - 7
	assert j["sorts"] == 1
	assert j["actions_restantes"] == actions_avant - 1


def test_chaque_victime_a_son_propre_jet_de_toucher(monkeypatch):
	# Un seuil imbattable pour la seconde : le jet est bien retiré par cible.
	m0, m1 = _monstre(0, 3, 4), _monstre(1, 2, 4)
	m1["caracts_base"]["Ag"] = 999
	combat_mod._refresh_snapshot_stats(m1)
	j = _joueur()
	j["cc"] = j["cd"] = j["toucher_magique"] = 1
	doc = _combat(j, [m0, m1])
	res = resolve_action(doc, "sort", m0["id"], sort=_sort_zone(
		{"forme": "carre", "origine": "lanceur", "rayon": 1}))
	assert len(res["cibles"]) == 2
	assert res["cibles"][1]["hit"] is False     # la seconde esquive, la zone continue


def test_seule_la_cible_designee_peut_faire_echouer_critiquement(monkeypatch):
	# Fumble garanti : sans la règle « une seule loterie », une zone large serait le
	# geste le plus dangereux du jeu pour celui qui le lance.
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 100)
	m0, m1, m2 = _monstre(0, 3, 4), _monstre(1, 2, 4), _monstre(2, 4, 4)
	j = _joueur()
	doc = _combat(j, [m0, m1, m2])
	penalites_avant = j["penalites"] + j["dette_actions"]
	res = resolve_action(doc, "sort", m0["id"], sort=_sort_zone(
		{"forme": "carre", "origine": "lanceur", "rayon": 1}))
	assert all(c["fumble"] for c in res["cibles"])            # les trois ratent
	# ... mais une SEULE action perdue, celle du jet de la cible désignée.
	assert (j["penalites"] + j["dette_actions"]) - penalites_avant == 1


def test_aucun_tir_ami():
	# Un compagnon debout au milieu de la nappe n'encaisse rien.
	m0 = _monstre(0, 3, 4)
	allie = build_joueur_snapshot(_character(_id="character:test_2", nom="Ordan"), 1)
	allie["pos"] = {"x": 2, "y": 4}
	allie["vivant"] = True
	j = _joueur()
	doc = _combat(j, [m0])
	doc["joueurs"].append(allie)
	doc["ordre_initiative"].append(allie["id"])
	pv_allie, pv_lanceur = allie["currentPV"], j["currentPV"]
	resolve_action(doc, "sort", m0["id"], sort=_sort_zone(
		{"forme": "carre", "origine": "lanceur", "rayon": 1}))
	assert allie["currentPV"] == pv_allie
	assert j["currentPV"] == pv_lanceur


def test_un_mort_de_la_zone_ne_bloque_pas_les_suivants():
	m0, m1 = _monstre(0, 3, 4), _monstre(1, 2, 4)
	m0["currentPV"] = 1
	doc = _combat(_joueur(), [m0, m1])
	res = resolve_action(doc, "sort", m0["id"], sort=_sort_zone(
		{"forme": "carre", "origine": "lanceur", "rayon": 1}, degats="20D6"))
	assert m0["vivant"] is False
	assert len(res["cibles"]) == 2 and res["cibles"][1]["hit"] is True
	assert m1["currentPV"] < m1["pv_max"]


def test_la_cible_designee_est_toujours_touchee_meme_hors_forme():
	# Zone poussée trop loin par son `decalage` : la cible désignée — celle contre qui
	# la portée a été validée et qu'on a payé pour frapper — reste de la partie.
	m0 = _monstre(0, 3, 4)
	doc = _combat(_joueur(), [m0])
	res = resolve_action(doc, "sort", m0["id"], sort=_sort_zone(
		{"forme": "rectangle", "origine": "lanceur",
		 "longueur": 1, "largeur": 1, "decalage": 3}))
	assert res["hit"] is True and m0["currentPV"] < m0["pv_max"]


def test_un_monstre_derriere_un_mur_est_epargne():
	# Mur en x=4 (sauf l'ouverture y=2) : l'explosion ne contourne pas l'angle.
	cells = [[1, 1, 1, 1, 0, 1, 1] if y != 2 else [1] * 7 for y in range(7)]
	m0, abrite = _monstre(0, 3, 4), _monstre(1, 5, 4)
	doc = _combat(_joueur(), [m0, abrite], cells=cells)
	res = resolve_action(doc, "sort", m0["id"],
						 sort=_sort_zone({"forme": "carre", "rayon": 2}, portee=2))
	assert "cibles" not in res                      # la cible désignée, et elle seule
	assert abrite["currentPV"] == abrite["pv_max"]


def test_le_journal_porte_une_ligne_par_victime():
	m0, m1 = _monstre(0, 3, 4), _monstre(1, 2, 4)
	doc = _combat(_joueur(), [m0, m1])
	resolve_action(doc, "sort", m0["id"], sort=_sort_zone(
		{"forme": "carre", "origine": "lanceur", "rayon": 1}))
	touches = [e for e in doc["log"] if e["kind"] in ("hit", "crit", "kill")]
	assert len(touches) == 2
	assert "Loup 0" in touches[0]["texte"] and "Loup 1" in touches[1]["texte"]
	# Chaque ligne porte SON gel d'état : c'est ce qui fait glisser les barres de PV
	# une victime après l'autre à la révélation, au rythme des animations.
	# (`vfx` n'est posé que si un canal résout une animation — aucune ici.)
	assert all(e.get("etat") for e in touches)
