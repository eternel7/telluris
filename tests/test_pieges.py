# tests/test_pieges.py
#
# PIÈGES (utils/pieges.py + leur branchement dans utils/combat.py) :
#   • tag codifié `pieges_<q>_<d>` d'une salle → pièges cachés posés LOIN des cases de départ ;
#   • détection à l'approche (porteurs de « Détection des pièges »), fouille (1 action) ;
#   • un piège DÉTECTÉ reste actif — seul le désamorçage le neutralise ;
#   • désamorçage (1 action) : animation + son pour la réussite comme pour l'échec ;
#   • pose de pièges par le joueur, déclenchés par les monstres qui ne les ont pas flairés ;
#   • XP personnelle (détection / désamorçage), créditée quelle que soit l'issue ;
#   • la vue client ne contient jamais un piège caché.
#
# Le hasard passe par `random.random` (jets d100 `_d100`) et `roll_dice`, fixés ici.

import asyncio
import copy
import json
import os
import sys

import pytest

from utils import combat as combat_mod
from utils import pieges
from utils.combat import resolve_action, vue_client
from _fixtures_magie import combat, textes
from _fixtures_magie import joueur as _joueur_fixture
from _fixtures_magie import monstre as _monstre_fixture

DEGATS = 7
REUSSITE = 0.0     # _d100 → 1 : tout jet réussit (seuil ≥ 5)
ECHEC = 0.999      # _d100 → 100 : tout jet échoue (seuil ≤ 95)


@pytest.fixture(autouse=True)
def _des_fixes(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)
	monkeypatch.setattr(combat_mod, "roll_dice", lambda notation: DEGATS)


def _jets(monkeypatch, valeur):
	monkeypatch.setattr(combat_mod.random, "random", lambda: valeur)


def joueur(**kw):
	j = _joueur_fixture(**kw)
	combat_mod._refresh_snapshot_stats(j)
	return j


def monstre(**kw):
	m = _monstre_fixture(**kw)
	combat_mod._refresh_snapshot_stats(m)
	return m


def voleur(**kw):
	"""Porteur des deux passives de niveau 1 (bonus dénormalisés sur le snapshot)."""
	return joueur(detection_pieges=20, desamorcage=20, **kw)


def piege_monde(x, y, danger=2, etat=pieges.ETAT_CACHE, pid="piege_0_0"):
	return pieges.nouveau_piege(pid, pieges.CAMP_MONDE, x, y, danger, etat=etat)


# ── Tag de salle ────────────────────────────────────────────────────────────────

def test_le_tag_code_quantite_et_danger():
	assert pieges.parametres_du_tag(["donjon", "pieges_4_2"]) == (4, 2)


def test_le_tag_est_borne():
	assert pieges.parametres_du_tag(["pieges_999_9"]) == (pieges.PIEGES_MAX, pieges.DANGER_MAX)
	assert pieges.parametres_du_tag(["pieges_3_0"]) == (3, pieges.DANGER_MIN)


def test_le_premier_tag_valide_gagne_et_les_autres_sont_ignores():
	assert pieges.parametres_du_tag(["pieges_x_2", "pieges_2_3", "pieges_5_5"]) == (2, 3)
	assert pieges.parametres_du_tag(["pieges", "pieges:4:2", "catacombe"]) is None
	assert pieges.parametres_du_tag(None) is None


def test_les_degats_suivent_le_danger():
	assert [pieges.degats_de(d) for d in range(1, 6)] == ["1D6", "2D6", "3D6", "4D6", "5D6"]


# ── Placement ───────────────────────────────────────────────────────────────────

def _grille(w, h, val=1):
	return [[val] * w for _ in range(h)]


def test_aucun_piege_pres_du_depart():
	cells = _grille(20, 20)
	poses = pieges.placer_pieges(cells, {"x": 20, "y": 20}, [(10, 10)], set(), 30, 2,
								 rand_fn=lambda: 0.5)
	assert len(poses) == 30
	assert all(max(abs(p["x"] - 10), abs(p["y"] - 10)) >= pieges.PIEGES_DISTANCE_DEPART
			   for p in poses)


def test_jamais_sur_un_mur_une_falaise_ou_une_case_interdite():
	cells = _grille(12, 12)
	cells[0][11] = 0
	cells[1][11] = 3
	poses = pieges.placer_pieges(cells, {"x": 12, "y": 12}, [(0, 0)], {(11, 2)}, 200, 1,
								 rand_fn=lambda: 0.99)
	cases = {(p["x"], p["y"]) for p in poses}
	assert not cases & {(11, 0), (11, 1), (11, 2)}
	assert all(p["camp"] == pieges.CAMP_MONDE and p["etat"] == pieges.ETAT_CACHE for p in poses)


def test_petite_carte_moins_de_pieges_plutot_que_pres_du_depart():
	"""Une salle où toute case est proche du départ ne reçoit AUCUN piège."""
	d = pieges.PIEGES_DISTANCE_DEPART
	cells = _grille(d, d)
	assert pieges.placer_pieges(cells, {"x": d, "y": d}, [(0, 0)], set(), 5, 3) == []


def test_le_placement_est_deterministe_sous_un_hasard_injecte():
	cells = _grille(15, 15)
	tirages = iter([0.1, 0.7, 0.3, 0.9] * 10)
	a = pieges.placer_pieges(cells, {"x": 15, "y": 15}, [(0, 0)], set(), 4, 2,
							 rand_fn=lambda: next(tirages))
	tirages = iter([0.1, 0.7, 0.3, 0.9] * 10)
	b = pieges.placer_pieges(cells, {"x": 15, "y": 15}, [(0, 0)], set(), 4, 2,
							 rand_fn=lambda: next(tirages))
	assert a == b and len({(p["x"], p["y"]) for p in a}) == 4


