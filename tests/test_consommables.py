# tests/test_consommables.py
#
# Tests des consommables à effet de gameplay. Import de utils.* → dépend de db.config
# (connexion CouchDB à l'import) : à lancer dans le conteneur, comme le reste.

import pytest

from utils.consommables import (
    effets_de, est_consommable, effet_instantane, caracts_avec_buffs, regen_bonus,
    esquive_bonus, caracts_detail,
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


def test_buff_v_applique():
    # V se buffe comme les autres caracts, à SON échelle (1-10) : une dague +1 V accélère
    # bel et bien le personnage (deplacement, initiative, cd).
    perso = _perso(effets_actifs=[{"buffs": {"V": 1}, "restants": 3}])
    assert caracts_avec_buffs(perso)["V"] == 6


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


# ── équipement comme source de buffs (champ item `bonus`, agrégé dans equipment_bonus) ──

def _eq_bonus(buffs, nom="Dague", icon="🗡️"):
    """Forme d'EquipmentBonus.model_dump() (seuls les champs lus par le chokepoint)."""
    return {"pv": 0, "pm": 0, "pa": 0, "malus_depl": 0, "cc_bonus": 0, "cd_bonus": 0,
            "degats_bonus": 0, "degats_dice": "", "initiative": 0,
            "buffs": dict(buffs),
            "buffs_sources": [{"nom": nom, "icon": icon, "buffs": dict(buffs)}]}


def test_equipement_buffe_les_caracts():
    perso = _perso(equipment_bonus=_eq_bonus({"Ag": 3, "V": 1}))
    buffed = caracts_avec_buffs(perso)
    assert buffed["Ag"] == 33 and buffed["V"] == 6


def test_equipement_competences_et_effets_se_cumulent():
    perso = _perso(
        equipment_bonus=_eq_bonus({"F": 3}),
        competences_bonus={"buffs": {"F": 4}, "regen_pv": 0, "regen_pm": 0, "esquive": 0},
        effets_actifs=[{"buffs": {"F": 10}, "restants": 2}],
    )
    assert caracts_avec_buffs(perso)["F"] == 57      # 40 + 3 + 4 + 10


def test_equipement_neutre_pour_regen_et_esquive():
    # EquipmentBonus ne porte ni regen_* ni esquive : la source est inerte pour ces helpers
    # (ses champs pv/pm sont des bonus de DÉRIVÉES, à ne pas confondre avec de la régén).
    perso = _perso(equipment_bonus=_eq_bonus({"Ag": 3}))
    perso["equipment_bonus"]["pv"] = 10
    assert regen_bonus(perso) == (0, 0)
    assert esquive_bonus(perso) == 0


# ── caracts_detail (grille « Profil modifié ») ───────────────────────────────────

def test_caracts_detail_ventile_les_sources_par_origine():
    perso = _perso(
        equipment_bonus=_eq_bonus({"Ag": 3}, nom="Dague"),
        competences_bonus={"buffs": {"F": 4}, "regen_pv": 0, "regen_pm": 0, "esquive": 0,
                           "buffs_sources": [{"nom": "Maîtrise", "icon": "🗡️",
                                              "buffs": {"F": 4}}]},
        effets_actifs=[{"nom": "Potion", "icon": "🧪", "buffs": {"F": 10}, "restants": 2}],
    )
    detail = caracts_detail(perso)

    assert detail["Ag"]["base"] == 30 and detail["Ag"]["total"] == 33
    assert detail["Ag"]["delta"] == 3
    assert detail["Ag"]["sources"] == [
        {"origine": "equipement", "nom": "Dague", "icon": "🗡️", "delta": 3}]

    assert detail["F"]["total"] == 54 and detail["F"]["delta"] == 14
    origines = {(s["origine"], s["nom"], s["delta"]) for s in detail["F"]["sources"]}
    assert origines == {("effet", "Potion", 10), ("competence", "Maîtrise", 4)}


def test_caracts_detail_caract_sans_modificateur():
    detail = caracts_detail(_perso())
    assert detail["R"] == {"base": 40, "total": 40, "delta": 0, "sources": []}


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
