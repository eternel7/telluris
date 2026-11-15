# tests/test_gen_defauts_zones_biomes.py
#
# Défauts de toutes les zones naturelles (dev/gen_defauts_zones_biomes.py, Auteur 15/11) : notation
# « id@E,S » → `regions`, périmètre (ni cité, ni habitable, ni calque de danger), ajout SANS retrait
# ni retouche d'un défaut présent, idempotence. Données en constantes, sauf le contrôle de la table
# sur le dump le plus récent (glob toléré, CLAUDE.md §20) ; aucun *_a_importer.json lu.

import glob
import importlib.util
import json
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("gen_defauts_zones_biomes",
											   RACINE / "dev" / "gen_defauts_zones_biomes.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


def test_notation_des_regions():
	assert gen.entree("loup@E,S", "espece", "espece:") == {"espece": "espece:loup",
														   "regions": ["europe", "steppes"]}
	assert gen.entree("pierre", "ressource", "item:") == {"ressource": "item:pierre"}


def test_perimetre_naturel_seul():
	for z in ("zone::coeur_ville", "zone:faubourg", "zone:habitable_maison", "zone:tres_dangereuse",
			  "zone:zone_danger_2"):
		assert gen.hors_perimetre(z)
	assert not gen.hors_perimetre("zone:foret_feuillus")
	assert not any(gen.hors_perimetre("zone:" + z) for z in gen.TABLE)


def test_ajoute_sans_retirer_ni_retoucher(monkeypatch):
	monkeypatch.setattr(gen, "TABLE", {"foret": (["loup@E", "ours"], ["Chene"])})
	docs = {"zone:foret": {"_id": "zone:foret", "_rev": "3-x", "type": "zone_influence",
						   "table_evenements": [{"type": "rien", "poids": 1}],
						   "defauts_rencontres": [{"espece": "espece:loup", "regions": ["afrique"]},
												  {"espece": "espece:cerf"}]}}
	(z,) = gen.zones_a_emettre(docs)
	assert "_rev" not in z and z["table_evenements"] == [{"type": "rien", "poids": 1}]
	assert z["defauts_rencontres"] == [{"espece": "espece:loup", "regions": ["afrique"]},
									   {"espece": "espece:cerf"}, {"espece": "espece:ours"}]
	assert z["defauts_ressources"] == [{"ressource": "item:Chene"}]
	docs["zone:foret"] = z
	assert gen.zones_a_emettre(docs) == []


def test_table_valide_sur_le_dernier_dump():
	dumps = sorted(glob.glob(str(RACINE / "jsons" / "telluris-dump-*.json")))
	if not dumps:
		pytest.skip("aucun dump")
	with open(dumps[-1], encoding="utf-8") as f:
		docs = {d["_id"]: d for d in json.load(f)["docs"]}
	assert gen.controler(docs) == []