def test_la_salle_taguee_pose_ses_pieges_loin_du_point_d_apparition(monkeypatch):
	_jets(monkeypatch, ECHEC)
	j = joueur(x=2, y=2)
	doc = combat([j], [monstre(x=15, y=15)], dims=(18, 18))
	salle = {"_id": "lieu:salle", "tags": ["donjon", "pieges_6_2"]}
	grid = {"dims": {"x": 18, "y": 18}, "cells": _grille(18, 18), "nav": {}}
	combat_mod._poser_pieges(doc, salle, grid, point_apparition={"x": 2, "y": 2},
							 rand_fn=lambda: 0.4)
	assert len(doc["pieges"]) == 6
	for p in doc["pieges"]:
		assert max(abs(p["x"] - 2), abs(p["y"] - 2)) >= pieges.PIEGES_DISTANCE_DEPART
		assert (p["x"], p["y"]) != (15, 15)   # jamais sous un acteur


def test_sans_point_d_apparition_chaque_membre_du_groupe_est_un_depart(monkeypatch):
	_jets(monkeypatch, ECHEC)
	a, b = joueur(x=1, y=1), joueur(idx=1, x=12, y=12, nom="Brun")
	doc = combat([a, b], [monstre(x=6, y=0)], dims=(14, 14))
	grid = {"dims": {"x": 14, "y": 14}, "cells": _grille(14, 14), "nav": {}}
	combat_mod._poser_pieges(doc, {"tags": ["pieges_30_1"]}, grid, rand_fn=lambda: 0.2)
	for p in doc["pieges"]:
		for m in (a, b):
			assert max(abs(p["x"] - m["pos"]["x"]), abs(p["y"] - m["pos"]["y"])) \
				>= pieges.PIEGES_DISTANCE_DEPART


def test_changer_d_etage_repose_les_pieges_du_nouvel_etage(monkeypatch):
	_jets(monkeypatch, ECHEC)
	j = joueur(x=1, y=1)
	doc = combat([j], [monstre(x=8, y=8)], dims=(16, 16))
	doc["etages"] = {"etage": "lieu:e1", "passages": []}
	doc["pieges"] = [piege_monde(5, 5), pieges.nouveau_piege(
		"piege_j0_1", pieges.CAMP_JOUEUR, 6, 6, 1)]
	etage2 = {"_id": "lieu:e2", "tags": ["pieges_3_4"], "dimensions": {"x": 16, "y": 16},
			  "cells": _grille(16, 16), "image": ""}
	combat_mod.changer_d_etage(doc, etage2, {"x": 1, "y": 1}, [monstre(x=14, y=14)], [])
	assert len(doc["pieges"]) == 3
	assert all(p["danger"] == 4 and p["camp"] == pieges.CAMP_MONDE for p in doc["pieges"])
	assert all(max(abs(p["x"] - 1), abs(p["y"] - 1)) >= pieges.PIEGES_DISTANCE_DEPART
			   for p in doc["pieges"])


def test_une_salle_sans_tag_n_a_aucun_piege():
	doc = combat([joueur()], [monstre()])
	grid = {"dims": {"x": 12, "y": 9}, "cells": _grille(12, 9), "nav": {}}
	combat_mod._poser_pieges(doc, {"tags": ["donjon"]}, grid)
	assert "pieges" not in doc


# ── Seuils ──────────────────────────────────────────────────────────────────────

def test_seuil_de_detection_borne_et_regle_par_danger_et_bonus():
	det = {"int": 40, "detection_pieges": 20}
	p1, p3 = {"danger": 1}, {"danger": 3}
	k = pieges.PIEGE_DIFFICULTE_PAR_DANGER
	assert pieges.seuil_detection(det, p1) == 50 + 40 + 20 - k
	assert pieges.seuil_detection(det, p3) == 50 + 40 + 20 - 3 * k
	assert pieges.seuil_detection(det, p3, pieges.PIEGE_BONUS_FOUILLE) \
		== pieges.seuil_detection(det, p3) + pieges.PIEGE_BONUS_FOUILLE
	assert pieges.seuil_detection({"int": 500}, p1) == 95
	assert pieges.seuil_detection({}, {"danger": 5}) == 5


def test_seuil_de_desamorcage_lit_l_agilite():
	k = pieges.PIEGE_DIFFICULTE_PAR_DANGER
	assert pieges.seuil_desamorcage({"ag": 40, "desamorcage": 20}, {"danger": 2}) == 110 - 2 * k


# ── Détection à l'approche ──────────────────────────────────────────────────────

def test_un_detecteur_repere_le_piege_a_deux_cases(monkeypatch):
	_jets(monkeypatch, REUSSITE)
	v = voleur(x=3, y=5)
	doc = combat([v], [monstre(x=10, y=8)])
	doc["pieges"] = [piege_monde(6, 5)]
	resolve_action(doc, "deplacer", dx=1, dy=0)   # (4,5) : à 2 cases du piège
	assert doc["pieges"][0]["etat"] == pieges.ETAT_DETECTE
	assert v["xp_pieges"] == pieges.XP_DETECTION
	assert any("repère un piège" in t for t in textes(doc))


