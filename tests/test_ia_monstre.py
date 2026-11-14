# tests/test_ia_monstre.py
#
# Types d'IA des monstres (utils/ia_monstre.py) : tags `ia_<type>[_<nombre>][_<profil>]`,
# trois axes (déplacement, cible, fuite), branchés dans `combat._run_monster_turn`.

import pytest

from utils import combat as combat_mod
from utils import ia_monstre as ia


# ── Lecture des tags ──────────────────────────────────────────────────────────────

def test_sans_tag_ia_par_defaut():
	assert ia.ia_de_tags(["predateur", "vol"], "profil:mage") == ia.DEFAUT
	assert ia.ia_du_snapshot(["predateur"], None) is None


def test_type_a_tirets_bas_reconnu():
	assert ia.ia_de_tags(["ia_hit_and_run"])["deplacement"] == "hit_and_run"


def test_nombre_et_defauts():
	assert ia.ia_de_tags(["ia_fuyard"])["fuite"] == ia.FUITE_DEFAUT
	assert ia.ia_de_tags(["ia_fuyard_50"])["fuite"] == 50
	assert ia.ia_de_tags(["ia_embuscade"])["rayon"] == ia.RAYON_EMBUSCADE_DEFAUT
	assert ia.ia_de_tags(["ia_embuscade_1"])["rayon"] == 1


def test_axes_cumulables():
	r = ia.ia_de_tags(["ia_meute", "ia_predateur", "ia_fuyard_20"])
	assert (r["deplacement"], r["cible"], r["fuite"]) == ("meute", "predateur", 20)


def test_le_tag_du_profil_l_emporte_sur_son_axe_seulement():
	tags = ["ia_meute", "ia_fuyard_30", "ia_berserker_champion", "ia_artilleur_heros_mage"]
	champion = ia.ia_de_tags(tags, "profil:champion")
	assert (champion["deplacement"], champion["cible"], champion["fuite"]) == ("meute", "berserker", 30)
	mage = ia.ia_de_tags(tags, "profil:heros_mage")
	assert (mage["deplacement"], mage["cible"]) == ("artilleur", "proche")
	assert ia.ia_de_tags(tags, "profil:novice")["deplacement"] == "meute"


def test_tag_inconnu_ignore():
	assert ia.ia_de_tags(["ia_", "ia_dormeur"], None) == ia.DEFAUT
	# Suffixe non numérique = un PROFIL : ce tag ne vaut que pour `profil:x_y_z`.
	assert ia.ia_de_tags(["ia_meute_x_y_z"], None) == ia.DEFAUT
	assert ia.ia_de_tags(["ia_meute_x_y_z"], "profil:x_y_z")["deplacement"] == "meute"


# ── Choix purs ────────────────────────────────────────────────────────────────────

def _j(i, pv, pv_max=100, d=1):
	return {"id": f"joueur_{i}", "currentPV": pv, "pv_max": pv_max, "_d": d}


def test_predateur_vise_le_plus_blesse_qu_il_atteint():
	a, b, c = _j(0, 90, d=1), _j(1, 20, d=3), _j(2, 5, d=9)
	choix = ia.choisir_cible({"cible": "predateur"}, {}, [a, b, c],
							 lambda j: j["_d"], lambda j: j["_d"] <= 4)
	assert choix is b       # c est plus blessé mais hors d'atteinte ce tour


def test_predateur_sans_proie_atteignable_prend_le_plus_proche():
	a, b = _j(0, 90, d=6), _j(1, 20, d=8)
	assert ia.choisir_cible({"cible": "predateur"}, {}, [a, b], lambda j: j["_d"], lambda j: False) is a


def test_berserker_vise_son_agresseur():
	a, b = _j(0, 90, d=1), _j(1, 90, d=5)
	m = {"dernier_agresseur": "joueur_1"}
	assert ia.choisir_cible({"cible": "berserker"}, m, [a, b], lambda j: j["_d"], lambda j: True) is b
	assert ia.choisir_cible({"cible": "berserker"}, {}, [a, b], lambda j: j["_d"], lambda j: True) is a


def test_doit_fuir_et_berserker_jamais():
	m = {"currentPV": 20, "pv_max": 100}
	assert ia.doit_fuir({"fuite": 30}, m)
	assert not ia.doit_fuir({"fuite": 10}, m)
	assert not ia.doit_fuir({"fuite": 30, "cible": "berserker"}, m)


