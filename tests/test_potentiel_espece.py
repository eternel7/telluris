# tests/test_potentiel_espece.py
# Potentiel d'une ESPÈCE, équipement compris (`potentiel.potentiel_espece`) et survie qui
# pèse l'armure selon la zone qu'elle couvre et la régén. Hasard absent : la référence d'un
# humanoïde est NUE, l'équipement est compté en espérance.

import pytest

from models import character_stats
from utils import characters, combat, potentiel, simulateur

ATTRS = {"V": 4, "F": 40, "R": 40, "Ag": 30, "Vol": 20, "Int": 15, "Cha": 10, "Ch": 10}
ITEMS = {
	"item:cotte":   {"nom": "Cotte", "categorie": "armure", "slots": ["torse"], "bonus_pa": 17},
	"item:heaume":  {"nom": "Heaume", "categorie": "armure", "slots": ["tete"], "bonus_pa": 17},
	"item:hache":   {"nom": "Hache", "categorie": "arme", "slots": ["main_droite"],
					 "portee": 1, "bonus_degats": 6},
	"item:masse":   {"nom": "Masse", "categorie": "arme", "slots": ["main_droite"],
					 "portee": 1, "bonus_degats": 3},
	"item:viande":  {"nom": "Viande", "categorie": "nourriture", "slots": []},
}


def _espece(eid, tags, items=()):
	return {"_id": eid, "type": "espece", "nom": eid.split(":")[1], "tags": tags,
			"items": list(items),
			"base_attributes": {k: {"min": v, "max": v} for k, v in ATTRS.items()}}


ORC = _espece("espece:orc", ["humanoide"], ["item:cotte", "item:hache", "item:viande"])
ORC_NU = _espece("espece:orc_nu", ["humanoide"])
ORC_DEUX_ARMES = _espece("espece:orc_armes", ["humanoide"], ["item:hache", "item:masse"])
# Une bête ne s'équipe pas, même si son doc liste des objets (butin).
LOUP = _espece("espece:loup", ["predateur"], ["item:cotte"])

DOCS = {**{k: {"_id": k, "type": "item", **v} for k, v in ITEMS.items()},
		**{e["_id"]: e for e in (ORC, ORC_NU, ORC_DEUX_ARMES, LOUP)}}


@pytest.fixture(autouse=True)
def db(monkeypatch):
	"""`recompute_equipment_bonus`, `_weapon_attacks` et `items_equipables_monstre` lisent le
	`get_doc` GLOBAL de leur module : détournés tous les deux. Les sorts d'un humanoïde
	(`roll_monster_sorts`) passent par `find_docs` : aucun ici."""
	monkeypatch.setattr(characters, "get_doc", DOCS.get)
	monkeypatch.setattr(combat, "get_doc", DOCS.get)
	monkeypatch.setattr(combat, "find_docs", lambda *a, **k: [])
	monkeypatch.setattr(character_stats, "MONSTRE_EQUIPEMENT_PROBA", 0.65)


def _pot(eid, **regles):
	return potentiel.potentiel_espece(eid, None, DOCS.get, regles or None)


# ── Référence nue et déterministe ────────────────────────────────────────────────────

def test_reference_d_un_humanoide_est_nue():
	snap = simulateur._snapshot_median(ORC, None)
	assert "slots" not in snap
	assert snap["attaque_profils"][0]["label"] == "Attaque naturelle"


def test_potentiel_espece_deterministe():
	assert _pot("espece:orc") == _pot("espece:orc")


# ── Bonus humanoïde + espérance d'équipement ─────────────────────────────────────────

def test_bete_ni_equipement_ni_bonus():
	r = _pot("espece:loup")
	assert r["equipement"] == 0 and r["bonus_humanoide"] == 0 and r["total"] == r["nu"]


def test_humanoide_sans_objet_ni_bonus():
	r = _pot("espece:orc_nu")
	assert r["equipement"] == 0 and r["bonus_humanoide"] == 0 and r["total"] == r["nu"]


