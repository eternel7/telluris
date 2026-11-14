# tests/test_sorts_longs_monstres.py
#
# Sorts LONGS lancés par un MONSTRE (utils/combat.py, `_lancer_capacite_monstre`) :
# - invocation : ses créatures rejoignent SON camp, jouent leur tour, se dissipent à
#   l'épuisement de leur durée ou à la mort de leur invocateur ; ni butin ni kill de quête ;
# - incantation longue : armée, PA et PM versés tour après tour, achevée par le chemin du
#   monstre, rompue par un coup encaissé (test de concentration) ;
# - sort maintenu : entretien en PM à chaque tour, rupture faute de PM, créatures tenues.

import pytest

from utils import combat as combat_mod
from utils.quetes import maj_progress_kills


def _attrs(**kw):
	base = {"V": 5, "F": 30, "R": 40, "Ag": 30, "Vol": 40, "Int": 40, "Cha": 10, "Ch": 10}
	base.update(kw)
	return {c: {"min": v, "max": v} for c, v in base.items()}


SQUELETTE = {"_id": "espece:squelette_test", "type": "espece", "nom": "Squelette",
			 "tags": ["monstre", "mort_vivant"], "base_attributes": _attrs(Vol=0, Int=0)}
MAGE = {"_id": "espece:liche_test", "type": "espece", "nom": "Liche",
		"tags": ["monstre", "mort_vivant"], "base_attributes": _attrs()}
INVOC = {"_id": "sort:levee_test", "type": "sort", "nom": "Levée des os", "magie": "Nécromancie",
		 "niveau": 1, "cout_pm": 6, "cible": "soi", "effets": {},
		 "invocation": {"espece": SQUELETTE["_id"], "nombre": 1, "duree": 2}}
INVOC_TENUE = dict(INVOC, _id="sort:cortege_test", nom="Cortège", maintien=2)
RITUEL = {"_id": "sort:rituel_test", "type": "sort", "nom": "Rituel de mort", "magie": "Nécromancie",
		  "niveau": 1, "cout_pm": 12, "cible": "ennemi", "portee": 6, "jet": "magique",
		  "incantation": 3, "effets": {"degats": "3D6"}}
CARAPACE = {"_id": "sort:carapace_test", "type": "sort", "nom": "Carapace d'os", "magie": "Nécromancie",
			"niveau": 1, "cout_pm": 4, "cible": "soi", "maintien": 3,
			"effets": {"buffs": {"R": 10}, "duree": 2}}
MUR = {"_id": "sort:mur_test", "type": "sort", "nom": "Mur d'os ardents", "magie": "Nécromancie",
	   "niveau": 1, "cout_pm": 6, "cible": "ennemi", "portee": 6, "jet": "magique", "maintien": 3,
	   "zone": {"forme": "carre", "rayon": 1, "origine": "cible"}, "effets": {"degats": "2D6"}}
CATALOGUE = {d["_id"]: d for d in (SQUELETTE, MAGE, INVOC, INVOC_TENUE, RITUEL, CARAPACE, MUR)}


@pytest.fixture(autouse=True)
def catalogue(monkeypatch):
	monkeypatch.setattr(combat_mod, "get_doc", lambda i: CATALOGUE.get(i))
	monkeypatch.setattr(combat_mod, "find_docs", lambda q: [])
	# d100 à 50 (touche, hors critique), chaque dé de dégâts à son minimum.
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50 if b == 100 else a)


def _joueur(x=4, y=6):
	return {"id": "joueur_0", "nom": "Frida", "vivant": True, "currentPV": 200, "pv_max": 200,
			"currentPM": 10, "pm_max": 10, "pa": 0, "pa_zones": {}, "ag": 0, "pm_def": 0,
			"pos": {"x": x, "y": y}, "effets_actifs": [], "facing": 0,
			"caracts_base": {"V": 5, "F": 30, "R": 30, "Ag": 0, "Vol": 20, "Int": 20, "Cha": 10, "Ch": 10}}


def _mage(sorts, x=4, y=1):
	m = combat_mod.build_monster_snapshot(MAGE, None, 0, calculer_xp=False)
	m["pos"] = {"x": x, "y": y}
	m["toucher_magique"] = 200
	m["sorts_connus"] = list(sorts)
	m["detecte"] = True
	return m


