# tests/test_magasins_superieurs.py
#
# Magasins de niveau supérieur : une catégorie de lieu qui en INCLUT d'autres
# (`character_stats.LIEU_CATEGORIES_FUSION`). La fusion est résolue À LA LECTURE des index
# de `utils/marche.py` — aucune recette n'est dupliquée en base — donc ces tests injectent
# leurs propres recettes via `_all_recettes` et leur propre table de fusion, sans DB.
#
# ⚠️ Le test le plus important du fichier est `test_table_vide_ne_change_RIEN` : c'est lui
# qui protège les catégories déjà en base, dont le comportement doit rester au bit près.

import pytest

from models import character_stats
from utils import marche


# ── Fixture : un petit monde de recettes + une table de fusion ──────────────────

RECETTES = [
	# apothicairerie : consomme l'herbe du jardinier + de la graisse (feuille), produit un onguent
	{"_id": "recette:onguent", "type": "recette", "lieu_categorie": "apothicairerie",
	 "objet_final": "onguent", "quantite_produite": 1,
	 "matieres_premieres": [{"item": "item:Herbe", "quantite": 2},
							{"sous_categorie": "graisse", "quantite": 1}]},
	# jardinier : consomme des graines (feuille), produit l'herbe → l'herbe n'est PAS une feuille
	{"_id": "recette:herbe", "type": "recette", "lieu_categorie": "jardinier",
	 "objet_final": "Herbe", "quantite_produite": 3,
	 "matieres_premieres": [{"sous_categorie": "graines", "quantite": 1}]},
	# recette EXCLUSIVE au grand magasin : croise les deux métiers (onguent + graines)
	{"_id": "recette:baume_du_grand_officine", "type": "recette",
	 "lieu_categorie": "grande_apothicairerie", "objet_final": "baume_rare",
	 "quantite_produite": 1,
	 "matieres_premieres": [{"item": "item:onguent", "quantite": 2},
							{"sous_categorie": "graines", "quantite": 1}]},
	# une recette PARTAGÉE par deux métiers réunis (même doc, deux catégories) sert à
	# vérifier le dédoublonnage de `lieu_recettes`.
	{"_id": "recette:ficelle", "type": "recette", "lieu_categorie": "corderie",
	 "objet_final": "ficelle", "quantite_produite": 1,
	 "matieres_premieres": [{"sous_categorie": "chanvre", "quantite": 1}]},
]


@pytest.fixture
def monde(monkeypatch):
	"""Index de marché bâtis sur RECETTES, table de fusion contrôlée. Les caches process
	sont vidés avant ET après : `reset_prix_cache` est la seule barrière entre deux tests."""
	monkeypatch.setattr(marche, "_all_recettes", lambda: list(RECETTES))
	monkeypatch.setattr(character_stats, "LIEU_CATEGORIES_FUSION", {
		"grande_apothicairerie": ["apothicairerie", "jardinier"],
		"grand_ensemble":        ["grande_apothicairerie"],       # inclusion transitive
	}, raising=False)
	marche.reset_prix_cache()
	yield
	marche.reset_prix_cache()


# ── categories_incluses ────────────────────────────────────────────────────────

def test_categorie_sans_fusion_est_seule(monde):
	assert marche.categories_incluses("apothicairerie") == ("apothicairerie",)


def test_categorie_inconnue_est_seule(monde):
	# Une catégorie qui n'a ni recette ni fusion se résout quand même en elle-même : le
	# reste du moteur reçoit alors des unions vides, exactement comme avant.
	assert marche.categories_incluses("auberge") == ("auberge",)


def test_categorie_vide_ne_resout_rien(monde):
	assert marche.categories_incluses("") == ()
	assert marche.categories_incluses(None) == ()


def test_fusion_simple_categorie_propre_en_tete(monde):
	# L'ordre compte : plusieurs appelants départagent les ex æquo par « le premier gagne »,
	# et c'est le métier du lieu qui doit gagner.
	assert marche.categories_incluses("grande_apothicairerie") == (
		"grande_apothicairerie", "apothicairerie", "jardinier")


def test_fusion_transitive(monde):
	assert marche.categories_incluses("grand_ensemble") == (
		"grand_ensemble", "grande_apothicairerie", "apothicairerie", "jardinier")


def test_inclusion_circulaire_ne_boucle_pas(monkeypatch):
	# La table est éditable à chaud depuis /admin : un cycle saisi à la main ne doit pas
	# faire boucler le premier tick venu.
	monkeypatch.setattr(marche, "_all_recettes", lambda: [])
	monkeypatch.setattr(character_stats, "LIEU_CATEGORIES_FUSION",
						{"a": ["b"], "b": ["c"], "c": ["a"]}, raising=False)
	marche.reset_prix_cache()
	try:
		assert marche.categories_incluses("a") == ("a", "b", "c")
		assert marche.categories_incluses("b") == ("b", "c", "a")
	finally:
		marche.reset_prix_cache()