def test_score_case_meute():
	assert ia.score_case_meute(-1, False) > ia.score_case_meute(0, False) > ia.score_case_meute(1, False)
	assert ia.score_case_meute(-1, True) < ia.score_case_meute(0, False)


# ── En combat ─────────────────────────────────────────────────────────────────────

def _espece(tags=()):
	return {"_id": "espece:cobaye", "nom": "Cobaye", "tags": list(tags),
			"base_attributes": {c: {"min": v, "max": v} for c, v in
								(("V", 4), ("F", 30), ("R", 40), ("Ag", 30),
								 ("Vol", 10), ("Int", 10), ("Cha", 10), ("Ch", 10))}}


@pytest.fixture(autouse=True)
def _sans_base(monkeypatch):
	monkeypatch.setattr(combat_mod, "get_doc", lambda i: None)
	monkeypatch.setattr(combat_mod, "find_docs", lambda q: [])
	# d100 à 50 (touche), dés de dégâts à 1 : personne ne meurt par accident.
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50 if b == 100 else a)


def _monstre(tags=(), x=4, y=1, idx=0, profil=None):
	m = combat_mod.build_monster_snapshot(_espece(tags), profil, idx)
	m["pos"] = {"x": x, "y": y}
	m["cc"] = 200
	return m


def _joueur(i=0, x=4, y=7, pv=200):
	return {"id": f"joueur_{i}", "nom": f"J{i}", "vivant": True, "currentPV": pv, "pv_max": 200,
			"currentPM": 0, "pm_max": 0, "pa": 0, "pa_zones": {}, "ag": 0, "pm_def": 0,
			"pos": {"x": x, "y": y}, "facing": 0, "effets_actifs": [],
			"caracts_base": {"V": 5, "F": 30, "R": 30, "Ag": 0, "Vol": 20, "Int": 20, "Cha": 10, "Ch": 10}}


def _arene(monstres, joueurs, n=12):
	return {"_id": "combat:test", "status": "active", "tour": 1, "log": [],
			"joueurs": joueurs, "monstres": monstres,
			"ordre_initiative": [j["id"] for j in joueurs] + [m["id"] for m in monstres],
			"acteur_courant_index": len(joueurs),
			"grid": {"dims": {"x": n, "y": n}, "cells": [[1] * n for _ in range(n)], "nav": {}}}


def _tour(doc, m):
	combat_mod._run_monster_turn(doc, m, doc["grid"])


def test_snapshot_fige_l_ia_du_profil():
	m = combat_mod.build_monster_snapshot(_espece(["ia_meute", "ia_berserker_champion"]),
										  {"_id": "profil:champion", "niveau": 4}, 0)
	assert m["ia"]["cible"] == "berserker" and m["ia"]["deplacement"] == "meute"
	assert "ia" not in combat_mod.build_monster_snapshot(_espece(), None, 0)


def test_cible_predateur_dans_le_tour():
	m = _monstre(["ia_predateur"], x=4, y=4)
	sain, blesse = _joueur(0, 4, 5, pv=200), _joueur(1, 6, 6, pv=30)
	doc = _arene([m], [sain, blesse])
	assert combat_mod._cible_joueur(doc, m) is blesse


def test_provocation_prime_sur_le_type():
	m = _monstre(["ia_predateur"], x=4, y=4)
	sain, blesse = _joueur(0, 4, 9, pv=200), _joueur(1, 4, 5, pv=30)
	m["effets_actifs"] = [{"provocation": 1, "provocateur_id": "joueur_0", "restants": 2}]
	doc = _arene([m], [sain, blesse])
	assert combat_mod._cible_joueur(doc, m) is sain


def test_agression_memorisee_pour_le_berserker():
	m = _monstre(["ia_berserker"], x=4, y=4)
	loin, pres = _joueur(0, 4, 9), _joueur(1, 4, 5)
	doc = _arene([m], [loin, pres])
	combat_mod._marquer_agression(m, loin)
	assert combat_mod._cible_joueur(doc, m) is loin


def test_fuyard_s_eloigne_sous_son_seuil():
	m = _monstre(["ia_fuyard_50"], x=5, y=5)
	m["currentPV"] = m["pv_max"] // 4
	j = _joueur(0, 5, 6)
	doc = _arene([m], [j])
	_tour(doc, m)
	assert combat_mod._cheby(m, j) > 1
	assert j["currentPV"] == 200
	assert any("prend la fuite" in l["texte"] for l in doc["log"])


