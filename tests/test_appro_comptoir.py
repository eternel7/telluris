# tests/test_appro_comptoir.py
#
# L'approvisionnement automatique alimente DEUX destinations : l'ATELIER (`stock_matieres`,
# ce que la production consomme) et le COMPTOIR (`stock_vente`, ce que le joueur achète).
#
# Sans la seconde, un intrant brut n'était achetable NULLE PART — les quatre payloads du
# marchand ne lisent que `resolve_stock_vente`, et rien ne faisait jamais passer une matière
# de la réserve au rayon. Aucun armurier ne vendait de fer, alors que les deux en stockaient
# quinze à dix-sept sortes.
#
# ⚠️ CE QUE CE FICHIER PROTÈGE AVANT TOUT : « la ligne de vitrine ne dépasse JAMAIS le stock
# cible ». C'est elle, et elle seule, qui rend le comptoir NEUTRE pour l'atelier — à la cible
# exactement, le surplus du rayon est nul, donc `_executer_production_batch` (qui ne puise que
# dans le surplus) et `ecouler_produits_pnj` (idem) ne peuvent pas y toucher. La rogner, ce
# serait laisser la production manger sa propre vitrine.
#
# Logique pure : `get_doc` et le catalogue de recettes sont servis en mémoire, aucun accès DB.

import random

import pytest

from models import character_stats
from utils import marche


# ── Fixtures ─────────────────────────────────────────────────────────────────────

FER = {"_id": "item:fer", "type": "item", "nom": "Fer", "categorie": "composant",
	   "sous_categorie": "fer", "slots": [], "poids": 1.0, "rarete": "commun"}
CUIR = {"_id": "item:cuir", "type": "item", "nom": "Cuir", "categorie": "composant",
		"sous_categorie": "cuir", "slots": [], "poids": 0.5, "rarete": "commun"}
LAME = {"_id": "item:lame", "type": "item", "nom": "Lame", "categorie": "arme",
		"sous_categorie": "", "slots": ["main_droite"], "poids": 1.5, "rarete": "commun"}

# `fer` et `cuir` sont des feuilles (aucune recette ne les produit) ; `lame` est le produit.
RECETTES = [{
	"_id": "recette:test_lame", "type": "recette", "lieu_categorie": "forge_test",
	"objet_final": "lame", "quantite_produite": 1,
	"matieres_premieres": [{"sous_categorie": "fer", "quantite": 2},
						   {"sous_categorie": "cuir", "quantite": 1}],
}]

CATALOGUE = {d["_id"]: d for d in (FER, CUIR, LAME)}


@pytest.fixture(autouse=True)
def _marche_en_memoire(monkeypatch):
	"""Recettes et docs servis depuis la mémoire ; les mémos de module sont vidés autour du
	test (`_marche_map` est calculé UNE fois par process, il empoisonnerait les voisins)."""
	monkeypatch.setattr(marche, "_all_recettes", lambda: RECETTES)
	monkeypatch.setattr(marche, "get_doc", lambda i: CATALOGUE.get(i))
	monkeypatch.setattr(marche, "resolve_item_ref",
						lambda i: (dict(CATALOGUE[i], item=i) if i in CATALOGUE else None))
	marche.reset_prix_cache()
	yield
	marche.reset_prix_cache()


def _lieu(**extra):
	doc = {"_id": "lieu:forge_test", "type": "lieu", "categorie": "forge_test",
		   "stock_matieres": {}, "stock_vente": []}
	doc.update(extra)
	return doc


def _qty(lieu, item_id):
	return next((int(e["qty"]) for e in lieu["stock_vente"] if e["item_id"] == item_id), 0)


# ── L'invariante ─────────────────────────────────────────────────────────────────

def test_la_vitrine_ne_depasse_JAMAIS_le_stock_cible():
	# LE test du fichier. Cent approvisionnements d'affilée : la ligne se stabilise à la
	# cible et n'y ajoute plus rien. Si elle la dépassait, le surplus deviendrait matière
	# première et la production se mettrait à manger la vitrine.
	lieu = _lieu()
	cible = marche.stock_cible_pour(lieu, dict(FER, item="item:fer"))
	for _ in range(100):
		marche.approvisionner(lieu)
		assert _qty(lieu, "item:fer") <= cible
	assert _qty(lieu, "item:fer") == cible


def test_a_la_cible_le_surplus_est_nul_donc_la_production_ignore_la_vitrine():
	# Corollaire direct, et la vraie raison d'être de l'invariante : la vitrine pleine ne
	# doit pas alimenter le batch. On la garnit, on vide la réserve, et rien ne peut cuire.
	lieu = _lieu()
	for _ in range(50):
		marche.approvisionner(lieu)
	garni = _qty(lieu, "item:fer")
	assert garni > 0
	lieu["stock_matieres"] = {}          # réserve vide, vitrine pleine
	# `resolve_fn` explicite : c'est lui qui reconnaît la clé-matière d'une ligne de rayon.
	produits = marche._executer_production_batch(lieu, RECETTES, marche.resolve_item_ref)
	assert produits == []
	assert _qty(lieu, "item:fer") == garni   # pas une unité prélevée


def test_une_cible_par_lieu_est_respectee():
	# `stock_cible` est défini PAR LIEU : la vitrine doit suivre CE réglage, pas le défaut.
	lieu = _lieu(stock_cible={"item": {"item:fer": 3}})
	for _ in range(30):
		marche.approvisionner(lieu)
	assert _qty(lieu, "item:fer") == 3