def test_categorie_qui_s_inclut_elle_meme(monde, monkeypatch):
	monkeypatch.setattr(character_stats, "LIEU_CATEGORIES_FUSION",
						{"x": ["x", "apothicairerie"]}, raising=False)
	marche.reset_prix_cache()
	assert marche.categories_incluses("x") == ("x", "apothicairerie")


# ── Union des index dérivés ────────────────────────────────────────────────────

def test_besoins_unionnent_les_metiers_reunis(monde):
	assert marche.besoins_categorie("apothicairerie") == ["graisse", "item:Herbe"]
	assert marche.besoins_categorie("jardinier") == ["graines"]
	# La grande maison achète les intrants des deux métiers ET les siens propres.
	assert marche.besoins_categorie("grande_apothicairerie") == [
		"graines", "graisse", "item:Herbe", "item:onguent"]


def test_produits_unionnent_les_metiers_reunis(monde):
	assert marche.produits_categorie("grande_apothicairerie") == {
		"item:onguent", "item:Herbe", "item:baume_rare"}


def test_feuilles_unionnent_les_metiers_reunis(monde):
	# ⚠️ `feuilles` est GLOBAL (« intrant qu'aucune recette du jeu ne produit »), pas par
	# catégorie : `item:Herbe` est produite par le jardinier, donc elle n'est livrée à
	# personne — l'apothicairerie de base doit l'acheter au joueur ou à un autre étal.
	# Seule l'UNION des besoins change avec la fusion.
	assert marche.appro_leaves_categorie("apothicairerie") == ["graisse"]
	assert marche.appro_leaves_categorie("jardinier") == ["graines"]
	assert marche.appro_leaves_categorie("grande_apothicairerie") == ["graines", "graisse"]


def test_lieu_recettes_unionne_categorie_propre_en_tete(monde):
	ids = [r["_id"] for r in marche.lieu_recettes("grande_apothicairerie")]
	assert ids == ["recette:baume_du_grand_officine", "recette:onguent", "recette:herbe"]


def test_lieu_recettes_dedoublonne_une_recette_partagee(monkeypatch):
	# Deux métiers réunis peuvent citer la MÊME recette : elle ne doit être cuite qu'une fois
	# (sinon le tirage pondéré de `_executer_production_batch` la favorise en silence).
	partagee = dict(RECETTES[3])
	monkeypatch.setattr(marche, "_all_recettes",
						lambda: [partagee, dict(partagee, lieu_categorie="boyauderie")])
	monkeypatch.setattr(character_stats, "LIEU_CATEGORIES_FUSION",
						{"grande_corderie": ["corderie", "boyauderie"]}, raising=False)
	marche.reset_prix_cache()
	try:
		assert [r["_id"] for r in marche.lieu_recettes("grande_corderie")] == ["recette:ficelle"]
	finally:
		marche.reset_prix_cache()


# ── Prédicats dérivés (aucun site d'appel n'a changé) ──────────────────────────

def test_lieu_buys_suit_la_fusion(monde):
	grand = {"categorie": "grande_apothicairerie"}
	base = {"categorie": "apothicairerie"}
	graines = {"_id": "item:Graines_de_souci", "sous_categorie": "graines"}
	# La boutique de base n'achète pas les graines ; la grande maison, si (le jardinier y est).
	assert marche.lieu_buys(base, graines) is False
	assert marche.lieu_buys(grand, graines) is True


def test_cle_matiere_lieu_prend_l_id_d_une_recette_item_ref_incluse(monde):
	# `item:Herbe` est référencée NOMMÉMENT par une recette d'apothicairerie : dans le grand
	# magasin elle doit entrer sous son id, pas sous sa sous-catégorie — sinon la recette
	# héritée ne retrouve jamais sa matière.
	herbe = {"_id": "item:Herbe", "sous_categorie": "herbe"}
	assert marche.cle_matiere_lieu("grande_apothicairerie", herbe) == "item:Herbe"
	assert marche.cle_matiere_lieu("jardinier", herbe) == "herbe"


