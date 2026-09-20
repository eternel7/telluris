"""Tests purs des commandes auprès d'un artisan (`utils/commande.py`).

Le pivot du fichier — `test_artisan_prend_commande_mais_ne_fabrique_pas_sur_mesure` — verrouille
la distinction qui porte tout le système : **prendre une commande** est dérivé des recettes et
ouvert à tout atelier ; **fabriquer sur mesure** est réservé aux grandes maisons. Les confondre
laisserait n'importe quelle échoppe de quartier créer des docs `item:`/`recette:` permanents.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from utils import commande, marche  # noqa: E402
from models import character_stats  # noqa: E402


CATEGORIE = "armurerie_de_test"

RECETTE = {
	"_id": "recette:test_epee",
	"type": "recette",
	"lieu_categorie": CATEGORIE,
	"objet_final": "Epee_longue",
	"quantite_produite": 1,
	"matieres_premieres": [{"sous_categorie": "fer_de_test", "quantite": 2},
						   {"item": "item:manche_de_test", "quantite": 1}],
}

_DB = {
	"item:Epee_longue": {"_id": "item:Epee_longue", "nom": "Épée longue", "icon": "⚔️",
						 "categorie": "arme", "sous_categorie": "", "poids": 2.0},
	"item:fer": {"_id": "item:fer", "nom": "Lingot de fer", "categorie": "metal",
				 "sous_categorie": "fer_de_test", "poids": 3.0},
	"item:manche_de_test": {"_id": "item:manche_de_test", "nom": "Manche",
							"categorie": "composant", "sous_categorie": "manche", "poids": 0.5},
	"item:cire": {"_id": "item:cire", "nom": "Cire", "categorie": "composant",
				  "sous_categorie": "cire", "poids": 0.3},
}


def _get_doc(doc_id):
	return _DB.get(doc_id)


ARTISAN = {"_id": "lieu:forge_du_coin", "categorie": CATEGORIE, "label": "La Forge du Coin"}
GRANDE_MAISON = {"_id": "lieu:grand_arsenal_de_lutece", "categorie": "grand_arsenal",
				 "label": "Le Grand Arsenal"}
ARTISAN_PROMU = {"_id": "lieu:forge_royale", "categorie": CATEGORIE, "tags": ["sur_mesure"]}
ECHOPPE = {"_id": "lieu:comptoir", "categorie": "categorie_sans_recette"}


@pytest.fixture
def index_semes(monkeypatch):
	"""Une seule recette dans le monde. `reset_prix_cache()` des deux côtés : ces index sont
	des caches de PROCESS, les laisser semés ferait mentir les tests suivants."""
	marche.reset_prix_cache()
	monkeypatch.setattr(marche, "_recettes_all", [RECETTE])
	yield
	marche.reset_prix_cache()


# ── Les deux capacités, et leur indépendance ────────────────────────────────────

def test_artisan_ordinaire_prend_commande(index_semes):
	assert commande.lieu_prend_commandes(ARTISAN, _get_doc) is True


def test_echoppe_sans_recette_ne_prend_aucune_commande(index_semes):
	assert commande.lieu_prend_commandes(ECHOPPE, _get_doc) is False
	assert commande.catalogue_commandable(ECHOPPE, _get_doc) == []


def test_artisan_prend_commande_mais_ne_fabrique_pas_sur_mesure(index_semes):
	# LE test pivot : les deux capacités sont indépendantes.
	assert commande.lieu_prend_commandes(ARTISAN, _get_doc) is True
	assert commande.lieu_fabrique_sur_mesure(ARTISAN) is False


def test_grande_maison_fabrique_sur_mesure(index_semes):
	assert commande.lieu_fabrique_sur_mesure(GRANDE_MAISON) is True


def test_tag_promeut_un_artisan(index_semes):
	# Le OU du prédicat : ouvrir la capacité par la donnée seule, sans changer de catégorie.
	assert commande.lieu_fabrique_sur_mesure(ARTISAN_PROMU) is True


def test_categories_accordantes_relues_et_non_recopiees():
	# Ajouter une grande maison à la table de fusion doit suffire : aucune liste en dur ici.
	for cat in character_stats.LIEU_CATEGORIES_FUSION:
		assert commande.lieu_fabrique_sur_mesure({"categorie": cat}) is True


def test_lieu_absent_ne_fait_rien_lever():
	assert commande.lieu_prend_commandes(None) is False
	assert commande.lieu_fabrique_sur_mesure(None) is False


# ── Le catalogue et les matières acceptées ──────────────────────────────────────

def test_catalogue_derive_des_recettes(index_semes):
	assert commande.catalogue_commandable(ARTISAN, _get_doc) == ["item:Epee_longue"]


# ── Matières et demi-produits écartés du catalogue ─────────────────────────────

# Une recette du même métier qui produit un DEMI-PRODUIT (catégorie `composant`), comme la
# hampe ou le cuir que l'Arsenal de Lutèce proposait à côté de ses armes.
RECETTE_HAMPE = {
	"_id": "recette:test_hampe",
	"type": "recette",
	"lieu_categorie": CATEGORIE,
	"objet_final": "hampe_de_test",
	"quantite_produite": 1,
	"matieres_premieres": [{"sous_categorie": "rondin_de_test", "quantite": 1}],
}
HAMPE = {"_id": "item:hampe_de_test", "nom": "Hampe", "categorie": "composant",
		 "sous_categorie": "hampe", "slots": [], "poids": 1.0}


@pytest.fixture
def index_avec_demi_produit(monkeypatch):
	marche.reset_prix_cache()
	monkeypatch.setattr(marche, "_recettes_all", [RECETTE, RECETTE_HAMPE])
	yield
	marche.reset_prix_cache()


def _db_avec(*docs):
	base = dict(_DB)
	base.update({d["_id"]: d for d in docs})
	return base.get


def test_un_demi_produit_nentre_pas_au_catalogue(index_avec_demi_produit):
	"""Le défaut constaté en jeu : « Hampe », « Cuir », « Acier plissé » proposés à la
	commande au même titre qu'une épée."""
	get = _db_avec(HAMPE)
	assert marche.produits_lieu(ARTISAN) == {"item:Epee_longue", "item:hampe_de_test"}
	assert commande.catalogue_commandable(ARTISAN, get) == ["item:Epee_longue"]