# ── Le comportement rendu possible ───────────────────────────────────────────────

def test_une_feuille_devient_achetable_sur_place():
	lieu = _lieu()
	marche.approvisionner(lieu)
	vendus = {l["item_id"] for l in marche.resolve_stock_vente(lieu)}
	assert {"item:fer", "item:cuir"} <= vendus


def test_la_reserve_de_l_atelier_est_alimentee_COMME_AVANT():
	# Le comptoir s'AJOUTE, il ne prélève pas : la production ne doit rien perdre.
	lieu = _lieu()
	debit = marche._appro_debit_pour("fer")
	marche.approvisionner(lieu)
	assert lieu["stock_matieres"]["fer"] == debit


def test_un_achat_est_regarni_au_tick_suivant():
	lieu = _lieu()
	for _ in range(50):
		marche.approvisionner(lieu)
	cible = _qty(lieu, "item:fer")
	next(e for e in lieu["stock_vente"] if e["item_id"] == "item:fer")["qty"] -= 1
	marche.approvisionner(lieu)
	assert _qty(lieu, "item:fer") == cible


def test_la_production_reste_rigoureusement_inchangee():
	# Neutralité mesurée : même graine, mêmes recettes, même réserve → même production,
	# que la vitrine soit garnie ou non.
	def produire(avec_vitrine):
		lieu = _lieu()
		if avec_vitrine:
			for _ in range(50):
				marche.approvisionner(lieu)
		lieu["stock_matieres"] = {"fer": 40, "cuir": 20}
		random.seed(4)
		return marche._executer_production_batch(lieu, RECETTES, marche.resolve_item_ref)

	assert produire(False) == produire(True)


# ── Les deux exceptions, assumées et documentées ─────────────────────────────────

def test_une_feuille_sans_doc_item_ne_monte_pas_en_vitrine():
	# `matiere_item_id` peut rendre un id inexistant (`item:branche`, `item:rondin`…) :
	# fail-soft, la matière reste consommable en production mais n'est pas vendue.
	recettes = [dict(RECETTES[0], _id="recette:test_manche", objet_final="lame",
					 matieres_premieres=[{"sous_categorie": "bois_fantome", "quantite": 1}])]
	marche._all_recettes = lambda: recettes
	marche.reset_prix_cache()
	lieu = _lieu()
	marche.approvisionner(lieu)
	assert lieu["stock_matieres"]["bois_fantome"] > 0     # l'atelier est servi
	assert lieu["stock_vente"] == []                      # le comptoir, non


def test_une_feuille_a_debit_nul_ne_monte_pas_en_vitrine(monkeypatch):
	# `APPRO_DEBIT["herbe"] = 0` : récolte joueur, aucune livraison — donc rien en vitrine.
	monkeypatch.setattr(character_stats, "APPRO_DEBIT", {"fer": 0}, raising=False)
	lieu = _lieu()
	marche.approvisionner(lieu)
	assert "fer" not in lieu["stock_matieres"]
	assert _qty(lieu, "item:fer") == 0
	assert _qty(lieu, "item:cuir") > 0                    # l'autre feuille passe bien


# ── Le trou que la mise en vitrine ouvre, et son garde ───────────────────────────

def test_aucun_arbitrage_acheter_puis_revendre_une_matiere_du_comptoir():
	"""Mettre une matière au comptoir la rend ACHETABLE — donc revendable au même endroit.

	⚠️ Sans garde, l'aller-retour est une MACHINE À OR : le rachat se faisait sur la fourchette
	pleine (`pmin`..`pmax`) alors que la vente au joueur part du même prix de base, et à partir
	de la relation ~60 le joueur revendait plus cher qu'il n'avait acheté (+55 cu l'unité à 70),
	indéfiniment. `params_vente_lieu` plafonne donc le rachat par `RACHAT_FACTEUR` dès que le
	lieu a l'objet EN RAYON, et plus seulement quand il le produit.
	"""
	lieu = _lieu(stock_matieres={"fer": 40},
				 stock_vente=[{"item_id": "item:fer", "qty": 25}])
	item = dict(FER, item="item:fer")
	pmin, pmax = marche.prix_range_cuivre(item, "item:fer")
	cible = marche.stock_cible_pour(lieu, item)
	for relation in (0, 30, 50, 60, 70, 90, 100):
		rel = {"value": relation}
		achat = marche.prix_marche(rel, "item:fer", pmin, pmax, "achat", 25, cible)
		vn, vx, stock = marche.params_vente_lieu(lieu, item, "item:fer")
		revente = marche.prix_marche(rel, "item:fer", vn, vx, "vente", stock, cible)
		assert revente <= achat, (
			f"arbitrage à relation {relation} : acheté {achat} cu, revendu {revente} cu")


def test_le_rachat_d_une_matiere_hors_rayon_garde_la_fourchette_pleine():
	# Le garde ne vise QUE ce que le comptoir vend : une matière absente du rayon reste
	# rachetée normalement — sinon on nerferait la revente de butin sans aucune raison.
	lieu = _lieu(stock_matieres={"fer": 10})          # rien en rayon
	pmin, pmax = marche.prix_range_cuivre(dict(FER, item="item:fer"), "item:fer")
	vn, vx, stock = marche.params_vente_lieu(lieu, dict(FER, item="item:fer"), "item:fer")
	assert (vn, vx, stock) == (pmin, pmax, 10)
