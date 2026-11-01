# tests/test_enseignes_icones.py
# Couleur, pictogramme et métier du marqueur d'une connexion (`utils/enseignes_icones`) :
# résolution catégorie → tag de capacité → grande maison → route.

import pytest

from models import character_stats
from utils import enseignes_icones as ei


def test_chaque_metier_pointe_une_famille_connue_avec_pictogramme_et_article():
	for cat, (famille, icone, metier) in ei.METIERS.items():
		assert famille in ei.FAMILLES, cat
		assert icone, cat
		# l'article fait l'accord du toast (« Une boucherie est proche. »)
		assert metier.split(" ", 1)[0] in {"un", "une", "le", "la", "l'", "des"}, cat


def test_toute_categorie_de_grande_maison_et_ses_metiers_ont_un_marqueur():
	"""Relu dans LIEU_CATEGORIES_FUSION : une grande maison ou un métier ajoutés sans entrée
	dans `METIERS` tomberaient en `route` (point bleu) sans un mot."""
	for grande, incluses in character_stats.LIEU_CATEGORIES_FUSION.items():
		for cat in [grande, *incluses]:
			assert ei.icone_lieu({"categorie": cat})["metier"], cat


def test_categorie_connue():
	famille, icone, metier = ei.METIERS["boucherie"]
	assert ei.icone_lieu({"categorie": "boucherie"}) == {
		"famille": famille, "rgb": ei.FAMILLES[famille], "icone": icone, "metier": metier}


@pytest.mark.parametrize("tag", sorted(ei.CAPACITE_METIER))
def test_capacite_accordee_par_tag(tag):
	attendu = ei.METIERS[ei.CAPACITE_METIER[tag]]
	bloc = ei.icone_lieu({"categorie": "maison_bourgeoise", "tags": [tag]})
	assert (bloc["famille"], bloc["icone"], bloc["metier"]) == attendu


def test_grande_maison_sans_entree_herite_de_sa_premiere_categorie(monkeypatch):
	monkeypatch.setattr(character_stats, "LIEU_CATEGORIES_FUSION",
		{"grande_maison_inedite": ["inconnue", "boucherie"]})
	famille, icone, _ = ei.METIERS["boucherie"]
	assert ei.icone_lieu({"categorie": "grande_maison_inedite"}) == {
		"famille": famille, "rgb": ei.FAMILLES[famille], "icone": icone,
		"metier": ei.LIBELLE_GRANDE_MAISON}


@pytest.mark.parametrize("doc", [{"categorie": "ville"}, {"categorie": "Porte de rempart"}, {}, None])
def test_sans_metier_c_est_une_route(doc):
	assert ei.icone_lieu(doc) == ei.ROUTE


def test_route_est_le_bleu_d_origine_des_passages():
	"""Le bleu du CSS `.passage-marque` (`--passage-rgb`) : une carte de pays reste inchangée."""
	assert ei.ROUTE["rgb"] == "110, 185, 255"
