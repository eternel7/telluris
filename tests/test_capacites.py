"""Tests des capacités de lieu (`utils/capacites.py`).

⚠️ RAISON D'ÊTRE DE CE FICHIER : `capacites.py` RECOPIE cinq prédicats qui vivent ailleurs.
La recopie n'est acceptable que verrouillée — d'où `test_la_table_ne_derive_pas_des_vrais_
predicats`, qui compare `capacites_de` aux VRAIES fonctions du jeu sur une matrice de cas.
Si quelqu'un change `auberge.lieu_est_taverne` sans toucher à la table, c'est ici que ça casse.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import capacites  # noqa: E402
from utils import auberge, montures, scriptorium, recrutement, commande  # noqa: E402
from models import character_stats  # noqa: E402


# Les prédicats RÉELS du jeu, dans l'ordre du catalogue.
PREDICATS = {
	"taverne": auberge.lieu_est_taverne,
	"montures": montures.lieu_vend_montures,
	"scriptorium": scriptorium.lieu_est_scriptorium,
	"recrutement": recrutement.lieu_recrute,
	"guilde": recrutement.lieu_de_guilde,
	"sur_mesure": commande.lieu_fabrique_sur_mesure,
}


def _matrice() -> list:
	"""Tous les docs à éprouver : le vide, chaque catégorie seule, chaque tag seul, les
	combinaisons croisées, et les formes dégradées (champs absents, `tags` à None)."""
	docs = [
		None, {}, {"tags": None}, {"categorie": None, "tags": []},
		{"categorie": "boulangerie"},
		{"categorie": "auberge"},                              # le doc réel d'Auxerre
		{"categorie": "etable"},
		{"categorie": "scriptorium"},
		{"categorie": "guilde_aventurier"},
		{"sous_categorie": "guilde_aventurier"},
		{"categorie": "grand_scriptorium", "tags": ["scriptorium"]},   # cas réel de Lutèce
		{"categorie": "grand_arsenal"},                        # grande maison : sur mesure d'office
		{"categorie": "armurerie"},                            # artisan : commande oui, sur mesure non
	]
	for cap in capacites.CAPACITES:
		docs.append({"tags": [cap["tag"]]})
		docs.append({"categorie": "chemin", "tags": [cap["tag"]]})
		docs.append({"categorie": "auberge", "tags": [cap["tag"]]})
		docs.append({"tags": [cap["tag"], "battle_map", "foret"]})
	return docs


def test_la_table_ne_derive_pas_des_vrais_predicats():
	"""LE test de ce fichier. Toute divergence entre la recopie et la source casse ici."""
	for doc in _matrice():
		attendu = {cle: bool(fn(doc)) for cle, fn in PREDICATS.items()}
		assert capacites.capacites_de(doc) == attendu, f"divergence sur {doc!r}"


def test_le_catalogue_couvre_exactement_les_predicats():
	assert {c["id"] for c in capacites.CAPACITES} == set(PREDICATS)
	assert len(capacites.CAPACITES) == len(PREDICATS)


def test_prendre_une_commande_nest_pas_une_capacite_de_la_table():
	"""⚠️ Invariante de conception. « Prendre une commande » est DÉRIVÉ des recettes du lieu :
	ce n'est ni une catégorie ni un tag, donc ça ne peut pas entrer dans cette table, dont
	`tags_apres` ne sait poser que des tags. Le jour où quelqu'un y ajoute une case
	`commande`, décocher ne retirerait rien et cocher ne donnerait rien."""
	assert "commande" not in {c["id"] for c in capacites.CAPACITES}
	assert "commande" not in capacites.TAGS_CAPACITE


def test_chaque_entree_du_catalogue_est_complete():
	for cap in capacites.CAPACITES:
		for cle in ("id", "label", "tag", "categories", "sous_categories", "note"):
			assert cle in cap, f"{cap.get('id')} : clé {cle} manquante"
		assert cap["label"] and cap["tag"] and cap["note"]


def test_les_tags_de_capacite_sont_distincts():
	tags = [c["tag"] for c in capacites.CAPACITES]
	assert len(set(tags)) == len(tags)
	assert capacites.TAGS_CAPACITE == set(tags)


# ── accordee_par_categorie ──────────────────────────────────────────────────────

def test_accordee_par_categorie():
	taverne = capacites.PAR_ID["taverne"]
	guilde = capacites.PAR_ID["guilde"]
	assert capacites.accordee_par_categorie(taverne, "auberge") is True
	assert capacites.accordee_par_categorie(taverne, "boulangerie") is False
	# La guilde est la seule accordée par une SOUS-catégorie…
	assert capacites.accordee_par_categorie(guilde, "n_importe_quoi", "guilde_aventurier") is True
	# …ET la seule à couvrir PLUSIEURS catégories : la maison est éclatée en quatre lieux
	# (réception, comptoir, façade, bureau du maître), dont le bureau, sans sous-catégorie.
	for cat in ("guilde_aventurier", "guilde_aventurier_comptoir",
				"guilde_aventurier_exterieur", "bureau_maitre_guilde"):
		assert capacites.accordee_par_categorie(guilde, cat) is True
	assert capacites.accordee_par_categorie(guilde, "boulangerie") is False


def test_categories_dune_capacite_relues_dans_la_variable_de_monde():
	"""⚠️ Le sur-mesure n'a pas de liste de catégories en dur : elle EST
	`LIEU_CATEGORIES_FUSION`. Ouvrir une grande maison de plus doit suffire, sans toucher au
	catalogue — et le test doit le constater, pas le retaper (CLAUDE.md §14)."""
	sur_mesure = capacites.PAR_ID["sur_mesure"]
	assert capacites.categories_de(sur_mesure) == sorted(character_stats.LIEU_CATEGORIES_FUSION)
	for cat in character_stats.LIEU_CATEGORIES_FUSION:
		assert capacites.accordee_par_categorie(sur_mesure, cat) is True
	assert capacites.accordee_par_categorie(sur_mesure, "armurerie") is False


def test_categories_relues_a_chaque_appel_pas_figees_a_limport(monkeypatch):
	# Les variables de monde se rechargent à chaud : une table figée ferait diverger
	# l'éditeur du jeu sans un mot.
	monkeypatch.setitem(character_stats.LIEU_CATEGORIES_FUSION, "grande_forge_de_test", ["armurerie"])
	assert capacites.accordee_par_categorie(capacites.PAR_ID["sur_mesure"],
											"grande_forge_de_test") is True


def test_catalogue_serialise_les_categories_resolues():
	"""Le client (`part-lieux-js.html`) ne lit que `categories` : `categories_var` ne doit
	jamais lui arriver non résolu, sinon toutes les cases des grandes maisons se décochent."""
	sur_mesure = next(c for c in capacites.catalogue() if c["id"] == "sur_mesure")
	assert sur_mesure["categories"] == sorted(character_stats.LIEU_CATEGORIES_FUSION)
	# …sans muter le catalogue source.
	assert capacites.PAR_ID["sur_mesure"]["categories"] == []


def test_accordee_par_categorie_supporte_les_valeurs_absentes():
	taverne = capacites.PAR_ID["taverne"]
	assert capacites.accordee_par_categorie(taverne, None) is False
	assert capacites.accordee_par_categorie(taverne, "") is False
	assert capacites.accordee_par_categorie(None, "auberge") is False


# ── tags_apres ──────────────────────────────────────────────────────────────────

def test_cocher_une_capacite_pose_son_tag():
	assert capacites.tags_apres([], {"taverne": True}, "chemin") == ["taverne"]


def test_decocher_retire_le_tag():
	assert capacites.tags_apres(["taverne"], {"taverne": False}, "chemin") == []


def test_un_tag_hors_capacite_survit_toujours():
	"""⚠️ Le formulaire ne possède QUE les cinq tags de capacité. Les tags de pondération
	de carte de combat (`#bm-tags`) et tout marquage d'auteur doivent traverser intacts."""
	avant = ["foret", "taverne", "battle_map"]
	apres = capacites.tags_apres(avant, {"taverne": False}, "chemin")
	assert apres == ["foret", "battle_map"]
	apres2 = capacites.tags_apres(avant, {"taverne": True, "montures": True}, "chemin")
	assert apres2[:2] == ["foret", "battle_map"]
	assert set(apres2[2:]) == {"taverne", "montures"}