def test_le_tag_commandable_deroge(index_avec_demi_produit):
	get = _db_avec(dict(HAMPE, tags=[marche.TAG_COMMANDABLE]))
	assert commande.catalogue_commandable(ARTISAN, get) == \
		["item:Epee_longue", "item:hampe_de_test"]


def test_une_piece_derogee_reste_non_personnalisable(index_avec_demi_produit):
	"""⚠️ Le plancher du système : le tag rouvre la COMMANDE, jamais la PERSONNALISATION.
	Les confondre laisserait façonner un lingot sur mesure."""
	deroge = dict(HAMPE, tags=[marche.TAG_COMMANDABLE])
	assert marche.item_commandable(deroge["_id"], deroge) is True
	assert marche.est_intermediaire(deroge) is True          # le fait brut ne bouge pas


def test_une_arme_reste_personnalisable():
	assert marche.est_intermediaire(_DB["item:Epee_longue"]) is False


def test_un_lieu_qui_ne_produit_que_des_matieres_ne_prend_pas_commande(monkeypatch):
	"""Onze boucheries et quatre tanneries du dump sont dans ce cas : seize recettes, et rien
	que des matières au bout. Leur section Commande n'aurait rien à montrer."""
	marche.reset_prix_cache()
	monkeypatch.setattr(marche, "_recettes_all", [RECETTE_HAMPE])
	get = _db_avec(HAMPE)
	assert marche.recettes_lieu(ARTISAN)              # il A des recettes…
	assert commande.catalogue_commandable(ARTISAN, get) == []
	assert commande.lieu_prend_commandes(ARTISAN, get) is False   # …et ne prend rien
	marche.reset_prix_cache()