def test_un_seul_jet_par_piege_et_par_detecteur(monkeypatch):
	_jets(monkeypatch, ECHEC)
	v = voleur(x=3, y=5)
	doc = combat([v], [monstre(x=10, y=8)])
	doc["pieges"] = [piege_monde(6, 3)]
	resolve_action(doc, "deplacer", dx=1, dy=0)
	assert doc["pieges"][0]["tentes"] == [v["id"]]
	_jets(monkeypatch, REUSSITE)
	resolve_action(doc, "deplacer", dx=0, dy=1)   # toujours à portée : pas de second jet
	assert doc["pieges"][0]["etat"] == pieges.ETAT_CACHE


def test_sans_competence_aucun_jet(monkeypatch):
	_jets(monkeypatch, REUSSITE)
	j = joueur(x=3, y=5)
	doc = combat([j], [monstre(x=10, y=8)])
	doc["pieges"] = [piege_monde(5, 5)]
	resolve_action(doc, "deplacer", dx=1, dy=0)
	assert doc["pieges"][0]["etat"] == pieges.ETAT_CACHE and doc["pieges"][0]["tentes"] == []


# ── Déclenchement par le groupe ─────────────────────────────────────────────────

def test_marcher_sur_un_piege_cache_le_declenche(monkeypatch):
	_jets(monkeypatch, ECHEC)
	j = joueur(x=3, y=5)
	doc = combat([j], [monstre(x=10, y=8)])
	doc["pieges"] = [piege_monde(4, 5)]
	pv = j["currentPV"]
	resolve_action(doc, "deplacer", dx=1, dy=0)
	assert j["currentPV"] == pv - DEGATS
	assert doc["pieges"][0]["etat"] == pieges.ETAT_DECLENCHE


def test_la_ligne_de_declenchement_porte_l_animation_quand_le_doc_existe(monkeypatch):
	"""`_avec_vfx` ne pose la charge que si l'animation est résolue : l'id est DIRECT
	(premier étage de la cascade), il l'est donc toujours."""
	_jets(monkeypatch, ECHEC)
	j = joueur(x=3, y=5)
	doc = combat([j], [monstre(x=10, y=8)])
	doc["pieges"] = [piege_monde(4, 5)]
	resolve_action(doc, "deplacer", dx=1, dy=0)
	ligne = next(e for e in doc["log"] if "déclenche un piège" in e["texte"])
	assert ligne["vfx"] == {"anim": pieges.ANIM_DECLENCHEMENT, "cible": j["id"]}


def test_un_piege_detecte_se_declenche_quand_meme(monkeypatch):
	_jets(monkeypatch, ECHEC)
	j = joueur(x=3, y=5)
	doc = combat([j], [monstre(x=10, y=8)])
	doc["pieges"] = [piege_monde(4, 5, etat=pieges.ETAT_DETECTE)]
	pv = j["currentPV"]
	resolve_action(doc, "deplacer", dx=1, dy=0)
	assert j["currentPV"] == pv - DEGATS
	assert doc["pieges"][0]["etat"] == pieges.ETAT_DECLENCHE


def test_un_piege_declenche_ou_desamorce_ne_sert_plus(monkeypatch):
	_jets(monkeypatch, ECHEC)
	for etat in (pieges.ETAT_DECLENCHE, pieges.ETAT_DESAMORCE):
		j = joueur(x=3, y=5)
		doc = combat([j], [monstre(x=10, y=8)])
		doc["pieges"] = [piege_monde(4, 5, etat=etat)]
		pv = j["currentPV"]
		resolve_action(doc, "deplacer", dx=1, dy=0)
		assert j["currentPV"] == pv


def test_un_volant_ne_declenche_rien(monkeypatch):
	_jets(monkeypatch, ECHEC)
	j = joueur(x=3, y=5, volant=True)
	doc = combat([j], [monstre(x=10, y=8)])
	doc["pieges"] = [piege_monde(4, 5)]
	pv = j["currentPV"]
	resolve_action(doc, "deplacer", dx=1, dy=0)
	assert j["currentPV"] == pv and doc["pieges"][0]["etat"] == pieges.ETAT_CACHE


def test_un_monstre_ne_declenche_pas_les_pieges_de_son_antre(monkeypatch):
	_jets(monkeypatch, ECHEC)
	loup = monstre(x=5, y=5)
	doc = combat([joueur(x=1, y=5)], [loup])
	doc["pieges"] = [piege_monde(4, 5)]
	loup["pos"] = {"x": 4, "y": 5}
	pv = loup["currentPV"]
	combat_mod._pieges_au_pas(doc, loup)
	assert loup["currentPV"] == pv and doc["pieges"][0]["etat"] == pieges.ETAT_CACHE


def test_un_piege_peut_mettre_a_terre(monkeypatch):
	_jets(monkeypatch, ECHEC)
	j = joueur(x=3, y=5, pv=5)
	doc = combat([j], [monstre(x=10, y=8)])
	doc["pieges"] = [piege_monde(4, 5)]
	resolve_action(doc, "deplacer", dx=1, dy=0)
	assert j["currentPV"] == 0 and doc["status"] == "defaite"


# ── Fouille ─────────────────────────────────────────────────────────────────────

def test_la_fouille_coute_une_action_et_rejoue_un_piege_deja_tente(monkeypatch):
	_jets(monkeypatch, ECHEC)
	v = voleur(x=3, y=5)
	doc = combat([v], [monstre(x=10, y=8)])
	doc["pieges"] = [piege_monde(5, 5)]
	combat_mod._detecter_pieges(doc, v)          # tentative à l'approche, ratée
	assert doc["pieges"][0]["tentes"] == [v["id"]]
	avant = v["attaques"]
	_jets(monkeypatch, REUSSITE)
	res = resolve_action(doc, "fouiller")
	assert res["reperes"] == ["piege_0_0"]
	assert v["attaques"] == avant + 1
	assert doc["pieges"][0]["etat"] == pieges.ETAT_DETECTE
	assert v["xp_pieges"] == pieges.XP_DETECTION