def _arene(mage, joueur):
	return {"_id": "combat:test", "status": "active", "tour": 1, "log": [],
			"joueurs": [joueur], "monstres": [mage],
			"ordre_initiative": [joueur["id"], mage["id"]], "acteur_courant_index": 1,
			"grid": {"dims": {"x": 9, "y": 9}, "cells": [[1] * 9 for _ in range(9)], "nav": {}}}


def _textes(doc):
	return [l["texte"] for l in doc["log"]]


# ── Invocation ────────────────────────────────────────────────────────────────────

def test_un_monstre_invoque_dans_son_camp():
	mage, j = _mage([INVOC["_id"]]), _joueur()
	doc = _arene(mage, j)
	pm = mage["currentPM"]
	assert combat_mod._tenter_capacite_monstre(doc, mage, doc["grid"]) is True
	crees = [m for m in doc["monstres"] if m.get("est_invocation")]
	assert len(crees) == 1
	c = crees[0]
	assert c["id"] == "monstre_1" and c["invocateur_id"] == mage["id"] and c["vivant"]
	assert c["xp_reward"] == 0 and c["invocation_restants"] == INVOC["invocation"]["duree"]
	# Joue juste après l'acteur courant, comme une invocation du joueur.
	assert doc["ordre_initiative"][doc["acteur_courant_index"] + 1] == c["id"]
	assert mage["currentPM"] == pm - INVOC["cout_pm"]
	# Pas de second appel tant que la première créature tient.
	options = combat_mod._options_capacite_monstre(doc, mage, doc["grid"])
	assert [o["invocations_actives"] for o in options if o.get("invocation")] == [1]


def test_la_creature_d_un_monstre_s_epuise_puis_quitte_le_combat():
	mage, j = _mage([INVOC["_id"]]), _joueur()
	doc = _arene(mage, j)
	combat_mod._tenter_capacite_monstre(doc, mage, doc["grid"])
	c = next(m for m in doc["monstres"] if m.get("est_invocation"))
	for _ in range(INVOC["invocation"]["duree"]):
		assert c["vivant"]
		doc["acteur_courant_index"] = doc["ordre_initiative"].index(c["id"])
		combat_mod._run_monster_turn(doc, c, doc["grid"])
	assert not c["vivant"] and c.get("dissipe")
	combat_mod._purger_invocations(doc)
	assert c["id"] not in [m["id"] for m in doc["monstres"]]
	assert c["id"] not in doc["ordre_initiative"]


def test_l_invocateur_tombe_ses_creatures_se_dissipent_et_la_victoire_suit():
	mage, j = _mage([INVOC["_id"]]), _joueur()
	doc = _arene(mage, j)
	combat_mod._tenter_capacite_monstre(doc, mage, doc["grid"])
	mage["vivant"] = False
	mage["currentPV"] = 0
	combat_mod._purger_invocations(doc)
	assert [m["id"] for m in doc["monstres"]] == [mage["id"]]
	assert doc["status"] == "victoire"


def test_une_creature_invoquee_ne_laisse_ni_butin_ni_kill_de_quete():
	mage, j = _mage([INVOC["_id"]]), _joueur()
	doc = _arene(mage, j)
	combat_mod._tenter_capacite_monstre(doc, mage, doc["grid"])
	c = next(m for m in doc["monstres"] if m.get("est_invocation"))
	c["vivant"] = False
	assert combat_mod._butin_du_monstre(c) == []
	perso = {"quetes_actives": [{"objectif": {"type": "kill", "cible": SQUELETTE["_id"],
											  "quantite": 3}, "progress": 0}]}
	maj_progress_kills(perso, [c])
	assert perso["quetes_actives"][0]["progress"] == 0


# ── Incantation longue ────────────────────────────────────────────────────────────

def _armer_rituel(actions=2):
	mage, j = _mage([RITUEL["_id"]]), _joueur()
	mage["actions_max"] = actions    # le rituel de 3 PA déborde sur les tours suivants
	doc = _arene(mage, j)
	combat_mod._reset_turn_budget(mage, doc)
	assert combat_mod._tenter_capacite_monstre(doc, mage, doc["grid"]) is True
	return doc, mage, j


def test_un_monstre_arme_son_incantation_puis_l_acheve_au_tour_suivant():
	doc, mage, j = _armer_rituel(actions=2)
	inc = mage["incantation"]
	assert inc["camp"] == "monstre" and inc["pa_investis"] == 2 and j["currentPV"] == 200
	doc["acteur_courant_index"] = 1
	combat_mod._run_monster_turn(doc, mage, doc["grid"])
	assert mage["incantation"] is None          # achevée en début de ce tour (3ᵉ PA)
	assert j["currentPV"] < 200                  # le rituel est parti
	assert mage["capacite_lancee"] is True       # c'était sa capacité du tour