def test_categories_intermediaires_relues_et_non_recopiees(monkeypatch):
	# Retirer `composant` de la variable de monde doit suffire à rouvrir le catalogue.
	monkeypatch.setattr(character_stats, "CATEGORIES_INTERMEDIAIRES", {"metal"})
	assert marche.est_intermediaire(HAMPE) is False
	monkeypatch.setattr(character_stats, "CATEGORIES_INTERMEDIAIRES", {"composant", "metal"})
	assert marche.est_intermediaire(HAMPE) is True


def test_le_memo_est_vide_par_reset_prix_cache(index_avec_demi_produit):
	"""⚠️ Sans ce vidage, poser le tag `commandable` depuis /admin resterait sans effet
	jusqu'au redémarrage du process — le symptôme le plus coûteux à diagnostiquer."""
	assert marche.item_commandable(HAMPE["_id"], HAMPE) is False
	marche.reset_prix_cache()
	deroge = dict(HAMPE, tags=[marche.TAG_COMMANDABLE])
	assert marche.item_commandable(deroge["_id"], deroge) is True


def test_item_introuvable_nentre_pas_au_catalogue(index_avec_demi_produit):
	# Il serait de toute façon sauté au rendu (`resolve_item_ref` ne le résout pas) : le
	# compter rendrait `lieu_prend_commandes` vrai pour un catalogue qui s'affiche vide.
	assert commande.catalogue_commandable(ARTISAN, lambda i: None) == []


def test_recette_pour_retrouve_la_recette(index_semes):
	assert commande.recette_pour(ARTISAN, "item:Epee_longue")["_id"] == RECETTE["_id"]
	assert commande.recette_pour(ARTISAN, "item:Inconnu") is None


def test_matiere_du_metier_acceptee(index_semes):
	assert commande.matiere_acceptee(ARTISAN, _DB["item:fer"]) is True
	assert commande.matiere_acceptee(ARTISAN, _DB["item:manche_de_test"]) is True


def test_matiere_hors_metier_refusee(index_semes):
	# Un armurier refuse la cire : §10 du cahier des charges.
	assert commande.matiere_acceptee(ARTISAN, _DB["item:cire"]) is False


# ── Les trois cas de matières (§7) ──────────────────────────────────────────────

def _prix_fn(item_id, item_doc, en_rayon):
	return 10


def test_cas_a_le_joueur_fournit_tout():
	joueur = {"_id": "character:j", "inventaire": ["item:fer", "item:fer", "item:manche_de_test"]}
	res = commande.sourcer(marche.recette_matieres(RECETTE), [joueur], ARTISAN, _get_doc, _prix_fn)
	assert len(res["fournies"]) == 3
	assert res["achetees"] == [] and res["manquantes"] == []
	assert res["cout_matieres"] == 0


# ── Appariement d'une clé de recette (le piège `item:argent`) ───────────────────

def test_cle_resolue_par_matiere_item_id():
	"""⚠️ Le marché résout une clé sous-catégorie en `item:<clé>` sans relire la
	`sous_categorie` du doc obtenu, et les deux DIVERGENT en base : `item:argent` porte
	`sous_categorie: "metaux_precieux"` alors que les recettes d'armurerie le désignent par
	la clé `argent`. Sans ce troisième appariement, un joueur portant un lingot d'argent ne
	pourrait pas le fournir, et aucun artisan n'accepterait l'argent en sur-mesure."""
	argent = {"_id": "item:argent", "nom": "Lingot d'argent",
			  "categorie": "metal", "sous_categorie": "metaux_precieux"}
	assert commande.correspond("item:argent", argent, "argent") is True
	# Les deux appariements directs restent vrais.
	assert commande.correspond("item:argent", argent, "item:argent") is True
	assert commande.correspond("item:argent", argent, "metaux_precieux") is True
	assert commande.correspond("item:argent", argent, "cuir") is False


