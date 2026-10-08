# tests/test_sorts_migres_contenu.py
#
# Contenu `jsons/migration_competences_sorts_a_importer.json` (dev/gen_sorts_migres.py) — les
# attaques magiques de compétence devenues des sorts, en UN fichier d'import :
#   · le générateur passe toutes ses gardes ; le fichier committé est sa sortie ;
#   · chaque attaque migrée a, dans le MÊME fichier, son remplaçant de compétence (même `_id`)
#     qui n'est plus une attaque, et son sort, son grimoire unique et sa recette ;
#   · chaque sort : catalyseur (constante) AVANT consommé (dés), PM = origine × PM_FACTEUR ;
#   · effets fusionnés avec TOUS les composants résolus par le moteur ;
#   · régénération idempotente (sorts et grimoires déjà importés ⇒ seuls restent les
#     remplaçants, qui ont leur propre règle de réémission).

import copy
import glob
import importlib.util
import json
import os
import sys

import pytest

from utils import sorts as S

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEV = os.path.join(RACINE, "dev")


@pytest.fixture(scope="module")
def gen():
	if DEV not in sys.path:
		sys.path.insert(0, DEV)
	spec = importlib.util.spec_from_file_location("gen_sorts_migres", os.path.join(DEV, "gen_sorts_migres.py"))
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


@pytest.fixture(scope="module")
def base():
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		pytest.skip("aucun dump committé")
	return {d["_id"]: d for d in json.load(open(dumps[-1], encoding="utf-8"))["docs"]
			if isinstance(d, dict) and d.get("_id")}


@pytest.fixture(scope="module")
def genere(gen, base):
	return gen.generer(base)


@pytest.fixture(scope="module")
def fichier(gen):
	return json.load(open(gen.SORTIE, encoding="utf-8"))


def _par_type(docs, t):
	return [d for d in docs if d.get("type") == t]


def test_le_generateur_passe_toutes_ses_gardes(genere):
	assert genere[1] == []


def test_fichier_committe_est_la_sortie(genere, fichier):
	assert genere[0] == fichier


def test_chaque_attaque_migree_a_son_remplacant_et_son_sort(gen, fichier):
	comps = {d["_id"]: d for d in _par_type(fichier, "competence")}
	sorts = {d["_id"]: d for d in _par_type(fichier, "sort")}
	assert len(sorts) == len(gen.MIGRES)
	for m in gen.MIGRES:
		remplacant = comps.get(m["competence"])
		assert remplacant is not None, m["competence"]
		# Le remplaçant n'est plus une attaque : contrôle/soutien, aucun dé de PV ou de PM.
		assert not (remplacant.get("effets") or {}).get("degats"), m["competence"]
		assert not (remplacant.get("effets") or {}).get("degats_pm"), m["competence"]
		assert remplacant["niveau"] == m["niveau"], m["competence"]
		sort = sorts["sort:" + gen.slug(m["nom"])]
		assert sort["nom"] == m["nom"]
		assert sort["effets"] == m["effets"]
		assert sort["cout_pm"] == round(m["cout_pm"] * gen.PM_FACTEUR)


def test_un_grimoire_unique_et_une_recette_par_sort(fichier):
	sorts = {d["_id"] for d in _par_type(fichier, "sort")}
	grimoires = [d for d in _par_type(fichier, "item") if d.get("sous_categorie") == "grimoire"]
	assert {g["sorts"][0] for g in grimoires if len(g["sorts"]) == 1} == sorts
	produits = {r["objet_final"] for r in _par_type(fichier, "recette")}
	assert {g["_id"][len("item:"):] for g in grimoires} <= produits


def test_composants_catalyseur_puis_consomme_plus_fort(fichier):
	for s in _par_type(fichier, "sort"):
		cat, cons = s["composants"]
		assert cat["consomme"] is False and cons["consomme"] is True, s["_id"]
		assert "D" not in cat["bonus"]["degats"] and "D" in cons["bonus"]["degats"], s["_id"]
		assert int(cat["bonus"]["degats"]) < int(cons["bonus"]["degats"].split("D")[0]) * \
			(1 + int(cons["bonus"]["degats"].split("D")[1])) / 2, s["_id"]


def test_le_moteur_lance_chaque_sort_avec_ses_composants(fichier):
	caracts = {c: 50 for c in S.CARACTS_FORMULE}
	for s in _par_type(fichier, "sort"):
		norm = S.normaliser_sort(s)
		assert norm is not None and S.capacite_utilisable_combat(norm), s["_id"]
		effets = S.fusionner_effets(norm["effets"], [c["bonus"] for c in s["composants"]])
		res = S.resoudre_effets(effets, caracts, des_fn=lambda _n: 1)
		assert res.get("degats"), s["_id"]
		assert S.effets_agissent_sur_cible(res), s["_id"]


def test_regeneration_idempotente(gen, base, genere):
	importee = copy.deepcopy(base)
	for d in genere[0]:
		if d["type"] != "competence":
			importee[d["_id"]] = dict(d, _rev="1-test")
	docs, erreurs = gen.generer(importee)
	assert erreurs == []
	assert all(d["type"] == "competence" for d in docs)
