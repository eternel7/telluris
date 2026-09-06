# tests/test_recettes_portee.py
#
# Portée géographique des recettes (spécialités de terroir) : une `recette:*` peut porter
# `lieu_portee`, un id de lieu ; elle n'est alors cuisinable que par les boutiques dont la
# chaîne d'ancêtres `lieu_parent` remonte jusqu'à lui. Champ ABSENT ⇒ portée mondiale.
#
# ⚠️ Deux tests portent tout le reste :
#   · `test_aucune_portee_ne_change_RIEN` — les 552 recettes déjà en base n'en portent aucune,
#     leur comportement doit rester identique au bit près ;
#   · `test_le_prix_ne_depend_PAS_du_lieu` — la portée dit où l'on fabrique, jamais combien ça
#     vaut. La scoper aurait rouvert l'arbitrage « acheter là où c'est produit, revendre là où
#     ça ne l'est pas », que tests/test_appro_comptoir.py verrouille.

import pytest

from models import character_stats
from utils import marche


# ── Un petit monde : un pays, deux cités, quatre boutiques ─────────────────────

PAYS = {"_id": "lieu:france", "type": "lieu", "categorie": "pays"}
CITE_A = {"_id": "lieu:auxerre", "type": "lieu", "categorie": "ville",
		  "lieu_parent": "lieu:france"}
CITE_B = {"_id": "lieu:ailleurs", "type": "lieu", "categorie": "ville"}   # hors du pays
FOURNIL_A = {"_id": "lieu:fournil_a", "type": "lieu", "categorie": "boulangerie",
			 "lieu_parent": "lieu:auxerre"}
FOURNIL_B = {"_id": "lieu:fournil_b", "type": "lieu", "categorie": "boulangerie",
			 "lieu_parent": "lieu:ailleurs"}
GRAND_FOURNIL = {"_id": "lieu:grand_fournil", "type": "lieu",
				 "categorie": "grande_boulangerie", "lieu_parent": "lieu:auxerre"}

DOCS = {d["_id"]: d for d in (PAYS, CITE_A, CITE_B, FOURNIL_A, FOURNIL_B, GRAND_FOURNIL)}

# Recette MONDIALE : tout fournil la cuit.
PAIN = {"_id": "recette:pain", "type": "recette", "lieu_categorie": "boulangerie",
		"objet_final": "pain", "quantite_produite": 1,
		"matieres_premieres": [{"sous_categorie": "farine", "quantite": 2}]}
# Spécialité de TERROIR : seulement sous `lieu:france`. `item:Vin` n'est produit par aucune
# recette → c'est une feuille, mais elle ne doit être livrée qu'ici.
CROISSANT = {"_id": "recette:croissant", "type": "recette", "lieu_categorie": "boulangerie",
			 "lieu_portee": "lieu:france", "objet_final": "Croissant", "quantite_produite": 4,
			 "matieres_premieres": [{"sous_categorie": "farine", "quantite": 2},
									{"item": "item:Beurre", "quantite": 3}]}
# Spécialité de CITÉ : seulement sous `lieu:auxerre`.
QUICHE = {"_id": "recette:quiche", "type": "recette", "lieu_categorie": "boulangerie",
		  "lieu_portee": "lieu:auxerre", "objet_final": "Quiche", "quantite_produite": 2,
		  "matieres_premieres": [{"item": "item:Creme", "quantite": 2}]}

RECETTES = [PAIN, CROISSANT, QUICHE]


@pytest.fixture
def monde(monkeypatch):
	monkeypatch.setattr(marche, "_all_recettes", lambda: list(RECETTES))
	monkeypatch.setattr(marche, "get_doc", lambda i: DOCS.get(i))
	monkeypatch.setattr(character_stats, "LIEU_CATEGORIES_FUSION",
						{"grande_boulangerie": ["boulangerie", "cuisine"]}, raising=False)
	marche.reset_prix_cache()
	yield
	marche.reset_prix_cache()


# ── portees_lieu ───────────────────────────────────────────────────────────────

def test_lieu_sans_parent_ne_porte_que_lui_meme(monde):
	assert marche.portees_lieu(PAYS) == ("lieu:france",)


def test_remontee_boutique_cite_pays(monde):
	assert marche.portees_lieu(FOURNIL_A) == ("lieu:fournil_a", "lieu:auxerre", "lieu:france")


def test_remontee_s_arrete_ou_la_chaine_s_arrete(monde):
	assert marche.portees_lieu(FOURNIL_B) == ("lieu:fournil_b", "lieu:ailleurs")


def test_doc_sans_id_est_fail_soft(monde):
	# Les fixtures de tests/test_marche_recettes.py sont des dicts nus : aucune portée, donc
	# rigoureusement le comportement d'avant.
	assert marche.portees_lieu({"categorie": "boulangerie"}) == ()
	assert marche.portees_lieu({}) == ()
	assert marche.portees_lieu(None) == ()


