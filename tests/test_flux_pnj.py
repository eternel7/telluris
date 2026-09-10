# tests/test_flux_pnj.py
#
# Le FLUX DE MARCHANDISES entre les boutiques d'une même cité.
#
# Ce que les PNJ consomment chez un marchand ne s'évapore plus tout à fait : une part
# (`VENTE_PNJ_REDISTRIB`) est versée au pool de flux de la CITÉ (`lieu.flux_marchand`), où les
# ateliers dont une recette réclame cette matière viennent puiser à leur propre tick. Aucun
# scan de voisins : un seul doc partagé, ouvert par l'appelant (`flux_cite`), refermé une fois
# (`persister_flux`).
#
# ⚠️ CE QUE CE FICHIER PROTÈGE AVANT TOUT, dans l'ordre :
#   1. `flux=None` ⇒ le tick est STRICTEMENT celui d'avant. Un lieu sans cité, une fixture, un
#      appelant qui n'a pas été branché : tous doivent continuer de tourner à l'identique.
#   2. L'ORDRE puiser-avant-écouler. L'inverser ferait reprendre à une boutique, dans le même
#      tick, ce qu'elle vient de vendre aux habitants — un tour de manège silencieux.
#   3. La garde `categorie == "ville"`. Sans elle le flux se poserait sur `lieu:france` et les
#      cités se fourniraient entre elles d'un bout à l'autre du royaume.
#
# Logique pure : recettes et docs servis en mémoire, `random` neutralisé, aucun accès DB.

import copy

import pytest

from models import character_stats
from utils import marche


# ── Fixtures ─────────────────────────────────────────────────────────────────────
# Une filière à deux étages : `ble` (feuille) → `farine` (moulin) → `pain` (boulangerie).
# `pain` n'est l'intrant d'AUCUNE recette : c'est la matière dont personne n'a l'usage, celle
# qui doit rester hors du pool.

BLE = {"_id": "item:ble", "type": "item", "nom": "Blé", "categorie": "composant",
	   "sous_categorie": "ble", "slots": [], "poids": 1.0, "rarete": "commun"}
FARINE = {"_id": "item:farine", "type": "item", "nom": "Farine", "categorie": "composant",
		  "sous_categorie": "farine", "slots": [], "poids": 1.0, "rarete": "commun"}
PAIN = {"_id": "item:pain", "type": "item", "nom": "Pain", "categorie": "composant",
		"sous_categorie": "pain", "slots": [], "poids": 0.5, "rarete": "commun"}

RECETTES = [
	{"_id": "recette:farine", "type": "recette", "lieu_categorie": "moulin_test",
	 "objet_final": "farine", "quantite_produite": 1,
	 "matieres_premieres": [{"sous_categorie": "ble", "quantite": 2}]},
	{"_id": "recette:pain", "type": "recette", "lieu_categorie": "boulangerie_test",
	 "objet_final": "pain", "quantite_produite": 1,
	 "matieres_premieres": [{"sous_categorie": "farine", "quantite": 2}]},
]

CITE = {"_id": "lieu:cite_test", "type": "lieu", "categorie": "ville", "label": "Cité d'essai"}
PAYS = {"_id": "lieu:pays_test", "type": "lieu", "categorie": "pays", "label": "Pays d'essai"}

CATALOGUE = {d["_id"]: d for d in (BLE, FARINE, PAIN, CITE, PAYS)}


