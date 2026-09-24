# tests/test_appro_extra.py
#
# `APPRO_EXTRA` : des matières livrées à une catégorie de lieu PAR DÉCLARATION, sans qu'aucune
# de ses recettes les consomme. Né pour les lingots précieux du grand arsenal (mithril,
# orichalque, adamantite) : matières de SUR-MESURE, l'intrant d'aucune recette, donc jamais
# livrées nulle part — l'audit économique les rapportait « sans source ».
#
# Logique pure : recettes et docs servis en mémoire, aucun accès DB.

import pytest

from models import character_stats
from utils import marche


MITHRIL = {"_id": "item:mithril", "type": "item", "nom": "Lingot de mithril", "categorie": "metal",
		   "sous_categorie": "metaux_precieux", "slots": [], "poids": 1, "rarete": "rare"}
FER = {"_id": "item:fer", "type": "item", "nom": "Fer", "categorie": "metal",
	   "sous_categorie": "fer", "slots": [], "poids": 1.0, "rarete": "commun"}
LAME = {"_id": "item:lame", "type": "item", "nom": "Lame", "categorie": "arme",
		"sous_categorie": "", "slots": ["main_droite"], "poids": 1.5, "rarete": "commun"}

RECETTES = [{
	"_id": "recette:test_lame", "type": "recette", "lieu_categorie": "forge_test",
	"objet_final": "lame", "quantite_produite": 1,
	"matieres_premieres": [{"sous_categorie": "fer", "quantite": 2}],
}]
CATALOGUE = {d["_id"]: d for d in (MITHRIL, FER, LAME)}


@pytest.fixture(autouse=True)
def _marche_en_memoire(monkeypatch):
	monkeypatch.setattr(marche, "_all_recettes", lambda: RECETTES)
	monkeypatch.setattr(marche, "get_doc", lambda i: CATALOGUE.get(i))
	monkeypatch.setattr(marche, "resolve_item_ref",
						lambda i: (dict(CATALOGUE[i], item=i) if i in CATALOGUE else None))
	monkeypatch.setattr(character_stats, "APPRO_EXTRA", {"forge_test": ["item:mithril"]})
	monkeypatch.setattr(character_stats, "APPRO_DEBIT", {"item:mithril": 1})
	monkeypatch.setattr(character_stats, "LIEU_CATEGORIES_FUSION",
						{"grande_forge_test": ["forge_test"]})
	marche.reset_prix_cache()
	yield
	marche.reset_prix_cache()


def _lieu(categorie="forge_test"):
	return {"_id": "lieu:" + categorie, "type": "lieu", "categorie": categorie,
			"stock_matieres": {}, "stock_vente": []}


def test_la_matiere_declaree_est_une_feuille_du_lieu_sans_recette_qui_la_consomme():
	assert "item:mithril" in marche.appro_leaves_categorie("forge_test")
	assert "item:mithril" in marche.appro_leaves_lieu(_lieu())
	# La feuille ordinaire est toujours là : la déclaration S'AJOUTE.
	assert "fer" in marche.appro_leaves_lieu(_lieu())


def test_elle_est_livree_a_la_reserve_et_au_comptoir_au_debit_regle_sous_son_id():
	lieu = _lieu()
	marche.approvisionner(lieu)
	assert lieu["stock_matieres"]["item:mithril"] == 1
	assert [e["qty"] for e in lieu["stock_vente"] if e["item_id"] == "item:mithril"] == [1]


def test_le_lieu_la_rachete_au_joueur():
	assert "item:mithril" in marche.besoins_categorie("forge_test")
	assert marche.cle_matiere_lieu("forge_test", MITHRIL, _lieu()) == "item:mithril"


def test_une_grande_maison_recoit_ce_quon_declare_pour_ses_metiers():
	assert "item:mithril" in marche.appro_leaves_lieu(_lieu("grande_forge_test"))


def test_une_autre_categorie_ne_recoit_rien():
	assert "item:mithril" not in marche.appro_leaves_lieu(_lieu("tannerie"))
	assert marche.appro_extra_categorie("") == set()


def test_la_table_du_code_livre_les_trois_lingots_au_grand_arsenal():
	# Défaut de code réel (pas celui de la fixture) : la décision du 24/09.
	defauts = character_stats.CODE_DEFAULTS
	assert sorted(defauts["APPRO_EXTRA"]["grand_arsenal"]) == [
		"item:adamantite", "item:mithril", "item:orichalque"]
	assert all(defauts["APPRO_DEBIT"][c] == 1 for c in defauts["APPRO_EXTRA"]["grand_arsenal"])