def test_la_fouille_applique_son_bonus(monkeypatch):
	v = voleur(x=3, y=5)
	piege = piege_monde(5, 5, danger=5)
	base = pieges.seuil_detection(v, piege)
	fouille = pieges.seuil_detection(v, piege, pieges.PIEGE_BONUS_FOUILLE)
	assert fouille == min(95, base + pieges.PIEGE_BONUS_FOUILLE)
	# Un jet juste au-dessus du seuil d'approche, sous celui de la fouille.
	roll = base + 1
	assert roll <= fouille
	_jets(monkeypatch, (roll - 1) / 100)
	doc = combat([v], [monstre(x=10, y=8)])
	doc["pieges"] = [piege]
	assert combat_mod._detecter_pieges(doc, v) == []
	assert resolve_action(doc, "fouiller")["reperes"] == [piege["id"]]


def test_la_fouille_ignore_les_pieges_au_dela_de_deux_cases(monkeypatch):
	_jets(monkeypatch, REUSSITE)
	v = voleur(x=3, y=5)
	doc = combat([v], [monstre(x=10, y=8)])
	doc["pieges"] = [piege_monde(3 + pieges.PIEGE_PORTEE_DETECTION + 1, 5)]
	res = resolve_action(doc, "fouiller")
	assert res["reperes"] == [] and any("ne trouve rien" in t for t in textes(doc))


def test_la_fouille_est_refusee_sans_competence():
	doc = combat([joueur()], [monstre(x=10, y=8)])
	assert "error" in resolve_action(doc, "fouiller")


# ── Désamorçage ─────────────────────────────────────────────────────────────────

def test_desamorcer_reussi_rend_le_piege_inerte_avec_animation_et_xp(monkeypatch):
	_jets(monkeypatch, REUSSITE)
	v = voleur(x=3, y=5)
	doc = combat([v], [monstre(x=10, y=8)])
	doc["pieges"] = [piege_monde(4, 5, etat=pieges.ETAT_DETECTE)]
	res = resolve_action(doc, "desamorcer", piege={"piege_id": "piege_0_0"})
	assert res["desamorce"] is True
	assert doc["pieges"][0]["etat"] == pieges.ETAT_DESAMORCE
	assert v["xp_pieges"] == pieges.XP_DESAMORCAGE
	assert doc["log"][-1]["vfx"]["anim"] == pieges.ANIM_DESAMORCAGE_REUSSI
	# Inerte : on peut maintenant marcher dessus.
	pv = v["currentPV"]
	resolve_action(doc, "deplacer", dx=1, dy=0)
	assert v["currentPV"] == pv


def test_desamorcer_rate_laisse_le_piege_actif_avec_l_animation_d_echec(monkeypatch):
	_jets(monkeypatch, ECHEC)
	v = voleur(x=3, y=5)
	doc = combat([v], [monstre(x=10, y=8)])
	doc["pieges"] = [piege_monde(4, 5, etat=pieges.ETAT_DETECTE)]
	res = resolve_action(doc, "desamorcer", piege={"piege_id": "piege_0_0"})
	assert res["desamorce"] is False
	assert doc["pieges"][0]["etat"] == pieges.ETAT_DETECTE
	assert v.get("xp_pieges", 0) == 0
	assert doc["log"][-1]["vfx"]["anim"] == pieges.ANIM_DESAMORCAGE_RATE


@pytest.mark.parametrize("cas", ["sans_competence", "cache", "loin", "sans_action"])
def test_desamorcer_refuse(cas):
	v = joueur(x=3, y=5) if cas == "sans_competence" else voleur(x=3, y=5)
	etat = pieges.ETAT_CACHE if cas == "cache" else pieges.ETAT_DETECTE
	x = 6 if cas == "loin" else 4
	doc = combat([v], [monstre(x=10, y=8)])
	doc["pieges"] = [piege_monde(x, 5, etat=etat)]
	if cas == "sans_action":
		v["attaques"] = v["actions_max"]
		combat_mod._refresh_actions(v)
	assert "error" in resolve_action(doc, "desamorcer", piege={"piege_id": "piege_0_0"})
	assert doc["pieges"][0]["etat"] == etat


# ── Vue client ──────────────────────────────────────────────────────────────────

def test_la_vue_client_ne_contient_aucun_piege_cache_et_ne_mute_pas_le_doc():
	v = voleur(x=3, y=5)
	doc = combat([v], [monstre(x=10, y=8)])
	doc["pieges"] = [piege_monde(8, 2, pid="a"),
					 piege_monde(4, 5, etat=pieges.ETAT_DETECTE, pid="b"),
					 piege_monde(1, 1, etat=pieges.ETAT_DECLENCHE, pid="c")]
	vue = vue_client(doc)
	assert [p["id"] for p in vue["pieges"]] == ["b", "c"]
	assert vue["pieges_desamorcables"] == ["b"]
	assert vue["peut_fouiller"] is True and vue["peut_desamorcer"] is True
	assert len(doc["pieges"]) == 3


def test_la_vue_client_pose_les_drapeaux_meme_sans_piege():
	"""Un bouton qui n'apparaîtrait que sur une carte piégée trahirait la carte."""
	vue = vue_client(combat([voleur()], [monstre(x=10, y=8)]))
	assert vue["peut_fouiller"] is True and vue["pieges"] == []


# ── Pose de pièges par le joueur ────────────────────────────────────────────────

