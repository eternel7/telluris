# tests/test_combat_effets.py
#
# Effets à DURÉE pendant un combat : un sort/une compétence/un consommable à `duree`
# s'empile sur les effets VIVANTS du snapshot, pèse réellement sur les dérivées
# (_refresh_snapshot_stats), se décrémente au tour de son porteur (_tick_effets_combat)
# et remonte sur le personnage à la fin (_finalize_membre).
#
# Logique pure : aucun accès DB (build_joueur_snapshot est exercé via un character
# minimal, sans slots → _weapon_attacks ne lit aucun item).

import pytest

from utils import combat as combat_mod
from utils.combat import (
    resolve_action, build_joueur_snapshot, _refresh_snapshot_stats,
    _tick_effets_combat, _reset_turn_budget, _empiler_effet_combat, _do_attack_on,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────────

def _character(**overrides):
    """Personnage minimal suffisant pour build_joueur_snapshot (pas d'équipement :
    `slots` vide → aucun get_doc, la fonction reste pure)."""
    char = {
        "_id": "character:test_1", "nom": "Frida", "voc": "guerrier", "race": "humain",
        "caracteristiques_current": {"V": 5, "F": 40, "R": 30, "Ag": 40,
                                     "Vol": 20, "Int": 20, "Cha": 20, "Ch": 20},
        "vocations_niveaux": {"guerrier": 1},
        "currentPV": 100, "currentPM": 40,
        "inventaire": [], "slots": {},
    }
    char.update(overrides)
    return char


def _sort_doc(**effets):
    return {"id": "sort:givre", "nom": "Armure de givre", "icon": "🧊",
            "cible": "soi", "cout_pm": 3, "portee": 1, "effets": effets}


def _combat(joueur, monstres=None):
    if monstres is None:
        monstres = [{"id": "monstre_0", "nom": "Loup", "vivant": True,
                     "pos": {"x": 3, "y": 4}, "currentPV": 20, "pv_max": 20,
                     "pa": 5, "ag": 30, "ch": 0, "cc": 50, "degats_cc": "1D6",
                     "pm_def": 30, "initiative": 20, "deplacement": 3, "xp_reward": 5}]
    joueur.setdefault("pos", {"x": 3, "y": 5})
    joueur.setdefault("vivant", True)
    return {
        "_id": "combat:test", "type": "combat", "status": "active", "tour": 1, "log": [],
        "ordre_initiative": ["joueur_0"] + [m["id"] for m in monstres],
        "acteur_courant_index": 0,
        "joueurs": [joueur], "monstres": monstres,
        "grid": {"dims": {"x": 7, "y": 7},
                 "cells": [[1] * 7 for _ in range(7)], "nav": {}},
    }


# ── Le snapshot porte de quoi se recalculer ──────────────────────────────────────

def test_snapshot_porte_la_base_permanente_et_les_effets_entrants():
    char = _character(effets_actifs=[
        {"nom": "Potion de force", "icon": "🧪", "buffs": {"F": 10},
         "regen_pv": 0, "regen_pm": 0, "esquive": 0, "restants": 3},
    ])
    snap = build_joueur_snapshot(char)
    # caracts_base = SANS les effets temporaires ; les dérivées, elles, en tiennent compte.
    assert snap["caracts_base"]["F"] == 40
    assert [e["restants"] for e in snap["effets_actifs"]] == [3]
    assert snap["voc_niveau"] == 1
    assert "equipment_bonus" in snap


def test_snapshot_et_refresh_immediat_donnent_les_memes_valeurs():
    # Invariant fondateur : le snapshot construit à l'entrée (caracts_avec_buffs complet)
    # et un recalcul depuis caracts_base + effets doivent coïncider, sinon entrer en
    # combat puis poser un effet changerait les stats sans raison.
    char = _character(effets_actifs=[
        {"nom": "Bénédiction", "icon": "✨", "buffs": {"F": 10, "R": 6},
         "regen_pv": 0, "regen_pm": 0, "esquive": 4, "restants": 3},
    ])
    snap = build_joueur_snapshot(char)
    avant = {k: snap[k] for k in ("cc", "cd", "pa", "pv_max", "pm_max", "degats_cc",
                                  "initiative", "esquive")}
    _refresh_snapshot_stats(snap)
    assert {k: snap[k] for k in avant} == avant


def test_les_copies_protegent_le_doc_perso():
    # Le combat ne doit pas muter les effets du personnage avant sa conclusion.
    entree = {"nom": "Potion", "icon": "🧪", "buffs": {"F": 10},
              "regen_pv": 0, "regen_pm": 0, "esquive": 0, "restants": 3}
    char = _character(effets_actifs=[entree])
    snap = build_joueur_snapshot(char)
    snap["effets_actifs"][0]["restants"] = 1
    assert entree["restants"] == 3


# ── Un buff acquis en combat pèse sur les dérivées ───────────────────────────────

def test_buff_lance_en_combat_modifie_les_derivees():
    snap = build_joueur_snapshot(_character())
    combat = _combat(snap)
    avant = {k: snap[k] for k in ("cc", "pa", "pv_max")}

    res = resolve_action(combat, "sort", sort={
        "doc": _sort_doc(buffs={"F": 20, "R": 10}, duree=3), "effets": {
            "buffs": {"F": 20, "R": 10}, "duree": 3}})

    assert "error" not in res
    assert snap["cc"] > avant["cc"]          # cc = (F + Ag*3)//4
    assert snap["pa"] > avant["pa"]          # pa = R // FACTEUR
    assert snap["pv_max"] > avant["pv_max"]  # pv_max = R*3 + F


def test_esquive_acquise_en_combat_protege_reellement(monkeypatch):
    # Le seuil de toucher physique est 50 + cc − (ag + esquive) : +40 d'esquive doit
    # faire manquer un coup qui passait.
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 55)
    attaquant = {"nom": "Loup", "cc": 50, "ch": 0, "degats_cc": "1D6",
                 "actions_max": 2, "actions_restantes": 2, "deplacement": 3,
                 "cells_moved": 0, "attaques": 0}

    sans = build_joueur_snapshot(_character())
    combat_sans = _combat(sans)
    _do_attack_on(combat_sans, attaquant, sans)
    assert sans["currentPV"] < 100      # touché

    avec = build_joueur_snapshot(_character())
    combat_avec = _combat(avec)
    _empiler_effet_combat(avec, {"nom": "Armure de givre", "icon": "🧊"},
                          {"esquive": 40, "duree": 3}, tour=1)
    assert avec["esquive"] == 40
    _do_attack_on(combat_avec, attaquant, avec)
    assert avec["currentPV"] == 100     # manqué