def test_cycle_de_parente_ne_boucle_pas(monkeypatch):
	# L'éditeur de carte peut poser un cycle : le premier tick venu ne doit pas s'y perdre.
	boucle = {"lieu:a": {"_id": "lieu:a", "lieu_parent": "lieu:b"},
			  "lieu:b": {"_id": "lieu:b", "lieu_parent": "lieu:a"}}
	monkeypatch.setattr(marche, "_all_recettes", lambda: [])
	monkeypatch.setattr(marche, "get_doc", lambda i: boucle.get(i))
	marche.reset_prix_cache()
	try:
		assert marche.portees_lieu(boucle["lieu:a"]) == ("lieu:a", "lieu:b")
	finally:
		marche.reset_prix_cache()


def test_reset_prix_cache_vide_le_memo_d_ancetres(monde):
	assert marche.portees_lieu(FOURNIL_A)[-1] == "lieu:france"
	orphelin = dict(FOURNIL_A)
	orphelin.pop("lieu_parent")
	DOCS["lieu:auxerre"] = {"_id": "lieu:auxerre", "type": "lieu", "categorie": "ville"}
	try:
		# Sans vidage, la chaîne mémoïsée survivrait au rebranchement de la cité.
		assert marche.portees_lieu(FOURNIL_A)[-1] == "lieu:france"
		marche.reset_prix_cache()
		assert marche.portees_lieu(FOURNIL_A) == ("lieu:fournil_a", "lieu:auxerre")
	finally:
		DOCS["lieu:auxerre"] = CITE_A
		marche.reset_prix_cache()


# ── Visibilité d'une recette portée ────────────────────────────────────────────

def test_une_recette_portee_sort_de_l_index_par_categorie(monde):
	# `lieu_recettes` est la couche NON portée : c'est ce qui empêche la spécialité de fuiter
	# vers toutes les boutiques du métier.
	assert [r["_id"] for r in marche.lieu_recettes("boulangerie")] == ["recette:pain"]


def test_recettes_lieu_ajoute_la_specialite_du_pays_et_de_la_cite(monde):
	assert [r["_id"] for r in marche.recettes_lieu(FOURNIL_A)] == [
		"recette:pain", "recette:quiche", "recette:croissant"]


def test_un_fournil_hors_portee_ne_voit_que_le_generique(monde):
	assert [r["_id"] for r in marche.recettes_lieu(FOURNIL_B)] == ["recette:pain"]


def test_la_specialite_de_cite_ne_deborde_pas_sur_le_pays(monde):
	# Une boutique posée directement sous le pays cuit le croissant, pas la quiche d'Auxerre.
	fournil_pays = {"_id": "lieu:fournil_pays", "type": "lieu",
					"categorie": "boulangerie", "lieu_parent": "lieu:france"}
	assert [r["_id"] for r in marche.recettes_lieu(fournil_pays)] == [
		"recette:pain", "recette:croissant"]


def test_la_portee_compose_avec_la_fusion_des_categories(monde):
	# Le Grand Fournil réunit boulangerie+cuisine ET se trouve sous Auxerre : il doit cuire
	# les deux spécialités, alors qu'aucune ne cite sa propre catégorie.
	assert {r["_id"] for r in marche.recettes_lieu(GRAND_FOURNIL)} == {
		"recette:pain", "recette:croissant", "recette:quiche"}


# ── Besoins, produits, feuilles ────────────────────────────────────────────────

def test_besoins_et_produits_suivent_la_portee(monde):
	assert marche.besoins_categorie("boulangerie") == ["farine"]
	assert marche.besoins_lieu(FOURNIL_B) == ["farine"]
	assert marche.besoins_lieu(FOURNIL_A) == ["farine", "item:Beurre", "item:Creme"]
	assert marche.produits_lieu(FOURNIL_B) == {"item:pain"}
	assert marche.produits_lieu(FOURNIL_A) == {"item:pain", "item:Croissant", "item:Quiche"}


def test_lieu_buys_suit_la_portee(monde):
	beurre = {"_id": "item:Beurre", "sous_categorie": ""}
	assert marche.lieu_buys(FOURNIL_A, beurre) is True
	assert marche.lieu_buys(FOURNIL_B, beurre) is False


def test_la_feuille_d_une_specialite_n_est_livree_que_dans_la_portee(monde):
	# ⚠️ Le cœur de la démonstration : deux fournils du même métier, un seul reçoit le beurre.
	assert marche.appro_leaves_lieu(FOURNIL_B) == ["farine"]
	assert marche.appro_leaves_lieu(FOURNIL_A) == ["farine", "item:Beurre", "item:Creme"]


def test_un_plat_de_terroir_n_est_PAS_une_feuille(monde):
	# `feuilles` reste GLOBAL : le croissant est produit par une recette, fût-elle portée,
	# donc il n'est livré à personne. Sans quoi tout fournil du monde s'en verrait livrer.
	assert "item:Croissant" not in marche._get_marche_map()["feuilles"]
	assert "item:Beurre" in marche._get_marche_map()["feuilles"]


