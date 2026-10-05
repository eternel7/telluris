"""Générateur des invocations MAINTENUES (dev/gen_sorts_invocation_maintenue.py).

Le générateur relit le dump committé : ces tests tiennent quel que soit son âge — un doc est
soit ÉCRIT, soit déjà présent à l'identique (idempotence), jamais perdu.
"""

import json
import os
import sys

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "dev"))

import gen_sorts_invocation_maintenue as gen  # noqa: E402
from utils import sorts  # noqa: E402


def _base():
	return {d["_id"]: d for d in json.load(open(gen.dernier_dump(), encoding="utf-8"))["docs"]
			if isinstance(d, dict) and d.get("_id")}


@pytest.fixture(scope="module")
def construits():
	docs, _lignes, erreurs, _avert = gen.construire(_base(), gen.docs_des_autres_imports())
	assert erreurs == []
	return docs


def test_le_generateur_passe_ses_gardes_et_est_idempotent(tmp_path, construits):
	sortie = tmp_path / "invocations.json"
	assert gen.main(["--sortie", str(sortie)]) == 0
	premier = sortie.read_text(encoding="utf-8")
	assert gen.main(["--sortie", str(sortie)]) == 0
	assert sortie.read_text(encoding="utf-8") == premier
	base, autres = _base(), gen.docs_des_autres_imports()
	ecrits = {d["_id"]: d for d in json.loads(premier)}
	for doc in construits:
		deja = base.get(doc["_id"]) or autres.get(doc["_id"])
		assert ecrits.get(doc["_id"]) == doc or (
			deja is not None and gen._sans_rev(deja) == doc), doc["_id"]


def test_chaque_sort_est_une_invocation_maintenue_que_le_moteur_lit_sans_perte(construits):
	assert len(construits) == len(gen.SORTS)
	for doc in construits:
		vue = sorts.normaliser_sort(doc)
		assert vue is not None, doc["_id"]
		assert sorts.est_maintenu(vue) and sorts.est_invocation(vue), doc["_id"]
		assert vue["maintien"] == doc["maintien"]
		assert vue["invocation"]["nombre"] == doc["invocation"]["nombre"]
		assert vue["famille"] == gen.FAMILLE_INVOCATION, "le répurgateur ne doit pas l'apprendre"
		assert vue["incantation"] == doc.get("incantation", sorts.INCANTATION_PA_DEFAUT)


def test_chaque_sort_a_un_consomme_et_un_catalyseur_operants(construits):
	for doc in construits:
		vue = sorts.normaliser_sort(doc)
		consomme = [c for c in vue["composants"] if c["consomme"]]
		catalyseur = [c for c in vue["composants"] if not c["consomme"]]
		assert len(consomme) == 1 and len(catalyseur) == 1, doc["_id"]
		avec_consomme = sorts.doc_effectif(vue, consomme[0]["bonus"])
		avec_catalyseur = sorts.doc_effectif(vue, catalyseur[0]["bonus"])
		# Le renfort change le DOC (entretien ou nombre), et l'entretien ne tombe jamais à 0.
		assert avec_consomme != vue and avec_catalyseur != vue, doc["_id"]
		assert avec_consomme["maintien"] >= 1 and avec_catalyseur["maintien"] >= 1


def test_aucune_espece_n_est_deja_invoquee_par_un_autre_sort(construits):
	ids = {d["_id"] for d in construits}
	tous = {**gen.docs_des_autres_imports(), **_base()}
	for doc in construits:
		espece = doc["invocation"]["espece"]
		autres = [s["_id"] for s in tous.values()
				  if s.get("type") == "sort" and (s.get("invocation") or {}).get("espece") == espece
				  and s["_id"] not in ids]
		assert autres == [], f"{doc['_id']} réinvoque {espece} ({autres})"


def test_a_puissance_egale_l_ecole_favorisee_paie_moins_d_entretien():
	favorisee = next(iter(gen.ECOLES_FAVORISEES))
	base = next(e for e in gen.COMPOSANTS if e not in gen.ECOLES_FAVORISEES)
	# Une puissance assez haute pour échapper au plancher et au plafond des deux côtés.
	p = gen.K_BASE * gen.MAINTIEN_PM_MAX / 2
	assert gen.entretien(p, favorisee) <= round(gen.entretien(p, base) * gen.FACTEUR_FAVORISE) + 1
	assert gen.entretien(p, favorisee) < gen.entretien(p, base)


def test_l_entretien_suit_la_formule_publiee(construits):
	base, autres = _base(), gen.docs_des_autres_imports()
	for doc in construits:
		inv = doc["invocation"]
		espece = base.get(inv["espece"]) or autres.get(inv["espece"])
		profil = base.get(inv["profil"]) if inv.get("profil") else None
		p = gen.puissance(espece, profil, inv["nombre"])
		assert doc["maintien"] == gen.entretien(p, doc["magie"]), doc["_id"]
		assert gen.MAINTIEN_MIN <= doc["maintien"] <= sorts.MAINTIEN_PM_MAX