def test_le_sac_reconnait_une_cle_resolue():
	db = dict(_DB, **{"item:argent": {"_id": "item:argent", "nom": "Lingot d'argent",
									  "categorie": "metal", "sous_categorie": "metaux_precieux"}})
	joueur = {"_id": "character:j", "inventaire": ["item:argent"]}
	trouves, manquants = commande.emplacements_fournis([("argent", 1)], [joueur], db.get)
	assert manquants == []
	assert trouves[0]["item_id"] == "item:argent"


def test_le_rayon_reconnait_une_cle_resolue():
	db = dict(_DB, **{"item:argent": {"_id": "item:argent", "nom": "Lingot d'argent",
									  "categorie": "metal", "sous_categorie": "metaux_precieux"}})
	lieu = dict(ARTISAN, stock_vente=[{"item_id": "item:argent", "qty": 4}])
	assert commande.achetable_sur_place(lieu, "argent", db.get) == ("item:argent", 4)


def test_cas_b_lartisan_vend_ce_qui_manque():
	joueur = {"_id": "character:j", "inventaire": []}
	lieu = dict(ARTISAN, stock_vente=[{"item_id": "item:fer", "qty": 5},
									  {"item_id": "item:manche_de_test", "qty": 2}])
	res = commande.sourcer(marche.recette_matieres(RECETTE), [joueur], lieu, _get_doc, _prix_fn)
	assert res["fournies"] == [] and res["manquantes"] == []
	assert res["cout_matieres"] == 30          # 2 fers + 1 manche, à 10 cu
	assert {a["item_id"] for a in res["achetees"]} == {"item:fer", "item:manche_de_test"}


def test_cas_c_matiere_introuvable_ne_fait_pas_echouer():
	joueur = {"_id": "character:j", "inventaire": []}
	res = commande.sourcer(marche.recette_matieres(RECETTE), [joueur], ARTISAN, _get_doc, _prix_fn)
	assert len(res["manquantes"]) == 2
	# La commande naîtra en attente, pas en échec.
	c = commande.nouvelle_commande(ARTISAN, "item:Epee_longue", {}, now=1000,
								   manquantes=res["manquantes"])
	assert c["statut"] == commande.ETAT_ATTENTE_MATERIAUX


def test_mixte_le_joueur_complete_ce_quil_a():
	joueur = {"_id": "character:j", "inventaire": ["item:fer"]}
	lieu = dict(ARTISAN, stock_vente=[{"item_id": "item:fer", "qty": 5},
									  {"item_id": "item:manche_de_test", "qty": 2}])
	res = commande.sourcer(marche.recette_matieres(RECETTE), [joueur], lieu, _get_doc, _prix_fn)
	assert len(res["fournies"]) == 1
	# Un seul fer manquant (pas deux) + le manche.
	achetes = {a["item_id"]: a["quantite"] for a in res["achetees"]}
	assert achetes == {"item:fer": 1, "item:manche_de_test": 1}


def test_matiere_du_sac_dun_compagnon():
	# Une bête de somme qui porte le lingot doit pouvoir le fournir sans transfert préalable.
	joueur = {"_id": "character:j", "inventaire": []}
	mule = {"_id": "monture:mule", "inventaire": ["item:fer", "item:fer", "item:manche_de_test"]}
	res = commande.sourcer(marche.recette_matieres(RECETTE), [joueur, mule], ARTISAN, _get_doc, _prix_fn)
	assert res["manquantes"] == []
	assert all(t["porteur"] is mule for t in res["fournies"])


def test_un_exemplaire_ne_compte_jamais_deux_fois():
	# La recette demande DEUX fers ; le joueur n'en a qu'un.
	joueur = {"_id": "character:j", "inventaire": ["item:fer", "item:manche_de_test"]}
	res = commande.sourcer(marche.recette_matieres(RECETTE), [joueur], ARTISAN, _get_doc, _prix_fn)
	assert res["manquantes"] == [{"cle": "fer_de_test", "quantite": 1}]


