# tests/test_combat_rayon.py
#
# RAYON / LANCE DE LUMIÈRE : zone offensive en LIGNE (rectangle 1×N ancré sur le lanceur)
# qui PERCE les murs (`zone.perce`) et touche AUSSI le camp du joueur (`zone.tir_ami`) —
# seul tir ami au LANCEMENT du jeu. Le lanceur n'est jamais sur la trajectoire (decalage 1).

import pytest

from utils import combat as combat_mod
from utils.combat import resolve_action
from _fixtures_magie import combat, sort
from _fixtures_magie import joueur as _joueur_fixture
from _fixtures_magie import monstre as _monstre_fixture


DEGATS = 7

RAYON = dict(cout_pm=5, cible="ennemi", portee=20, nom="Rayon de lumière", icon="☀",
			 effets={"degats": "25+3D8"},
			 zone={"forme": "rectangle", "origine": "lanceur", "orientation": "cible",
				   "longueur": 20, "largeur": 1, "decalage": 1,
				   "perce": True, "tir_ami": True})

# Grille 12×9, un mur vertical en x=9 : derrière lui, un second monstre.
W, H = 12, 9
CELLS = [[0 if x == 9 else 1 for x in range(W)] for _ in range(H)]


@pytest.fixture(autouse=True)
def _des_fixes(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)
	monkeypatch.setattr(combat_mod, "roll_dice", lambda notation: DEGATS)


def monstre(**kw):
	m = _monstre_fixture(**kw)
	combat_mod._refresh_snapshot_stats(m)
	return m


def joueur(**kw):
	j = _joueur_fixture(**kw)
	combat_mod._refresh_snapshot_stats(j)
	return j


def _scene(rayon=RAYON, pv_ami=None):
	"""Mage (1,5) → cible (6,5) ; un allié AVANT la cible (3,5), un allié APRÈS (7,5),
	un monstre derrière le mur (11,5), un allié HORS de la ligne (3,2)."""
	mage = joueur(pm=60, x=1, y=5)
	avant = joueur(idx=1, x=3, y=5, nom="Brun")
	apres = joueur(idx=2, x=7, y=5, nom="Ysolde")
	hors = joueur(idx=3, x=3, y=2, nom="Garin")
	if pv_ami is not None:
		avant["currentPV"] = pv_ami
	for j in (mage, avant, apres, hors):
		j["pv_initial"] = j["currentPV"]
	cible = monstre(idx=0, x=6, y=5)
	derriere = monstre(idx=1, x=11, y=5)
	for m in (cible, derriere):
		m["pv_initial"] = m["currentPV"]
	doc = combat([mage, avant, apres, hors], [cible, derriere], cells=CELLS, dims=(W, H))
	res = resolve_action(doc, "sort", cible_id="monstre_0", sort=sort(**rayon))
	return doc, res, mage, avant, apres, hors, cible, derriere


def test_le_rayon_touche_tout_sur_sa_ligne_avant_et_apres_la_cible():
	doc, res, mage, avant, apres, hors, cible, derriere = _scene()
	assert "error" not in res
	touches = {t["id"] for t in res["allies_touches"]}
	assert touches == {avant["id"], apres["id"]}
	assert avant["currentPV"] < avant["pv_initial"] and apres["currentPV"] < apres["pv_initial"]
	assert hors["currentPV"] == hors["pv_initial"]          # hors de la ligne
	assert mage["currentPV"] == mage["pv_initial"]          # le lanceur tire, il n'est pas touché
	assert cible["currentPV"] < cible["pv_initial"]


def test_le_rayon_perce_le_mur():
	doc, res, *_, derriere = _scene()
	assert derriere["currentPV"] < derriere["pv_initial"]
	assert len(res["cibles"]) == 2                      # la cible désignée + le monstre emmuré


def test_sans_perce_le_mur_arrete_le_rayon():
	rayon = {**RAYON, "zone": {**RAYON["zone"], "perce": False}}
	*_, derriere = _scene(rayon)
	assert derriere["currentPV"] == derriere["pv_initial"]


def test_sans_tir_ami_les_allies_sont_epargnes():
	rayon = {**RAYON, "zone": {**RAYON["zone"], "tir_ami": False}}
	doc, res, mage, avant, apres, *_ = _scene(rayon)
	assert "allies_touches" not in res
	assert avant["currentPV"] == avant["pv_initial"] and apres["currentPV"] == apres["pv_initial"]


def test_un_allie_peut_tomber_sous_le_rayon():
	"""Même cascade qu'un coup de monstre : `_traiter_ko`, ligne de journal nommée."""
	doc, res, mage, avant, *_ = _scene(pv_ami=3)
	assert avant["currentPV"] == 0
	assert any("Brun est pris dans" in (e.get("texte") or "") for e in doc["log"])
