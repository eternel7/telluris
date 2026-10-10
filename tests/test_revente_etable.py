# tests/test_revente_etable.py
#
# L'ÉTABLE REVENDEUSE : sans aucune recette, elle met en rayon le harnachement de monture
# (un `slot` ∈ `montures.SLOTS_MONTURE`) que les artisans de sa cité déversent au flux, et le
# vend `REVENTE_MAJORATION` × la fourchette de l'artisan. Acheter à la source reste moins cher.
#
# Logique pure : recettes et docs servis en mémoire, `random` neutralisé, aucun accès DB.

import copy

import pytest

from models import character_stats
from utils import marche

CUIR = {"_id": "item:cuir", "type": "item", "nom": "Cuir", "categorie": "composant",
		"sous_categorie": "cuir", "slots": [], "poids": 1.0, "rarete": "commun"}
SELLE = {"_id": "item:selle", "type": "item", "nom": "Selle", "categorie": "armure",
		 "slots": ["monture_dos"], "tags": ["harnachement"], "poids": 8.0, "rarete": "commun"}
CEINTURE = {"_id": "item:ceinture", "type": "item", "nom": "Ceinture", "categorie": "armure",
			"slots": ["taille"], "poids": 0.5, "rarete": "commun"}

RECETTES = [
	{"_id": "recette:selle", "type": "recette", "lieu_categorie": "bourrellerie_test",
	 "objet_final": "selle", "quantite_produite": 1,
	 "matieres_premieres": [{"sous_categorie": "cuir", "quantite": 3}]},
	{"_id": "recette:ceinture", "type": "recette", "lieu_categorie": "bourrellerie_test",
	 "objet_final": "ceinture", "quantite_produite": 1,
	 "matieres_premieres": [{"sous_categorie": "cuir", "quantite": 1}]},
]

CITE = {"_id": "lieu:cite_test", "type": "lieu", "categorie": "ville", "label": "Cité d'essai"}
CATALOGUE = {d["_id"]: d for d in (CUIR, SELLE, CEINTURE, CITE)}


@pytest.fixture(autouse=True)
def _marche_en_memoire(monkeypatch):
	monkeypatch.setattr(marche, "_all_recettes", lambda: RECETTES)
	monkeypatch.setattr(marche, "get_doc", lambda i: CATALOGUE.get(i))
	monkeypatch.setattr(marche, "resolve_item_ref",
						lambda i: (dict(CATALOGUE[i], item=i) if i in CATALOGUE else None))
	monkeypatch.setattr(marche.random, "random", lambda: 0.99)          # aucune vente PNJ
	monkeypatch.setattr(character_stats, "ATELIER_TRANSFO_PROBA", 0.0)  # pas de production
	monkeypatch.setattr(character_stats, "APPRO_DEBIT_DEFAUT", 0)       # pas d'appro parasite
	monkeypatch.setattr(character_stats, "VENTE_PNJ_PROBA", 0.0)
	monkeypatch.setattr(character_stats, "FLUX_SURPLUS_PART", 1.0)
	monkeypatch.setattr(character_stats, "FLUX_PART_MAX", 1.0)
	marche.reset_prix_cache()
	yield
	marche.reset_prix_cache()


def _bourrelier(**extra):
	doc = {"_id": "lieu:bourrelier", "type": "lieu", "categorie": "bourrellerie_test",
		   "lieu_parent": CITE["_id"], "stock_matieres": {}, "stock_vente": []}
	doc.update(extra)
	return doc


def _etable(**extra):
	doc = {"_id": "lieu:etable", "type": "lieu", "categorie": "etable",
		   "lieu_parent": CITE["_id"]}
	doc.update(extra)
	return doc


def _qty(lieu, item_id):
	return next((e["qty"] for e in lieu.get("stock_vente", []) if e["item_id"] == item_id), 0)


def test_le_harnachement_est_revendable_le_reste_non():
	assert marche.item_revendable(SELLE)
	assert not marche.item_revendable(CEINTURE)
	assert marche.lieu_revend(_etable(), SELLE)
	assert not marche.lieu_revend(_bourrelier(), SELLE)
	# Une étable reconnue par le TAG, comme `montures.lieu_vend_montures`.
	assert marche.lieu_revend({"categorie": "relais", "tags": ["montures"]}, SELLE)