def test_reserve_datelier_jamais_VENDUE():
	"""⚠️ La réserve de l'atelier n'est PAS le comptoir. Rien ne fait jamais passer une
	matière de l'une à l'autre : la VENDRE casserait l'invariante « la vitrine est regarnie
	jusqu'au stock_cible et jamais au-dessus » (`tests/test_appro_comptoir.py`)."""
	lieu = dict(ARTISAN, stock_matieres={"fer_de_test": 99, "item:manche_de_test": 99},
				stock_vente=[])
	joueur = {"_id": "character:j", "inventaire": []}
	res = commande.sourcer(marche.recette_matieres(RECETTE), [joueur], lieu, _get_doc, _prix_fn)
	assert len(res["manquantes"]) == 2
	assert res["achetees"] == []


def test_reserve_datelier_CONSOMMEE_pour_une_commande_de_catalogue():
	"""…mais l'artisan la CONSOMME pour fabriquer, exactement comme le ferait son tick de
	production. Sans cela, 65 % du catalogue du monde naîtrait `en_attente_materiaux` : les
	intermédiaires (cuir, tendons, os…) vivent dans la réserve, pas en vitrine."""
	lieu = dict(ARTISAN, stock_matieres={"fer_de_test": 99, "item:manche_de_test": 99},
				stock_vente=[])
	joueur = {"_id": "character:j", "inventaire": []}
	res = commande.sourcer(marche.recette_matieres(RECETTE), [joueur], lieu, _get_doc,
						   atelier=True)
	assert res["manquantes"] == []
	assert res["cout_matieres"] == 0          # déjà compris dans le prix de la pièce
	assert {a["cle"]: a["reserve"] for a in res["atelier"]} == \
		{"fer_de_test": 2, "item:manche_de_test": 1}


def test_consommation_de_la_reserve_puis_du_rayon():
	lieu = dict(ARTISAN, stock_matieres={"fer_de_test": 1},
				stock_vente=[{"item_id": "item:fer", "qty": 3}])
	joueur = {"_id": "character:j", "inventaire": ["item:manche_de_test"]}
	res = commande.sourcer(marche.recette_matieres(RECETTE), [joueur], lieu, _get_doc,
						   atelier=True)
	assert res["manquantes"] == []
	part = next(a for a in res["atelier"] if a["cle"] == "fer_de_test")
	assert (part["reserve"], part["rayon"]) == (1, 1)   # réserve d'abord, rayon ensuite
	commande.consommer_atelier(lieu, res["atelier"])
	assert "fer_de_test" not in lieu["stock_matieres"]  # clé vidée, pas laissée à 0
	assert lieu["stock_vente"] == [{"item_id": "item:fer", "qty": 2}]


def test_rayon_insuffisant_compte_comme_manquant():
	lieu = dict(ARTISAN, stock_vente=[{"item_id": "item:fer", "qty": 1}])
	joueur = {"_id": "character:j", "inventaire": ["item:manche_de_test"]}
	res = commande.sourcer(marche.recette_matieres(RECETTE), [joueur], lieu, _get_doc, _prix_fn)
	assert res["achetees"] == []
	assert res["manquantes"] == [{"cle": "fer_de_test", "quantite": 2}]


# ── Prélèvement ─────────────────────────────────────────────────────────────────

def test_retrait_du_plus_grand_index_au_plus_petit():
	joueur = {"_id": "character:j",
			  "inventaire": ["item:fer", "item:cire", "item:fer", "item:manche_de_test"]}
	trouves, manquants = commande.emplacements_fournis(
		marche.recette_matieres(RECETTE), [joueur], _get_doc)
	assert manquants == []
	commande.retirer_fournitures(trouves)
	# Seule la cire reste : les index décalés n'ont pas fait retirer le mauvais objet.
	assert joueur["inventaire"] == ["item:cire"]


