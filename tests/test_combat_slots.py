# tests/test_combat_slots.py
#
# Coût en action de la réorganisation de la barre EN COMBAT (action `editer_barre`).
# C'est l'ENTRÉE en mode édition qui est facturée, pas chaque case modifiée : le
# contenu des cases vit sur le doc du personnage et reste écrit par /api/slot_action,
# hors du moteur de combat.
#
# ⚠️ Le point sensible : `actions_restantes` n'est jamais décrémenté, il est RECALCULÉ
# par _refresh_actions depuis des compteurs. Une action facturée doit donc être un
# compteur, ET ce compteur doit être remis à zéro par _reset_turn_budget — sinon
# l'édition redevient gratuite dès le tour suivant.

import pytest

from utils.combat import resolve_action, _refresh_actions, _reset_turn_budget


def _joueur(actions_max=3, **overrides):
    j = {
        "id": "joueur_0", "nom": "Frida", "vivant": True, "pos": {"x": 3, "y": 5},
        "currentPV": 100, "pv_max": 100, "currentPM": 40, "pm_max": 40,
        "actions_max": actions_max, "actions_restantes": actions_max,
        "attaques": 0, "ramasses": 0, "consommes": 0, "sorts": 0, "competences": 0,
        "editions": 0, "penalites": 0, "cells_moved": 0,
        "deplacement": 4, "initiative": 30, "charge": 0, "charge_max": 200,
    }
    j.update(overrides)
    return j


def _combat(joueur):
    return {
        "_id": "combat:test", "type": "combat", "status": "active", "tour": 1, "log": [],
        "ordre_initiative": ["joueur_0", "monstre_0"], "acteur_courant_index": 0,
        "joueurs": [joueur],
        # `actions_max` est indispensable : épuiser ses actions fait PASSER LE TOUR, et
        # _reset_turn_budget s'applique alors au monstre.
        "monstres": [{"id": "monstre_0", "nom": "Loup", "vivant": True,
                      "pos": {"x": 3, "y": 1}, "currentPV": 20, "pv_max": 20,
                      "pa": 5, "ag": 30, "ch": 0, "cc": 50, "degats_cc": "1D6",
                      "pm_def": 30, "initiative": 20, "deplacement": 3, "xp_reward": 5,
                      "actions_max": 2, "actions_restantes": 2}],
        "grid": {"dims": {"x": 7, "y": 7}, "cells": [[1] * 7 for _ in range(7)], "nav": {}},
    }


def test_editer_barre_coute_une_action():
    j = _joueur(actions_max=3)
    combat = _combat(j)
    res = resolve_action(combat, "editer_barre")

    assert res.get("edition_barre") is True
    assert j["editions"] == 1
    assert j["actions_restantes"] == 2


def test_editer_barre_journalise():
    """Sans ligne de journal, la disparition d'une action serait inexplicable."""
    j = _joueur()
    combat = _combat(j)
    resolve_action(combat, "editer_barre")
    assert any("réorganise" in e["texte"] for e in combat["log"])


def test_editer_barre_ne_touche_pas_au_personnage():
    """Le moteur ne débite que le TEMPS : le contenu des cases n'est pas de son ressort."""
    j = _joueur()
    combat = _combat(j)
    resolve_action(combat, "editer_barre")
    assert "slots_actions" not in j


def test_plusieurs_entrees_facturees_separement():
    """Sortir puis rentrer dans le mode édition coûte une seconde action."""
    j = _joueur(actions_max=3)
    combat = _combat(j)
    resolve_action(combat, "editer_barre")
    resolve_action(combat, "editer_barre")
    assert j["editions"] == 2
    assert j["actions_restantes"] == 1


def test_refuse_sans_action_restante():
    """Budget épuisé par une attaque : la garde en tête de resolve_action refuse.
    (On épuise via un compteur plutôt qu'en éditant, sinon consommer la dernière action
    ferait tourner le tour et le joueur reviendrait avec un budget neuf.)"""
    j = _joueur(actions_max=1, attaques=1)
    _refresh_actions(j)
    assert j["actions_restantes"] == 0

    res = resolve_action(_combat(j), "editer_barre")
    assert "error" in res
    assert j["editions"] == 0          # rien n'a été facturé


