"""Ordre dans lequel une commande puise dans les SACS (`routers.commande._resoudre`).

Ce qui n'a aucun autre recours se sert en premier :
1. les trophées de la recette — sacs seuls ;
2. les matières sur mesure — sinon le comptoir, souvent vide ;
3. le reste de la recette — que l'artisan trouve aussi de son côté.

Cas d'origine (Zora, Collier de crocs « à garde de crocs ») : un seul croc en sac partait dans
la recette, et le croc sur mesure restait « manquant » alors que l'artisan avait les siens.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from routers import commande as rc  # noqa: E402
from utils import characters, marche  # noqa: E402


MAISON = "grand_arsenal"   # une des `LIEU_CATEGORIES_FUSION` : elle fabrique sur mesure
CROCS = "item:crocs_de_test"
TETE = "item:tete_de_test"

RECETTE_COLLIER = {
	"_id": "recette:ordre_collier", "type": "recette", "lieu_categorie": MAISON,
	"objet_final": "Collier_de_test", "quantite_produite": 1,
	"matieres_premieres": [{"sous_categorie": "crocs", "quantite": 3},
						   {"sous_categorie": "tendons", "quantite": 1}],
}
RECETTE_CASQUE = {
	"_id": "recette:ordre_casque", "type": "recette", "lieu_categorie": MAISON,
	"objet_final": "Casque_de_test", "quantite_produite": 1,
	"matieres_premieres": [{"item": TETE, "quantite": 1, "trophee": True}],
}

_MONDE = {
	"item:Collier_de_test": {"_id": "item:Collier_de_test", "nom": "Collier", "categorie": "armure",
							 "sous_categorie": "", "slots": ["cou"], "poids": 0.15},
	"item:Casque_de_test": {"_id": "item:Casque_de_test", "nom": "Casque", "categorie": "armure",
							"sous_categorie": "", "slots": ["tete"], "poids": 3.0},
	CROCS: {"_id": CROCS, "nom": "Crocs", "categorie": "composant", "sous_categorie": "crocs",
			"slots": [], "poids": 0.1, "tags": ["fabrication_armure"],
			"fabrication": {"nom": "à garde de crocs", "modificateurs": {"bonus_degats": 2}}},
	"item:tendon_de_test": {"_id": "item:tendon_de_test", "nom": "Tendon", "categorie": "composant",
							"sous_categorie": "tendons", "slots": [], "poids": 0.1},
	TETE: {"_id": TETE, "nom": "Tête", "categorie": "composant", "sous_categorie": "carcasse",
		   "slots": [], "poids": 16.0, "tags": ["fabrication_armure"],
		   "fabrication": {"nom": "cornu", "modificateurs": {"bonus_pv": 2}}},
}
# L'artisan a dans SA réserve de quoi faire la recette du collier : 3 crocs et 1 tendon.
LIEU = {"_id": "lieu:arsenal_ordre", "categorie": MAISON, "label": "L'Arsenal",
		"stock_matieres": {"crocs": 3, "tendons": 1}}
_MONDE[LIEU["_id"]] = LIEU


def _get(doc_id):
	return _MONDE.get(doc_id)


@pytest.fixture
def atelier(monkeypatch):
	"""Même bordure que `test_commande_piece_apportee` : recettes semées, base stubbée."""
	marche.reset_prix_cache()
	monkeypatch.setattr(marche, "_recettes_all", [RECETTE_COLLIER, RECETTE_CASQUE])
	monkeypatch.setattr(marche, "_matieres_fab_memo", [CROCS, TETE])
	monkeypatch.setattr(rc, "get_doc", _get)
	monkeypatch.setattr(characters, "get_doc", _get)
	monkeypatch.setattr(marche, "get_doc", _get)
	monkeypatch.setattr(rc.recrutement, "porteurs_effectifs", lambda *a, **k: [])
	monkeypatch.setattr(rc, "find_docs", lambda *a, **k: [])
	monkeypatch.setattr(rc, "get_relation", lambda *a, **k: {"value": 50})
	monkeypatch.setattr(rc, "save_doc", lambda d: d)
	yield
	marche.reset_prix_cache()


def _devis(monkeypatch, inventaire, body):
	character = {"_id": "character:j", "lieu": LIEU["_id"], "or": 50, "commandes": [],
				 "inventaire": list(inventaire)}
	monkeypatch.setattr(rc, "get_selected_character", lambda u: character)
	return rc.devis_commande({"_id": "user:j"}, body)


def test_un_seul_croc_en_sac_sert_la_matiere_sur_mesure(atelier, monkeypatch):
	rep = _devis(monkeypatch, [CROCS],
				 {"item_id": "item:Collier_de_test", "matieres": [{"item": CROCS, "quantite": 1}]})
	assert rep["manquantes"] == []
	# Le croc du sac va au sur-mesure ; la recette est servie par la réserve de l'artisan.
	assert [(f["cle"], f["item_id"]) for f in rep["fournies"]] == [(CROCS, CROCS)]
	assert rep["achetees"] == []
	assert rep["devis"]["credit_matieres"] == 0   # aucun ingrédient de recette apporté


def test_sans_sur_mesure_le_croc_reste_une_remise_de_recette(atelier, monkeypatch):
	rep = _devis(monkeypatch, [CROCS], {"item_id": "item:Collier_de_test"})
	assert rep["manquantes"] == []
	assert [f["cle"] for f in rep["fournies"]] == ["crocs"]


def test_deux_crocs_en_sac_servent_les_deux_passes(atelier, monkeypatch):
	rep = _devis(monkeypatch, [CROCS, CROCS],
				 {"item_id": "item:Collier_de_test", "matieres": [{"item": CROCS, "quantite": 1}]})
	assert rep["manquantes"] == []
	assert sorted(f["cle"] for f in rep["fournies"]) == sorted([CROCS, "crocs"])


def test_le_trophee_de_recette_garde_la_priorite_sur_le_sur_mesure(atelier, monkeypatch):
	"""Un trophée n'a AUCUN autre recours : le sur-mesure ne doit pas le lui prendre."""
	rep = _devis(monkeypatch, [TETE],
				 {"item_id": "item:Casque_de_test", "matieres": [{"item": TETE, "quantite": 1}]})
	assert [f["cle"] for f in rep["fournies"]] == [TETE]
	manque = rep["manquantes"]
	assert len(manque) == 1 and manque[0]["cle"] == TETE and not manque[0].get("trophee")