POSE = pieges.normaliser_pose({"item": "item:Chausse_trappes", "danger": 2, "zone": 1,
							   "effets": {"buffs": {"V": -2}, "duree": 1},
							   "nom": "Chausse-trappes", "icon": "📌"})


def _poser(doc, x, y, pose=POSE):
	return resolve_action(doc, "poser_piege", piege={"pose": pose, "x": x, "y": y,
													 "nom": "Chausse-trappes", "icon": "📌"})


def test_normaliser_pose_liste_blanche_et_defauts():
	assert pieges.normaliser_pose({"danger": 2}) is None   # sans objet : rien à poser
	lu = pieges.normaliser_pose({"item": "item:x", "danger": 9, "zone": 7, "portee": 0,
								 "effets": {"buffs": {"V": -2}, "duree": 2, "regen_pv": -3},
								 "inconnu": 1})
	assert lu["danger"] == pieges.DANGER_MAX and lu["zone"] == pieges.POSE_ZONE_MAX
	assert lu["portee"] == 1 and lu["degats"] == pieges.degats_de(pieges.DANGER_MAX)
	# Régén négative GARDÉE : c'est un poison (perte au tour de la victime).
	assert lu["effets"] == {"buffs": {"V": -2}, "duree": 2, "regen_pv": -3}
	assert "inconnu" not in lu
	assert pieges.normaliser_pose({"item": "item:x", "effets": {"buffs": {"V": -2}}})["effets"] == {}


def test_poser_un_piege_couvre_son_carre_et_coute_une_action():
	v = voleur(x=3, y=5)
	doc = combat([v], [monstre(x=10, y=8)])
	avant = v["attaques"]
	res = _poser(doc, 4, 5)
	assert res["pose"] is True and v["attaques"] == avant + 1
	[p] = doc["pieges"]
	assert p["camp"] == pieges.CAMP_JOUEUR and p["etat"] == pieges.ETAT_DETECTE
	assert sorted(map(tuple, p["cases"])) == sorted(
		(x, y) for x in (3, 4, 5) for y in (4, 5, 6))
	assert p["poseur_id"] == v["id"]


def test_la_zone_est_filtree_aux_cases_marchables():
	cells = [[1] * 12 for _ in range(9)]
	cells[4][5] = 0
	cells[6][5] = 3
	v = voleur(x=3, y=5)
	doc = combat([v], [monstre(x=10, y=8)], cells=cells)
	_poser(doc, 4, 5)
	cases = {tuple(c) for c in doc["pieges"][0]["cases"]}
	assert (5, 4) not in cases and (5, 6) not in cases and (4, 5) in cases


@pytest.mark.parametrize("x,y,etat", [(6, 5, None), (10, 8, None), (4, 5, "piege")])
def test_pose_refusee(x, y, etat):
	cells = [[1] * 12 for _ in range(9)]
	v = voleur(x=3, y=5)
	doc = combat([v], [monstre(x=10, y=8)], cells=cells)
	if etat == "piege":
		doc["pieges"] = [piege_monde(4, 5, etat=pieges.ETAT_DETECTE)]
	assert "error" in _poser(doc, x, y)


def test_pose_refusee_sur_un_mur_ou_sans_action():
	cells = [[1] * 12 for _ in range(9)]
	cells[5][4] = 0
	v = voleur(x=3, y=5)
	doc = combat([v], [monstre(x=10, y=8)], cells=cells)
	assert "error" in _poser(doc, 4, 5)
	v["attaques"] = v["actions_max"]
	combat_mod._refresh_actions(v)
	assert "error" in _poser(doc, 3, 4)


def test_le_groupe_ne_declenche_jamais_son_piege(monkeypatch):
	_jets(monkeypatch, ECHEC)
	v = voleur(x=3, y=5)
	doc = combat([v], [monstre(x=10, y=8)])
	_poser(doc, 4, 5)
	pv = v["currentPV"]
	resolve_action(doc, "deplacer", dx=1, dy=0)
	assert v["currentPV"] == pv and doc["pieges"][0]["etat"] == pieges.ETAT_DETECTE


def test_un_monstre_qui_entre_dans_la_zone_declenche_sur_tous_les_monstres_de_la_zone(monkeypatch):
	_jets(monkeypatch, ECHEC)
	v = voleur(x=1, y=1)
	a, b, c = monstre(x=5, y=5), monstre(idx=1, x=4, y=4), monstre(idx=2, x=9, y=8)
	doc = combat([v], [a, b, c])
	doc["pieges"] = [pieges.nouveau_piege("piege_j0_0", pieges.CAMP_JOUEUR, 4, 5, 2,
										  cases=[[x, y] for x in (3, 4, 5) for y in (4, 5, 6)],
										  effets={"buffs": {"V": -2}, "duree": 1},
										  nom="Chausse-trappes")]
	pv = (a["currentPV"], b["currentPV"], c["currentPV"])
	combat_mod._pieges_au_pas(doc, a)
	assert (a["currentPV"], b["currentPV"], c["currentPV"]) == (pv[0] - DEGATS, pv[1] - DEGATS, pv[2])
	assert doc["pieges"][0]["etat"] == pieges.ETAT_DECLENCHE
	assert any(e.get("vfx", {}).get("anim") == pieges.ANIM_DECLENCHEMENT for e in doc["log"])
	assert any("Chausse-trappes" == (eff.get("nom")) for eff in a.get("effets_actifs") or [])


def test_un_piege_pose_peut_tuer_et_donner_la_victoire(monkeypatch):
	_jets(monkeypatch, ECHEC)
	loup = monstre(x=4, y=5, pv=5)
	doc = combat([voleur(x=1, y=1)], [loup])
	doc["pieges"] = [pieges.nouveau_piege("piege_j0_0", pieges.CAMP_JOUEUR, 4, 5, 1)]
	combat_mod._pieges_au_pas(doc, loup)
	assert loup["vivant"] is False and doc["status"] == "victoire"