def test_actions_max_et_charge_max_restent_figes():
    # Anti-régression : les recalculer donnerait des actions gratuites au cast et
    # rendrait rétroactivement surchargé à l'expiration.
    snap = build_joueur_snapshot(_character())
    actions_max, charge_max = snap["actions_max"], snap["charge_max"]
    _empiler_effet_combat(snap, {"nom": "Hâte", "icon": "💨"},
                          {"buffs": {"Ag": 40, "F": 40}, "duree": 3}, tour=1)
    assert snap["actions_max"] == actions_max
    assert snap["charge_max"] == charge_max


# ── Tick : durée = tours du porteur ──────────────────────────────────────────────

def test_effet_expire_apres_sa_duree_en_tours_du_porteur():
    snap = build_joueur_snapshot(_character())
    combat = _combat(snap)
    cc_initial = snap["cc"]
    _empiler_effet_combat(snap, {"nom": "Force du géant", "icon": "💪"},
                          {"buffs": {"F": 20}, "duree": 2}, tour=1)
    assert snap["cc"] > cc_initial

    # Tour de pose : épargné (l'effet doit servir au moins le tour où il est lancé).
    _tick_effets_combat(combat, snap)
    assert snap["effets_actifs"][0]["restants"] == 2

    combat["tour"] = 2
    _tick_effets_combat(combat, snap)
    assert snap["effets_actifs"][0]["restants"] == 1
    assert snap["cc"] > cc_initial

    combat["tour"] = 3
    _tick_effets_combat(combat, snap)
    assert snap["effets_actifs"] == []
    assert snap["cc"] == cc_initial       # dérivées revenues à leur valeur d'entrée
    assert any("se dissipe" in e.get("texte", "") for e in combat["log"])


def test_effet_entrant_tick_aussi():
    # Ferme l'exploit : une potion bue juste avant d'entrer ne dure plus tout le combat.
    char = _character(effets_actifs=[
        {"nom": "Potion", "icon": "🧪", "buffs": {"F": 10},
         "regen_pv": 0, "regen_pm": 0, "esquive": 0, "restants": 2},
    ])
    snap = build_joueur_snapshot(char)
    combat = _combat(snap)
    _tick_effets_combat(combat, snap)
    assert snap["effets_actifs"][0]["restants"] == 1


def test_regen_applique_au_tour_du_porteur_et_clampe():
    snap = build_joueur_snapshot(_character(currentPV=10, currentPM=0))
    combat = _combat(snap)
    _empiler_effet_combat(snap, {"nom": "Régénération", "icon": "🌿"},
                          {"regen_pv": 5, "regen_pm": 3, "duree": 5}, tour=1)
    _tick_effets_combat(combat, snap)
    assert snap["currentPV"] == 15
    assert snap["currentPM"] == 3

    # Clamp au maximum : la régén ne dépasse jamais pv_max.
    snap["currentPV"] = snap["pv_max"] - 1
    combat["tour"] = 2
    _tick_effets_combat(combat, snap)
    assert snap["currentPV"] == snap["pv_max"]


