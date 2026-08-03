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
    depecage_carcasse, appliquer_marchandage, compter_transaction,
)


# ── matiere_item_id ──────────────────────────────────────────────────────────────

def test_matiere_item_id_sous_categorie():
    assert matiere_item_id("cuir") == "item:cuir"


def test_matiere_item_id_item_ref_inchange():
    # Une clé item-ref est déjà un id — pas de double préfixe item:item:…
    assert matiere_item_id("item:Herbes_medicinales") == "item:Herbes_medicinales"


def test_matiere_item_id_override_legacy():
    assert matiere_item_id("bougie") == "item:Bougie"


def test_matiere_item_id_matieres_au_doc_capitalise():
    # `chiffon` et `reactif_brut` sont CONSOMMÉS par des recettes (scriptorium,
    # laboratoire d'alchimie) et leur doc générique porte un id capitalisé. Sans
    # l'override, `get_doc` rend None et la matière est valorisée au plancher de
    # 1 cu EN SILENCE — prix faux propagé à tout ce qui en dérive.
    assert matiere_item_id("chiffon") == "item:Chiffon"
    assert matiere_item_id("reactif_brut") == "item:Reactif_brut"


def test_matiere_item_id_bois_reste_derive():
    # Les quatre calibres de bois n'ont PAS d'override : leur doc générique est
    # `item:<sous_categorie>` (cf. dev/gen_matieres_generiques_bois.py), les docs
    # par essence (item:Branche_de_Chene…) ne sont pas des génériques.
    for sc in ("branche", "petit_rondin", "rondin", "gros_rondin"):
        assert matiere_item_id(sc) == "item:" + sc


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


# ── appliquer_marchandage : une réussite ne dégrade jamais un prix déjà négocié ─────

def test_marchandage_reussi_persiste_le_prix():
    # pmin=50, pmax=150 ; frac 0.2 → prix = 50 + 100*0.2 = 70 (cohérent avec la formule
    # de marchander(), pour que la comparaison de favorabilité du 2e test soit valide).
    relation = {"value": 50}
    deal = {"prix": 70, "frac": 0.2, "roll": 40, "seuil": 50, "succes": True,
            "min": 50, "max": 150}

    issue = appliquer_marchandage(relation, "item:X", "achat", deal, now=1000)

    assert relation["prix_negocies"]["item:X"]["achat"] == {"frac": 0.2}
    assert issue["prix_negocie"] == 70


def test_marchandage_achat_reussi_mais_moins_favorable_ne_degrade_pas():
    # Le joueur a déjà 70 (frac 0.2). Un second jet, réussi mais de justesse (frac 0.7,
    # prix 120 > 70), ne doit PAS remplacer le bon prix par un moins bon — c'est le bug
    # signalé : une « réussite » ne doit jamais augmenter un prix d'achat déjà négocié.
    relation = {"value": 50, "prix_negocies": {"item:X": {"achat": {"frac": 0.2}}}}
    deal = {"prix": 120, "frac": 0.7, "roll": 45, "seuil": 50, "succes": True,
            "min": 50, "max": 150}

    issue = appliquer_marchandage(relation, "item:X", "achat", deal, now=1001)

    assert relation["prix_negocies"]["item:X"]["achat"] == {"frac": 0.2}  # inchangé
    assert issue["prix_negocie"] == 70  # l'ancien prix reste applicable, pas 120


def test_marchandage_achat_reussi_et_plus_favorable_ecrase_lancien():
    relation = {"value": 50, "prix_negocies": {"item:X": {"achat": {"frac": 0.2}}}}
    deal = {"prix": 60, "frac": 0.1, "roll": 10, "seuil": 50, "succes": True,
            "min": 50, "max": 150}

    issue = appliquer_marchandage(relation, "item:X", "achat", deal, now=1002)

    assert relation["prix_negocies"]["item:X"]["achat"] == {"frac": 0.1}
    assert issue["prix_negocie"] == 60


def test_marchandage_vente_reussi_mais_moins_favorable_ne_degrade_pas():
    # Symétrique côté vente : plus favorable au joueur = prix plus HAUT. Le joueur a
    # déjà 130 (frac 0.8) ; un second jet réussi mais moins bon (frac 0.3 → 80) ne doit
    # pas remplacer 130 par 80.
    relation = {"value": 50, "prix_negocies": {"item:X": {"vente": {"frac": 0.8}}}}
    deal = {"prix": 80, "frac": 0.3, "roll": 45, "seuil": 50, "succes": True,
            "min": 50, "max": 150}

    issue = appliquer_marchandage(relation, "item:X", "vente", deal, now=1003)

    assert relation["prix_negocies"]["item:X"]["vente"] == {"frac": 0.8}  # inchangé
    assert issue["prix_negocie"] == 130  # ancien prix (pmin + (pmax-pmin)*0.8) conservé


