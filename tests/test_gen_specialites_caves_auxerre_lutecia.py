# tests/test_gen_specialites_caves_auxerre_lutecia.py — les boissons de cave d'Auxerre et de Lutèce.
# Tests PURS sur les tables : `main()` (garde-fous sur dump) n'est pas exécuté ici.

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dev"))

import gen_specialites_caves_auxerre_lutecia as gen  # noqa: E402
import gen_specialites_chartres_rhemi as lot_cr  # noqa: E402

LOT = gen.construire_lot()
PAR_ID = {d["_id"]: d for d in LOT}
RECETTES = [d for d in LOT if d["type"] == "recette"]


def test_aucun_id_en_double_ni_repris_du_lot_chartres_rhemi():
	assert [i for i, n in Counter(d["_id"] for d in LOT).items() if n > 1] == []
	assert not set(PAR_ID) & {d["_id"] for d in lot_cr.construire_lot()}


def test_tenancier_et_eau_de_vie_relus_pas_reemis():
	assert "pnj:marchand_cave" not in PAR_ID
	assert "item:Eau_de_vie" not in PAR_ID
	intrants = {m["item"] for r in RECETTES for m in r["matieres_premieres"]}
	assert "item:Eau_de_vie" in intrants


def test_recettes_de_cave_portees_a_auxerre_ou_lutece():
	for r in RECETTES:
		assert r["lieu_categorie"] == gen.CAVE
		assert r["lieu_portee"] in (gen.AUXERRE, gen.LUTECIA)


def test_chaque_cite_a_un_produit_final_de_cave():
	# Un produit FINAL (consommable), pas seulement un condiment : sinon la cave n'a rien à servir.
	for cite in (gen.AUXERRE, gen.LUTECIA):
		assert any(spec[8] == cite and spec[3] == "consommable" for spec in gen.PRODUITS.values()), cite


def test_matieres_existantes_reutilisees_et_neuves_generiques():
	intrants = {m["item"] for r in RECETTES for m in r["matieres_premieres"]}
	for reutilisee in ("item:Raisin", "item:Vin_de_pays", "item:Miel"):
		assert reutilisee in intrants and reutilisee not in PAR_ID
	for (slug, *_r) in gen.MATIERES:
		doc = PAR_ID["item:" + slug]
		assert doc["categorie"] == "composant" and doc["valeur"]
		assert "Auxerre" not in doc["nom"] and "Lut" not in doc["nom"]


def test_le_condiment_a_une_valeur_qui_coupe_la_propagation():
	for slug in gen.VALEURS:
		v = PAR_ID["item:" + slug]["valeur"]
		assert v[0]["cu"] < v[1]["cu"]