def test_expiration_reclampe_les_pv():
    # Un buff de R relève pv_max ; à son expiration, les PV ne doivent pas rester
    # au-dessus du nouveau plafond.
    snap = build_joueur_snapshot(_character())
    combat = _combat(snap)
    pv_max_base = snap["pv_max"]
    _empiler_effet_combat(snap, {"nom": "Vigueur", "icon": "❤️"},
                          {"buffs": {"R": 20}, "duree": 1}, tour=1)
    snap["currentPV"] = snap["pv_max"]
    assert snap["currentPV"] > pv_max_base

    combat["tour"] = 2
    _tick_effets_combat(combat, snap)
    assert snap["pv_max"] == pv_max_base
    assert snap["currentPV"] == pv_max_base


def test_le_tick_passe_par_reset_turn_budget():
    # Le tick doit être branché sur le seul hook « début de tour » du moteur, sinon un
    # effet ne se décrémenterait jamais en jeu réel.
    snap = build_joueur_snapshot(_character())
    combat = _combat(snap)
    snap["effets_actifs"] = [{"nom": "X", "icon": "✨", "buffs": {},
                              "regen_pv": 0, "regen_pm": 0, "esquive": 0, "restants": 2}]
    _reset_turn_budget(snap, combat)
    assert snap["effets_actifs"][0]["restants"] == 1


# ── Rétro-compatibilité : combats déjà en base ───────────────────────────────────

def test_snapshot_sans_caracts_base_traverse_sans_dommage():
    # Un combat créé avant la feature n'a ni caracts_base ni effets_actifs : les deux
    # fonctions doivent être des no-op, pas des KeyError.
    vieux = {"id": "joueur_0", "nom": "Frida", "vivant": True, "currentPV": 60,
             "pv_max": 80, "currentPM": 20, "pm_max": 30, "cc": 50, "pa": 5,
             "actions_max": 3, "actions_restantes": 3}
    combat = _combat(dict(vieux))
    snap = combat["joueurs"][0]
    _refresh_snapshot_stats(snap)
    _tick_effets_combat(combat, snap)
    assert snap["cc"] == 50 and snap["pa"] == 5 and snap["pv_max"] == 80


# ── Remontée sur le personnage en fin de combat ──────────────────────────────────

def _finalize(monkeypatch, snap, char, status="victoire"):
    """Exécute _finalize_membre en neutralisant la sauvegarde (aucune DB en test)."""
    monkeypatch.setattr(combat_mod, "save_doc", lambda doc: doc)
    combat = _combat(snap)
    combat["xp_gagnee"] = 0
    combat_mod._finalize_membre(combat, snap, char, status)
    return char


def test_effet_restant_remonte_sur_le_personnage(monkeypatch):
    char = _character()
    snap = build_joueur_snapshot(char)
    _empiler_effet_combat(snap, {"nom": "Armure de givre", "icon": "🧊"},
                          {"buffs": {"R": 6}, "duree": 3}, tour=1)
    _finalize(monkeypatch, snap, char)
    assert [e["nom"] for e in char["effets_actifs"]] == ["Armure de givre"]
    # `pose_tour` n'a de sens qu'en combat : il ne suit pas.
    assert "pose_tour" not in char["effets_actifs"][0]


def test_effet_expire_ne_remonte_pas(monkeypatch):
    char = _character(effets_actifs=[
        {"nom": "Potion", "icon": "🧪", "buffs": {"F": 10},
         "regen_pv": 0, "regen_pm": 0, "esquive": 0, "restants": 1},
    ])
    snap = build_joueur_snapshot(char)
    combat = _combat(snap)
    _tick_effets_combat(combat, snap)          # restants 1 → 0, purgé
    _finalize(monkeypatch, snap, char)
    assert char["effets_actifs"] == []


def test_pas_de_duplication_a_la_remontee(monkeypatch):
    # L'entrée du snapshot EST celle du personnage (copiée à l'entrée) : la remonter
    # doit écraser, jamais s'ajouter.
    char = _character(effets_actifs=[
        {"nom": "Potion", "icon": "🧪", "buffs": {"F": 10},
         "regen_pv": 0, "regen_pm": 0, "esquive": 0, "restants": 5},
    ])
    snap = build_joueur_snapshot(char)
    _finalize(monkeypatch, snap, char)
    assert len(char["effets_actifs"]) == 1


# ── Le porteur n'est pas forcément joueur_0 ──────────────────────────────────────