def test_marchandage_echec_ne_touche_pas_prix_negocies():
    relation = {"value": 50}
    deal = {"prix": 999, "frac": 0.99, "roll": 80, "seuil": 50, "succes": False,
            "min": 50, "max": 150}

    issue = appliquer_marchandage(relation, "item:Y", "achat", deal, now=1004)

    assert relation.get("prix_negocies", {}) == {}
    assert issue["prix_negocie"] is None


# ── Fidélité marchande ──────────────────────────────────────────────────────────
# Commercer répare une relation dégradée : +1 tous les RELATION_FIDELITE_TRANSACTIONS
# échanges (ventes ET achats confondus), tant que la relation est SOUS le seuil. Le
# compteur ne tourne que sous le seuil et repart de zéro au-dessus.

@pytest.fixture
def fidelite(monkeypatch):
    """Réglage nominal : 10 transactions, seuil au neutre (50)."""
    monkeypatch.setattr(character_stats, "RELATION_FIDELITE_TRANSACTIONS", 10)
    monkeypatch.setattr(character_stats, "RELATION_FIDELITE_SEUIL", 50)


def test_fidelite_sous_le_palier_ne_donne_rien(fidelite):
    relation = {"value": 40}

    for _ in range(9):
        issue = compter_transaction(relation)

    assert issue == {"compteur": 9, "restant": 1, "gain": False, "relation": 40, "modifie": True}
    assert relation["fidelite_transactions"] == 9
    assert relation["value"] == 40


def test_fidelite_dixieme_transaction_rend_un_point(fidelite):
    relation = {"value": 40, "fidelite_transactions": 9}

    issue = compter_transaction(relation)

    assert issue["gain"] is True
    assert issue["relation"] == 41
    assert relation["value"] == 41
    assert relation["fidelite_transactions"] == 0  # le compteur repart pour 10


def test_fidelite_au_dessus_du_seuil_remet_le_compteur_a_zero(fidelite):
    # Un client déjà bien vu ne capitalise pas d'avance : le compteur accumulé pendant la
    # brouille est effacé dès que la relation repasse au-dessus du seuil.
    relation = {"value": 60, "fidelite_transactions": 7}

    issue = compter_transaction(relation)

    assert issue["gain"] is False
    assert issue["modifie"] is True  # le compteur a bougé (7 → 0) → l'appelant doit sauver
    assert relation["fidelite_transactions"] == 0
    assert relation["value"] == 60


def test_fidelite_au_dessus_du_seuil_sans_compteur_ne_modifie_rien(fidelite):
    # Rien à écrire : l'appelant ne doit pas sauver le doc relation à chaque transaction.
    relation = {"value": 60}

    issue = compter_transaction(relation)

    assert issue["modifie"] is False
    assert "fidelite_transactions" not in relation


def test_fidelite_s_arrete_en_atteignant_le_seuil(fidelite):
    # 49 → 50 au 10e échange, puis plus rien : le seuil (neutre par défaut) est un plafond.
    relation = {"value": 49, "fidelite_transactions": 9}

    assert compter_transaction(relation)["relation"] == 50

    for _ in range(10):
        issue = compter_transaction(relation)

    assert issue["gain"] is False
    assert relation["value"] == 50


def test_fidelite_seuil_au_dessus_du_neutre(fidelite, monkeypatch):
    # Le seuil est une variable de monde : réglé à 70, la fidélité mène jusqu'à « Estimé ».
    monkeypatch.setattr(character_stats, "RELATION_FIDELITE_SEUIL", 70)
    relation = {"value": 55, "fidelite_transactions": 9}

    issue = compter_transaction(relation)

    assert issue["gain"] is True
    assert relation["value"] == 56


def test_fidelite_desactivee_par_world_var(fidelite, monkeypatch):
    monkeypatch.setattr(character_stats, "RELATION_FIDELITE_TRANSACTIONS", 0)
    relation = {"value": 40}

    for _ in range(20):
        issue = compter_transaction(relation)

    assert issue == {"compteur": 0, "restant": 0, "gain": False, "relation": 40, "modifie": False}
    assert "fidelite_transactions" not in relation
    assert relation["value"] == 40


def test_fidelite_ne_releve_pas_un_banni(fidelite):
    # Relation 0 = transactions interdites (403 côté endpoints) : la fidélité ne doit pas
    # devenir la porte de sortie d'un bannissement.
    relation = {"value": 0}

    for _ in range(20):
        issue = compter_transaction(relation)

    assert issue["gain"] is False
    assert relation["value"] == 0