def test_un_tag_redondant_avec_la_categorie_n_est_pas_pose():
	"""Le doc de référence (`lieu:auberge_de_la_tour_de_l_horloge`) ne porte AUCUN tag :
	sa catégorie suffit. Poser `taverne` en plus serait du bruit."""
	assert capacites.tags_apres([], {"taverne": True}, "auberge") == []


def test_un_tag_redondant_deja_present_est_retire():
	"""Corollaire : si la catégorie devient `auberge`, le tag `taverne` devenu inutile
	disparaît — sans changer le comportement, `lieu_est_taverne` restant vrai."""
	assert capacites.tags_apres(["taverne"], {"taverne": True}, "auberge") == []


def test_tags_apres_reste_coherent_avec_capacites_de():
	"""La boucle complète : ce que le formulaire écrit doit rendre vraies les capacités
	demandées — c'est la seule chose qui compte pour le joueur."""
	for voulues in ({"taverne": True}, {"montures": True, "scriptorium": True},
					{"recrutement": True}, {"guilde": True},
					{c["id"]: True for c in capacites.CAPACITES}):
		for categorie in ("", "chemin", "auberge", "etable", "guilde_aventurier"):
			doc = {"categorie": categorie,
				   "tags": capacites.tags_apres(["foret"], voulues, categorie)}
			obtenues = capacites.capacites_de(doc)
			for cle, veut in voulues.items():
				assert obtenues[cle] is True, f"{cle} perdue pour categorie={categorie!r}"
			assert "foret" in doc["tags"]


def test_tags_apres_supporte_les_entrees_absentes():
	assert capacites.tags_apres(None, None, None) == []
	assert capacites.tags_apres(None, {}, "auberge") == []