def test_fuyard_accule_se_bat():
	m = _monstre(["ia_fuyard_50"], x=0, y=0)
	m["currentPV"] = m["pv_max"] // 4
	j = _joueur(0, 1, 1)
	doc = _arene([m], [j])
	doc["grid"]["cells"] = [[1 if (x, y) in ((0, 0), (1, 1)) else 0 for x in range(12)] for y in range(12)]
	_tour(doc, m)
	assert j["currentPV"] < 200


def test_berserker_ne_fuit_jamais():
	m = _monstre(["ia_fuyard_50", "ia_berserker"], x=5, y=5)
	m["currentPV"] = m["pv_max"] // 4
	j = _joueur(0, 5, 6)
	doc = _arene([m], [j])
	_tour(doc, m)
	assert j["currentPV"] < 200


def test_hit_and_run_frappe_une_fois_puis_se_replie():
	m = _monstre(["ia_hit_and_run"], x=5, y=3)
	m["deplacement"] = 6
	j = _joueur(0, 5, 5)
	doc = _arene([m], [j])
	_tour(doc, m)
	assert m["attaques"] == 1
	assert j["currentPV"] < 200
	assert combat_mod._cheby(m, j) > 1
	assert any("se replie" in l["texte"] for l in doc["log"])


def test_brute_frappe_tant_qu_il_peut_et_reste():
	m = _monstre([], x=5, y=3)
	j = _joueur(0, 5, 5)
	doc = _arene([m], [j])
	_tour(doc, m)
	assert combat_mod._cheby(m, j) == 1


def test_embuscade_dort_puis_surgit():
	m = _monstre(["ia_embuscade_2"], x=5, y=5)
	j = _joueur(0, 5, 10)
	doc = _arene([m], [j])
	_tour(doc, m)
	assert m["pos"] == {"x": 5, "y": 5} and not m.get("eveille")
	j["pos"] = {"x": 5, "y": 7}
	_tour(doc, m)
	assert m["eveille"]
	assert j["currentPV"] < 200


def test_embuscade_reveillee_par_un_coup():
	m = _monstre(["ia_embuscade"], x=5, y=5)
	combat_mod._marquer_agression(m, _joueur(0, 5, 11))
	assert m["eveille"]


def test_embuscade_regagne_son_poste():
	m = _monstre(["ia_embuscade_1"], x=5, y=5)
	m["eveille"] = True
	m["poste"] = {"x": 5, "y": 2}
	j = _joueur(0, 5, 11)
	doc = _arene([m], [j])
	_tour(doc, m)
	assert combat_mod._cheby(m, {"pos": {"x": 5, "y": 2}}) < 3


def test_artilleur_garde_sa_portee():
	m = _monstre(["ia_artilleur"], x=5, y=5)
	m["attaque_profils"] = [{"mode": "tir", "portee": 5, "ranged": True, "toucher": "cd",
							 "degats": "degats_cd"}]
	m["cd"], m["degats_cd"] = 200, "1D4"
	j = _joueur(0, 5, 6)
	doc = _arene([m], [j])
	_tour(doc, m)
	assert combat_mod._cheby(m, j) > 1


def test_meute_cherche_le_dos():
	m = _monstre(["ia_meute"], x=5, y=1)
	m["deplacement"] = 10
	j = _joueur(0, 5, 5)
	j["facing"] = 0          # regarde le Nord, vers le loup : le dos est au Sud
	doc = _arene([m], [j])
	_tour(doc, m)
	assert m["pos"]["y"] > 5, f"le loup aurait dû contourner : {m['pos']}"


def test_meute_se_repartit():
	a = _monstre(["ia_meute"], x=5, y=1, idx=0)
	b = _monstre(["ia_meute"], x=6, y=1, idx=1)
	a["deplacement"] = b["deplacement"] = 10
	j = _joueur(0, 5, 5)
	doc = _arene([a, b], [j])
	_tour(doc, a)
	_tour(doc, b)
	assert a["case_visee"] != b["case_visee"]


def test_protecteur_rejoint_le_blesse():
	gardien = _monstre(["ia_protecteur"], x=1, y=1, idx=0)
	blesse = _monstre([], x=8, y=8, idx=1)
	blesse["currentPV"] = 1
	j = _joueur(0, 10, 1)
	doc = _arene([gardien, blesse], [j])
	_tour(doc, gardien)
	assert combat_mod._cheby(gardien, blesse) < 7
