# tests/test_marche_recettes.py
#
# Tests des références d'items dans les recettes (clé matière = sous_categorie OU id
# d'item `item:*`). Import de utils.* → dépend de db.config (connexion CouchDB à
# l'import) : à lancer dans le conteneur, comme le reste. Seules les fonctions pures
# sont testées (recettes passées en paramètre, pas de find_docs).

import pytest

from utils.marche import recette_matieres, matiere_item_id, _executer_production_batch


# ── matiere_item_id ──────────────────────────────────────────────────────────────

def test_matiere_item_id_sous_categorie():
    assert matiere_item_id("cuir") == "item:cuir"


def test_matiere_item_id_item_ref_inchange():
    # Une clé item-ref est déjà un id — pas de double préfixe item:item:…
    assert matiere_item_id("item:Herbes_medicinales") == "item:Herbes_medicinales"


def test_matiere_item_id_override_legacy():
    assert matiere_item_id("bougie") == "item:Bougie"


# ── recette_matieres (clé mixte sous_categorie / item) ──────────────────────────

def test_recette_matieres_item_ref():
    r = {"matieres_premieres": [{"item": "item:Herbes_medicinales", "quantite": 2}]}
    assert recette_matieres(r) == [("item:Herbes_medicinales", 2)]


def test_recette_matieres_mixte():
    r = {"matieres_premieres": [
        {"item": "item:Herbes_a_bruler", "quantite": 3},
        {"sous_categorie": "graisse", "quantite": 1},
    ]}
    assert recette_matieres(r) == [("item:Herbes_a_bruler", 3), ("graisse", 1)]


def test_recette_matieres_item_prioritaire_sur_sous_categorie():
    r = {"matieres_premieres": [{"item": "item:X", "sous_categorie": "herbe", "quantite": 1}]}
    assert recette_matieres(r) == [("item:X", 1)]


def test_recette_matieres_mono_legacy():
    r = {"matiere_premiere_sous_categorie": "sang", "quantite_matiere": 2}
    assert recette_matieres(r) == [("sang", 2)]


def test_recette_matieres_entree_invalide_ignoree():
    r = {"matieres_premieres": [{"quantite": 4}],
         "matiere_premiere_sous_categorie": "os", "quantite_matiere": 1}
    # Aucune entrée valide dans matieres_premieres → repli mono-entrée.
    assert recette_matieres(r) == [("os", 1)]


# ── _executer_production_batch (stock keyé par item id) ─────────────────────────

def _recette_elixir():
    return {
        "type": "recette",
        "lieu_categorie": "laboratoire_d_alchimie",
        "objet_final": "elixir_revigorant",
        "quantite_produite": 1,
        "matieres_premieres": [
            {"item": "item:Herbes_medicinales", "quantite": 2},
            {"item": "item:Herbes_a_bruler", "quantite": 2},
            {"sous_categorie": "sang", "quantite": 1},
        ],
    }


def test_batch_consomme_les_cles_item_ref():
    lieu = {"stock_matieres": {"item:Herbes_medicinales": 2, "item:Herbes_a_bruler": 2, "sang": 1}}
    produits = _executer_production_batch(lieu, [_recette_elixir()])
    assert {"item_id": "item:elixir_revigorant", "qty": 1} in produits
    # Toutes les entrées ont été drainées (et purgées du stock).
    assert lieu["stock_matieres"] == {}
    assert {"item_id": "item:elixir_revigorant", "qty": 1} in lieu["stock_vente"]


def test_batch_incomplet_ne_cuit_pas_et_conserve_le_stock():
    # Il manque les herbes à brûler → la recette n'est pas applicable, rien n'est perdu.
    lieu = {"stock_matieres": {"item:Herbes_medicinales": 2, "sang": 1}}
    produits = _executer_production_batch(lieu, [_recette_elixir()])
    assert produits == []
    assert lieu["stock_matieres"]["item:Herbes_medicinales"] == 2
    assert lieu["stock_matieres"]["sang"] == 1


def test_batch_matiere_item_ref_non_consommee_mise_en_rayon_sans_double_prefixe():
    # Une clé item-ref qu'aucune recette ne consomme part en rayon sous son id tel quel.
    lieu = {"stock_matieres": {"item:Herbes_medicinales": 3}}
    produits = _executer_production_batch(lieu, [])
    assert produits == [{"item_id": "item:Herbes_medicinales", "qty": 3}]
    assert lieu["stock_vente"] == [{"item_id": "item:Herbes_medicinales", "qty": 3}]
