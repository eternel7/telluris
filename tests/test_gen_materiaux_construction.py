# tests/test_gen_materiaux_construction.py
#
# Pierres de construction (dev/gen_materiaux_construction.py, Auteur 16/11) : objets en
# sous-catégorie « pierre » (stock Matériaux des implantations), défauts de zones ADDITIFS,
# DELTA seul et rejeu idempotent. Dump synthétique : aucun fichier de jsons/ n'est lu.

import importlib.util
import pathlib

from utils import colonisation as col

RACINE = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("gen_materiaux_construction",
											   RACINE / "dev" / "gen_materiaux_construction.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


def _dump():
	docs = [{"_id": f"zone:{z}", "_rev": "1-x", "type": "zone_influence", "nom": z,
			 "defauts_ressources": [{"ressource": "item:pierre", "regions": ["europe"]}]} for z in gen.TABLE]
	return docs


def test_objets_et_zones_emis_en_delta_additif():
	sortie = gen.generer(_dump())
	objets = [d for d in sortie if d["_id"].startswith("item:")]
	assert len(objets) == len(gen.OBJETS)
	zone = next(d for d in sortie if d["_id"] == "zone:carriere")
	assert "_rev" not in zone
	assert zone["defauts_ressources"][0] == {"ressource": "item:pierre", "regions": ["europe"]}   # gardé tel quel
	assert [e["ressource"] for e in zone["defauts_ressources"][1:]] == [f"item:{p}" for p in gen.TABLE["carriere"]]


def test_rejeu_apres_import_ne_reemet_rien():
	dump = _dump()
	premiere = {d["_id"]: d for d in gen.generer(dump)}
	importe = [premiere.get(d["_id"], d) for d in dump] + [d for i, d in premiere.items() if i.startswith("item:")]
	assert gen.generer(importe) == []


def test_chaque_pierre_rejoint_le_stock_materiaux():
	for ident in gen.OBJETS:
		assert col.stock_de_item(gen.doc_objet(ident), ["matiere.autre"], col.DEFAUTS)["stock"] == "materiaux"


def test_objets_ouvres_tagues_sans_rien_changer_d_autre():
	dump = [{"_id": i, "_rev": "1-x", "type": "item", "categorie": "outil", "tags": None}
			for i in gen.OBJETS_TAGUES]
	dump[0]["tags"] = [gen.TAG]                                    # déjà tagué : pas réémis
	sortie = gen.generer_tags(dump)
	assert [d["_id"] for d in sortie] == gen.OBJETS_TAGUES[1:]
	assert all(d["tags"] == [gen.TAG] and d["categorie"] == "outil" and "_rev" not in d for d in sortie)
	assert gen.generer_tags([{**d, "tags": [gen.TAG]} for d in dump]) == []   # rejeu après import


def test_le_tag_est_celui_que_lit_la_regle_materiaux():
	regle = next(r for r in col.DEFAUTS["depots"] if r["stock"] == "materiaux")
	assert gen.TAG in regle["tags"]
