# tests/test_consommables.py
#
# Tests des consommables à effet de gameplay. Import de utils.* → dépend de db.config
# (connexion CouchDB à l'import) : à lancer dans le conteneur, comme le reste.

import pytest

from utils.consommables import (
    effets_de, est_consommable, effet_instantane, caracts_avec_buffs, regen_bonus,
    empiler_effet, appliquer_instantane, tick_effets, effets_actifs_payload,
)


def _potion(**effets):
    return {"_id": "item:potion", "nom": "Potion", "icon": "🧪",
            "categorie": "consommable", "poids": 0.2, "effets": effets}


# ── est_consommable / effet_instantane ──────────────────────────────────────────

def test_consommable_sans_effets_est_inerte():
    # Rétro-compat : Torche/Bougie (categorie consommable, pas d'effets) → pas consommable.
    assert not est_consommable({"categorie": "consommable"})
    assert not est_consommable({"categorie": "consommable", "effets": {}})


def test_categorie_non_consommable_ignoree():
    assert not est_consommable({"categorie": "arme", "effets": {"pv": 10}})


def test_consommable_actif():
    assert est_consommable(_potion(pv=40))
    assert est_consommable(_potion(buffs={"F": 10}, duree=5))
    assert est_consommable(_potion(regen_pv=2, duree=3))


def test_effet_instantane_eligibilite_combat():
    assert effet_instantane(_potion(pv=40))
    assert effet_instantane(_potion(pm=15))
    assert not effet_instantane(_potion(buffs={"F": 10}, duree=5))  # buff pur → hors combat
    assert not effet_instantane(_potion(regen_pv=2, duree=3))


def test_effets_de_normalise_valeurs_invalides():
    eff = effets_de(_potion(pv="abc", pm=-5, buffs={"F": "x", "Ag": 10}, duree=3))
    assert eff["pv"] == 0 and eff["pm"] == 0
    assert eff["buffs"] == {"Ag": 10}
    assert eff["duree"] == 3


# ── caracts_avec_buffs ───────────────────────────────────────────────────────────

def _perso(**extra):
    base = {
        "caracteristiques_current": {"V": 5, "F": 40, "R": 40, "Ag": 30,
                                     "Vol": 30, "Int": 30, "Cha": 20, "Ch": 20},
        "currentPV": 100, "currentPM": 50,
    }
    base.update(extra)
    return base


def test_buffs_sommes_multi_effets():
    perso = _perso(effets_actifs=[
        {"buffs": {"F": 10}, "restants": 3},
        {"buffs": {"F": 5, "Ag": 10}, "restants": 1},
    ])
    buffed = caracts_avec_buffs(perso)
    assert buffed["F"] == 55 and buffed["Ag"] == 40
    assert buffed["R"] == 40  # non buffé, inchangé


def test_buffs_ne_mutent_pas_l_original():
    perso = _perso(effets_actifs=[{"buffs": {"F": 10}, "restants": 3}])
    caracts_avec_buffs(perso)
    assert perso["caracteristiques_current"]["F"] == 40


def test_buff_v_ignore():
    # V reste sur l'échelle 1-10 : jamais buffé, même si la donnée en contient un.
    perso = _perso(effets_actifs=[{"buffs": {"V": 5}, "restants": 3}])
    assert caracts_avec_buffs(perso)["V"] == 5


def test_buff_caract_absente_ignoree():
    perso = {"caracteristiques_current": {"F": 40},
             "effets_actifs": [{"buffs": {"Xyz": 10}, "restants": 1}]}
    assert "Xyz" not in caracts_avec_buffs(perso)


def test_malus_clampe_a_zero():
    perso = _perso(effets_actifs=[{"buffs": {"Cha": -50}, "restants": 2}])
    assert caracts_avec_buffs(perso)["Cha"] == 0


def test_sans_effets_actifs_copie_identique():
    perso = _perso()
    assert caracts_avec_buffs(perso) == perso["caracteristiques_current"]


# ── empiler_effet / appliquer_instantane ────────────────────────────────────────

def test_empiler_effet_a_duree():
    perso = _perso()
    entry = empiler_effet(perso, _potion(buffs={"F": 10}, regen_pv=2, duree=5))
    assert entry is not None
    assert perso["effets_actifs"] == [entry]
    assert entry["restants"] == 5 and entry["buffs"] == {"F": 10} and entry["regen_pv"] == 2


def test_empiler_effet_instantane_pur_ne_cree_rien():
    perso = _perso()
    assert empiler_effet(perso, _potion(pv=40)) is None
    assert perso.get("effets_actifs", []) == []


def test_empilement_deux_exemplaires():
    perso = _perso()
    item = _potion(buffs={"F": 10}, duree=5)
    empiler_effet(perso, item)
    empiler_effet(perso, item)
    assert len(perso["effets_actifs"]) == 2
    assert caracts_avec_buffs(perso)["F"] == 60


