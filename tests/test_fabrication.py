"""Tests purs des variantes fabriquées sur mesure (`utils/fabrication.py`).

Ce que ce fichier verrouille, et pourquoi :
- l'IDENTITÉ d'une combinaison ne dépend pas de l'ordre de saisie (§14 du cahier des charges) —
  sans quoi commander « épée + acier + cristal » puis « épée + cristal + acier » créerait deux
  définitions pour le même objet ;
- la LISTE BLANCHE : un doc de contenu ne peut pas injecter `slots`, `sorts` ni `type` ;
- la recette générée porte `sur_commande` et prend le base pour intrant ;
- `assurer_variante` est idempotent et refuse d'écraser un `_id` occupé par autre chose.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import fabrication  # noqa: E402
from models import character_stats  # noqa: E402


EPEE = {
	"_id": "item:Epee_longue", "type": "item", "nom": "Épée longue",
	"icon": "⚔️", "categorie": "arme", "sous_categorie": "", "slots": ["main_droite"],
	"tags": ["cac", "tranchant"], "poids": 2.0, "portee": 1,
	"bonus_degats": 3, "bonus_degats_dice": 6, "rarete": "commun",
	"restriction": {"F": 12},
}

ACIER = {
	"_id": "item:acier", "type": "item", "nom": "Lingot d'acier",
	"categorie": "metal", "sous_categorie": "acier", "poids": 2.5,
	"fabrication": {
		"nom": "en acier",
		"modificateurs": {
			"bonus_degats": 2,
			"poids": {"facteur": 1.1},
			"restriction": {"F": 14},
		},
	},
}

CRISTAL = {
	"_id": "item:Cristal_de_feu", "type": "item", "nom": "Cristal de feu",
	"categorie": "composant", "sous_categorie": "gemme", "poids": 0.2,
	"rarete": "rare",
	"fabrication": {
		"nom": "au cristal de feu",
		"modificateurs": {
			"bonus": {"Int": 2},
			"effets": {"degats_feu": 4},
			"valeur": {"facteur": 2.0},
			"rarete": "rare",
		},
	},
}

# Une matière SANS bloc `fabrication` — le cas des 1 324 items déjà en base.
BOIS = {
	"_id": "item:Branche_de_Chene", "type": "item", "nom": "Branche de Chêne",
	"categorie": "composant", "sous_categorie": "branche", "poids": [1, 3],
}


# ── Identité d'une combinaison ───────────────────────────────────────────────────

def test_ordre_des_matieres_sans_influence():
	a = fabrication.variante_id(EPEE, [{"item": "item:acier", "quantite": 2},
									   {"item": "item:Cristal_de_feu", "quantite": 1}])
	b = fabrication.variante_id(EPEE, [{"item": "item:Cristal_de_feu", "quantite": 1},
									   {"item": "item:acier", "quantite": 2}])
	assert a == b


def test_quantites_agregees_et_triees():
	# Deux lignes de la même matière valent une ligne de quantité cumulée.
	une_ligne = fabrication.normaliser_matieres([{"item": "item:acier", "quantite": 3}])
	deux_lignes = fabrication.normaliser_matieres([{"item": "item:acier", "quantite": 1},
												   {"item": "item:acier", "quantite": 2}])
	assert une_ligne == deux_lignes == [{"item": "item:acier", "quantite": 3}]


def test_forme_chaine_acceptee_et_entrees_vides_ecartees():
	assert fabrication.normaliser_matieres(["item:acier", {"item": None}, 42, {}]) == \
		[{"item": "item:acier", "quantite": 1}]


def test_quantite_differente_donne_une_variante_differente():
	un = fabrication.variante_id(EPEE, [{"item": "item:acier", "quantite": 1}])
	deux = fabrication.variante_id(EPEE, [{"item": "item:acier", "quantite": 2}])
	assert un != deux


def test_signature_stable_entre_deux_appels():
	# `hash()` natif est salé par processus : deux redémarrages donneraient deux ids.
	assert fabrication.signature("item:Epee_longue", [{"item": "item:acier", "quantite": 1}]) == \
		fabrication.signature("item:Epee_longue", [{"item": "item:acier", "quantite": 1}])


def test_id_de_variante_prefixe_par_le_slug_du_base():
	vid = fabrication.variante_id(EPEE, [{"item": "item:acier", "quantite": 1}])
	assert vid.startswith("item:Epee_longue_")
	assert len(vid.rsplit("_", 1)[-1]) == fabrication.SIGNATURE_LONGUEUR


# ── Ce qu'une matière apporte ────────────────────────────────────────────────────

def test_matiere_sans_bloc_fabrication_napporte_rien():
	props = fabrication.proprietes_matiere(BOIS)
	assert props == {"nom": "", "modificateurs": {}}


def test_liste_blanche_ignore_les_champs_interdits():
	piegee = {"_id": "item:piege", "fabrication": {"modificateurs": {
		"slots": ["tete"], "sorts": ["sort:boule_de_feu"], "type": "sort",
		"_id": "item:autre", "bonus_degats": 1,
	}}}
	assert fabrication.proprietes_matiere(piegee)["modificateurs"] == {"bonus_degats": 1}


def test_bonus_additifs_cumules_avec_la_quantite():
	mods = fabrication.appliquer_modificateurs(EPEE, [(ACIER, 2)])
	# base 3 + (2 × 2 lingots)
	assert mods["bonus_degats"] == 7


def test_fusion_des_bonus_de_caracteristique_et_des_effets():
	mods = fabrication.appliquer_modificateurs(EPEE, [(CRISTAL, 1), (CRISTAL, 1)])
	assert mods["bonus"] == {"Int": 4}
	assert mods["effets"] == {"degats_feu": 8}


def test_restriction_prend_le_plus_exigeant():
	# Le base exige F 12, l'acier F 14 : alourdir ne peut pas rendre l'arme plus facile.
	mods = fabrication.appliquer_modificateurs(EPEE, [(ACIER, 1)])
	assert mods["restriction"] == {"F": 14}


def test_rarete_monte_jamais_ne_descend():
	mods = fabrication.appliquer_modificateurs(EPEE, [(CRISTAL, 1)])
	assert mods["rarete"] == "rare"
	# L'échelle est relue depuis MULT_RARETE, pas retapée ici.
	assert character_stats.MULT_RARETE["rare"] > character_stats.MULT_RARETE["commun"]


def test_composition_commutative():
	a = fabrication.appliquer_modificateurs(EPEE, [(ACIER, 1), (CRISTAL, 1)])
	b = fabrication.appliquer_modificateurs(EPEE, [(CRISTAL, 1), (ACIER, 1)])
	assert a == b


def test_de_de_degats_borne():
	enorme = {"_id": "item:x", "fabrication": {"modificateurs": {"bonus_degats_dice": 999}}}
	mods = fabrication.appliquer_modificateurs(EPEE, [(enorme, 1)])
	assert mods["bonus_degats_dice"] == fabrication.DICE_MAX


def test_facteur_hors_bornes_clampe():
	fou = {"_id": "item:x", "fabrication": {"modificateurs": {"poids": {"facteur": 1000}}}}
	doc = fabrication.variante_doc(EPEE, [(fou, 1)])
	assert doc["poids"] == round(2.0 * fabrication.FACTEUR_MAX, 2)


def test_facteur_malforme_est_neutre():
	casse = {"_id": "item:x", "fabrication": {"modificateurs": {"poids": {"facteur": "lourd"}}}}
	doc = fabrication.variante_doc(EPEE, [(casse, 1)])
	assert doc["poids"] == 2.0


# ── Le doc de la variante ────────────────────────────────────────────────────────

def test_variante_herite_des_caracteristiques_intrinseques():
	doc = fabrication.variante_doc(EPEE, [(ACIER, 1)])
	assert doc["categorie"] == "arme"
	assert doc["slots"] == ["main_droite"]
	assert doc["tags"] == ["cac", "tranchant"]
	assert doc["portee"] == 1
	assert doc["type"] == "item"


def test_variante_ne_recopie_ni_rev_ni_fabrication_du_base():
	base_derive = dict(EPEE, _rev="7-abc", fabrication={"base_item": "item:autre_chose"})
	doc = fabrication.variante_doc(base_derive, [(ACIER, 1)])
	assert "_rev" not in doc
	assert doc["fabrication"]["base_item"] == "item:Epee_longue"


def test_nom_compose_dans_lordre_normalise():
	# L'ordre d'affichage suit l'ordre des matières telles qu'on les passe : c'est l'appelant
	# qui normalise avant d'appeler. Les deux fragments doivent être présents.
	doc = fabrication.variante_doc(EPEE, [(ACIER, 1), (CRISTAL, 1)])
	assert doc["nom"].startswith("Épée longue")
	assert "en acier" in doc["nom"] and "au cristal de feu" in doc["nom"]


def test_nom_inchange_si_aucune_matiere_ne_porte_de_fragment():
	doc = fabrication.variante_doc(EPEE, [(BOIS, 1)])
	assert doc["nom"] == "Épée longue"


def test_poids_min_max_conserve_sa_forme():
	base = dict(EPEE, poids=[1.0, 3.0])
	doc = fabrication.variante_doc(base, [(ACIER, 1)])
	assert doc["poids"] == [round(1.0 * 1.1, 2), round(3.0 * 1.1, 2)]


def test_valeur_explicite_figee_a_la_creation():
	doc = fabrication.variante_doc(EPEE, [(ACIER, 1)], cout_base_cuivre=100, cout_matieres_cuivre=50)
	socle = int(round(150 * character_stats.COMMANDE_MARGE))
	assert doc["valeur"][0] == {"cu": socle}
	assert doc["valeur"][1]["cu"] > socle


def test_marge_du_sur_mesure_distincte_de_marge_transfo():
	# La raison d'être de COMMANDE_MARGE : réutiliser MARGE_TRANSFO facturerait la variante
	# d'un objet DÉJÀ transformé une seconde fois à ×5.
	assert character_stats.COMMANDE_MARGE < character_stats.MARGE_TRANSFO


def test_bloc_de_tracabilite_complet():
	doc = fabrication.variante_doc(EPEE, [(ACIER, 2), (CRISTAL, 1)],
								   lieu_id="lieu:forge", now=1758300000)
	trace = doc["fabrication"]
	assert trace["base_item"] == "item:Epee_longue"
	assert trace["matieres"] == [{"item": "item:Cristal_de_feu", "quantite": 1},
								 {"item": "item:acier", "quantite": 2}]
	assert trace["lieu"] == "lieu:forge"
	assert trace["cree_at"] == 1758300000
	assert trace["recette"].startswith(fabrication.PREFIXE_RECETTE)


# ── La recette générée ───────────────────────────────────────────────────────────

def test_recette_porte_le_drapeau_sur_commande():
	rec = fabrication.recette_variante_doc(EPEE, [(ACIER, 1)], "armurerie")
	assert rec[fabrication.CLE_SUR_COMMANDE] is True
	assert rec["type"] == "recette"
	assert rec["lieu_categorie"] == "armurerie"


def test_le_base_est_un_intrant_de_la_recette():
	rec = fabrication.recette_variante_doc(EPEE, [(ACIER, 2)], "armurerie")
	assert rec["matieres_premieres"][0] == {"item": "item:Epee_longue", "quantite": 1}
	assert {"item": "item:acier", "quantite": 2} in rec["matieres_premieres"]


def test_objet_final_resout_vers_la_variante():
	from utils import marche
	rec = fabrication.recette_variante_doc(EPEE, [(ACIER, 1)], "armurerie")
	assert marche.objet_final_item_id(rec["objet_final"]) == fabrication.variante_id(EPEE, [{"item": "item:acier"}])


def test_recette_lisible_par_recette_matieres():
	from utils import marche
	rec = fabrication.recette_variante_doc(EPEE, [(ACIER, 2), (CRISTAL, 1)], "armurerie")
	entrees = dict(marche.recette_matieres(rec))
	assert entrees["item:Epee_longue"] == 1
	assert entrees["item:acier"] == 2
	assert entrees["item:Cristal_de_feu"] == 1


# ── assurer_variante : idempotence et collisions ─────────────────────────────────

def _fausse_db(seed=None):
	db = dict(seed or {})

	def get_doc(doc_id):
		return db.get(doc_id)

	def save_doc(doc):
		db[doc["_id"]] = doc
		return doc

	return db, get_doc, save_doc


def test_premiere_commande_cree_item_et_recette():
	db, get_doc, save_doc = _fausse_db()
	doc, cree = fabrication.assurer_variante(EPEE, [(ACIER, 1)], {"_id": "lieu:forge", "categorie": "armurerie"},
											 get_doc, save_doc)
	assert cree is True
	assert doc["_id"] in db
	assert doc["fabrication"]["recette"] in db


def test_seconde_commande_ne_recree_rien():
	db, get_doc, save_doc = _fausse_db()
	fabrication.assurer_variante(EPEE, [(ACIER, 1)], {"_id": "lieu:forge", "categorie": "armurerie"},
								 get_doc, save_doc)
	avant = dict(db)
	doc, cree = fabrication.assurer_variante(EPEE, [(ACIER, 1)], {"_id": "lieu:forge", "categorie": "armurerie"},
											 get_doc, save_doc)
	assert cree is False
	assert db == avant          # aucun doc ajouté
	assert doc is avant[doc["_id"]]  # le doc existant est rendu tel quel, jamais réécrit


def test_doc_existant_jamais_retouche():
	# Le contenu d'une variante déjà vendue ne doit pas bouger sous son acheteur.
	db, get_doc, save_doc = _fausse_db()
	doc, _ = fabrication.assurer_variante(EPEE, [(ACIER, 1)], {"_id": "lieu:forge", "categorie": "armurerie"},
										  get_doc, save_doc, cout_base_cuivre=100)
	doc["nom"] = "Nom gravé par le premier artisan"
	relu, cree = fabrication.assurer_variante(EPEE, [(ACIER, 1)], {"_id": "lieu:autre", "categorie": "grand_arsenal"},
											  get_doc, save_doc, cout_base_cuivre=99999)
	assert cree is False
	assert relu["nom"] == "Nom gravé par le premier artisan"


def test_id_occupe_par_autre_chose_leve():
	# Un PUT complet écraserait le doc en silence (CLAUDE.md §11) : on refuse d'écrire.
	vid = fabrication.variante_id(EPEE, [{"item": "item:acier", "quantite": 1}])
	db, get_doc, save_doc = _fausse_db({vid: {"_id": vid, "type": "item", "nom": "Autre chose"}})
	try:
		fabrication.assurer_variante(EPEE, [(ACIER, 1)], {"_id": "lieu:forge", "categorie": "armurerie"},
									 get_doc, save_doc)
	except ValueError:
		return
	raise AssertionError("une collision d'_id doit lever, pas écraser")