@pytest.fixture(autouse=True)
def _marche_en_memoire(monkeypatch):
	"""Recettes et docs en mémoire ; `random` neutralisé (production coupée, demande PNJ
	toujours servie, en totalité) ; mémos de module vidés autour du test — `_marche_map` et
	`cles_consommees` sont calculés UNE fois par process et empoisonneraient les voisins."""
	monkeypatch.setattr(marche, "_all_recettes", lambda: RECETTES)
	monkeypatch.setattr(marche, "get_doc", lambda i: CATALOGUE.get(i))
	monkeypatch.setattr(marche, "resolve_item_ref",
						lambda i: (dict(CATALOGUE[i], item=i) if i in CATALOGUE else None))
	monkeypatch.setattr(marche.random, "random", lambda: 0.0)
	monkeypatch.setattr(character_stats, "ATELIER_TRANSFO_PROBA", 0.0)  # pas de production
	monkeypatch.setattr(character_stats, "APPRO_DEBIT_DEFAUT", 0)       # pas d'appro parasite
	monkeypatch.setattr(character_stats, "VENTE_PNJ_PROBA", 1.0)        # demande toujours là
	monkeypatch.setattr(character_stats, "VENTE_PNJ_FRACTION", 1.0)     # tout le surplus part
	monkeypatch.setattr(character_stats, "VENTE_PNJ_REDISTRIB", 0.5)
	marche.reset_prix_cache()
	yield
	marche.reset_prix_cache()


def _moulin(**extra):
	"""Consomme `ble`, produit `farine`."""
	doc = {"_id": "lieu:moulin", "type": "lieu", "categorie": "moulin_test",
		   "lieu_parent": CITE["_id"], "stock_matieres": {}, "stock_vente": []}
	doc.update(extra)
	return doc


def _boulangerie(**extra):
	"""Consomme `farine`, produit `pain`."""
	doc = {"_id": "lieu:boulangerie", "type": "lieu", "categorie": "boulangerie_test",
		   "lieu_parent": CITE["_id"], "stock_matieres": {}, "stock_vente": []}
	doc.update(extra)
	return doc


def _cite():
	return copy.deepcopy(CITE)


# ── 1. `flux=None` : rien ne change ──────────────────────────────────────────────

def test_sans_flux_le_tick_est_STRICTEMENT_celui_d_avant():
	# LE verrou de non-régression. Le paramètre par défaut et un None explicite doivent
	# produire exactement le même doc — et aucun des deux ne doit inventer de champ.
	defaut = _boulangerie(stock_cible={"item": {"item:pain": 2}},
						  stock_vente=[{"item_id": "item:pain", "qty": 10}])
	explicite = copy.deepcopy(defaut)

	marche.tick_atelier(defaut, RECETTES)
	marche.tick_atelier(explicite, RECETTES, None)

	assert defaut == explicite
	assert "flux_marchand" not in defaut
	# Les deux greffes sont inertes sans contexte, sans lever.
	assert marche.puiser_flux(defaut, None) is False
	assert marche._crediter_flux(None, [{"item_id": "item:farine", "qty": 4}]) is False


def test_flux_cite_refuse_tout_doc_qui_n_est_pas_une_ville():
	# Les cités portent `lieu_parent: lieu:france`. Sans cette garde, une cité qui tique
	# elle-même verserait son flux sur le doc du PAYS, et les villes se fourniraient entre
	# elles à travers tout le royaume.
	assert marche.flux_cite(None) is None
	assert marche.flux_cite(PAYS) is None
	assert marche.flux_cite(_moulin()) is None
	assert marche.flux_cite(_cite()) is not None


def test_flux_cite_relit_le_pool_en_base_et_ignore_une_quantite_illisible():
	cite = _cite()
	cite["flux_marchand"] = {"item:farine": 3, "item:ble": "boum", "item:pain": 0}
	flux = marche.flux_cite(cite)
	assert flux["pool"] == {"item:farine": 3}
	assert flux["change"] is False


# ── 2. Crédit : ce dont un atelier a l'usage, et rien d'autre ─────────────────────

def test_seule_une_matiere_dont_un_atelier_a_l_usage_entre_au_pool():
	# `farine` est l'intrant de la boulangerie → elle circule. `pain` n'est l'intrant
	# d'aucune recette → il est vraiment consommé, il ne réapparaît nulle part.
	flux = marche.flux_cite(_cite())
	marche._crediter_flux(flux, [{"item_id": "item:farine", "qty": 8},
								 {"item_id": "item:pain", "qty": 8}])
	assert flux["pool"] == {"item:farine": 4}    # 8 × VENTE_PNJ_REDISTRIB (0.5)
	assert flux["change"] is True


