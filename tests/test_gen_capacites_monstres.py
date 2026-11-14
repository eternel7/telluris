# tests/test_gen_capacites_monstres.py
#
# Générateur `dev/gen_capacites_monstres.py` : DELTA seul, idempotent, refus fail-closed.
# Docs synthétiques (CLAUDE.md §20 : jamais de fichier `*_a_importer.json` lu ici).

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dev"))
import gen_capacites_monstres as gen  # noqa: E402


def _base():
	profils = [{"_id": f"profil:{p}", "type": "profil"} for p in
			   ("apprenti", "mage", "heros_mage", "seigneur_mage", "champion", "seigneur")]
	especes = [{"_id": f"espece:{e}", "type": "espece", "tags": ["x"],
				"base_attributes": {"Vol": {"min": 40, "max": 40}, "Int": {"min": 40, "max": 40}}}
			   for e in sorted(set(gen.ATTRIBUTION) | set(gen.MAGIE) | set(gen.IA))]
	return profils + especes


def test_toutes_les_competences_de_la_table_se_normalisent():
	from utils.competences import normaliser_competence
	for suffixe in gen.COMPETENCES:
		assert normaliser_competence(gen.doc_competence(suffixe)), suffixe


def test_attribution_ne_cite_que_des_competences_connues():
	for e, comps in gen.ATTRIBUTION.items():
		assert set(comps) <= set(gen.COMPETENCES), e


def test_emet_puis_rejeu_vide():
	docs = _base()
	sortie, _ = gen.construire(docs)
	assert len([d for d in sortie if d["_id"].startswith("competence:")]) == len(gen.COMPETENCES)
	base = {d["_id"]: d for d in docs}
	base.update({d["_id"]: d for d in sortie})
	assert gen.construire(list(base.values()))[0] == []


def test_seuls_competences_et_tags_changent_et_rien_n_est_retire():
	docs = _base()
	manticore = next(d for d in docs if d["_id"] == "espece:manticore")
	manticore["nom"] = "Manticore"
	manticore["competences"] = ["competence:autre"]
	sortie, _ = gen.construire(docs)
	m = next(d for d in sortie if d["_id"] == "espece:manticore")
	assert m["nom"] == "Manticore"
	assert m["competences"][0] == "competence:autre"
	assert "competence:monstre_dard_caudal" in m["competences"]
	assert m["tags"][0] == "x" and "ia_predateur" in m["tags"]


def test_espece_absente_refuse_le_lot():
	docs = [d for d in _base() if d["_id"] != "espece:dragon"]
	with pytest.raises(ValueError, match="espece:dragon"):
		gen.construire(docs)


def test_id_pris_par_une_autre_vocation_refuse_le_lot():
	docs = _base() + [{"_id": "competence:monstre_toile", "type": "competence", "vocation": "voleur"}]
	with pytest.raises(ValueError, match="monstre_toile"):
		gen.construire(docs)


def test_profil_absent_refuse_le_lot():
	docs = [d for d in _base() if d["_id"] != "profil:heros_mage"]
	with pytest.raises(ValueError, match="profil absent"):
		gen.construire(docs)