def test_le_bourrelier_deverse_son_surplus_de_selles_bien_qu_aucune_recette_ne_les_consomme():
	cible = 2
	bourrelier = _bourrelier(stock_cible={"item": {"item:selle": cible, "item:ceinture": cible}},
							 stock_vente=[{"item_id": "item:selle", "qty": cible + 5},
										  {"item_id": "item:ceinture", "qty": cible + 5}])
	flux = marche.flux_cite(copy.deepcopy(CITE))
	marche._deverser_surplus_flux(bourrelier, flux)
	assert flux["pool"] == {"item:selle": 5}         # la ceinture, sans preneur, reste en rayon
	assert _qty(bourrelier, "item:selle") == cible


def test_l_etable_puise_le_harnachement_en_rayon_jusqu_a_sa_cible():
	cible = 3
	etable = _etable(stock_cible={"item": {"item:selle": cible}})
	flux = marche.flux_cite(copy.deepcopy(CITE))
	flux["pool"] = {"item:selle": cible + 4, "item:ceinture": 6, "item:cuir": 6}
	assert marche.tick_atelier(etable, [], flux)
	assert _qty(etable, "item:selle") == cible                  # jamais au-dessus de la cible
	assert flux["pool"] == {"item:selle": 4, "item:ceinture": 6, "item:cuir": 6}
	assert flux["change"]
	# Rayon plein : le tick suivant ne prend plus rien.
	assert not marche.puiser_revente(etable, flux)


def test_l_etable_ne_renvoie_pas_a_la_ville_ce_qu_elle_y_a_pris():
	etable = _etable(stock_cible={"item": {"item:selle": 1}},
					 stock_vente=[{"item_id": "item:selle", "qty": 9}])
	flux = marche.flux_cite(copy.deepcopy(CITE))
	assert not marche._deverser_surplus_flux(etable, flux)
	assert _qty(etable, "item:selle") == 9


def test_un_atelier_ordinaire_ne_puise_pas_le_harnachement():
	flux = marche.flux_cite(copy.deepcopy(CITE))
	flux["pool"] = {"item:selle": 5}
	assert not marche.puiser_revente(_bourrelier(), flux)
	assert flux["pool"] == {"item:selle": 5}


def test_sans_flux_l_etable_ne_fait_rien():
	etable = _etable()
	assert not marche.puiser_revente(etable, None)
	assert "stock_vente" not in etable


def test_l_etable_vend_plus_cher_que_l_artisan(monkeypatch):
	monkeypatch.setattr(character_stats, "REVENTE_MAJORATION", 1.15)
	source = marche.prix_achat_lieu(_bourrelier(), SELLE, "item:selle")
	assert source == marche.prix_range_cuivre(SELLE, "item:selle")
	revente = marche.prix_achat_lieu(_etable(), SELLE, "item:selle")
	m = character_stats.REVENTE_MAJORATION
	assert revente == (max(1, round(source[0] * m)), max(1, round(source[1] * m)))
	assert revente[0] > source[0] and revente[1] > source[1]
	# Ce que l'étable ne revend pas garde la fourchette d'origine.
	assert (marche.prix_achat_lieu(_etable(), CEINTURE, "item:ceinture")
			== marche.prix_range_cuivre(CEINTURE, "item:ceinture"))


def test_une_majoration_sous_1_ne_fait_jamais_de_l_etable_la_moins_chere(monkeypatch):
	monkeypatch.setattr(character_stats, "REVENTE_MAJORATION", 0.5)
	assert (marche.prix_achat_lieu(_etable(), SELLE, "item:selle")
			== marche.prix_range_cuivre(SELLE, "item:selle"))


def test_le_prix_affiche_au_rayon_de_l_etable_est_majore(monkeypatch):
	monkeypatch.setattr(character_stats, "REVENTE_MAJORATION", 1.15)
	etable = _etable(stock_vente=[{"item_id": "item:selle", "qty": 1}])
	ligne = marche.resolve_stock_vente(etable)[0]
	assert (ligne["prix_min"], ligne["prix_max"]) == marche.prix_achat_lieu(etable, SELLE, "item:selle")


def test_l_etable_ne_rachete_pas_le_harnachement():
	assert not marche.lieu_buys(_etable(), dict(SELLE, item="item:selle"))
