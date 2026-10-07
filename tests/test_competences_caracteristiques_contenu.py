# tests/test_competences_caracteristiques_contenu.py
#
# Contenu `jsons/competences_caracteristiques_a_importer.json`
# (dev/gen_competences_caracteristiques.py) — actives du lot 1 → 10 retouchées en formules :
#   · le générateur passe toutes ses gardes ;
#   · chaque doc émis = le doc du dump, `effets` seul changé, et porte une formule ;
#   · valeur d'origine conservée à la caractéristique de référence (tolérance RELUE) ;
#   · garde-fous des sorts : buff ≤ {Car/3}, jamais de V, durée intacte ;
#   · fichier committé conforme au générateur ; régénération idempotente (doc déjà converti
#     ⇒ sauté).

import glob
import importlib.util
import json
import os
import sys

import pytest

from utils import sorts as S

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEV = os.path.join(RACINE, "dev")
FICHIER = os.path.join(RACINE, "jsons", "competences_caracteristiques_a_importer.json")


@pytest.fixture(scope="module")
def gen():
	if DEV not in sys.path:
		sys.path.insert(0, DEV)
	spec = importlib.util.spec_from_file_location(
		"gen_competences_caracteristiques", os.path.join(DEV, "gen_competences_caracteristiques.py"))
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


def _docs():
	return json.load(open(FICHIER, encoding="utf-8"))


def test_le_generateur_passe_toutes_ses_gardes(genere):
	assert genere[2] == []


def test_fichier_conforme_et_regeneration_idempotente(gen, base, genere):
	docs = genere[0]
	assert gen.generer(base)[0] == docs
	# Tant que le lot n'est pas importé, le fichier committé est exactement la sortie.
	if not any("{" in json.dumps(base[d["_id"]].get("effets")) for d in _docs()):
		assert docs == _docs()
	# Une fois importé (base = docs émis), plus rien n'est réémis.
	convertie = dict(base, **{d["_id"]: d for d in docs})
	assert gen.generer(convertie)[0] == []


def test_seul_effets_change_et_porte_une_formule(base):
	for d in _docs():
		avant = {k: v for k, v in base[d["_id"]].items() if k != "_rev"}
		assert {k: v for k, v in d.items() if k != "effets"} == \
			{k: v for k, v in avant.items() if k != "effets"}, d["_id"]
		assert d["mode"] == "active", d["_id"]
		assert "{" in json.dumps(d["effets"]), d["_id"]
		assert d["effets"].get("duree") == avant["effets"].get("duree"), d["_id"]


def test_valeur_conservee_a_la_reference(gen, base):
	for d in _docs():
		ref = {c: gen.ref(d["niveau"]) for c in S.CARACTS_FORMULE}
		for champ in _champs_formule(d["effets"]):
			v0 = gen._lire(base[d["_id"]]["effets"], champ, ref)
			v1 = gen._lire(d["effets"], champ, ref)
			assert abs(v1 - v0) <= max(1, abs(v0) * gen.TOLERANCE), (d["_id"], champ, v0, v1)


def test_garde_fous_d_equilibrage(gen):
	for d in _docs():
		for car, f in (d["effets"].get("buffs") or {}).items():
			if S.est_formule(f):
				assert car != "V", d["_id"]
				for _code, div in S._RE_JETON.findall(f):
					assert int(div or 1) >= gen.DIVISEUR_BUFF_MIN, d["_id"]
		assert not S.est_formule(d["effets"].get("duree")), d["_id"]


def _champs_formule(effets):
	out = [k for k, v in effets.items() if k != "buffs" and S.est_formule(v)]
	return out + ["buffs." + c for c, v in (effets.get("buffs") or {}).items() if S.est_formule(v)]
