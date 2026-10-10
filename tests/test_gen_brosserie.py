"""Contenu de la brosserie (dev/gen_brosserie.py) — forme du lot, sans base.

Les garde-fous économiques (fausse feuille, flux par cité, grande maison croisée) sont ceux
de dev/gen_bourrellerie.py et tournent sur le dump au lancement ; ici, ce qui doit tenir
quel que soit le dump : les décisions de contenu et la forme des docs.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_bourrellerie as base
from dev import gen_brosserie as gen


def _lot():
	return [base.item_doc(s, gen.ITEMS) for s in gen.ITEMS]


def test_items_bien_formes_et_chacun_a_sa_recette():
	assert base.controler_items(_lot()) == []
	assert set(gen.ITEMS) == set(gen.RECETTES)
	ids = [base.recette_doc(s, gen.RECETTES)["_id"] for s in gen.RECETTES]
	assert len(ids) == len(set(ids))


def test_aucun_id_partage_avec_la_bourrellerie():
	assert not set(gen.ITEMS) & set(base.ITEMS)


def test_le_brossier_ne_vend_pas_de_grenaille_precieuse():
	"""Décision de l'auteur : la virole est en fer — toute matière d'une recette de brosserie
	est mise en vente à son comptoir."""
	for slug, (cat, matieres, _q) in gen.RECETTES.items():
		if cat == "brosserie":
			assert "metaux_precieux" not in {c for c, _n in matieres}, slug


def test_brosse_et_pinceau_existants_ont_un_debouche():
	consommateurs = {cle: {cat for cat, matieres, _q in gen.RECETTES.values()
						   if cle in {c for c, _n in matieres}}
					 for cle in ("item:brosse", "item:pinceau")}
	assert consommateurs["item:brosse"] == {"savonnerie", "tissage"}
	assert consommateurs["item:pinceau"] == {"bijouterie", "atelier_de_cirier"}


def test_la_viole_se_tient_comme_un_instrument():
	viole = base.item_doc("Viole_d_archet", gen.ITEMS)
	assert viole["categorie"] == "arme" and viole["sous_categorie"] == "instrument"
	assert viole["slots"] == ["main_droite", "main_gauche"] and viole["deux_mains"] is True
	assert viole["cible"] == "ennemi" and "cac" in viole["tags"]


def test_consommables_et_catalyseurs():
	lot = {d["_id"]: d for d in _lot()}
	for i in ("item:Chandelle_de_glyphes", "item:Toilette_de_marchand"):
		assert lot[i]["categorie"] == "consommable" and lot[i]["effets"].get("duree")
	for i in ("item:Pinceau_de_glyphes", "item:Aspersoir_de_sauge", "item:Plumeau_d_augure"):
		assert lot[i]["categorie"] == "catalyseur" and lot[i]["slots"] == ["main_gauche"]