def test_un_monstre_qui_canalise_ne_bouge_ni_ne_frappe():
	doc, mage, j = _armer_rituel(actions=1)
	pm_avant = mage["currentPM"] + mage["incantation"]["pm_verses"]
	pos = dict(mage["pos"])
	doc["acteur_courant_index"] = 1
	combat_mod._run_monster_turn(doc, mage, doc["grid"])     # 2ᵉ PA : il canalise
	assert mage["incantation"]["pa_investis"] == 2
	assert mage["pos"] == pos and j["currentPV"] == 200
	doc["acteur_courant_index"] = 1
	combat_mod._run_monster_turn(doc, mage, doc["grid"])     # 3ᵉ PA : le sort part
	assert mage["incantation"] is None and j["currentPV"] < 200
	# PM versés par tranches, jamais redébités au départ du sort.
	assert pm_avant - mage["currentPM"] == RITUEL["cout_pm"]


def test_un_coup_peut_rompre_l_incantation_d_un_monstre(monkeypatch):
	doc, mage, j = _armer_rituel()
	monkeypatch.setattr(combat_mod, "_resoudre_jet", lambda a, d, s, furtif=False: {
		"roll": 99, "seuil": s, "touche": False, "critique": False, "fumble": False,
		"mult_degats": 1})
	combat_mod._concentration_monstre(doc, mage, j, 15)
	assert mage["incantation"] is None
	assert any("perd le fil" in t for t in _textes(doc))


# ── Sorts maintenus ───────────────────────────────────────────────────────────────

def test_un_monstre_entretient_son_sort_puis_le_perd_faute_de_pm():
	mage, j = _mage([CARAPACE["_id"]]), _joueur()
	doc = _arene(mage, j)
	assert combat_mod._tenter_capacite_monstre(doc, mage, doc["grid"]) is True
	assert [c["sort_id"] for c in mage["concentrations"]] == [CARAPACE["_id"]]
	entree = next(e for e in mage["effets_actifs"] if e["source_id"] == CARAPACE["_id"])
	assert entree.get("maintenu") is True
	pm = mage["currentPM"]
	combat_mod._reset_turn_budget(mage, doc)
	assert mage["currentPM"] == pm - CARAPACE["maintien"]
	mage["currentPM"] = CARAPACE["maintien"] - 1
	combat_mod._reset_turn_budget(mage, doc)
	assert not mage.get("concentrations")
	assert not any(e["source_id"] == CARAPACE["_id"] for e in mage["effets_actifs"])


def test_une_invocation_maintenue_d_un_monstre_tombe_avec_sa_concentration():
	mage, j = _mage([INVOC_TENUE["_id"]]), _joueur()
	doc = _arene(mage, j)
	combat_mod._tenter_capacite_monstre(doc, mage, doc["grid"])
	c = next(m for m in doc["monstres"] if m.get("est_invocation"))
	assert c["sort_maintenu"] == INVOC_TENUE["_id"]
	# Tenue par l'entretien : son compteur ne bouge plus.
	restants = c["invocation_restants"]
	doc["acteur_courant_index"] = doc["ordre_initiative"].index(c["id"])
	combat_mod._run_monster_turn(doc, c, doc["grid"])
	assert c["vivant"] and c["invocation_restants"] == restants
	mage["currentPM"] = 0
	combat_mod._reset_turn_budget(mage, doc)
	assert not c["vivant"] and c.get("dissipe")


def test_la_zone_persistante_d_un_monstre_brule_le_joueur_qui_y_reste():
	mage, j = _mage([MUR["_id"]]), _joueur()
	doc = _arene(mage, j)
	assert combat_mod._tenter_capacite_monstre(doc, mage, doc["grid"]) is True
	zones = doc.get("zones_persistantes") or []
	assert [z["lanceur_id"] for z in zones] == [mage["id"]]
	pv = j["currentPV"]
	combat_mod._bruler_zones(doc, j)
	assert j["currentPV"] < pv
	# Le monstre tombe : son mur s'éteint avec lui.
	mage["vivant"] = False
	mage["currentPV"] = 0
	combat_mod._purger_invocations(doc)
	assert not doc.get("zones_persistantes")