def test_consommer_la_derniere_action_termine_le_tour():
    """Cas limite assumé : entrer en mode édition avec une seule action restante rend
    la main. L'action a été payée — le panneau reste utilisable côté client, les
    écritures de slots ne passant pas par le moteur de combat."""
    j = _joueur(actions_max=1)
    combat = _combat(j)
    resolve_action(combat, "editer_barre")
    # Le tour a bouclé (monstre puis retour au joueur) : budget neuf, compteur remis à 0.
    assert j["editions"] == 0
    assert j["actions_restantes"] == 1
    assert any("réorganise" in e["texte"] for e in combat["log"])


def test_le_compteur_est_remis_a_zero_au_tour_suivant():
    """RÉGRESSION : sans la remise à zéro dans _reset_turn_budget, `editions` s'accumule
    et le joueur perdrait définitivement une action par édition passée."""
    j = _joueur(actions_max=3)
    combat = _combat(j)
    resolve_action(combat, "editer_barre")
    assert j["actions_restantes"] == 2

    _reset_turn_budget(j)
    assert j["editions"] == 0
    assert j["actions_restantes"] == 3


def test_editions_compte_dans_le_budget_avec_les_autres_compteurs():
    """`_refresh_actions` doit additionner `editions` comme les autres consommations."""
    j = _joueur(actions_max=4, editions=2, attaques=1)
    _refresh_actions(j)
    assert j["actions_restantes"] == 1


# ── À QUI appartient la barre affichée ───────────────────────────────────────────
# RÉGRESSION : les écritures de slots passent par le chokepoint `_acteur`, qui SANS
# `compagnon_id` retombe sur le personnage principal. Le client doit donc viser l'acteur
# courant — sans quoi réorganiser la barre d'un compagnon écrit sur le doc du principal,
# et la réponse renvoie la barre du principal, affichée comme celle du compagnon.
# Ces tests figent les deux replis dont dépend `acteurCompagnonId()` côté client.

def _combat_groupe(index_actif):
    principal = _joueur()
    principal["character_id"] = "character:principal"
    compagnon = _joueur(); compagnon["id"] = "joueur_1"
    compagnon["character_id"] = "aventurier:compagnon"
    combat = _combat(principal)
    combat["character_id"] = "character:principal"
    combat["joueurs"] = [principal, compagnon]
    combat["ordre_initiative"] = ["joueur_0", "joueur_1", "monstre_0"]
    combat["acteur_courant_index"] = index_actif
    return combat


def test_acteur_courant_est_le_compagnon_quand_c_est_son_tour():
    from routers.combat import _actor_character_id
    assert _actor_character_id(_combat_groupe(1)) == "aventurier:compagnon"


def test_repli_sur_le_principal_pendant_un_tour_de_monstre():
    from routers.combat import _actor_character_id
    assert _actor_character_id(_combat_groupe(2)) == "character:principal"


def test_joueur_0_est_bien_le_principal():
    """Le client replie sur `joueurs[0]`, le serveur sur `combat["character_id"]` : les
    deux doivent désigner le MÊME personnage, sinon la barre affichée et la cible
    d'écriture divergent pendant un tour de monstre. `create_combat_doc` construit
    `joueur_0` depuis le personnage principal — c'est ce contrat qu'on fige ici."""
    from utils.combat import build_joueur_snapshot
    principal = {
        "_id": "character:principal", "nom": "Frida", "voc": "guerrier", "race": "humain",
        "caracteristiques_current": {"V": 5, "F": 40, "R": 30, "Ag": 40,
                                     "Vol": 20, "Int": 20, "Cha": 20, "Ch": 20},
        "vocations_niveaux": {"guerrier": 1}, "currentPV": 100, "currentPM": 40,
        "inventaire": [], "slots": {},
    }
    snap = build_joueur_snapshot(principal, joueur_index=0)
    assert snap["id"] == "joueur_0"
    assert snap["character_id"] == principal["_id"]
