"""Recettes à TROPHÉE (`marche.est_recette_trophee`) : une pièce nommée faite d'un morceau de
monstre que SEUL le client apporte.

⚠️ RAISON D'ÊTRE DE CE FICHIER. Une recette à trophée est un doc `recette:*` ordinaire à un
drapeau près (`trophee: true` sur un intrant). Si ce drapeau cesse d'être lu, rien ne lève :
- le trophée devient un besoin du métier, donc une feuille LIVRÉE, donc une tête de Minotaure
  en vente au comptoir de l'Arsenal (`appro_leaves_categorie` → `approvisionner`) ;
- la maison achète les têtes au joueur et le tick cuit des casques cornus de lui-même ;
- la commande va chercher le trophée dans la réserve ou au pool de la cité.
Ce fichier attrape les trois.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from utils import commande, marche  # noqa: E402
from models import character_stats  # noqa: E402


METIER = "armurerie_de_test"
MAISON = "grand_arsenal_de_test"
TETE = "item:minotaure_tete_de_test"

RECETTE_ORDINAIRE = {
	"_id": "recette:test_epee", "type": "recette", "lieu_categorie": METIER,
	"objet_final": "Epee_de_test", "quantite_produite": 1,
	"matieres_premieres": [{"sous_categorie": "fer_de_test", "quantite": 2}],
}
# Recette de la GRANDE MAISON : le trophée, plus un intrant que rien d'autre ne consomme —
# il ne doit pas devenir une feuille livrée non plus.
RECETTE_TROPHEE = {
	"_id": "recette:test_casque_cornu", "type": "recette", "lieu_categorie": MAISON,
	"objet_final": "Casque_cornu_de_test", "quantite_produite": 1,
	"matieres_premieres": [{"item": TETE, "quantite": 1, "trophee": True},
						   {"sous_categorie": "cuir_de_test", "quantite": 1}],
}

_DB = {
	"item:Epee_de_test": {"_id": "item:Epee_de_test", "nom": "Épée", "categorie": "arme",
						  "sous_categorie": "", "poids": 2.0},
	"item:Casque_cornu_de_test": {"_id": "item:Casque_cornu_de_test", "nom": "Casque cornu",
								  "categorie": "armure", "sous_categorie": "", "poids": 3.0},
	TETE: {"_id": TETE, "nom": "Tête de Minotaure", "categorie": "composant",
		   "sous_categorie": "carcasse", "poids": 16.0, "portion_de": "item:minotaure"},
	"item:fer_de_test": {"_id": "item:fer_de_test", "nom": "Fer", "categorie": "metal",
						 "sous_categorie": "fer_de_test", "poids": 1.0},
	"item:cuir_de_test": {"_id": "item:cuir_de_test", "nom": "Cuir", "categorie": "composant",
						  "sous_categorie": "cuir_de_test", "poids": 1.0},
}


def _get_doc(doc_id):
	return _DB.get(doc_id)


ARSENAL = {"_id": "lieu:arsenal_de_test", "categorie": MAISON}
FORGE = {"_id": "lieu:forge_de_test", "categorie": METIER}


@pytest.fixture
def index_semes(monkeypatch):
	"""Deux recettes dans le monde ; la grande maison réunit l'armurerie. `reset_prix_cache()`
	des deux côtés : ces index sont des caches de PROCESS."""
	marche.reset_prix_cache()
	monkeypatch.setattr(marche, "_recettes_all", [RECETTE_ORDINAIRE, RECETTE_TROPHEE])
	monkeypatch.setitem(character_stats.LIEU_CATEGORIES_FUSION, MAISON, [METIER])
	monkeypatch.setattr(marche, "get_doc", _get_doc)
	monkeypatch.setattr(commande, "resolve_item_ref", _get_doc)
	yield
	marche.reset_prix_cache()


def test_drapeau_lu_sur_l_intrant():
	assert marche.cles_trophee(RECETTE_TROPHEE) == {TETE}
	assert marche.est_recette_trophee(RECETTE_TROPHEE)
	assert not marche.est_recette_trophee(RECETTE_ORDINAIRE)
	# Forme mono-entrée historique : jamais un trophée.
	assert not marche.est_recette_trophee({"matiere_premiere_sous_categorie": "crane"})


def test_le_trophee_n_est_ni_besoin_ni_feuille(index_semes):
	for cle in (TETE, "cuir_de_test"):
		assert cle not in marche.besoins_categorie(MAISON)
		assert cle not in marche.appro_leaves_categorie(MAISON)
		assert cle not in marche._get_marche_map()["feuilles"]
		assert cle not in marche.cles_consommees()
	# La recette ordinaire, elle, est intacte.
	assert "fer_de_test" in marche.appro_leaves_categorie(MAISON)


def test_l_appro_ne_livre_jamais_le_trophee(index_semes):
	lieu = dict(ARSENAL)
	marche.approvisionner(lieu)
	assert TETE not in (lieu.get("stock_matieres") or {})
	assert TETE not in {e.get("item_id") for e in lieu.get("stock_vente") or []}


def test_la_maison_n_achete_pas_le_trophee_mais_rachete_la_piece(index_semes):
	assert marche.lieu_buys(ARSENAL, _DB[TETE]) is False
	assert marche.lieu_buys(ARSENAL, _DB["item:Casque_cornu_de_test"]) is True


def test_hors_du_tick_mais_au_catalogue(index_semes):
	assert RECETTE_TROPHEE not in marche.recettes_lieu(ARSENAL)
	assert marche.recettes_trophee_lieu(ARSENAL) == [RECETTE_TROPHEE]
	assert "item:Casque_cornu_de_test" in commande.catalogue_commandable(ARSENAL, _get_doc)
	assert commande.recette_pour(ARSENAL, "item:Casque_cornu_de_test") is RECETTE_TROPHEE


def test_le_metier_reuni_n_herite_pas_de_la_recette_de_la_maison(index_semes):
	assert marche.recettes_trophee_lieu(FORGE) == []
	assert "item:Casque_cornu_de_test" not in commande.catalogue_commandable(FORGE, _get_doc)


def _sourcer(porteurs, lieu):
	return commande.sourcer(marche.recette_matieres(RECETTE_TROPHEE), porteurs, lieu, _get_doc,
							atelier=True, trophees=marche.cles_trophee(RECETTE_TROPHEE))


def test_l_artisan_ne_fournit_jamais_le_trophee(index_semes):
	"""Même avec des têtes en réserve, au rayon et au pool de la cité : seul le client l'apporte."""
	lieu = dict(ARSENAL, stock_matieres={TETE: 3, "cuir_de_test": 3},
				stock_vente=[{"item_id": TETE, "qty": 3}])
	flux = {"pool": {TETE: 5}}
	src = commande.sourcer(marche.recette_matieres(RECETTE_TROPHEE), [{"_id": "c", "inventaire": []}],
						   lieu, _get_doc, atelier=True, flux=flux,
						   trophees=marche.cles_trophee(RECETTE_TROPHEE))
	assert src["manquantes"] == [{"cle": TETE, "quantite": 1, "trophee": True,
								  "nom": "Tête de Minotaure"}]
	assert [a["cle"] for a in src["atelier"]] == ["cuir_de_test"]


def test_le_client_apporte_son_trophee(index_semes):
	lieu = dict(ARSENAL, stock_matieres={"cuir_de_test": 1})
	joueur = {"_id": "c", "inventaire": [{"item": TETE, "poids": 20.0}]}
	src = _sourcer([joueur], lieu)
	assert src["manquantes"] == []
	assert [(f["cle"], f["item_id"]) for f in src["fournies"]] == [(TETE, TETE)]
