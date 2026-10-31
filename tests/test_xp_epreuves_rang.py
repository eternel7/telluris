# tests/test_xp_epreuves_rang.py
# XP d'une épreuve de rang = XP de la bête + tiers du niveau d'entrée du rang visé (Auteur, 31/10).
import copy
import importlib.util
import json
import os

from models import character_stats
from utils import chasse

RACINE = os.path.join(os.path.dirname(__file__), "..")


def _charger(nom):
	spec = importlib.util.spec_from_file_location(nom, os.path.join(RACINE, "dev", f"{nom}.py"))
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod


GEN = _charger("gen_xp_epreuves_maelys")
with open(GEN.dernier_dump(), encoding="utf-8") as _f:
	DUMP = {d["_id"]: d for d in json.load(_f)["docs"]}


def test_part_de_promotion_est_le_tiers_du_niveau_d_entree():
	for rang, niveau in character_stats.QUETE_RANG_NIVEAU_ENTREE.items():
		cout = character_stats.xp_seuil_niveau(niveau + 1) - character_stats.xp_seuil_niveau(niveau)
		assert chasse.xp_promotion(rang) == round(cout / 3)
	assert chasse.xp_promotion("F") == 0   # rang d'inscription : pas d'épreuve


def test_la_part_croit_avec_le_rang():
	parts = [chasse.xp_promotion(r) for r in character_stats.QUETE_RANG_NIVEAU_ENTREE]
	assert parts == sorted(parts) and len(set(parts)) == len(parts)


def test_l_epreuve_ajoute_la_part_sans_toucher_au_cuivre(monkeypatch):
	comptoir = {"_id": "lieu:comptoir"}
	lieu = {"_id": "lieu:x", "label": "X"}
	espece = {"_id": "espece:x", "nom": "Bête", "base_attributes": {"FOR": {"min": 100, "max": 100}}}
	profil = {"_id": "profil:x", "niveau": 5, "nom": "Élite"}
	lire = {"profil:x": profil}.get
	q = chasse._construire_quete_rang(comptoir, "lieu:c", lieu, espece, None, "profil:x", "A", lire)
	base = round((5 * 4 + 100 // 10) * character_stats.QUETE_CHASSE_XP_FACTEUR)
	assert q["rang_vise"] == "S"
	assert q["recompenses"]["xp"] == base + chasse.xp_promotion("S")
	assert q["recompenses"]["cuivre"] == round(base * character_stats.QUETE_CUIVRE_PAR_XP)


def test_xp_des_epreuves_de_maelys_et_generateurs_alignes():
	missions = _charger("gen_missions_rang_b_a_lutecia")
	assert missions.RECOMPENSES_B["xp"] == GEN.XP_ORIGINE["B"] + chasse.xp_promotion("B")
	assert missions.RECOMPENSES_A["xp"] == GEN.XP_ORIGINE["A"] + chasse.xp_promotion("A")
	doc = GEN.generer(DUMP)[0]
	for service in doc["services"].values():
		for entree in service.get("offres") or []:
			rec = entree["offre"]["recompenses"]
			assert rec["xp"] == GEN.XP_ORIGINE[rec["rang_guilde"]] + chasse.xp_promotion(rec["rang_guilde"])


def test_seule_l_xp_change_et_regeneration_idempotente():
	def sans_xp(doc):
		doc = copy.deepcopy(doc)
		doc.pop("_rev", None)
		for service in doc["services"].values():
			for entree in service.get("offres") or []:
				entree["offre"]["recompenses"].pop("xp", None)
		return doc
	doc = GEN.generer(DUMP)[0]
	assert "_rev" not in doc
	assert sans_xp(doc) == sans_xp(DUMP[GEN.MAELYS])
	assert GEN.generer({GEN.MAELYS: doc})[0] == doc
