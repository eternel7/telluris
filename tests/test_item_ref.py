"""Références d'items localisées (utils/characters.py) — logique pure, sans DB.

Une entrée d'inventaire est une RÉFÉRENCE d'instance : elle peut porter un `poids` propre,
et désormais un `lieu_parent` — le lieu qui a délivré CET exemplaire. Le doc item, lui, reste
générique (une carte d'aventurier est la même partout ; seule la guilde qui la remet change).
`resolve_item_ref` est le seul endroit où cette localisation devient visible : tout ce que le
client affiche d'un objet passe par lui, et il n'affiche que `nom`.
"""

import pytest

from utils import characters


ITEMS = {
	"item:carte_aventurier": {
		"_id": "item:carte_aventurier", "type": "item", "nom": "Carte d'aventurier",
		"categorie": "document", "poids": 0.05,
	},
	"item:epee": {"_id": "item:epee", "type": "item", "nom": "Épée", "poids": [3, 4]},
	"lieu:auxerre": {"_id": "lieu:auxerre", "type": "lieu", "label": "Auxerre"},
}


@pytest.fixture(autouse=True)
def _db(monkeypatch):
	"""`characters.get_doc` est importé au niveau module → c'est lui qu'on remplace."""
	monkeypatch.setattr(characters, "get_doc", ITEMS.get)


def test_item_ref_lieu():
	assert characters.item_ref_lieu({"item": "item:carte_aventurier", "lieu_parent": "lieu:auxerre"}) == "lieu:auxerre"
	assert characters.item_ref_lieu({"item": "item:epee", "poids": 3.5}) is None
	assert characters.item_ref_lieu("item:epee") is None       # référence legacy (chaîne)


def test_item_label():
	assert characters.item_label("Carte d'aventurier", ITEMS["lieu:auxerre"]) == "Carte d'aventurier (Auxerre)"
	assert characters.item_label("Carte d'aventurier", None) == "Carte d'aventurier"
	# Lieu introuvable (supprimé depuis) : on ne fabrique pas un « (None) », on rend le nom nu.
	assert characters.item_label("Carte d'aventurier", {}) == "Carte d'aventurier"


def test_lieu_label():
	"""Pendant de `item_label` pour les lieux — et SOURCE UNIQUE : c'est d'avoir recopié la
	formule qu'un type de quête a fini par afficher `lieu:athanor` au joueur."""
	assert characters.lieu_label(ITEMS["lieu:auxerre"]) == "Auxerre"
	# Les docs `lieu:*` ne portent QUE `label` ; `nom` n'est qu'une tolérance pour un autre type.
	assert characters.lieu_label({"nom": "Le Temple"}) == "Le Temple"
	# Doc sans nom d'affichage : on rend le SLUG, jamais l'id — un id affiché est un défaut.
	assert characters.lieu_label({"_id": "lieu:athanor"}) == "athanor"
	# Lieu introuvable : le repli se nomme depuis l'id demandé, toujours sans son préfixe.
	assert characters.lieu_label(None, "lieu:le_saloir") == "le_saloir"
	assert characters.lieu_label(None) == ""


@pytest.mark.parametrize("doc,lieu_id", [
	({"label": "Auxerre"}, "lieu:auxerre"),
	({"nom": "Temple"}, "lieu:temple"),
	({"_id": "lieu:athanor"}, ""),
	({}, "lieu:le_saloir"),
	(None, "lieu:x"),
])
def test_lieu_label_ne_rend_jamais_un_identifiant(doc, lieu_id):
	assert not characters.lieu_label(doc, lieu_id).startswith("lieu:")


def test_resolve_item_ref_nomme_la_guilde_qui_a_delivre_l_instance():
	doc = characters.resolve_item_ref(
		{"item": "item:carte_aventurier", "poids": 0.05, "lieu_parent": "lieu:auxerre"}
	)
	assert doc["nom"] == "Carte d'aventurier (Auxerre)"
	assert doc["lieu_parent"] == "lieu:auxerre"
	assert doc["poids"] == 0.05
	# Le doc en base, lui, n'est pas touché : il reste générique pour tout le monde.
	assert ITEMS["item:carte_aventurier"]["nom"] == "Carte d'aventurier"


def test_resolve_item_ref_sans_lieu_garde_le_nom_nu():
	# Non-régression : un objet ordinaire n'est d'aucune ville.
	assert characters.resolve_item_ref({"item": "item:epee", "poids": 3.5})["nom"] == "Épée"
	assert characters.resolve_item_ref("item:epee")["nom"] == "Épée"
	assert "lieu_parent" not in characters.resolve_item_ref("item:epee")
