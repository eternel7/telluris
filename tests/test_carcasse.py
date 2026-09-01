# tests/test_carcasse.py
# Découpe d'une grosse carcasse en portions localisées (utils/carcasse.py) et dépeçage
# d'une portion au comptoir de la boucherie (utils/marche._matieres_entrantes).

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import character_stats
from utils import carcasse
from utils.marche import _matieres_entrantes, depecage_carcasse


def _cerf():
	"""Doc carcasse tel que le pose `dev/gen_carcasses_parties.py` (profil quadrupède)."""
	return {
		"_id": "item:cerf", "type": "item", "sous_categorie": "carcasse",
		"poids": [100, 250],
		"decoupe": [
			{"item": "item:cerf_tete",  "quantite": 1, "fraction": 0.12},
			{"item": "item:cerf_corps", "quantite": 1, "fraction": 0.52},
			{"item": "item:cerf_patte", "quantite": 4, "fraction": 0.28},
			{"item": "item:cerf_queue", "quantite": 1, "fraction": 0.08},
		],
	}


# ── Ce qui rend une carcasse découpable ─────────────────────────────────────────

def test_seule_la_donnee_decide_ni_la_sous_categorie_ni_le_poids():
	assert carcasse.item_est_decoupable(_cerf())
	# Une carcasse ordinaire, même lourde, ne l'est pas : rien n'a été authoré pour elle.
	assert not carcasse.item_est_decoupable(
		{"_id": "item:loup", "sous_categorie": "carcasse", "poids": [900, 900]})
	assert not carcasse.item_est_decoupable(None)
	assert not carcasse.item_est_decoupable({"decoupe": []})


def test_entrees_illisibles_ecartees_une_a_une_pas_toute_la_decoupe():
	# Fail-soft : une entrée fautive coûte une portion, jamais la mécanique entière.
	doc = {"decoupe": [
		{"item": "item:x_tete", "quantite": 1, "fraction": 0.5},
		{"item": "pas_un_item", "quantite": 1, "fraction": 0.5},   # préfixe absent
		{"item": "item:x_bras", "quantite": 0, "fraction": 0.5},   # quantité nulle
		{"item": "item:x_pied", "quantite": 1, "fraction": 0},     # fraction nulle
		{"item": "item:x_aile", "quantite": 1, "fraction": "oui"}, # illisible
		"pas un dict",
	]}
	entrees = carcasse.entrees_decoupe(doc)
	assert [e["item"] for e in entrees] == ["item:x_tete"]


# ── Découpe : conservation de la masse ──────────────────────────────────────────

def test_decoupe_rend_une_piece_par_exemplaire_et_conserve_le_poids():
	pieces = carcasse.decouper_ref({"item": "item:cerf", "poids": 200.0}, _cerf())
	assert [p["item"] for p in pieces] == [
		"item:cerf_tete", "item:cerf_corps",
		"item:cerf_patte", "item:cerf_patte", "item:cerf_patte", "item:cerf_patte",
		"item:cerf_queue",
	]
	# 12 % / 52 % / 4 × 7 % / 8 % de 200 kg.
	assert pieces[0]["poids"] == 24.0
	assert pieces[1]["poids"] == 104.0
	assert all(p["poids"] == 14.0 for p in pieces[2:6])
	assert round(sum(p["poids"] for p in pieces), 2) == 200.0


def test_le_reliquat_d_arrondi_va_sur_la_derniere_piece():
	# Un poids qui ne tombe pas juste : sans reliquat, la découpe créerait ou détruirait de
	# la matière — donc de la valeur, le prix d'une carcasse dérivant de son poids.
	for poids in (137.77, 100.01, 999.99, 12345.67):
		pieces = carcasse.decouper_ref({"item": "item:cerf", "poids": poids}, _cerf())
		assert round(sum(p["poids"] for p in pieces), 2) == round(poids, 2), poids


def test_carcasse_sans_decoupe_ou_sans_poids_ne_rend_rien():
	assert carcasse.decouper_ref({"item": "item:loup", "poids": 500}, {"_id": "item:loup"}) is None
	assert carcasse.decouper_ref({"item": "item:cerf", "poids": 0}, _cerf()) is None


# ── Le seuil de poids : un garde-fou, pas une commodité ─────────────────────────

def test_sous_le_seuil_l_instance_n_est_pas_decoupable():
	# Les quantités du dépeçage sont planchées à 1 : sans seuil, débiter sans fin rendrait
	# 1 crâne PAR morceau, aussi petit soit-il. Le seuil ferme cette porte.
	leger = {"item": "item:cerf", "poids": 99.0}
	assert not carcasse.item_est_decoupable(_cerf(), 99.0)
	assert carcasse.item_est_decoupable(_cerf(), 100.0)
	assert carcasse.decouper_ref(leger, _cerf()) is None
	# Sans instance (le doc seul), on répond sur la seule présence du champ — ce dont le
	# générateur et la fiche d'un item non porté ont besoin.
	assert carcasse.item_est_decoupable(_cerf())


