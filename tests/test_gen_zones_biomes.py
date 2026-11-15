# tests/test_gen_zones_biomes.py
#
# Zones par biome (dev/gen_zones_biomes.py, Auteur 16/11) : noms GÉNÉRIQUES, aucune créature des
# mythes en défaut, aucun `regions`, chaîne de bois complète découpable par `utils/bois.py`,
# repeinte qui ne touche que les zones. Données en constantes, sauf le contrôle de références sur
# le dump le plus récent (glob toléré, CLAUDE.md §20) ; aucun fichier *_a_importer.json lu.

import glob
import importlib.util
import json
from pathlib import Path

import pytest

from models import character_stats
from utils import bois

RACINE = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("gen_zones_biomes", RACINE / "dev" / "gen_zones_biomes.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

# Mots d'un lieu réel : une zone décrit un milieu, jamais un endroit (Auteur, 16/11).
LIEUX_REELS = ("atlas", "nil", "sahel", "sahara", "afrique", "europe", "asie", "amazon", "congo",
			   "tibet", "andes", "gobi", "namib", "sonora", "rift", "madagascar", "kilimandjaro",
			   "abyssin", "ethiop", "australi", "mediterran", "sudd", "okavango", "arcti" + "que du nord")


def _texte_zone(slug):
	nom = gen.ZONES[slug][0]
	return (slug + " " + nom).lower()


@pytest.mark.parametrize("slug", sorted(gen.ZONES))
def test_nom_et_id_de_zone_generiques(slug):
	assert not [m for m in LIEUX_REELS if m in _texte_zone(slug)]


# Tags d'une créature des mythes ou d'un être pensant : jamais un défaut de zone (Auteur, 16/11 —
# elles se posent sur un placement). La faune géante ordinaire (`monstre` seul) reste admise.
TAGS_MYTHES = {"legendaire", "boss", "esprit", "humanoide", "mort_vivant", "demon", "magique"}


def test_aucune_creature_des_mythes_en_defaut():
	"""Les défauts ne portent que la faune ordinaire : aucun tag de `TAGS_MYTHES`."""
	neuves = set(gen.ESPECES)
	for slug in neuves:
		assert "animal" in gen.ESPECES[slug][2]
	dumps = sorted(glob.glob(str(RACINE / "jsons" / "telluris-dump-*.json")))
	if not dumps:
		pytest.skip("aucun dump")
	base = {d["_id"]: d for d in json.load(open(dumps[-1], encoding="utf-8"))["docs"]}
	for slug, (_, _, _, especes, _) in gen.ZONES.items():
		for e in especes:
			if e in neuves:
				continue
			tags = (base.get(f"espece:{e}") or {}).get("tags") or []
			assert not set(tags) & TAGS_MYTHES, f"{slug} : espece:{e} est une créature des mythes"


def test_zone_sans_regions_et_copiee_de_son_modele():
	modele = {"_id": "zone:garrigue", "intensite_max": 0.7, "modificateurs": {"danger": 1},
			  "table_evenements": [{"type": "combat", "poids": 25}]}
	z = gen.doc_zone("maquis", {"zone:garrigue": modele})
	assert z["intensite_max"] == 0.7 and z["modificateurs"] == {"danger": 1}
	assert z["table_evenements"] == modele["table_evenements"]
	assert z["table_evenements"] is not modele["table_evenements"]
	assert all("regions" not in d for d in z["defauts_rencontres"] + z["defauts_ressources"])


def test_chaine_de_bois_complete_et_decoupable():
	docs = {d["sous_categorie"]: d for d in gen.docs_essence("Acacia")}
	assert list(docs) == [p for p, _, _ in gen.PALIERS]
	assert docs["tronc"]["poids"] == [docs["arbre"]["poids"][0], docs["arbre"]["poids"][1] / 2]
	assert docs["tronc"]["nom"] == "Tronc d'Acacia" and docs["rondin"]["_id"] == "item:Rondin_de_Acacia"
	assert "a_couper" not in docs["branche"]["tags"]

	def find(sel, fields=None):
		return [d for d in docs.values() if d["sous_categorie"] == sel.get("sous_categorie")]

	# Chaque palier coupable descend au suivant de la MÊME essence, selon l'échelle du moteur.
	echelle = character_stats.BOIS_A_COUPER
	for palier, d in docs.items():
		if palier == "branche" or palier not in echelle:
			continue
		cible = bois.cible_coupe(d, find)
		assert cible is not None and echelle.index(cible["sous_categorie"]) == echelle.index(palier) - 1


def test_repeinte_ne_touche_que_les_zones():
	lieu = {"_id": "lieu:x", "_rev": "3-a", "cells": [[1]],
			"zone_influences": [{"zone": "zone:lac", "x": 1, "y": 2}, {"zone": "zone:desert", "x": 3, "y": 4}],
			"rencontres": [{"espece": "espece:crocodile", "zones": ["zone:lac", "zone:fleuve_tropical"]},
						   {"espece": "espece:esprit"}]}
	r = gen.repeindre(lieu, {"zone:lac": "zone:fleuve_tropical"})
	assert "_rev" not in r and r["cells"] == [[1]]
	assert [p["zone"] for p in r["zone_influences"]] == ["zone:fleuve_tropical", "zone:desert"]
	assert r["zone_influences"][0]["x"] == 1
	assert r["rencontres"] == [{"espece": "espece:crocodile", "zones": ["zone:fleuve_tropical"]},
							   {"espece": "espece:esprit"}]
	assert lieu["zone_influences"][0]["zone"] == "zone:lac"


def test_delta_refuse_un_id_neuf_pris_et_saute_l_identique():
	base = {"item:Pin": {"_id": "item:Pin", "_rev": "1", "nom": "Autre"},
			"zone:lac": {"_id": "zone:lac", "_rev": "2", "nom": "Lac"}}
	docs = [{"_id": "item:Pin", "nom": "Pin"}, {"_id": "zone:lac", "nom": "Lac"}, {"_id": "item:Neuf"}]
	emis, refus = gen.delta(docs, base, {"item:Pin", "item:Neuf"})
	assert refus == ["item:Pin"] and emis == [{"_id": "item:Neuf"}]


def test_references_du_lot_existent_dans_le_dernier_dump():
	dumps = sorted(glob.glob(str(RACINE / "jsons" / "telluris-dump-*.json")))
	if not dumps:
		pytest.skip("aucun dump")
	base = {d["_id"]: d for d in json.load(open(dumps[-1], encoding="utf-8"))["docs"]}
	docs = gen.construire(base)
	assert gen.verifier(docs, base) == []