def test_un_monstre_qui_flaire_le_piege_le_contourne(monkeypatch):
	_jets(monkeypatch, REUSSITE)
	loup = monstre(x=6, y=5)
	doc = combat([voleur(x=2, y=5)], [loup])
	doc["pieges"] = [pieges.nouveau_piege("piege_j0_0", pieges.CAMP_JOUEUR, 5, 5, 1)]
	combat_mod._flairer_pieges(doc, loup)
	assert doc["pieges"][0]["vu_par"] == [loup["id"]]
	assert (5, 5) in combat_mod._cases_evitees(doc, loup)
	grid = combat_mod.get_combat_grid(doc)
	assert combat_mod._monster_step_toward(doc, loup, doc["joueurs"][0], grid)
	assert (loup["pos"]["x"], loup["pos"]["y"]) != (5, 5)
	assert doc["pieges"][0]["etat"] == pieges.ETAT_DETECTE


def test_un_monstre_qui_rate_son_flair_ne_rejoue_pas_et_marche_dessus(monkeypatch):
	_jets(monkeypatch, ECHEC)
	loup = monstre(x=6, y=5)
	# Couloir d'une case : le seul chemin passe par le piège.
	couloir = [[1 if y == 5 else 0 for _ in range(12)] for y in range(9)]
	doc = combat([voleur(x=2, y=5)], [loup], cells=couloir)
	doc["pieges"] = [pieges.nouveau_piege("piege_j0_0", pieges.CAMP_JOUEUR, 5, 5, 1)]
	combat_mod._flairer_pieges(doc, loup)
	_jets(monkeypatch, REUSSITE)
	combat_mod._flairer_pieges(doc, loup)
	assert doc["pieges"][0]["tentes"] == [loup["id"]] and doc["pieges"][0]["vu_par"] == []
	pv = loup["currentPV"]
	grid = combat_mod.get_combat_grid(doc)
	combat_mod._monster_step_toward(doc, loup, doc["joueurs"][0], grid)
	assert (loup["pos"]["x"], loup["pos"]["y"]) == (5, 5)
	assert loup["currentPV"] == pv - DEGATS


def test_la_vue_client_montre_les_pieges_du_joueur():
	v = voleur(x=3, y=5)
	doc = combat([v], [monstre(x=10, y=8)])
	_poser(doc, 4, 5)
	assert [p["camp"] for p in vue_client(doc)["pieges"]] == [pieges.CAMP_JOUEUR]


# ── XP ──────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("status", ["victoire", "defaite", "fuite"])
def test_l_xp_des_pieges_est_creditee_quelle_que_soit_l_issue_une_seule_fois(monkeypatch, status):
	credits = []
	monkeypatch.setattr(combat_mod, "grant_xp", lambda doc, xp: credits.append(xp))
	monkeypatch.setattr(combat_mod, "save_doc", lambda doc: doc)
	v = voleur(x=3, y=5)
	v["xp_pieges"] = pieges.XP_DETECTION + pieges.XP_DESAMORCAGE
	doc = combat([v], [monstre(x=10, y=8)])
	doc["xp_gagnee"] = 0
	perso = {"_id": v["character_id"], "combats_recompenses": [], "inventaire": []}
	assert combat_mod._finalize_membre(doc, v, perso, status)
	assert pieges.XP_DETECTION + pieges.XP_DESAMORCAGE in credits
	n = len(credits)
	combat_mod._finalize_membre(doc, v, perso, status)   # re-finalisation : garde exactly-once
	assert len(credits) == n
	assert doc["xp_gagnee"] == 0


# ── Router : l'objet de la pose ─────────────────────────────────────────────────

COMP = {"_id": "competence:pose_chausse_trappes", "type": "competence", "vocation": "voleur",
		"niveau": 2, "mode": "passive", "nom": "Pose : Chausse-trappes", "icon": "📌",
		"pose_piege": {"item": "item:Chausse_trappes", "danger": 1, "zone": 1}}
ITEM = {"_id": "item:Chausse_trappes", "type": "item", "nom": "Chausse-trappes", "poids": 0.5}


@pytest.fixture
def monde(monkeypatch):
	from routers import combat as rc
	docs = {d["_id"]: d for d in (COMP, ITEM)}

	def save(doc):
		docs[doc["_id"]] = doc
		return doc

	# Copie à chaque lecture, comme CouchDB : relire après un refus doit rendre l'état SAUVÉ.
	monkeypatch.setattr(rc, "get_doc", lambda i: copy.deepcopy(docs.get(i)))
	monkeypatch.setattr(rc, "save_doc", save)
	v = voleur(x=3, y=5)
	v["character_id"] = "character:test_0"
	doc = combat([v], [monstre(x=10, y=8)])
	doc["user_id"] = "user:u"
	docs[doc["_id"]] = doc
	return {"docs": docs, "rc": rc, "combat": doc}


def _poser_http(monde, inventaire, x=4, y=5):
	rc = monde["rc"]
	monde["docs"]["character:test_0"] = {
		"_id": "character:test_0", "competences_connues": [COMP["_id"]],
		"inventaire": inventaire}
	body = rc.ActionRequest(type="poser_piege", competence_id=COMP["_id"], x=x, y=y)
	return asyncio.run(rc.combat_action("combat:test", body, {"_id": "user:u"}))


