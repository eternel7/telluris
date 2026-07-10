# tests/test_marche_recettes.py
#
# Tests des références d'items dans les recettes (clé matière = sous_categorie OU id
# d'item `item:*`). Import de utils.* → dépend de db.config (connexion CouchDB à
# l'import) : à lancer dans le conteneur, comme le reste. Seules les fonctions pures
# sont testées (recettes passées en paramètre, pas de find_docs).

import pytest

from utils import marche
from models import character_stats
from utils.marche import (
    recette_matieres, matiere_item_id, _executer_production_batch, ecouler_produits_pnj,
    depecage_carcasse,
)


# ── matiere_item_id ──────────────────────────────────────────────────────────────

def test_matiere_item_id_sous_categorie():
    assert matiere_item_id("cuir") == "item:cuir"


def test_matiere_item_id_item_ref_inchange():
    # Une clé item-ref est déjà un id — pas de double préfixe item:item:…
    assert matiere_item_id("item:Herbes_medicinales") == "item:Herbes_medicinales"


def test_matiere_item_id_override_legacy():
    assert matiere_item_id("bougie") == "item:Bougie"


# ── Dépeçage : loot de matière ciblée par clé item-ref (sang de démon) ──────────

def test_depecage_demon_donne_sang_demon_seche():
    # Une carcasse démoniaque rend son sang séché (clé item-ref → item:Sang_demon_seche)
    # EN PLUS de ses matières charnues normales (membership additive par tags).
    demon = {"tags": ["demon", "infernal"], "base_attributes": {}}
    out = dict(depecage_carcasse(demon, poids=character_stats.DEPECAGE_POIDS_REF))
    assert out.get("item:Sang_demon_seche") == 1        # au poids de réf, facteur = 1
    assert "sang" in out and "coeur" in out             # matières normales conservées
    # La clé item-ref traverse la résolution telle quelle (pas de item:item:…).
    assert matiere_item_id("item:Sang_demon_seche") == "item:Sang_demon_seche"
    # Une espèce non démoniaque n'en produit pas.
    loup = {"tags": ["animal"], "base_attributes": {}}
    assert "item:Sang_demon_seche" not in dict(
        depecage_carcasse(loup, poids=character_stats.DEPECAGE_POIDS_REF))


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


# ── Pool unifié : le rayon (stock_vente) sert aussi de matière (surplus seulement) ──

def _recettes_arc():
    # Corde (boyaux → cordes_d_arc) + arc (manche + cordes_d_arc → Arc).
    corde = {
        "type": "recette", "lieu_categorie": "fletcher", "objet_final": "cordes_d_arc",
        "quantite_produite": 1,
        "matieres_premieres": [{"sous_categorie": "boyaux", "quantite": 2}],
    }
    arc = {
        "type": "recette", "lieu_categorie": "fletcher", "objet_final": "Arc",
        "quantite_produite": 1,
        "matieres_premieres": [
            {"sous_categorie": "manche", "quantite": 1},
            {"sous_categorie": "cordes_d_arc", "quantite": 1},
        ],
    }
    return [corde, arc]


def _resolve_arc(item_id):
    # Stub sans DB : la corde en rayon porte la sous-catégorie attendue par la recette d'arc.
    sc = {"item:cordes_d_arc": "cordes_d_arc"}.get(item_id, "")
    return {"_id": item_id, "item": item_id, "categorie": "composant", "sous_categorie": sc}


def test_pool_unifie_chaine_corde_puis_arc_en_gardant_une_base_en_vente():
    # boyaux → 3 cordes ; le surplus au-dessus de la cible (2) alimente la recette d'arc.
    lieu = {
        "categorie": "fletcher",
        "stock_matieres": {"boyaux": 6, "manche": 3},
        "stock_vente": [],
        "stock_cible": {"item": {"item:cordes_d_arc": 2}},
    }
    _executer_production_batch(lieu, _recettes_arc(), resolve_fn=_resolve_arc)
    vente = {e["item_id"]: e["qty"] for e in lieu["stock_vente"]}
    # Un arc a été fabriqué à partir d'une corde en surplus (chaînage intra-tick).
    assert vente.get("item:Arc") == 1
    # Une base de cordes reste en vente au niveau de la cible (surplus seul consommé).
    assert vente.get("item:cordes_d_arc") == 2
    # Conservation de la masse : boyaux épuisés, 1 manche consommée pour l'arc.
    assert "boyaux" not in lieu["stock_matieres"]
    assert lieu["stock_matieres"].get("manche") == 2


def test_pool_unifie_sans_surplus_ne_consomme_pas_le_rayon():
    # Cordes en rayon exactement au niveau de la cible → aucun surplus → pas d'arc, rayon intact.
    lieu = {
        "categorie": "fletcher",
        "stock_matieres": {"manche": 3},
        "stock_vente": [{"item_id": "item:cordes_d_arc", "qty": 2}],
        "stock_cible": {"item": {"item:cordes_d_arc": 2}},
    }
    produits = _executer_production_batch(lieu, _recettes_arc(), resolve_fn=_resolve_arc)
    assert produits == []
    assert all(e["item_id"] != "item:Arc" for e in lieu["stock_vente"])
    assert lieu["stock_vente"] == [{"item_id": "item:cordes_d_arc", "qty": 2}]
    assert lieu["stock_matieres"]["manche"] == 3


# ── ecouler_produits_pnj (demande PNJ objet par objet) ───────────────────────────

def test_ecoulement_pnj_objet_par_objet(monkeypatch):
    # Chaque produit tire indépendamment sa demande PNJ : avec un jet qui passe pour le 1er
    # produit et échoue pour le 2e, seul le 1er s'écoule au même tick (plus « tout d'un bloc »).
    monkeypatch.setattr(marche, "resolve_item_ref",
                        lambda item_id: {"_id": item_id, "item": item_id})
    monkeypatch.setattr(character_stats, "VENTE_PNJ_PROBA", 0.5)
    monkeypatch.setattr(character_stats, "VENTE_PNJ_FRACTION", 1.0)
    # Séquence de jets : 0.0 < 0.5 → item:A demandé ; 0.9 ≥ 0.5 → item:B ignoré.
    seq = iter([0.0, 0.9])
    monkeypatch.setattr(marche.random, "random", lambda: next(seq))

    lieu = {
        "stock_cible": {"item": {"item:A": 2, "item:B": 2}},
        "stock_vente": [
            {"item_id": "item:A", "qty": 10},
            {"item_id": "item:B", "qty": 10},
        ],
    }
    ecoules = ecouler_produits_pnj(lieu)

    # Seul A (jet réussi) s'écoule ; son excédent (10−2) part entièrement (fraction 1.0).
    assert ecoules == [{"item_id": "item:A", "qty": 8}]
    assert lieu["stock_vente"][0]["qty"] == 2   # A ramené au stock cible
    assert lieu["stock_vente"][1]["qty"] == 10  # B intact (pas de demande ce tick)


def test_ecoulement_pnj_proba_nulle_ne_fait_rien(monkeypatch):
    # Proba globale nulle → aucun produit demandé, court-circuit sans toucher random.random.
    monkeypatch.setattr(character_stats, "VENTE_PNJ_PROBA", 0.0)
    monkeypatch.setattr(character_stats, "VENTE_PNJ_FRACTION", 1.0)
    lieu = {"stock_vente": [{"item_id": "item:A", "qty": 10}]}
    assert ecouler_produits_pnj(lieu) == []
    assert lieu["stock_vente"][0]["qty"] == 10
