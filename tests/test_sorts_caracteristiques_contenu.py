# tests/test_sorts_caracteristiques_contenu.py
#
# Contenu `jsons/sorts_caracteristiques_a_importer.json` (dev/gen_sorts_caracteristiques.py) :
#   · règle de contenu des sorts : un composant consommé ET un catalyseur ;
#   · garde-fous d'équilibrage des formules (relus depuis le fichier, jamais retapés) ;
#   · chaque sort a son animation dédiée, dont le son existe et dont la base est active ;
#   · chaque sort a son grimoire UNIQUE et sa recette — aucun n'est « sans grimoire » ;
#   · aucune collision d'`_id` avec le dump ; régénération idempotente.

import glob
import importlib.util
import json
import os

import pytest

from utils import grimoires
from utils import sorts as S

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FICHIER = os.path.join(RACINE, "jsons", "sorts_caracteristiques_a_importer.json")
SONS = os.path.join(RACINE, "templates", "resources", "sounds")

# Garde-fous d'équilibrage (compétence telluris-magie § Formules à caractéristiques).
DIVISEUR_BUFF_MIN = 3        # aucun buff au-delà de {Car/3}
DUREE_MAX_A_80 = 6           # aucune durée au-delà de 6 tours pour une caract à 80
CARACTS_80 = {c: 80 for c in S.CARACTS_FORMULE}


def _docs():
	return json.load(open(FICHIER, encoding="utf-8"))


def _dump():
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		pytest.skip("aucun dump committé")
	return {d["_id"]: d for d in json.load(open(dumps[-1], encoding="utf-8"))["docs"]
			if isinstance(d, dict) and d.get("_id")}


def _sorts():
	return [d for d in _docs() if d["type"] == "sort"]


def test_chaque_sort_a_un_consomme_et_un_catalyseur():
	for s in _sorts():
		compos = s["composants"]
		assert any(c["consomme"] for c in compos), s["_id"]
		assert any(not c["consomme"] for c in compos), s["_id"]


def test_chaque_sort_est_valide_et_porte_au_moins_une_formule():
	for s in _sorts():
		norm = S.normaliser_sort(s)
		assert norm is not None, s["_id"]
		assert S.sort_utilisable_combat(norm), s["_id"]
		assert "{" in json.dumps(s["effets"]) + str(s.get("portee")), s["_id"]


def test_garde_fous_d_equilibrage():
	for s in _sorts():
		for car, f in (s["effets"].get("buffs") or {}).items():
			assert car != "V", "%s : V n'est pas à l'échelle des autres caracts" % s["_id"]
			if S.est_formule(f):
				for _code, div in S._RE_JETON.findall(f):
					assert int(div or 1) >= DIVISEUR_BUFF_MIN, s["_id"]
		duree = S.resoudre_effets(S._bonus_dict(s["effets"]), CARACTS_80,
								  des_fn=lambda _n: 0)["duree"]
		assert duree <= DUREE_MAX_A_80, s["_id"]


def test_chaque_sort_a_son_animation_et_son_son():
	docs = {d["_id"]: d for d in _docs()}
	sons = set(os.listdir(SONS))
	for s in _sorts():
		anim = docs.get(s["animation"])
		assert anim and anim["type"] == "animation", s["_id"]
		assert anim["actif"] and anim["fichier"], s["_id"]
		assert anim["son"] in sons, "%s : son %s absent" % (s["_id"], anim["son"])


def test_les_animations_de_base_existent_et_sont_actives():
	gen = _charger_generateur()
	base = _dump()
	for spec in gen.SORTS:
		anim = base.get(spec["anim"]["base"])
		assert anim and anim.get("actif"), spec["anim"]["base"]


def test_chaque_sort_a_son_grimoire_et_sa_recette():
	docs = _docs()
	union = {**_dump(), **{d["_id"]: d for d in docs}}
	reduite = {k: d for k, d in union.items()
			   if d.get("type") == "recette" or grimoires.est_grimoire(d)}
	manquants, _lignes, erreurs = grimoires.grimoires_manquants(reduite, sorts_en_plus=_sorts())
	assert not erreurs
	assert manquants == []


def test_aucune_collision_d_id_avec_le_dump():
	base = _dump()
	for d in _docs():
		existant = base.get(d["_id"])
		if existant is not None:
			assert {k: v for k, v in existant.items() if k != "_rev"} == d, d["_id"]


def _charger_generateur():
	chemin = os.path.join(RACINE, "dev", "gen_sorts_caracteristiques.py")
	spec = importlib.util.spec_from_file_location("gen_sorts_caracteristiques", chemin)
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod


def test_regeneration_idempotente_et_conforme_au_fichier():
	gen = _charger_generateur()
	base = _dump()
	docs1, err1 = gen.generer(base)
	docs2, err2 = gen.generer(base)
	assert not err1 and not err2
	assert docs1 == docs2
	# Le fichier committé est exactement ce que le générateur produit — tant que ces sorts
	# ne sont pas encore dans le dump (importés, ils sont SAUTÉS : le générateur n'émet rien).
	if not any(d["_id"] in base for d in _docs()):
		assert docs1 == _docs()