def test_poser_retire_exactement_un_objet(monde):
	rep = _poser_http(monde, [{"item": ITEM["_id"], "poids": 0.5}] * 2)
	assert rep["action_result"]["pose"] is True
	assert len(monde["docs"]["character:test_0"]["inventaire"]) == 1
	assert rep["actions_pieges"][0]["stock"] == 1


def test_poser_sans_objet_est_refuse(monde):
	from fastapi import HTTPException
	with pytest.raises(HTTPException) as e:
		_poser_http(monde, [])
	assert e.value.status_code == 422 and "Chausse-trappes" in e.value.detail


def test_l_objet_reste_au_sac_si_le_moteur_refuse(monde):
	rep = _poser_http(monde, [{"item": ITEM["_id"], "poids": 0.5}], x=9, y=1)  # hors portée
	assert "error" in rep["action_result"]
	assert len(monde["docs"]["character:test_0"]["inventaire"]) == 1


# ── Compétences (clés passives, apprentissage) ──────────────────────────────────

from utils import competences as competences_util  # noqa: E402
from utils.sorts import _bonus_dict  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dev import gen_pieges  # noqa: E402

LOT = {d["_id"]: d for d in gen_pieges.docs_competences()}


def _find(selector):
	return [d for d in LOT.values() if all(d.get(k) == v for k, v in selector.items())]


def test_bonus_dict_lit_les_deux_cles_de_pieges():
	lu = _bonus_dict({"detection_pieges": 20, "desamorcage": 15})
	assert lu["detection_pieges"] == 20 and lu["desamorcage"] == 15
	assert _bonus_dict({})["detection_pieges"] == 0


def test_bonus_passifs_agrege_detection_et_desamorcage():
	perso = {"competences_connues": ["competence:detection_des_pieges_voleur",
									 "competence:desamorcage_des_pieges_voleur"]}
	bonus = competences_util.bonus_passifs(perso, LOT.get)
	assert bonus["detection_pieges"] == gen_pieges.BONUS_DETECTION
	assert bonus["desamorcage"] == gen_pieges.BONUS_DESAMORCAGE


@pytest.mark.parametrize("voc", gen_pieges.VOCATIONS)
@pytest.mark.parametrize("slug", sorted(gen_pieges.PASSIVES))
def test_detection_et_desamorcage_s_apprennent_a_leur_niveau(voc, slug):
	cid = f"competence:{slug}_{voc}"
	requis = gen_pieges.NIVEAUX_PASSIVES[voc][slug]
	for niveau, ok in ((requis - 1, False), (requis, True)):
		perso = {"voc": voc, "vocations_niveaux": {voc: niveau}, "competences_connues": []}
		ids = {c["id"] for c in competences_util.competences_apprenables(perso, _find)}
		assert (cid in ids) is ok
	guerrier = {"voc": "guerrier", "vocations_niveaux": {"guerrier": 9}, "competences_connues": []}
	assert not competences_util.competences_apprenables(guerrier, _find)


@pytest.mark.parametrize("voc", gen_pieges.VOCATIONS)
def test_une_pose_par_niveau_et_un_objet_different_chacune(voc):
	poses = [competences_util.normaliser_competence(d) for d in LOT.values()
			 if d["vocation"] == voc and d.get("pose_piege")]
	niveaux = sorted(c["niveau"] for c in poses)
	assert niveaux == [ligne[0] for ligne in gen_pieges.POSES[voc]]
	assert niveaux == list(range(niveaux[0], 9))   # un palier par niveau jusqu'au 8
	assert all(c["pose_piege"] for c in poses)
	assert not any(competences_util.competence_utilisable_combat(c) for c in poses)
	# Plus dangereuse OU plus large à chaque niveau (jamais les deux en baisse).
	poses.sort(key=lambda c: c["niveau"])
	for avant, apres in zip(poses, poses[1:]):
		a, b = avant["pose_piege"], apres["pose_piege"]
		assert (b["danger"], b["zone"]) != (a["danger"], a["zone"]) or b["effets"] != a["effets"]
		assert b["danger"] >= a["danger"] or b["zone"] > a["zone"]


def test_aucun_objet_consomme_deux_fois_et_chaque_objet_neuf_a_sa_recette():
	items = [d["pose_piege"]["item"] for d in LOT.values() if d.get("pose_piege")]
	assert len(items) == len(set(items)) == sum(len(p) for p in gen_pieges.POSES.values())
	produits = {d["objet_final"] for d in gen_pieges.docs_objets() if d["type"] == "recette"}
	assert {i[len("item:"):] for i in gen_pieges.OBJETS} == produits


def test_assassin_detection_au_2_desamorcage_au_4_poses_du_5_au_8():
	"""Demande explicite : l'échelle de l'assassin commence plus tard que celle du voleur."""
	niveaux = {d["_id"]: d["niveau"] for d in LOT.values() if d["vocation"] == "assassin"}
	assert niveaux.pop("competence:detection_des_pieges_assassin") == 2
	assert niveaux.pop("competence:desamorcage_des_pieges_assassin") == 4
	assert sorted(niveaux.values()) == [5, 6, 7, 8]


def test_les_pieges_de_l_assassin_immobilisent_sans_tuer():
	"""Entrave de V sur chacun, aucun poison (il se porte à la lame ou à distance), et des
	dégâts plus faibles que ceux d'un piège ordinaire de même danger (`degats_de`)."""
	def maxi(notation):   # dégâts maximaux d'une notation `nDm`
		n, m = notation.upper().split("D")
		return int(n or 1) * int(m)
	poses = [competences_util.normaliser_competence(d)["pose_piege"] for d in LOT.values()
			 if d["vocation"] == "assassin" and d.get("pose_piege")]
	assert poses
	for p in poses:
		assert p["effets"]["buffs"]["V"] < 0 and p["effets"]["duree"] > 0
		assert not any(p["effets"].get(k, 0) < 0 for k in ("regen_pv", "regen_pm"))
		assert maxi(p["degats"]) < maxi(pieges.degats_de(p["danger"]))