def test_cles_consommees_est_l_index_INVERSE_du_marche():
	# Le seul index qui aille des clés vers « quelqu'un sait quoi faire de ça ».
	cles = marche.cles_consommees()
	assert "ble" in cles and "farine" in cles
	assert "pain" not in cles


def test_le_pool_est_plafonne_par_cle():
	# Une matière que personne ne vient chercher ne doit pas gonfler indéfiniment le doc de la
	# ville — `stock_matieres` est déjà le seul réservoir non borné du jeu, on n'en fait pas un
	# second.
	flux = marche.flux_cite(_cite())
	for _ in range(200):
		marche._crediter_flux(flux, [{"item_id": "item:farine", "qty": 10}])
	assert flux["pool"]["item:farine"] == character_stats.STOCK_CIBLE_DEFAUT


def test_une_part_nulle_ne_redistribue_rien(monkeypatch):
	monkeypatch.setattr(character_stats, "VENTE_PNJ_REDISTRIB", 0.0)
	flux = marche.flux_cite(_cite())
	assert marche._crediter_flux(flux, [{"item_id": "item:farine", "qty": 8}]) is False
	assert flux["pool"] == {}


# ── 3. Tirage : la boutique qui en a l'usage sert en RÉSERVE ──────────────────────

def test_la_boutique_qui_en_a_besoin_puise_en_reserve_sous_la_cle_de_cle_matiere_lieu():
	# Destination : `stock_matieres`, pas le rayon — c'est de la matière première, elle passe
	# par l'atelier. Et sous la clé de `cle_matiere_lieu`, celle-là même qu'emprunte une vente
	# au marchand : la recette doit la retrouver.
	boulangerie = _boulangerie()
	flux = marche.flux_cite(_cite())
	flux["pool"] = {"item:farine": 6}

	assert marche.puiser_flux(boulangerie, flux) is True
	assert boulangerie["stock_matieres"] == {"farine": 6}
	assert boulangerie["stock_vente"] == []      # rien en vitrine
	assert flux["pool"] == {}                    # le lot a quitté le pool
	assert flux["change"] is True


def test_une_boutique_sans_ce_besoin_ne_touche_pas_au_pool():
	# Le moulin consomme du blé, pas de la farine : le lot ne bouge pas, il attend son artisan.
	moulin = _moulin()
	flux = marche.flux_cite(_cite())
	flux["pool"] = {"item:farine": 6}

	assert marche.puiser_flux(moulin, flux) is False
	assert moulin["stock_matieres"] == {}
	assert flux["pool"] == {"item:farine": 6}
	assert flux["change"] is False


def test_un_lieu_qui_PRODUIT_l_item_ne_le_repuise_pas():
	# Anti-boucle : un atelier dont un produit est aussi l'intrant d'une de ses propres
	# recettes reprendrait sans fin ce qu'il vient de vendre aux PNJ.
	moulin = _moulin(categorie="moulin_test")
	flux = marche.flux_cite(_cite())
	flux["pool"] = {"item:ble": 6}
	# Le moulin a bien BESOIN de blé…
	assert "ble" in marche.besoins_lieu(moulin)
	assert marche.puiser_flux(moulin, flux) is True
	assert moulin["stock_matieres"] == {"ble": 6}

	# …mais s'il le produisait, la garde `lieu_produit` couperait le circuit.
	autarcique = _moulin(_id="lieu:autarcique", categorie="autarcie_test")
	autarcique_recettes = RECETTES + [
		{"_id": "recette:ble", "type": "recette", "lieu_categorie": "autarcie_test",
		 "objet_final": "ble", "quantite_produite": 1,
		 "matieres_premieres": [{"sous_categorie": "ble", "quantite": 1}]}]
	marche.reset_prix_cache()
	original = marche._all_recettes
	marche._all_recettes = lambda: autarcique_recettes
	try:
		flux2 = marche.flux_cite(_cite())
		flux2["pool"] = {"item:ble": 6}
		assert marche.puiser_flux(autarcique, flux2) is False
		assert flux2["pool"] == {"item:ble": 6}
	finally:
		marche._all_recettes = original
		marche.reset_prix_cache()