def test_un_compagnon_beneficie_de_son_propre_buff():
    principal = build_joueur_snapshot(_character(), joueur_index=0)
    compagnon = build_joueur_snapshot(
        _character(_id="aventurier:bob", nom="Bob"), joueur_index=1)
    combat = _combat(principal)
    combat["joueurs"].append(compagnon)
    combat["ordre_initiative"].insert(1, "joueur_1")
    combat["acteur_courant_index"] = 1       # c'est au compagnon de jouer
    cc_principal = principal["cc"]

    # L'acteur est celui que désigne `acteur_courant_index`, pas forcément joueur_0.
    res = resolve_action(combat, "sort", sort={
        "doc": _sort_doc(buffs={"F": 20}, duree=3),
        "effets": {"buffs": {"F": 20}, "duree": 3}})

    assert "error" not in res
    assert [e["nom"] for e in compagnon["effets_actifs"]] == ["Armure de givre"]
    # Le buff du compagnon ne déteint pas sur le principal.
    assert principal.get("effets_actifs") == []
    assert principal["cc"] == cc_principal


# ── Non-cumul en combat (cf. utils/consommables : poser_effet / cumul_effets) ─────

def test_relancer_le_meme_sort_remplace_l_entree():
    # Une source = une entrée : relancer le même sort ne double pas le buff, il repart
    # de zéro (durée relancée). Sinon deux tours de cast suffiraient à empiler sans fin.
    snap = build_joueur_snapshot(_character())
    combat = _combat(snap)
    _empiler_effet_combat(snap, _sort_doc(), {"buffs": {"F": 20}, "duree": 3}, tour=1)
    cc_bufffe = snap["cc"]

    combat["tour"] = 2
    _tick_effets_combat(combat, snap)
    assert snap["effets_actifs"][0]["restants"] == 2
    _empiler_effet_combat(snap, _sort_doc(), {"buffs": {"F": 20}, "duree": 3}, tour=2)

    assert len(snap["effets_actifs"]) == 1
    assert snap["effets_actifs"][0]["restants"] == 3      # durée relancée
    assert snap["cc"] == cc_bufffe                        # le buff n'a PAS doublé


def test_deux_sorts_differents_ne_se_cumulent_pas_sur_la_meme_caract():
    # Deux sources différentes coexistent, mais sur une même caract seul le meilleur
    # compte — et l'expiration du plus fort fait ressortir le plus faible.
    char = _character()
    base = build_joueur_snapshot(_character())["cc"]
    snap = build_joueur_snapshot(char)
    combat = _combat(snap)
    _empiler_effet_combat(snap, {"id": "sort:faible", "nom": "Vigueur", "icon": "💪"},
                          {"buffs": {"F": 10}, "duree": 5}, tour=1)
    faible = snap["cc"]
    _empiler_effet_combat(snap, {"id": "sort:fort", "nom": "Force du géant", "icon": "🗿"},
                          {"buffs": {"F": 20}, "duree": 1}, tour=1)
    fort = snap["cc"]
    assert fort > faible > base

    combat["tour"] = 2
    _tick_effets_combat(combat, snap)        # le plus fort expire, le plus faible tient
    assert [e["nom"] for e in snap["effets_actifs"]] == ["Vigueur"]
    assert snap["cc"] == faible


def test_regen_non_cumulee_au_tick():
    # Deux régénérations en cours : seule la meilleure rend des PV/PM par tour.
    snap = build_joueur_snapshot(_character(currentPV=10, currentPM=0))
    combat = _combat(snap)
    _empiler_effet_combat(snap, {"id": "sort:a", "nom": "Régénération", "icon": "🌿"},
                          {"regen_pv": 5, "regen_pm": 3, "duree": 5}, tour=1)
    _empiler_effet_combat(snap, {"id": "sort:b", "nom": "Sève", "icon": "🍃"},
                          {"regen_pv": 2, "regen_pm": 4, "duree": 5}, tour=1)
    _tick_effets_combat(combat, snap)
    assert snap["currentPV"] == 15        # 10 + 5 (le meilleur), pas 10 + 7
    assert snap["currentPM"] == 4         # 0 + 4 (le meilleur), pas 0 + 7


def test_esquive_non_cumulee():
    snap = build_joueur_snapshot(_character())
    esquive_base = snap["esquive"]
    _empiler_effet_combat(snap, {"id": "sort:a", "nom": "Voile", "icon": "🌫️"},
                          {"esquive": 20, "duree": 3}, tour=1)
    _empiler_effet_combat(snap, {"id": "sort:b", "nom": "Brume", "icon": "💨"},
                          {"esquive": 15, "duree": 3}, tour=1)
    assert snap["esquive"] == esquive_base + 20
