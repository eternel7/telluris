# tests/test_direction_mine_borin.py
# Borin indique le Temple-Portail de Saint-Austrelin pendant une commission de la mine
# (dev/gen_direction_mine_borin.py, rejoué contre le DERNIER dump), et la condition
# `commission_donjon` qui garde ce choix (utils/pnj.condition_ok, linter, router).

import glob
import json
import os
import re

import pytest

from dev import gen_direction_mine_borin as g
from utils import donjon, lint_dialogues, pnj
from utils.lint_dialogues import analyser

MINE = "donjon:mine_de_saint_austrelin"


def _dump():
	dumps = sorted(glob.glob(os.path.join(g.RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		pytest.skip("aucun dump")
	with open(dumps[-1], encoding="utf-8") as f:
		return {d["_id"]: d for d in json.load(f)["docs"]}


@pytest.fixture(scope="module")
def base():
	return _dump()


@pytest.fixture(scope="module")
def borin(base):
	return g.etat_vise(base[g.PNJ])


def _visibles(doc, donjons=(), flags=None):
	contexte = {"quetes_actives": set(), "quetes_reussies": set(), "flags": flags or {},
				"donjons_commission": set(donjons)}
	return {c["id"] for c in pnj._choix_visibles(doc, doc["dialogue"]["noeud_depart"], contexte)}


# ── Condition `commission_donjon` ──────────────────────────────────────────────

def test_condition_structuree_des_deux_cotes():
	assert "commission_donjon" in pnj.CONDITIONS_STRUCTUREES
	assert "commission_donjon" in lint_dialogues.CONDITIONS_STRUCTUREES


def test_condition_vraie_seulement_pour_le_donjon_de_la_commission():
	ctx = pnj.contexte_dialogue({}, {}, lambda _l: 0, donjons_commission={MINE})
	assert pnj.condition_ok({"commission_donjon": MINE}, ctx)
	assert not pnj.condition_ok({"commission_donjon": "donjon:autre"}, ctx)
	sans = pnj.contexte_dialogue({}, {}, lambda _l: 0)
	assert not pnj.condition_ok({"commission_donjon": MINE}, sans)
	# Fail-closed sur une valeur non textuelle.
	assert not pnj.condition_ok({"commission_donjon": [MINE]}, ctx)


def test_le_linter_refuse_un_id_qui_n_est_pas_un_donjon(borin):
	doc = json.loads(json.dumps(borin))
	for c in doc["dialogue"]["noeuds"][doc["dialogue"]["noeud_depart"]]["choix"]:
		if c["id"] == g.CHOIX_ID:
			c["condition"] = {"commission_donjon": "mine_de_saint_austrelin"}
	assert analyser([doc])["erreurs"] == 1


def test_le_donjon_de_la_commission_est_relu_depuis_sa_salle(base):
	"""Le router passe `donjon_de_lieu(objectif.lieu)` : la salle de la mine désigne bien MINE."""
	donjons = [d for d in base.values() if d.get("type") == "donjon"]
	salle = base[MINE]["battle_maps"][0]["lieu"]
	assert donjon.donjon_de_lieu(salle, lambda _sel: donjons)["_id"] == MINE


# ── Contenu ────────────────────────────────────────────────────────────────────

def test_passe_le_linter(borin):
	rapport = analyser([borin])
	assert rapport["erreurs"] == 0, rapport["trouvailles"]


def test_regeneration_idempotente(borin):
	assert g.modifies({g.PNJ: borin, g.DONJON: {}}) == []


def test_le_mandataire_de_la_mine_est_bien_gautier(base):
	assert base["pnj:gautier_de_valcroix"]["services"]["commission"]["donjon"] == MINE


def test_visible_seulement_pendant_une_commission_de_la_mine(borin):
	assert g.CHOIX_ID not in _visibles(borin)
	assert g.CHOIX_ID not in _visibles(borin, donjons=["donjon:petra_crue"])
	assert g.CHOIX_ID in _visibles(borin, donjons=[MINE])


def test_garde_les_autres_choix_de_borin(base, borin):
	# Le dump peut déjà porter le choix (delta importé) : on l'écarte des deux côtés.
	avant = [c["id"] for c in base[g.PNJ]["dialogue"]["noeuds"]["accueil"]["choix"]
			 if c["id"] != g.CHOIX_ID]
	apres = [c["id"] for c in borin["dialogue"]["noeuds"]["accueil"]["choix"]]
	assert [i for i in apres if i != g.CHOIX_ID] == avant
	assert apres.index(g.CHOIX_ID) == apres.index(g.AVANT) - 1


def test_indique_l_est_et_le_temple(borin):
	texte = borin["dialogue"]["noeuds"][g.NOEUD]["texte"]
	for mot in ("est", "Temple-Portail de Saint-Austrelin", "mine"):
		assert mot in texte


def test_borin_tutoie_et_raconte_au_vous(borin):
	texte = borin["dialogue"]["noeuds"][g.NOEUD]["texte"]
	for replique in re.findall(r"«([^»]*)»", texte):
		assert not re.search(r"\b(vous|votre|vos)\b", replique, re.I)