def test_retrait_reparti_sur_deux_porteurs():
	joueur = {"_id": "character:j", "inventaire": ["item:fer", "item:cire"]}
	mule = {"_id": "monture:mule", "inventaire": ["item:fer", "item:manche_de_test"]}
	trouves, manquants = commande.emplacements_fournis(
		marche.recette_matieres(RECETTE), [joueur, mule], _get_doc)
	assert manquants == []
	commande.retirer_fournitures(trouves)
	assert joueur["inventaire"] == ["item:cire"]
	assert mule["inventaire"] == []


def test_emplacements_retenus_partages_entre_deux_passes():
	"""⚠️ Le router source en DEUX passes (ingrédients de la recette, puis matières sur
	mesure) et leur fait partager `retenus`. Sans ce partage, le même lingot serait crédité
	comme ingrédient ET fourni gratuitement comme matière sur mesure — le joueur paierait
	une fois pour deux usages du même objet."""
	joueur = {"_id": "character:j", "inventaire": ["item:fer"]}
	retenus = set()
	passe1, _ = commande.emplacements_fournis([("fer_de_test", 1)], [joueur], _get_doc, retenus)
	passe2, manquants2 = commande.emplacements_fournis([("fer_de_test", 1)], [joueur], _get_doc, retenus)
	assert len(passe1) == 1
	assert passe2 == []
	assert manquants2 == [{"cle": "fer_de_test", "quantite": 1}]


def test_sans_partage_chaque_passe_repart_a_zero():
	# Le comportement par défaut (un seul appel) reste celui d'avant : `retenus` local.
	joueur = {"_id": "character:j", "inventaire": ["item:fer"]}
	a, _ = commande.emplacements_fournis([("fer_de_test", 1)], [joueur], _get_doc)
	b, _ = commande.emplacements_fournis([("fer_de_test", 1)], [joueur], _get_doc)
	assert len(a) == len(b) == 1


def test_retrait_du_rayon_purge_les_lignes_vides():
	lieu = dict(ARTISAN, stock_vente=[{"item_id": "item:fer", "qty": 2},
									  {"item_id": "item:manche_de_test", "qty": 5}])
	commande.retirer_du_rayon(lieu, [{"item_id": "item:fer", "quantite": 2}])
	assert lieu["stock_vente"] == [{"item_id": "item:manche_de_test", "qty": 5}]


# ── Devis (§9) ──────────────────────────────────────────────────────────────────

def test_devis_somme_bien_ses_termes():
	d = commande.devis(prix_base=100, cout_matieres=30, matieres_distinctes=1)
	assert d["cout_fabrication"] == int(round(100 * character_stats.COMMANDE_FACON_PART))
	assert d["supplement_complexite"] == 0       # une seule matière : pas de surcoût
	assert d["total"] == d["prix_base"] + d["cout_matieres"] + d["cout_fabrication"]


def test_supplement_court_a_partir_de_la_deuxieme_matiere():
	simple = commande.devis(100, 0, matieres_distinctes=1)
	double = commande.devis(100, 0, matieres_distinctes=2)
	assert double["supplement_complexite"] > simple["supplement_complexite"] == 0


def test_commander_ne_coute_jamais_le_prix_plus_les_ingredients():
	"""⚠️ Le piège économique du système. Les ingrédients de la recette sont DÉJÀ dans
	`prix_base` (coût de revient propagé × MARGE_TRANSFO) : les refacturer rendrait la
	commande plus chère que le même objet pris en rayon, et personne ne commanderait rien."""
	rayon = 100
	commandee = commande.devis(prix_base=rayon)["total"]
	# La commande coûte la façon en plus, et rien d'autre : pas de seconde facturation.
	assert commandee == rayon + int(round(rayon * character_stats.COMMANDE_FACON_PART))


def test_matieres_apportees_valent_une_remise():
	sans = commande.devis(100, credit_matieres=0)
	avec = commande.devis(100, credit_matieres=40)
	assert avec["credit_matieres"] == 40
	assert avec["total"] == sans["total"] - 40
	# …mais la façon reste due : l'artisan vend son temps, pas seulement sa matière.
	assert avec["cout_fabrication"] == sans["cout_fabrication"] > 0


