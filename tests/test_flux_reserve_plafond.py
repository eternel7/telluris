# tests/test_flux_reserve_plafond.py
#
# DEUX déblocages du flux de cité, nés d'une commande de harnachement restée en attente à
# Chartres (dump du 10/10, 18:37) :
#
# - la RÉSERVE MORTE part au pool à chaque tick : les crins de la boucherie (dépeçage) dormaient
#   en `stock_matieres`, qu'elle ne consomme pas, et n'en sortaient qu'au déclenchement d'une
#   passe de production (10 % par tick) ;
# - un INTERMÉDIAIRE que l'atelier consomme lui-même est plafonné à `STOCK_INTERMEDIAIRE_MAX` :
#   faute de crins, la seule recette applicable du bourrelier (la boucle de fer) en avait
#   empilé 858 pour une cible de 25.
#
# Logique pure : recettes et docs servis en mémoire, aucun accès DB.

import pytest

from models import character_stats
from utils import marche

CRINS = {"_id": "item:crins", "type": "item", "nom": "Crins", "categorie": "composant",
		 "sous_categorie": "crins", "slots": [], "poids": 0.2, "rarete": "commun"}
CUIR = {"_id": "item:cuir", "type": "item", "nom": "Cuir", "categorie": "composant",
		"sous_categorie": "cuir", "slots": [], "poids": 1.0, "rarete": "commun"}
BOUCLE = {"_id": "item:boucle", "type": "item", "nom": "Boucle", "categorie": "composant",
		  "sous_categorie": "boucle", "slots": [], "poids": 0.1, "rarete": "commun"}
SELLE = {"_id": "item:selle", "type": "item", "nom": "Selle", "categorie": "armure",
		 "slots": ["monture_dos"], "poids": 8.0, "rarete": "commun"}
OS = {"_id": "item:os", "type": "item", "nom": "Os", "categorie": "composant",
	  "sous_categorie": "os", "slots": [], "poids": 0.5, "rarete": "commun"}

RECETTES = [
	# Le bourrelier : la boucle est un intermédiaire qu'il consomme lui-même (selle).
	{"_id": "recette:boucle", "type": "recette", "lieu_categorie": "bourrellerie_test",
	 "objet_final": "boucle", "quantite_produite": 1,
	 "matieres_premieres": [{"sous_categorie": "cuir", "quantite": 1}]},
	{"_id": "recette:selle", "type": "recette", "lieu_categorie": "bourrellerie_test",
	 "objet_final": "selle", "quantite_produite": 1,
	 "matieres_premieres": [{"item": "item:boucle", "quantite": 2},
							{"sous_categorie": "crins", "quantite": 1}]},
	# La boucherie consomme de la viande, pas des crins ni des os.
	{"_id": "recette:saucisse", "type": "recette", "lieu_categorie": "boucherie_test",
	 "objet_final": "selle", "quantite_produite": 1,
	 "matieres_premieres": [{"sous_categorie": "viande", "quantite": 5}]},
]

CATALOGUE = {d["_id"]: d for d in (CRINS, CUIR, BOUCLE, SELLE, OS)}


def _resolve(i):
	return dict(CATALOGUE[i], item=i) if i in CATALOGUE else None


@pytest.fixture(autouse=True)
def _marche_en_memoire(monkeypatch):
	monkeypatch.setattr(marche, "_all_recettes", lambda: RECETTES)
	monkeypatch.setattr(marche, "get_doc", lambda i: CATALOGUE.get(i))
	monkeypatch.setattr(marche, "resolve_item_ref", _resolve)
	monkeypatch.setattr(character_stats, "FLUX_SURPLUS_PART", 1.0)
	monkeypatch.setattr(character_stats, "STOCK_CIBLE_DEFAUT", 25)
	monkeypatch.setattr(character_stats, "STOCK_INTERMEDIAIRE_MAX", 50)
	marche.reset_prix_cache()
	yield
	marche.reset_prix_cache()


def _boucherie(**extra):
	doc = {"_id": "lieu:boucherie", "type": "lieu", "categorie": "boucherie_test",
		   "lieu_parent": "lieu:cite", "stock_matieres": {}, "stock_vente": []}
	doc.update(extra)
	return doc


def _bourrelier(**extra):
	doc = {"_id": "lieu:bourrelier", "type": "lieu", "categorie": "bourrellerie_test",
		   "lieu_parent": "lieu:cite", "stock_matieres": {}, "stock_vente": []}
	doc.update(extra)
	return doc


def _flux(**pool):
	return {"doc": {}, "pool": {"item:" + k: v for k, v in pool.items()}, "change": False}


def _qty(lieu, item_id):
	return next((e["qty"] for e in lieu.get("stock_vente", []) if e["item_id"] == item_id), 0)


# ── La réserve morte part au pool ───────────────────────────────────────────────