# ── 4. L'ordre dans le tick ──────────────────────────────────────────────────────

def test_on_puise_AVANT_d_ecouler_donc_pas_de_tour_de_manege():
	# Le moulin a du blé en vitrine (l'appro met les feuilles au comptoir) et le blé est un
	# intrant de SES recettes. Au tick où les PNJ lui en prennent, il ne doit pas le reprendre
	# aussitôt : ce qui vient d'être écoulé attend le tick suivant.
	moulin = _moulin(stock_cible={"item": {"item:ble": 2}},
					 stock_vente=[{"item_id": "item:ble", "qty": 10}])
	flux = marche.flux_cite(_cite())

	marche.tick_atelier(moulin, RECETTES, flux)

	# 10 − 2 = 8 écoulés, dont la moitié au pool ; rien n'est revenu en réserve ce tick-ci.
	assert moulin["stock_matieres"] == {}
	assert flux["pool"] == {"item:ble": 4}

	# Au tick SUIVANT, en revanche, le moulin sert bien son propre besoin.
	marche.tick_atelier(moulin, RECETTES, flux)
	assert moulin["stock_matieres"]["ble"] == 4


def test_rien_n_est_cree_la_redistribution_est_une_PORTION():
	# Invariante d'économie : sur une longue série de ticks, ce qui ressort du pool ne peut
	# jamais dépasser ce que les PNJ ont consommé.
	moulin = _moulin(stock_cible={"item": {"item:farine": 2}},
					 stock_vente=[{"item_id": "item:farine", "qty": 40}])
	boulangerie = _boulangerie()
	flux = marche.flux_cite(_cite())

	consomme = 0
	depart = 40
	for _ in range(10):
		avant = next((e["qty"] for e in moulin["stock_vente"] if e["item_id"] == "item:farine"), 0)
		marche.tick_atelier(moulin, RECETTES, flux)
		apres = next((e["qty"] for e in moulin["stock_vente"] if e["item_id"] == "item:farine"), 0)
		consomme += avant - apres
		marche.tick_atelier(boulangerie, RECETTES, flux)

	recu = boulangerie["stock_matieres"].get("farine", 0) + flux["pool"].get("item:farine", 0)
	assert consomme == depart - 2          # le rayon s'arrête au stock cible
	assert 0 < recu <= consomme            # une PORTION, jamais davantage


# ── 5. Persistance : une écriture, et seulement si le pool a bougé ────────────────

def test_persister_flux_n_ecrit_que_si_le_pool_a_bouge():
	sauves = []
	save = lambda doc: sauves.append(doc.get("_id")) or doc

	cite = _cite()
	flux = marche.flux_cite(cite)
	assert marche.persister_flux(flux, save) is False   # rien n'a bougé → aucune écriture
	assert sauves == []

	marche._crediter_flux(flux, [{"item_id": "item:farine", "qty": 8}])
	assert marche.persister_flux(flux, save) is True
	assert sauves == ["lieu:cite_test"]
	assert cite["flux_marchand"] == {"item:farine": 4}

	# Contexte absent (lieu hors ville) : no-op, jamais d'exception.
	assert marche.persister_flux(None, save) is False
	assert sauves == ["lieu:cite_test"]


def test_un_pool_vide_retire_le_champ_plutot_que_d_y_laisser_un_dict_vide():
	cite = _cite()
	cite["flux_marchand"] = {"item:farine": 6}
	flux = marche.flux_cite(cite)
	marche.puiser_flux(_boulangerie(), flux)
	assert marche.persister_flux(flux, lambda doc: doc) is True
	assert "flux_marchand" not in cite
