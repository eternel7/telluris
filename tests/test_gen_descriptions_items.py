"""dev/gen_descriptions_items.py — une description pour chaque item qui n'en a pas, jamais plus.

Verrouille : un item déjà décrit n'est jamais réécrit (import PUT complet), une variante suit
`fabrication.description_variante` sur le texte NEUF de son modèle, le bois se décrit par
essence × forme, et un item qu'aucune source ne couvre fait échouer le lot au lieu de recevoir
un texte par défaut.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_descriptions_items as gen
from utils import fabrication

DAGUE = {"_id": "item:Dague", "_rev": "3-x", "type": "item", "nom": "Dague", "icon": "🗡️",
		 "categorie": "arme", "sous_categorie": "", "slots": ["main_droite"], "poids": 0.3}
MITHRIL = {"_id": "item:mithril", "type": "item", "nom": "Lingot de mithril",
		   "description": "Texte de la matière."}
DAGUE_MITHRIL = {"_id": "item:Dague_0123abcd", "_rev": "1-x", "type": "item",
				 "nom": "Dague en mithril", "icon": "🗡️", "categorie": "arme",
				 "fabrication": {"base_item": "item:Dague",
								 "matieres": [{"item": "item:mithril", "quantite": 1}]}}
RONDIN = {"_id": "item:Rondin_de_Chene", "type": "item", "nom": "Rondin de Chêne", "icon": "🪵",
		  "categorie": "composant", "sous_categorie": "rondin",
		  "tags": ["bois", "a_couper", "essence_chene"]}
DECRIT = {"_id": "item:Arc", "type": "item", "nom": "Arc", "icon": "🏹", "description": "Déjà là."}


def _par_id(docs):
	return {d["_id"]: d for d in docs}


def test_seuls_les_items_sans_description_sortent_sans_rev():
	sortie, manquants, _inutiles = gen.generer([DAGUE, DECRIT, RONDIN, {"_id": "lieu:x", "type": "lieu"}])
	assert manquants == []
	par_id = _par_id(sortie)
	assert set(par_id) == {"item:Dague", "item:Rondin_de_Chene"}
	assert "_rev" not in par_id["item:Dague"]
	assert par_id["item:Dague"]["description"] == gen.DESCRIPTIONS["Dague"]
	# Seule `description` est ajoutée, placée juste après `icon`.
	cles = list(par_id["item:Dague"])
	assert cles[cles.index("icon") + 1] == "description"
	assert {k: v for k, v in par_id["item:Dague"].items() if k != "description"} == \
		{k: v for k, v in DAGUE.items() if k != "_rev"}


def test_une_description_vide_compte_comme_absente():
	sortie, _m, _i = gen.generer([dict(DAGUE, description="  ")])
	assert sortie[0]["description"] == gen.DESCRIPTIONS["Dague"]


def test_la_variante_suit_la_regle_de_fabrication_avec_le_texte_neuf_du_modele():
	sortie, manquants, _i = gen.generer([DAGUE_MITHRIL, DAGUE, MITHRIL])
	assert manquants == []
	par_id = _par_id(sortie)
	attendu = fabrication.description_variante(
		dict(DAGUE, description=gen.DESCRIPTIONS["Dague"]), [(MITHRIL, 1)])
	assert par_id["item:Dague_0123abcd"]["description"] == attendu
	assert attendu.startswith(gen.DESCRIPTIONS["Dague"])
	assert "Lingot de mithril" in attendu


def test_la_variante_reprend_la_description_deja_en_base_du_modele():
	sortie, _m, _i = gen.generer([DAGUE_MITHRIL, dict(DAGUE, description="Texte en base."), MITHRIL])
	assert [d["_id"] for d in sortie] == ["item:Dague_0123abcd"]
	assert sortie[0]["description"].startswith("Texte en base. ")


def test_le_bois_se_decrit_par_essence_et_forme():
	sortie, _m, _i = gen.generer([RONDIN])
	de, trait = gen.ESSENCES["chene"]
	assert sortie[0]["description"] == gen.FORMES_BOIS["rondin"].format(de=de) + " " + trait


def test_un_item_non_couvert_fait_echouer_le_lot():
	inconnu = {"_id": "item:Objet_jamais_vu", "type": "item", "nom": "?"}
	sortie, manquants, _i = gen.generer([inconnu, DAGUE])
	assert manquants == ["item:Objet_jamais_vu"]


def test_chaque_essence_a_un_article_et_un_trait():
	for essence, (de, trait) in gen.ESSENCES.items():
		assert de.startswith(("de ", "d'")), essence
		assert trait.strip(), essence