def test_humanoide_equipe_gain_et_bonus():
	r = _pot("espece:orc")
	bonus = potentiel.REGLES_POTENTIEL["bonus_humanoide"]
	assert r["bonus_humanoide"] == bonus > 0
	assert r["equipement"] > 0
	# La nourriture n'est pas portable : seules l'arme et l'armure sont mesurées.
	assert {d["item"] for d in r["detail"]} == {"item:cotte", "item:hache"}
	assert all(d["gain"] > 0 for d in r["detail"])
	assert r["total"] == pytest.approx((r["nu"] + r["equipement"]) * (1 + bonus), abs=0.1)


def test_esperance_suit_la_proba_de_tirage(monkeypatch):
	monkeypatch.setattr(character_stats, "MONSTRE_EQUIPEMENT_PROBA", 0.0)
	assert _pot("espece:orc")["equipement"] == 0
	monkeypatch.setattr(character_stats, "MONSTRE_EQUIPEMENT_PROBA", 1.0)
	r = _pot("espece:orc")
	# Cotte et hache occupent des slots distincts : à p=1 les deux sont portées.
	assert r["equipement"] == pytest.approx(sum(d["gain"] for d in r["detail"]), abs=0.15)


def test_deux_armes_pour_une_main_ne_comptent_qu_une_fois(monkeypatch):
	monkeypatch.setattr(character_stats, "MONSTRE_EQUIPEMENT_PROBA", 1.0)
	r = _pot("espece:orc_armes")
	gains = [d["gain"] for d in r["detail"]]
	assert len(gains) == 2
	# Une seule main_droite : gain moyen des deux, pas leur somme.
	assert r["equipement"] == pytest.approx(sum(gains) / 2, abs=0.15)


def test_esperance_min_binomiale():
	assert potentiel._esperance_min(1, 2, 0.5) == pytest.approx(0.75)   # 1 − 0.5²
	assert potentiel._esperance_min(2, 2, 0.5) == pytest.approx(1.0)    # 2 × 0.5
	assert potentiel._esperance_min(1, 0, 0.5) == 0


def test_bonus_humanoide_reglable():
	sans = _pot("espece:orc", bonus_humanoide=0.0)
	avec = _pot("espece:orc", bonus_humanoide=0.5)
	assert avec["total"] == pytest.approx(sans["total"] * 1.5, abs=0.2)


# ── Survie : armure pesée par zone, régén ────────────────────────────────────────────

def _snap(**k):
	base = {"pv_max": 100, "pa": 0, "ag": 0, "esquive": 0, "actions_max": 1,
			"degats_cc": "1D6", "cc": 50}
	return {**base, **k}


def test_survie_armure_localisee_pesee_par_sa_zone():
	casque = _snap(pa=10, pa_zones={"tete": 10})
	global_ = _snap(pa=10)
	s_casque = potentiel.potentiel_combat(casque, {})["survie"]
	s_global = potentiel.potentiel_combat(global_, {})["survie"]
	# Le casque ne protège que la tranche « tête » du d100 : bien moins qu'un PA partout.
	assert s_casque < s_global
	attendu = 100 * (1 + potentiel.REGLES_POTENTIEL["facteur_pa"] * combat.pa_de_zone(casque))
	assert s_casque == pytest.approx(attendu, abs=0.1)


def test_survie_compte_la_regen():
	r = potentiel.REGLES_POTENTIEL
	s = potentiel.potentiel_combat(_snap(regen_pv_base=2), {})["survie"]
	assert s == pytest.approx(100 + 2 * r["tours_reference"], abs=0.1)


def test_casque_rapporte_moins_que_cotte(monkeypatch):
	# Même bonus_pa, zones différentes : le torse (35 % des coups) vaut plus que la tête (7 %).
	docs = {**DOCS, "espece:orc": {**ORC, "items": ["item:cotte", "item:heaume"]}}
	monkeypatch.setattr(combat, "get_doc", docs.get)
	monkeypatch.setattr(characters, "get_doc", docs.get)
	g = {d["item"]: d["gain"] for d in potentiel.potentiel_espece("espece:orc", None, docs.get)["detail"]}
	assert g["item:cotte"] > g["item:heaume"] > 0