def test_le_seuil_est_bake_sur_le_doc_et_prime_sur_la_world_var():
	gros = dict(_cerf(), decoupe_poids_min=500)
	assert not carcasse.item_est_decoupable(gros, 300.0)
	assert carcasse.item_est_decoupable(gros, 500.0)
	# Valeur illisible ⇒ repli sur la world-var, jamais « pas de seuil ».
	casse = dict(_cerf(), decoupe_poids_min="beaucoup")
	assert carcasse.seuil_decoupe(casse) == float(character_stats.CARCASSE_DECOUPE_POIDS_MIN)


# ── L'outil : une LAME, pas la hache du bûcheron ────────────────────────────────

def _docs(table):
	return lambda i: table.get(i)


def test_arme_tranchante_partagee_par_le_groupe_et_lue_dans_les_slots():
	table = {
		"item:Epee_courte": {"_id": "item:Epee_courte", "tags": ["cac", "tranchant"]},
		"item:Masse":       {"_id": "item:Masse", "tags": ["cac"]},
	}
	nu = {"inventaire": [], "slots": {}}
	masse = {"inventaire": ["item:Masse"], "slots": {}}
	# Une lame AU FOURREAU (équipée) compte : on ne dégaine pas pour dépecer.
	lame_en_main = {"inventaire": [], "slots": {"main_droite": "item:Epee_courte"}}

	assert not carcasse.a_arme_tranchante(masse, _docs(table))
	assert carcasse.a_arme_tranchante(lame_en_main, _docs(table))
	# Mise en commun : il suffit qu'UN membre de l'expédition porte la lame.
	assert carcasse.a_arme_tranchante(nu, _docs(table), [masse, lame_en_main])
	assert not carcasse.a_arme_tranchante(nu, _docs(table), [masse])


def test_le_tag_est_une_variable_de_monde():
	table = {"item:Serpe": {"_id": "item:Serpe", "tags": ["lame_rituelle"]}}
	porteur = {"inventaire": ["item:Serpe"], "slots": {}}
	assert not carcasse.a_arme_tranchante(porteur, _docs(table))
	avant = character_stats.CARCASSE_TRANCHANT_TAG
	try:
		character_stats.CARCASSE_TRANCHANT_TAG = "lame_rituelle"
		assert carcasse.a_arme_tranchante(porteur, _docs(table))
	finally:
		character_stats.CARCASSE_TRANCHANT_TAG = avant


# ── Dépeçage d'une portion au comptoir ──────────────────────────────────────────

def _tete_de_cerf(poids):
	"""Portion telle que générée : sa table `depecage` est BAKÉE sur le doc item."""
	return {
		"_id": "item:cerf_tete", "item": "item:cerf_tete", "type": "item",
		"categorie": "composant", "sous_categorie": "carcasse", "poids": poids,
		"source_espece": "espece:cerf", "partie": "tete",
		"depecage": [["crane", 1], ["crocs", 1], ["cuir_brut", 1], ["os", 1]],
	}


def test_une_portion_se_depece_sur_SA_table_sans_lire_d_espece():
	# ⚠️ Le cœur du dispositif : `espece:cerf_tete` n'existe pas. Sans la branche `depecage`
	# de `_matieres_entrantes`, la portion se vendrait au boucher sans rien lui apporter —
	# en silence, et sans que rien ne le signale.
	out = dict(_matieres_entrantes(_tete_de_cerf(character_stats.DEPECAGE_POIDS_REF),
								   {}, "boucherie"))
	assert out == {"crane": 1, "crocs": 1, "cuir_brut": 1, "os": 1}
	# Aucune matière de corps : une tête ne rend ni viande ni boyaux.
	assert "viande" not in out and "boyaux" not in out


def test_la_portion_suit_l_echelle_de_poids_comme_une_carcasse_entiere():
	out = dict(_matieres_entrantes(_tete_de_cerf(3 * character_stats.DEPECAGE_POIDS_REF),
								   {}, "boucherie"))
	assert out["crane"] == 3 and out["os"] == 3


def test_une_carcasse_entiere_passe_toujours_par_son_espece():
	# Le chemin historique n'est pas touché : sans champ `depecage`, on lit l'espèce.
	espece = {"_id": "espece:cerf", "tags": ["animal"]}
	attendu = dict(depecage_carcasse(espece, {}, character_stats.DEPECAGE_POIDS_REF))
	appels = []

	import utils.marche as marche
	get_doc_reel = marche.get_doc
	try:
		marche.get_doc = lambda i: (appels.append(i), espece if i == "espece:cerf" else None)[1]
		out = dict(_matieres_entrantes(
			{"_id": "item:cerf", "item": "item:cerf", "sous_categorie": "carcasse",
			 "poids": character_stats.DEPECAGE_POIDS_REF}, {}, "boucherie"))
	finally:
		marche.get_doc = get_doc_reel
	assert appels == ["espece:cerf"]
	assert out == attendu