def test_actions_pieges_payload_compte_le_stock():
	perso = {"competences_connues": ["competence:pose_chausse_trappes"],
			 "inventaire": [{"item": "item:Chausse_trappes", "poids": 0.5}, "item:Chausse_trappes",
							{"item": "item:autre"}]}
	[p] = competences_util.actions_pieges_payload(perso, LOT.get)
	assert p["stock"] == 2 and p["item"] == "item:Chausse_trappes"


def test_le_generateur_passe_ses_garde_fous_sur_le_dump_et_est_idempotent(tmp_path):
	sortie = tmp_path / "pieges.json"
	assert gen_pieges.main(["--sortie", str(sortie)]) == 0
	premier = sortie.read_text(encoding="utf-8")
	assert gen_pieges.main(["--sortie", str(sortie)]) == 0
	assert sortie.read_text(encoding="utf-8") == premier
	# Pas un fichier vide : tout le lot part (rien de tout cela n'est encore en base).
	attendu = (len(gen_pieges.docs_competences()) + len(gen_pieges.docs_objets())
			   + len(gen_pieges.ANIMATIONS))
	assert len(json.loads(premier)) == attendu


def test_les_competences_de_pieges_ont_leur_case_de_barre():
	"""Passives qui ouvrent une action de combat : 🔎 fouiller, 🛠 désamorcer, une case par
	piège à poser. Jamais épinglées d'office (la barre DÉRIVÉE reste celle d'avant)."""
	from utils import slots_actions
	ids = {"competence:detection_des_pieges_voleur": "fouiller",
		   "competence:desamorcage_des_pieges_voleur": "desamorcer",
		   "competence:pose_chausse_trappes": "poser_piege"}
	perso = {"competences_connues": list(ids)}
	for cid, action in ids.items():
		assert competences_util.action_piege(competences_util.normaliser_competence(LOT[cid])) == action
		assert slots_actions._entree_possedee({"type": "competence", "ref": cid}, perso, LOT.get)
	assert [p["action"] for p in competences_util.actions_pieges_payload(perso, LOT.get)] \
		== ["desamorcer", "fouiller", "poser_piege"]   # niveau puis nom
	assert competences_util.competences_epinglees_effectives(perso, LOT.get) == []


def test_une_passive_ordinaire_n_a_toujours_pas_de_case():
	from utils import slots_actions
	docs = dict(LOT, **{"competence:esquive": {"_id": "competence:esquive", "type": "competence",
											   "vocation": "voleur", "mode": "passive",
											   "effets": {"esquive": 10}}})
	perso = {"competences_connues": ["competence:esquive"]}
	assert not slots_actions._entree_possedee(
		{"type": "competence", "ref": "competence:esquive"}, perso, docs.get)


def test_apprendre_une_competence_de_piege_la_pose_dans_la_premiere_case_libre():
	from utils import slots_actions
	cid = "competence:pose_chausse_trappes"
	perso = {"competences_connues": [cid]}
	entree = {"type": "competence", "ref": cid}
	assert slots_actions.placer_si_libre(perso, entree, LOT.get) is True
	slots = slots_actions.slots_effectifs(perso, LOT.get)
	premiere_libre = len(slots_actions.ENTREES_DERIVEES)   # barre dérivée : socle puis libre
	assert slots[premiere_libre] == entree
	assert slots_actions.placer_si_libre(perso, entree, LOT.get) is False   # déjà là
	assert sum(1 for s in slots_actions.slots_effectifs(perso, LOT.get) if s == entree) == 1


def test_barre_pleine_rien_ne_bouge():
	from utils import slots_actions
	cid = "competence:pose_chausse_trappes"
	plein = [{"type": "attaque", "ref": "cac"}, {"type": "ramasser"}, {"type": "fuir"}]
	plein += [{"type": "attaque", "ref": "jet"}] * (slots_actions.slots_max() - len(plein))
	perso = {"competences_connues": [cid], "slots_actions": plein}
	avant = slots_actions.slots_effectifs(perso, LOT.get)
	assert slots_actions.placer_si_libre(perso, {"type": "competence", "ref": cid}, LOT.get) is False
	assert slots_actions.slots_effectifs(perso, LOT.get) == avant


def test_la_detection_a_l_approche_vaut_sans_case_de_barre(monkeypatch):
	"""La case n'est que le bouton de la FOUILLE : la passive agit par `competences_bonus`,
	même retirée de la barre."""
	from _fixtures_magie import character
	from utils.combat import build_joueur_snapshot
	cid = "competence:detection_des_pieges_voleur"
	perso = character(competences_connues=[cid], voc="voleur",
					  slots_actions=[{"type": "attaque", "ref": "cac"}, {"type": "ramasser"},
									 {"type": "fuir"}])
	competences_util.recompute_competences_bonus(perso, LOT.get)
	j = build_joueur_snapshot(perso, 0)
	j["pos"] = {"x": 3, "y": 5}
	assert j["detection_pieges"] == gen_pieges.BONUS_DETECTION
	_jets(monkeypatch, REUSSITE)
	doc = combat([j], [monstre(x=10, y=8)])
	doc["pieges"] = [piege_monde(5, 5)]
	resolve_action(doc, "deplacer", dx=1, dy=0)
	assert doc["pieges"][0]["etat"] == pieges.ETAT_DETECTE