def test_produit_d_un_metier_reuni_est_rachete_sur_la_bande_plafonnee(monde):
	# ⚠️ Sans ça la fusion rouvrirait la machine à or que `RACHAT_FACTEUR` bouche : un bien
	# produit par un métier réuni doit être racheté ≤ son coût de revient, pas sur la
	# fourchette pleine. Cf. tests/test_appro_comptoir.py::test_aucun_arbitrage_…
	grand = {"categorie": "grande_apothicairerie", "stock_vente": [], "stock_matieres": {}}
	onguent = {"_id": "item:onguent", "sous_categorie": "", "poids": 0.5, "rarete": "commun"}
	assert marche.lieu_produit(grand, onguent) is True
	pmin_vente, pmax_vente, _stock = marche.params_vente_lieu(grand, onguent, "item:onguent")
	pmin, _pmax = marche.prix_range_cuivre(onguent, "item:onguent")
	assert pmax_vente == pmin
	assert pmin_vente == max(1, round(pmin * float(character_stats.RACHAT_FACTEUR)))


# ── Non-régression et réglage à chaud ──────────────────────────────────────────

def test_table_vide_ne_change_RIEN(monkeypatch):
	"""Le test qui protège les catégories déjà en base : sans fusion, chaque accesseur rend
	exactement ce que rendait l'index brut."""
	monkeypatch.setattr(marche, "_all_recettes", lambda: list(RECETTES))
	monkeypatch.setattr(character_stats, "LIEU_CATEGORIES_FUSION", {}, raising=False)
	marche.reset_prix_cache()
	try:
		brut = marche._get_marche_map()
		for cat in ("apothicairerie", "jardinier", "corderie", "grande_apothicairerie"):
			assert marche.besoins_categorie(cat) == sorted(brut["besoins"].get(cat, set()))
			assert marche.produits_categorie(cat) == brut["produits"].get(cat, set())
			assert marche.appro_leaves_categorie(cat) == sorted(
				brut["besoins"].get(cat, set()) & brut["feuilles"])
			assert [r["_id"] for r in marche.lieu_recettes(cat)] == [
				r["_id"] for r in RECETTES if r["lieu_categorie"] == cat]
	finally:
		marche.reset_prix_cache()


def test_reset_prix_cache_vide_le_memo_de_fusion(monkeypatch):
	"""Régler la table depuis /admin doit prendre effet au rechargement — le mémo de fusion
	est vidé par `reset_prix_cache`, appelé par /admin/world_variables/reload."""
	monkeypatch.setattr(marche, "_all_recettes", lambda: list(RECETTES))
	monkeypatch.setattr(character_stats, "LIEU_CATEGORIES_FUSION", {}, raising=False)
	marche.reset_prix_cache()
	try:
		assert marche.categories_incluses("grande_apothicairerie") == ("grande_apothicairerie",)
		assert marche.lieu_recettes("grande_apothicairerie") == [RECETTES[2]]

		character_stats.LIEU_CATEGORIES_FUSION["grande_apothicairerie"] = ["apothicairerie"]
		# Sans le vidage, la valeur mémoïsée survivrait au réglage.
		assert marche.categories_incluses("grande_apothicairerie") == ("grande_apothicairerie",)
		marche.reset_prix_cache()
		assert marche.categories_incluses("grande_apothicairerie") == (
			"grande_apothicairerie", "apothicairerie")
		assert len(marche.lieu_recettes("grande_apothicairerie")) == 2
	finally:
		marche.reset_prix_cache()


# ── La table livrée ────────────────────────────────────────────────────────────

def test_la_table_livree_ne_reference_que_des_categories_a_recettes():
	"""Chaque catégorie INCLUSE par la table du code doit être un métier qui existe — une
	faute de frappe y serait muette (union vide, le grand magasin perd le métier en silence).
	Contrôlé contre la liste des catégories du jeu, pas contre la base."""
	metiers = {
		"apothicairerie", "armurerie", "atelier_d_artisan", "atelier_de_cirier",
		"atelier_de_l_empenneur", "bijouterie", "boucherie", "boulangerie", "bourrellerie",
		"boyauderie", "brosserie", "corderie", "cordonnerie", "cuisine", "fletcher", "fumoir",
		"jardinier", "laboratoire_d_alchimie", "lutherie", "maroquinerie", "necromancie",
		"plumasserie", "salaison", "savonnerie", "scriptorium", "tabletterie", "tannerie",
		"taxidermie", "tissage",
	}
	table = character_stats.CODE_DEFAULTS["LIEU_CATEGORIES_FUSION"]
	assert table, "la table de fusion livrée ne doit pas être vide"
	for grande, incluses in table.items():
		assert grande not in metiers, f"{grande} écrase un métier de base"
		assert len(incluses) >= 2, f"{grande} ne réunit pas au moins deux métiers"
		assert len(set(incluses)) == len(incluses), f"{grande} cite deux fois le même métier"
		for metier in incluses:
			assert metier in metiers, f"{grande} inclut une catégorie inconnue : {metier}"
