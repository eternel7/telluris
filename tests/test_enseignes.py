"""Tests du tirage de noms d'enseigne (`utils/enseignes.py`).

⚠️ AUCUN test ne laisse `rand_fn` à son défaut : `random.shuffle` rendrait ces
assertions dépendantes du hasard (piège CLAUDE.md §14). On passe partout un
mélangeur INERTE — l'ordre du produit cartésien devient alors déterministe et
lisible, ce qui est exactement ce qu'on veut vérifier.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import enseignes  # noqa: E402


def inerte(liste):
	"""Mélangeur qui ne mélange pas — contrat de `random.shuffle` (en place, rend None)."""
	return None


# ── Le cas nominal ──────────────────────────────────────────────────────────────

def test_rend_exactement_n_labels_distincts():
	labels = enseignes.tirer_labels("armurerie", 5, "lieu:lutecia", rand_fn=inerte)
	assert len(labels) == 5
	assert len(set(labels)) == 5


def test_croise_la_tournure_du_metier_et_le_toponyme_de_la_cite():
	labels = enseignes.tirer_labels("armurerie", 3, "lieu:lutecia", rand_fn=inerte)
	assert labels[0] == "L'Enclume de la Seine"
	for label in labels:
		assert label.startswith("L'Enclume")


def test_une_cite_sans_toponymes_prend_les_generiques():
	labels = enseignes.tirer_labels("armurerie", 1, "lieu:inconnue", rand_fn=inerte)
	assert labels == ["L'Enclume du Marché"]
	assert enseignes.toponymes_de("lieu:inconnue") == enseignes.TOPONYMES_DEFAUT


def test_lieu_parent_absent_prend_aussi_les_generiques():
	assert enseignes.toponymes_de("") == enseignes.TOPONYMES_DEFAUT
	assert enseignes.toponymes_de(None) == enseignes.TOPONYMES_DEFAUT


def test_toponymes_de_rend_une_copie():
	"""L'appelant ne doit pas pouvoir vider la table du module en mutant sa réponse."""
	liste = enseignes.toponymes_de("lieu:auxerre")
	liste.append("du Néant")
	assert "du Néant" not in enseignes.TOPONYMES_PAR_LIEU["lieu:auxerre"]


# ── L'exclusion : le seul rempart contre deux `lieu:<slug>` identiques ───────────

def test_aucun_label_exclu_n_est_propose():
	deja = {"L'Enclume de la Seine", "L'Enclume du Parvis"}
	labels = enseignes.tirer_labels("armurerie", 3, "lieu:lutecia", exclus=deja, rand_fn=inerte)
	assert len(labels) == 3
	assert not (set(labels) & deja)


def test_exclus_accepte_une_sequence_quelconque():
	"""Le client envoie une liste JSON, pas un set — les deux doivent passer."""
	labels = enseignes.tirer_labels(
		"armurerie", 2, "lieu:lutecia", exclus=["L'Enclume de la Seine"], rand_fn=inerte)
	assert "L'Enclume de la Seine" not in labels


def test_exclus_vide_ou_absent_ne_gene_pas():
	assert len(enseignes.tirer_labels("armurerie", 2, "lieu:lutecia", exclus=(), rand_fn=inerte)) == 2
	assert len(enseignes.tirer_labels("armurerie", 2, "lieu:lutecia", rand_fn=inerte)) == 2


# ── Le catalogue épuisé ─────────────────────────────────────────────────────────

def test_catalogue_epuise_suffixe_sans_jamais_rendre_moins_que_demande():
	"""`grande_boulangerie` n'a que 2 tournures × 10 toponymes génériques = 20 noms.
	On en demande 60 : la fonction doit tenir sa promesse, jamais rendre 20."""
	labels = enseignes.tirer_labels("grande_boulangerie", 60, "lieu:xxx", rand_fn=inerte)
	assert len(labels) == 60
	assert len(set(labels)) == 60


def test_les_suffixes_partent_en_romain_puis_en_chiffres():
	labels = enseignes.tirer_labels("grande_boulangerie", 21, "lieu:xxx", rand_fn=inerte)
	assert labels[20].endswith(" II")
	# 20 noms nus + 9 romains × 20 + le début des décimaux → le 201ᵉ est suffixé « 11 ».
	longs = enseignes.tirer_labels("grande_boulangerie", 210, "lieu:xxx", rand_fn=inerte)
	assert len(set(longs)) == 210
	assert longs[200].endswith(" 11")


def test_le_suffixage_respecte_aussi_exclus():
	deja = {"Le Grand Fournil du Marché II"}
	labels = enseignes.tirer_labels(
		"grande_boulangerie", 40, "lieu:xxx", exclus=deja, rand_fn=inerte)
	assert len(set(labels)) == 40
	assert not (set(labels) & deja)


# ── Les catégories hors catalogue ───────────────────────────────────────────────

def test_categorie_inconnue_retombe_sur_son_propre_nom():
	labels = enseignes.tirer_labels("atelier_de_chose", 2, "", rand_fn=inerte)
	assert len(labels) == 2
	for label in labels:
		assert label.startswith("Atelier De Chose")


def test_categorie_vide_ne_casse_pas():
	labels = enseignes.tirer_labels("", 2, "", rand_fn=inerte)
	assert len(labels) == 2
	for label in labels:
		assert label.startswith("L'Échoppe")


# ── Les bornes ──────────────────────────────────────────────────────────────────

def test_n_nul_ou_negatif_rend_une_liste_vide():
	assert enseignes.tirer_labels("armurerie", 0, "lieu:lutecia", rand_fn=inerte) == []
	assert enseignes.tirer_labels("armurerie", -3, "lieu:lutecia", rand_fn=inerte) == []


def test_n_illisible_rend_une_liste_vide():
	"""Le corps de requête vient du client : un `n` non entier ne doit pas lever."""
	assert enseignes.tirer_labels("armurerie", None, "lieu:lutecia", rand_fn=inerte) == []
	assert enseignes.tirer_labels("armurerie", "trois", "lieu:lutecia", rand_fn=inerte) == []


def test_n_numerique_en_chaine_est_accepte():
	assert len(enseignes.tirer_labels("armurerie", "4", "lieu:lutecia", rand_fn=inerte)) == 4


# ── Le catalogue lui-même ───────────────────────────────────────────────────────

def test_toutes_les_tournures_sont_non_vides():
	for categorie, tournures in enseignes.TOURNURES.items():
		assert tournures, f"{categorie} : aucune tournure"
		assert len(set(tournures)) == len(tournures), f"{categorie} : tournure en double"


def test_le_rand_fn_injecte_est_bien_appele():
	"""Garde-fou du garde-fou : si le mélange cessait d'être injecté, ces tests
	deviendraient silencieusement dépendants du hasard."""
	vus = []
	enseignes.tirer_labels("armurerie", 1, "lieu:lutecia", rand_fn=vus.append)
	assert len(vus) == 1
	assert "L'Enclume de la Seine" in vus[0]