def test_remise_plafonnee_au_prix_de_la_piece():
	"""Sans ce plafond : acheter du fer au comptoir, le rapporter comme matière, et repartir
	avec l'épée pour une pièce de cuivre."""
	d = commande.devis(100, credit_matieres=10 ** 6)
	assert d["credit_matieres"] == 100
	assert d["total"] == d["cout_fabrication"]


def test_total_jamais_nul():
	assert commande.devis(0, 0, 0, 0)["total"] >= 1


def test_matieres_sur_mesure_facturees_en_supplement():
	# Elles ne sont dans le prix d'aucun objet de base : aucune recette ne les cite.
	sans = commande.devis(100, cout_matieres=0, matieres_distinctes=1)
	avec = commande.devis(100, cout_matieres=25, matieres_distinctes=1)
	assert avec["total"] == sans["total"] + 25


def test_detail_du_calcul_conserve_sur_la_commande():
	d = commande.devis(100, 30, 10, 2)
	c = commande.nouvelle_commande(ARTISAN, "item:Epee_longue", d, now=1000)
	assert c["devis"] == d
	assert c["paye"] == d["total"]


# ── Cycle de vie (§8) ───────────────────────────────────────────────────────────

def _payee(now=1000):
	return commande.nouvelle_commande(ARTISAN, "item:Epee_longue", {"total": 50}, now=now)


def test_commande_complete_nait_payee():
	assert _payee()["statut"] == commande.ETAT_PAYEE


def test_statut_en_fabrication_puis_terminee(monkeypatch):
	monkeypatch.setattr(character_stats, "COMMANDE_DELAI_SECONDES", 600)
	c = _payee(now=1000)
	assert commande.statut(c, 1000) == commande.ETAT_EN_FABRICATION
	assert commande.statut(c, 1599) == commande.ETAT_EN_FABRICATION
	assert commande.statut(c, 1600) == commande.ETAT_TERMINEE


def test_statut_expire_passe_la_peremption(monkeypatch):
	monkeypatch.setattr(character_stats, "COMMANDE_DELAI_SECONDES", 0)
	monkeypatch.setattr(character_stats, "COMMANDE_PEREMPTION_SECONDES", 100)
	c = _payee(now=1000)
	assert commande.statut(c, 1099) == commande.ETAT_TERMINEE
	assert commande.statut(c, 1100) == commande.ETAT_EXPIREE


def test_delai_nul_fabrique_immediatement(monkeypatch):
	monkeypatch.setattr(character_stats, "COMMANDE_DELAI_SECONDES", 0)
	assert commande.statut(_payee(now=1000), 1000) == commande.ETAT_TERMINEE


def test_etats_figes_rendus_tels_quels():
	for etat in (commande.ETAT_LIVREE, commande.ETAT_ANNULEE,
				 commande.ETAT_IMPOSSIBLE, commande.ETAT_ATTENTE_MATERIAUX):
		c = dict(_payee(now=1000), statut=etat)
		assert commande.statut(c, 10 ** 9) == etat


def test_retirable_seulement_chez_le_bon_artisan(monkeypatch):
	monkeypatch.setattr(character_stats, "COMMANDE_DELAI_SECONDES", 0)
	c = _payee(now=1000)
	assert commande.retirable(c, "lieu:forge_du_coin", 1000) is True
	assert commande.retirable(c, "lieu:grand_arsenal_de_lutece", 1000) is False


def test_une_commande_livree_nest_plus_retirable(monkeypatch):
	monkeypatch.setattr(character_stats, "COMMANDE_DELAI_SECONDES", 0)
	c = _payee(now=1000)
	commande.marquer(c, commande.ETAT_LIVREE)
	assert commande.retirable(c, "lieu:forge_du_coin", 1000) is False