def test_cle_matiere_lieu_prend_l_id_d_un_intrant_porte(monde):
	beurre = {"_id": "item:Beurre", "sous_categorie": "graisse"}
	assert marche.cle_matiere_lieu("boulangerie", beurre, FOURNIL_A) == "item:Beurre"
	assert marche.cle_matiere_lieu("boulangerie", beurre, FOURNIL_B) == "graisse"
	# Sans `lieu_doc`, comportement d'avant : la catégorie seule décide.
	assert marche.cle_matiere_lieu("boulangerie", beurre) == "graisse"


def test_approvisionner_ne_livre_la_matiere_portee_qu_a_la_boutique_concernee(monde, monkeypatch):
	monkeypatch.setattr(marche, "resolve_item_ref", lambda iid: None)   # rien en vitrine
	monkeypatch.setattr(character_stats, "APPRO_DEBIT", {}, raising=False)
	monkeypatch.setattr(character_stats, "APPRO_DEBIT_DEFAUT", 5, raising=False)
	dedans, dehors = dict(FOURNIL_A), dict(FOURNIL_B)
	marche.approvisionner(dedans)
	marche.approvisionner(dehors)
	assert dedans["stock_matieres"] == {"farine": 5, "item:Beurre": 5, "item:Creme": 5}
	assert dehors["stock_matieres"] == {"farine": 5}


# ── Les deux verrous ───────────────────────────────────────────────────────────

def test_aucune_portee_ne_change_RIEN(monkeypatch):
	"""Le test qui protège les 552 recettes déjà en base : sans `lieu_portee`, chaque
	accesseur conscient du lieu rend exactement ce que rend la couche par catégorie."""
	sans_portee = [{k: v for k, v in r.items() if k != "lieu_portee"} for r in RECETTES]
	monkeypatch.setattr(marche, "_all_recettes", lambda: sans_portee)
	monkeypatch.setattr(marche, "get_doc", lambda i: DOCS.get(i))
	monkeypatch.setattr(character_stats, "LIEU_CATEGORIES_FUSION", {}, raising=False)
	marche.reset_prix_cache()
	try:
		for lieu in (FOURNIL_A, FOURNIL_B):
			cat = lieu["categorie"]
			assert marche.besoins_lieu(lieu) == marche.besoins_categorie(cat)
			assert marche.produits_lieu(lieu) == marche.produits_categorie(cat)
			assert marche.appro_leaves_lieu(lieu) == marche.appro_leaves_categorie(cat)
			assert marche.recettes_lieu(lieu) == marche.lieu_recettes(cat)
		# Et les trois recettes sont bien redevenues mondiales.
		assert len(marche.lieu_recettes("boulangerie")) == 3
	finally:
		marche.reset_prix_cache()


def test_le_prix_ne_depend_PAS_du_lieu(monde):
	"""⚠️ La portée dit OÙ L'ON FABRIQUE, jamais COMBIEN ÇA VAUT.

	Si `_get_recipe_map` / `_cout_memo` devenaient scopés, un objet sans recette locale
	retomberait sur son prix poids/rareté au lieu du coût propagé × MARGE_TRANSFO : on
	l'achèterait là où il est produit pour le revendre plus cher là où il ne l'est pas.
	C'est exactement la machine à or que `test_appro_comptoir` verrouille."""
	croissant = {"_id": "item:Croissant", "poids": 0.15, "rarete": "commun",
				 "sous_categorie": "boulangerie"}
	from utils.characters import item_sale_price_cuivre
	# La recette portée est bien dans l'index de PRIX, qui reste global…
	assert marche._get_recipe_map().get("item:Croissant")
	# … et le coût est donc PROPAGÉ (× MARGE_TRANSFO), pas rabattu sur le plancher poids/rareté.
	cout = marche.cout_production_cuivre("item:Croissant", croissant, "item:Croissant")
	assert cout > item_sale_price_cuivre(croissant, "item:Croissant")

	# La fourchette est identique des deux côtés de la portée : c'est ce qui interdit
	# l'arbitrage géographique.
	marche.reset_prix_cache()
	hors = marche.prix_range_cuivre(croissant, "item:Croissant")
	marche.reset_prix_cache()
	marche.recettes_lieu(FOURNIL_A)          # « réchauffe » les index depuis un lieu DANS la portée
	assert marche.prix_range_cuivre(croissant, "item:Croissant") == hors

	# Seule la BANDE de rachat change, et dans le bon sens : le fournil qui le produit le
	# rachète plafonné à son coût de revient ; celui qui ne le produit pas ne peut jamais
	# l'acheter plus cher que la borne haute du premier.
	dedans = marche.params_vente_lieu(FOURNIL_A, croissant, "item:Croissant")
	dehors = marche.params_vente_lieu(FOURNIL_B, croissant, "item:Croissant")
	assert dedans[1] == cout and dedans[0] < dedans[1]
	assert dehors[1] > dedans[1]