def test_relancer_rejoue_le_meme_ordre(atelier, monkeypatch):
	"""La commande de Zora, restée en attente avant le correctif : « Relancer » la débloque."""
	character = {"_id": "character:j", "lieu": LIEU["_id"], "or": 50, "inventaire": [CROCS],
				 "commandes": [{"id": "c1", "lieu": LIEU["_id"], "item": "item:Collier_de_test",
								"base_item": "item:Collier_de_test",
								"matieres": [{"item": CROCS, "quantite": 1}],
								"statut": "en_attente_materiaux",
								"manquantes": [{"cle": CROCS, "quantite": 1}],
								"devis": {"total": 1}, "paye": 0, "cree_at": 1, "pret_at": 1}]}
	monkeypatch.setattr(rc, "get_selected_character", lambda u: character)
	monkeypatch.setattr(rc, "_payload_commande", lambda c, *a, **k: {"message": k.get("message")})
	monkeypatch.setattr(rc, "_consommer", lambda *a, **k: None)
	monkeypatch.setattr(rc.fabrication, "assurer_variante",
						lambda base, *a, **k: (dict(base, _id="item:Collier_de_test_var"), True))
	rep = asyncio.run(rc.relancer_commande({"_id": "user:j"}, {"commande_id": "c1"}))
	assert rep["message"].startswith("L'artisan s'y met")
	assert character["inventaire"] == []
	assert character["commandes"][0]["item"] == "item:Collier_de_test_var"
