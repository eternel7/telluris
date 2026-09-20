"""Non-contamination des index du marché par les recettes `sur_commande`.

⚠️ RAISON D'ÊTRE DE CE FICHIER. Une recette de variante est un doc `recette:*` ordinaire à un
drapeau près. Si ce drapeau cesse d'être lu, la conséquence n'est pas une erreur mais une
DÉRIVE SILENCIEUSE de l'économie du monde entier :

- toutes les boutiques de la catégorie se mettent à fabriquer la pièce unique d'un joueur et
  à l'exposer en rayon (`lieu_recettes` → `tick_atelier`) ;
- chacun de ses intrants devient un besoin du métier, donc une feuille auto-approvisionnée,
  donc une marchandise vendue au comptoir (`besoins_categorie` → `appro_leaves_categorie`) ;
- le recalcul global `feuilles = inputs − outputs` peut faire d'une matière une FAUSSE FEUILLE,
  qui n'est alors plus jamais livrée — et gèle sans bruit toutes les recettes qui la citent.

Aucun de ces trois effets ne lève d'exception. C'est ce fichier, et lui seul, qui les attrape.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from utils import marche, fabrication  # noqa: E402


CATEGORIE = "armurerie_de_test"

# Une recette authorée ordinaire : le métier la cuit, et son intrant est une feuille.
RECETTE_NORMALE = {
	"_id": "recette:test_normale",
	"type": "recette",
	"lieu_categorie": CATEGORIE,
	"objet_final": "Epee_longue",
	"quantite_produite": 1,
	"matieres_premieres": [{"sous_categorie": "fer_de_test", "quantite": 2}],
}

# La même forme, produite par une commande sur mesure. Ses intrants (dont une matière que
# RIEN d'autre ne consomme) ne doivent apparaître nulle part.
RECETTE_COMMANDE = fabrication.recette_variante_doc(
	{"_id": "item:Epee_longue", "nom": "Épée longue"},
	[({"_id": "item:cristal_de_test", "nom": "Cristal"}, 1)],
	CATEGORIE,
)


@pytest.fixture
def index_semes(monkeypatch):
	"""Sème les deux recettes dans l'index process, en le rendant tel qu'on l'a trouvé.

	⚠️ `reset_prix_cache()` avant ET après : ces index sont des caches de PROCESS partagés par
	tout le module (cf. `telluris-db` § caches process). Les laisser semés ferait mentir
	n'importe quel test de marché lancé après celui-ci, dans un ordre qu'on ne contrôle pas."""
	marche.reset_prix_cache()
	monkeypatch.setattr(marche, "_recettes_all", [RECETTE_NORMALE, RECETTE_COMMANDE])
	yield
	marche.reset_prix_cache()


# ── Le drapeau lui-même ──────────────────────────────────────────────────────────

def test_predicat_lit_bien_le_drapeau():
	assert marche.est_sur_commande(RECETTE_COMMANDE) is True
	assert marche.est_sur_commande(RECETTE_NORMALE) is False
	assert marche.est_sur_commande({}) is False
	assert marche.est_sur_commande(None) is False


# ── Les trois index de PRODUCTION l'ignorent ─────────────────────────────────────

def test_lieu_recettes_ne_sert_jamais_une_recette_de_commande(index_semes):
	ids = {r.get("_id") for r in marche.lieu_recettes(CATEGORIE)}
	assert RECETTE_NORMALE["_id"] in ids
	assert RECETTE_COMMANDE["_id"] not in ids


def test_besoins_ignorent_les_intrants_dune_commande(index_semes):
	besoins = set(marche.besoins_categorie(CATEGORIE))
	assert "fer_de_test" in besoins
	# Ni la matière sur mesure, ni l'objet de base (qui est pourtant un intrant de la recette).
	assert "item:cristal_de_test" not in besoins
	assert "item:Epee_longue" not in besoins


def test_produits_ignorent_la_variante(index_semes):
	produits = marche.produits_categorie(CATEGORIE)
	assert "item:Epee_longue" in produits
	assert fabrication.variante_id({"_id": "item:Epee_longue"},
								   [{"item": "item:cristal_de_test"}]) not in produits


def test_feuilles_dappro_ne_gagnent_pas_la_matiere_sur_mesure(index_semes):
	feuilles = set(marche.appro_leaves_categorie(CATEGORIE))
	assert "fer_de_test" in feuilles
	assert "item:cristal_de_test" not in feuilles


def test_cles_consommees_ignorent_la_commande(index_semes):
	# L'index inverse du flux de cité : une matière sur mesure ne doit pas se mettre à
	# circuler entre les boutiques d'une ville.
	assert "item:cristal_de_test" not in marche.cles_consommees()


def test_lieu_buys_ne_souvre_pas_sur_lintrant_dune_commande(index_semes):
	lieu = {"_id": "lieu:forge", "categorie": CATEGORIE}
	cristal = {"_id": "item:cristal_de_test", "sous_categorie": "cristal_de_test"}
	assert marche.lieu_buys(lieu, cristal) is False


# ── L'index de PRIX, lui, la garde ───────────────────────────────────────────────

def test_une_variante_se_revend_la_ou_son_modele_se_revend(index_semes):
	"""Corollaire de l'exclusion : la recette de la variante étant `sur_commande`, elle est
	absente de `produits_lieu`. Sans le repli sur `fabrication.base_item`, une pièce
	commandée ne pourrait être revendue à PERSONNE — pas même à l'atelier qui l'a forgée,
	alors que le modèle dont elle dérive s'y rachète."""
	lieu = {"_id": "lieu:forge", "categorie": CATEGORIE}
	variante = {
		"_id": "item:Epee_longue_abc12345", "categorie": "arme",
		"fabrication": {"base_item": "item:Epee_longue"},
	}
	assert marche.lieu_produit(lieu, {"_id": "item:Epee_longue"}) is True
	assert marche.lieu_produit(lieu, variante) is True
	assert marche.lieu_buys(lieu, variante) is True


def test_variante_dun_modele_etranger_non_rachetee(index_semes):
	lieu = {"_id": "lieu:forge", "categorie": CATEGORIE}
	etrangere = {"_id": "item:Bougie_abc12345", "categorie": "outil",
				 "fabrication": {"base_item": "item:Bougie"}}
	assert marche.lieu_buys(lieu, etrangere) is False


def test_item_sans_bloc_fabrication_inchange(index_semes):
	# Aucune migration : les 1 324 items en base n'ont pas ce champ.
	lieu = {"_id": "lieu:forge", "categorie": CATEGORIE}
	assert marche.lieu_produit(lieu, {"_id": "item:Epee_longue"}) is True
	assert marche.lieu_produit(lieu, {"_id": "item:Inconnu"}) is False


def test_recipe_map_garde_la_recette_de_commande(index_semes):
	# C'est la dissymétrie voulue : la variante doit pouvoir être VALORISÉE depuis ses
	# intrants, sans être FABRIQUÉE pour autant.
	variante = fabrication.variante_id({"_id": "item:Epee_longue"}, [{"item": "item:cristal_de_test"}])
	assert RECETTE_COMMANDE in marche._get_recipe_map().get(variante, [])