def test_double_retrait_impossible(monkeypatch):
	# L'invariante du §8 : une commande ne se fabrique jamais deux fois. Le passage en
	# `livree` et l'ajout à l'inventaire tiennent dans la même mutation, donc le même save.
	monkeypatch.setattr(character_stats, "COMMANDE_DELAI_SECONDES", 0)
	perso = {"inventaire": [], "commandes": [_payee(now=1000)]}
	c = perso["commandes"][0]
	assert commande.retirable(c, "lieu:forge_du_coin", 1000)
	perso["inventaire"].append(commande.ref_livree(c))
	commande.marquer(c, commande.ETAT_LIVREE)
	assert commande.retirable(c, "lieu:forge_du_coin", 1000) is False
	assert len(perso["inventaire"]) == 1


def test_reference_livree_porte_sa_tracabilite():
	c = commande.nouvelle_commande(ARTISAN, "item:Epee_longue", {"total": 50}, now=1234,
								   poids=2.2)
	ref = commande.ref_livree(c)
	assert ref["item"] == "item:Epee_longue"
	assert ref["fabrique_par"] == "lieu:forge_du_coin"
	assert ref["commande_at"] == 1234
	assert ref["poids"] == 2.2


def test_reference_sans_poids_quand_il_est_nul():
	# Pas de champ `poids` inutile : une référence nue vaut le min du doc.
	ref = commande.ref_livree(commande.nouvelle_commande(ARTISAN, "item:X", {}, now=1))
	assert "poids" not in ref


# ── Purge paresseuse ────────────────────────────────────────────────────────────

def test_purge_balaie_les_commandes_soldees(monkeypatch):
	monkeypatch.setattr(character_stats, "COMMANDE_DELAI_SECONDES", 0)
	perso = {"commandes": [
		dict(_payee(now=1000), statut=commande.ETAT_LIVREE),
		dict(_payee(now=1000), statut=commande.ETAT_ANNULEE),
		_payee(now=1000),
	]}
	assert commande.purger_commandes(perso, 1000) == 2
	assert len(perso["commandes"]) == 1


def test_purge_conserve_une_commande_expiree(monkeypatch):
	# Le joueur revenu trop tard doit VOIR ce qu'il a perdu, pas trouver une liste vide.
	monkeypatch.setattr(character_stats, "COMMANDE_DELAI_SECONDES", 0)
	monkeypatch.setattr(character_stats, "COMMANDE_PEREMPTION_SECONDES", 10)
	perso = {"commandes": [_payee(now=1000)]}
	assert commande.statut(perso["commandes"][0], 2000) == commande.ETAT_EXPIREE
	assert commande.purger_commandes(perso, 2000) == 0


def test_purge_ne_touche_pas_le_doc_si_rien_a_faire():
	perso = {}
	assert commande.purger_commandes(perso, 1000) == 0
	assert "commandes" not in perso        # aucune clé créée pour rien


def test_trouver_par_id():
	c = _payee()
	perso = {"commandes": [c]}
	assert commande.trouver(perso, c["id"]) is c
	assert commande.trouver(perso, "inconnu") is None
	assert commande.trouver(perso, None) is None


# ── Vue client ──────────────────────────────────────────────────────────────────

def test_vue_resout_le_nom_et_le_compte_a_rebours(monkeypatch):
	monkeypatch.setattr(character_stats, "COMMANDE_DELAI_SECONDES", 600)
	c = _payee(now=1000)
	v = commande.vue(c, _get_doc, now=1100)
	assert v["statut"] == commande.ETAT_EN_FABRICATION
	assert v["pret_dans"] == 500
	assert v["retirable"] is False
	assert v["sur_mesure"] is False


def test_vue_dune_commande_sur_mesure():
	c = commande.nouvelle_commande(GRANDE_MAISON, "item:Epee_longue_abc", {"total": 9},
								   now=1000, base_item="item:Epee_longue")
	assert commande.vue(c, _get_doc, now=1000)["sur_mesure"] is True


def test_poids_attendu_prend_le_minimum():
	assert commande.poids_attendu({"poids": [1.5, 4.0]}) == 1.5
	assert commande.poids_attendu({"poids": 2.0}) == 2.0
	assert commande.poids_attendu(None) == 0