def test_la_reserve_morte_de_la_boucherie_part_au_pool():
	"""Le cas de Chartres : 25 crins en rayon (à la cible, donc aucun surplus) et 21 en
	réserve, que la boucherie ne consomme pas."""
	lieu = _boucherie(stock_matieres={"crins": 21},
					  stock_vente=[{"item_id": "item:crins", "qty": 25}])
	flux = _flux()
	assert marche._deverser_surplus_flux(lieu, flux, reserve=True) is True
	assert flux["pool"] == {"item:crins": 21} and flux["change"] is True
	assert "crins" not in lieu["stock_matieres"]
	assert _qty(lieu, "item:crins") == 25, "le rayon ne descend pas sous sa cible"


def test_sans_reserve_comportement_d_avant():
	lieu = _boucherie(stock_matieres={"crins": 21})
	flux = _flux()
	assert marche._deverser_surplus_flux(lieu, flux) is False
	assert flux["pool"] == {} and lieu["stock_matieres"] == {"crins": 21}


def test_le_plafond_du_pool_tient_pour_la_reserve():
	lieu = _boucherie(stock_matieres={"crins": 21})
	flux = _flux(crins=20)
	marche._deverser_surplus_flux(lieu, flux, reserve=True)
	assert flux["pool"]["item:crins"] == 25
	assert lieu["stock_matieres"]["crins"] == 16


def test_une_matiere_que_le_lieu_consomme_reste_en_reserve():
	lieu = _bourrelier(stock_matieres={"crins": 10, "cuir": 10})
	flux = _flux()
	marche._deverser_surplus_flux(lieu, flux, reserve=True)
	assert flux["pool"] == {}


def test_une_matiere_dont_personne_n_a_l_usage_ne_circule_pas():
	lieu = _boucherie(stock_matieres={"os": 30})
	flux = _flux()
	marche._deverser_surplus_flux(lieu, flux, reserve=True)
	assert flux["pool"] == {} and lieu["stock_matieres"] == {"os": 30}


def test_une_cle_sans_doc_ne_circule_jamais():
	lieu = _boucherie(stock_matieres={"carcasse": 3})
	flux = _flux()
	marche._deverser_surplus_flux(lieu, flux, reserve=True)
	assert flux["pool"] == {}


def test_le_marchand_de_propriete_garde_sa_reserve(monkeypatch):
	"""`appro=False` (atelier d'une propriété) : sa réserve est ce qu'on lui a confié."""
	monkeypatch.setattr(character_stats, "ATELIER_TRANSFO_PROBA", 0.0)
	monkeypatch.setattr(character_stats, "VENTE_PNJ_PROBA", 0.0)
	lieu = _boucherie(stock_matieres={"crins": 21})
	flux = _flux()
	marche.tick_detaille(lieu, [], flux, appro=False)
	assert flux["pool"] == {}
	marche.tick_detaille(lieu, [], flux)
	assert flux["pool"] == {"item:crins": 21}


# ── Plafond d'un intermédiaire consommé sur place ───────────────────────────────

def _produire(lieu):
	return marche._executer_production_batch(lieu, marche.recettes_lieu(lieu), _resolve)


def test_l_intermediaire_s_arrete_au_plafond():
	"""Sans crins, la selle ne cuit jamais : la boucle, seule applicable, s'arrête à 50."""
	lieu = _bourrelier(stock_matieres={"cuir": 500})
	_produire(lieu)
	assert _qty(lieu, "item:boucle") == character_stats.STOCK_INTERMEDIAIRE_MAX
	assert lieu["stock_matieres"]["cuir"] == 500 - character_stats.STOCK_INTERMEDIAIRE_MAX


def test_un_rayon_deja_au_dela_ne_produit_plus():
	lieu = _bourrelier(stock_matieres={"cuir": 10},
					   stock_vente=[{"item_id": "item:boucle", "qty": 858}])
	_produire(lieu)
	assert _qty(lieu, "item:boucle") == 858
	assert lieu["stock_matieres"]["cuir"] == 10


def test_le_plafond_n_empeche_pas_l_aval_de_consommer():
	"""Au plafond, le surplus au-dessus de la cible reste la matière de la selle."""
	lieu = _bourrelier(stock_matieres={"crins": 3},
					   stock_vente=[{"item_id": "item:boucle", "qty": 50}])
	_produire(lieu)
	assert _qty(lieu, "item:selle") == 3
	assert _qty(lieu, "item:boucle") == 44


def test_un_produit_que_le_lieu_ne_consomme_pas_n_est_pas_plafonne():
	lieu = _bourrelier(stock_matieres={"crins": 5},
					   stock_vente=[{"item_id": "item:boucle", "qty": 60},
									{"item_id": "item:selle", "qty": 80}])
	_produire(lieu)
	assert _qty(lieu, "item:selle") == 85