def test_appliquer_instantane_clampe_aux_max():
    perso = _perso(currentPV=180, currentPM=50)
    rendu = appliquer_instantane(perso, _potion(pv=40, pm=15), pv_max=200, pm_max=60)
    assert perso["currentPV"] == 200 and rendu["pv_rendu"] == 20
    assert perso["currentPM"] == 60 and rendu["pm_rendu"] == 10


# ── tick_effets / regen_bonus ────────────────────────────────────────────────────

def test_tick_decremente_et_purge():
    perso = _perso(effets_actifs=[
        {"nom": "A", "buffs": {}, "restants": 2},
        {"nom": "B", "buffs": {}, "restants": 1},
    ])
    expires = tick_effets(perso)
    assert [e["nom"] for e in expires] == ["B"]
    assert [e["restants"] for e in perso["effets_actifs"]] == [1]


def test_tick_sans_champ_no_op():
    perso = {"caracteristiques_current": {}}
    assert tick_effets(perso) == []


def test_regen_bonus_somme():
    perso = _perso(effets_actifs=[
        {"regen_pv": 2, "regen_pm": 1, "restants": 3},
        {"regen_pv": 3, "restants": 1},
    ])
    assert regen_bonus(perso) == (5, 1)


def test_effets_actifs_payload_copies():
    perso = _perso(effets_actifs=[{"nom": "A", "restants": 2}])
    payload = effets_actifs_payload(perso)
    payload[0]["restants"] = 99
    assert perso["effets_actifs"][0]["restants"] == 2


# ── Budget d'actions en combat (compteur `consommes`) ───────────────────────────

from utils.combat import _refresh_actions, _reset_turn_budget, resolve_action


def test_refresh_actions_compte_les_consommations():
    actor = {"actions_max": 3, "attaques": 1, "ramasses": 0, "consommes": 1,
             "cells_moved": 0, "deplacement": 4}
    _refresh_actions(actor)
    assert actor["actions_restantes"] == 1


def test_refresh_actions_retro_compat_sans_consommes():
    # Vieux docs combat sans le compteur : .get(..., 0) partout.
    actor = {"actions_max": 2, "attaques": 1, "cells_moved": 0, "deplacement": 4}
    _refresh_actions(actor)
    assert actor["actions_restantes"] == 1


def test_reset_turn_budget_remet_consommes():
    actor = {"actions_max": 2, "attaques": 1, "ramasses": 0, "consommes": 1,
             "cells_moved": 2, "actions_restantes": 0}
    _reset_turn_budget(actor)
    assert actor["consommes"] == 0 and actor["actions_restantes"] == 2


# ── resolve_action("consommer") ─────────────────────────────────────────────────

def _combat_doc():
    """Combat minimal : grille ouverte en ligne (pas de battle_map_id → pas de DB),
    monstre vivant ÉLOIGNÉ pour ne pas déclencher son tour, joueur à 3 actions."""
    joueur = {
        "id": "joueur_0", "nom": "Testeur",
        "currentPV": 100, "pv_max": 160, "currentPM": 20, "pm_max": 60,
        "actions_max": 3, "actions_restantes": 3,
        "attaques": 0, "ramasses": 0, "consommes": 0, "cells_moved": 0,
        "deplacement": 4, "deplacement_base": 4,
        "charge": 10.0, "charge_max": 200,
        "pos": {"x": 1, "y": 1}, "facing": 0, "portee": 1,
    }
    monstre = {"id": "monstre_0", "nom": "Loup", "vivant": True,
               "currentPV": 20, "pv_max": 20, "pos": {"x": 8, "y": 8}}
    return {
        "status": "active", "tour": 1, "log": [],
        "joueurs": [joueur], "monstres": [monstre],
        "ordre_initiative": ["joueur_0", "monstre_0"],
        "acteur_courant_index": 0,
        "grid": {"dims": {"x": 10, "y": 10}, "cells": [[1] * 10 for _ in range(10)]},
    }


def test_consommer_refuse_sans_item():
    doc = _combat_doc()
    assert "error" in resolve_action(doc, "consommer", item=None)


def test_consommer_refuse_item_buff_pur():
    doc = _combat_doc()
    res = resolve_action(doc, "consommer", item=_potion(buffs={"F": 10}, duree=5))
    assert "error" in res
    assert doc["joueurs"][0]["consommes"] == 0


def test_consommer_applique_et_decompte():
    doc = _combat_doc()
    res = resolve_action(doc, "consommer", item=_potion(pv=40, pm=15))
    j = doc["joueurs"][0]
    assert res["consomme"] is True
    assert j["currentPV"] == 140 and j["currentPM"] == 35
    assert res["pv_rendu"] == 40 and res["pm_rendu"] == 15
    assert j["consommes"] == 1 and j["actions_restantes"] == 2
    assert j["charge"] == 9.8  # poids de la potion (0.2) retiré du sac
    assert doc["log"] and doc["log"][-1]["kind"] == "sys"


def test_consommer_clampe_aux_max_du_snapshot():
    doc = _combat_doc()
    doc["joueurs"][0]["currentPV"] = 150
    res = resolve_action(doc, "consommer", item=_potion(pv=40))
    assert doc["joueurs"][0]["currentPV"] == 160
    assert res["pv_rendu"] == 10
