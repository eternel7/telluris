# tests/test_competences.py
#
# Tests du système de compétences de vocation (miroir des sorts). Logique pure :
# utils/competences.py (normalisation, passives, apprentissage, choix de départ),
# le repli des passives dans utils/consommables.caracts_avec_buffs / regen_bonus,
# et la branche "competence" de resolve_action (utils/combat.py).

import pytest

from models import character_stats
from utils.consommables import caracts_avec_buffs, regen_bonus
from utils.competences import (
    normaliser_competence, est_passive, est_active,
    competence_utilisable_combat, competence_utilisable_exploration,
    empiler_effet_competence, bonus_passifs, recompute_competences_bonus,
    cout_apprentissage, vocation_choisit_competence, competences_apprenables,
    competences_depart_par_vocation, liste_competences_payload,
)
from utils import combat as combat_mod
from utils.combat import resolve_action


def _comp(**overrides):
    doc = {
        "_id": "competence:frappe", "type": "competence", "nom": "Frappe puissante",
        "icon": "⚔️", "description": "Un coup lourd.",
        "vocation": "guerrier", "niveau": 0, "mode": "active", "cout_pm": 0,
        "cible": "ennemi", "jet": "cc", "portee": 1,
        "effets": {"degats": "2D6"},
    }
    doc.update(overrides)
    return doc


def _passive(**overrides):
    doc = {
        "_id": "competence:maitrise", "type": "competence", "nom": "Maîtrise martiale",
        "icon": "🗡️", "vocation": "guerrier", "niveau": 0, "mode": "passive",
        "effets": {"buffs": {"F": 4}},
    }
    doc.update(overrides)
    return doc


# ── Normalisation ────────────────────────────────────────────────────────────────

def test_normaliser_rejette_les_non_competences():
    assert normaliser_competence({"type": "sort", "vocation": "guerrier"}) is None
    assert normaliser_competence({"type": "competence"}) is None   # vocation absente
    assert normaliser_competence(None) is None


def test_cout_pm_nul_est_valide():
    # Différence clé avec les sorts (qui exigent cout_pm > 0) : une compétence martiale
    # ne consomme aucune magie.
    comp = normaliser_competence(_comp(cout_pm=0))
    assert comp is not None and comp["cout_pm"] == 0


def test_defauts_de_normalisation():
    comp = normaliser_competence({
        "_id": "competence:x", "type": "competence", "vocation": "voleur",
    })
    assert comp["mode"] == "passive"      # défaut prudent : pas d'action
    assert comp["cible"] == "soi"
    assert comp["jet"] == "cc"
    assert comp["portee"] == 1
    assert comp["niveau"] == 0
    assert comp["effets"]["buffs"] == {}


def test_mode_et_jet_inconnus_retombent_sur_les_defauts():
    comp = normaliser_competence(_comp(mode="ultime", jet="psychique"))
    assert comp["mode"] == "passive" and comp["jet"] == "cc"


def test_buff_sur_v_filtre():
    # V est sur l'échelle 1-10 : jamais bufffé (règle partagée avec sorts/consommables).
    comp = normaliser_competence(_passive(effets={"buffs": {"V": 3, "F": 5}}))
    assert comp["effets"]["buffs"] == {"F": 5}


def test_buff_negatif_conserve():
    comp = normaliser_competence(_comp(effets={"buffs": {"F": 8, "Ag": -4}, "duree": 3}))
    assert comp["effets"]["buffs"] == {"F": 8, "Ag": -4}


# ── Éligibilité combat / exploration ─────────────────────────────────────────────

def test_utilisable_combat_exige_une_part_instantanee():
    assert competence_utilisable_combat(normaliser_competence(_comp())) is True
    assert competence_utilisable_combat(
        normaliser_competence(_comp(effets={"pv": 10}))) is True
    # Buff seul → perdu en combat (pas de tick), donc inutilisable.
    assert competence_utilisable_combat(
        normaliser_competence(_comp(effets={"buffs": {"F": 5}, "duree": 3}))) is False
    # Une passive n'est jamais une action.
    assert competence_utilisable_combat(normaliser_competence(_passive())) is False


def test_utilisable_exploration_exige_cible_soi():
    soin = normaliser_competence(_comp(cible="soi", cout_pm=6, effets={"pv": 12}))
    assert competence_utilisable_exploration(soin) is True
    buff = normaliser_competence(_comp(cible="soi", effets={"buffs": {"F": 8}, "duree": 3}))
    assert competence_utilisable_exploration(buff) is True
    # Ciblée ennemi → combat seulement.
    assert competence_utilisable_exploration(normaliser_competence(_comp())) is False
    assert competence_utilisable_exploration(normaliser_competence(_passive())) is False


def test_empiler_effet_competence():
    perso = {"effets_actifs": []}
    comp = normaliser_competence(_comp(cible="soi", effets={"buffs": {"F": 8}, "duree": 3}))
    entry = empiler_effet_competence(perso, comp)
    assert entry["restants"] == 3 and entry["buffs"] == {"F": 8}
    assert perso["effets_actifs"] == [entry]
    # Rien à empiler si pas de durée.
    assert empiler_effet_competence(perso, normaliser_competence(_comp(effets={"pv": 5}))) is None
    assert len(perso["effets_actifs"]) == 1


# ── Passives : bonus permanent ───────────────────────────────────────────────────

_DOCS = {
    "competence:maitrise": _passive(),
    "competence:vigueur": _passive(_id="competence:vigueur", nom="Vigueur",
                                   effets={"buffs": {"F": 2, "R": 3}, "regen_pv": 1}),
    "competence:frappe": _comp(),
}


def _get_doc(doc_id):
    return _DOCS.get(doc_id)


def _perso(**extra):
    base = {
        "caracteristiques_current": {"V": 5, "F": 40, "R": 40, "Ag": 30,
                                     "Vol": 40, "Int": 20, "Cha": 20, "Ch": 20},
        "currentPV": 100, "currentPM": 50,
        "voc": "guerrier",
        "inventaire": [], "slots": {},
        "vocations_niveaux": {"guerrier": 0},
        "competences_connues": [], "effets_actifs": [],
    }
    base.update(extra)
    return base


def test_bonus_passifs_somme_les_passives_et_ignore_les_actives():
    perso = _perso(competences_connues=["competence:maitrise", "competence:vigueur",
                                        "competence:frappe"])
    bonus = bonus_passifs(perso, _get_doc)
    assert bonus["buffs"] == {"F": 6, "R": 3}   # 4 + 2 ; l'active ne contribue pas
    assert bonus["regen_pv"] == 1 and bonus["regen_pm"] == 0


def test_recompute_competences_bonus_ecrit_le_champ():
    perso = _perso(competences_connues=["competence:maitrise"])
    recompute_competences_bonus(perso, _get_doc)
    assert perso["competences_bonus"] == {"buffs": {"F": 4}, "regen_pv": 0, "regen_pm": 0}


def test_passive_arrive_dans_les_caracts():
    # LE test clé : le bonus dénormalisé est replié par caracts_avec_buffs, donc une
    # passive est effective partout (fiche, exploration, snapshot de combat).
    perso = _perso(competences_connues=["competence:maitrise"])
    recompute_competences_bonus(perso, _get_doc)
    assert caracts_avec_buffs(perso)["F"] == 44
    # caracteristiques_current reste la valeur BRUTE (les buffs ne sont jamais stockés).
    assert perso["caracteristiques_current"]["F"] == 40


def test_passive_et_effet_actif_se_cumulent():
    perso = _perso(competences_connues=["competence:maitrise"],
                   effets_actifs=[{"buffs": {"F": 6}, "regen_pv": 2, "restants": 3}])
    recompute_competences_bonus(perso, _get_doc)
    assert caracts_avec_buffs(perso)["F"] == 50          # 40 + 4 (passive) + 6 (potion)
    assert regen_bonus(perso) == (2, 0)


def test_regen_passive_dans_regen_bonus():
    perso = _perso(competences_connues=["competence:vigueur"])
    recompute_competences_bonus(perso, _get_doc)
    assert regen_bonus(perso) == (1, 0)


def test_perso_sans_competences_inchange():
    # Rétro-compat : un personnage d'avant la feature n'a ni competences_connues ni
    # competences_bonus — caracts_avec_buffs/regen_bonus doivent se comporter comme avant.
    perso = {"caracteristiques_current": {"F": 40}}
    assert caracts_avec_buffs(perso) == {"F": 40}
    assert regen_bonus(perso) == (0, 0)


# ── Apprentissage ────────────────────────────────────────────────────────────────

def test_cout_apprentissage(monkeypatch):
    monkeypatch.setattr(character_stats, "COMPETENCE_COUT_COEFF", 2)
    assert cout_apprentissage(normaliser_competence(_comp(niveau=0))) == 2
    assert cout_apprentissage(normaliser_competence(_comp(niveau=3))) == 8


def test_vocation_choisit_competence_est_le_complement_des_sorts(monkeypatch):
    monkeypatch.setattr(character_stats, "SORT_VOCATIONS_DEPART", ["elementaliste", "pretre"])
    assert vocation_choisit_competence("guerrier") is True
    assert vocation_choisit_competence("paladin") is True    # hybride : pas de sort gratuit
    assert vocation_choisit_competence("elementaliste") is False
    assert vocation_choisit_competence(None) is False


def _find_docs(_selector):
    return [
        _passive(),                                                        # guerrier niv 0
        _comp(),                                                           # guerrier niv 0
        _comp(_id="competence:maitre_darmes", nom="Maître d'armes", niveau=3),
        _comp(_id="competence:coup_bas", nom="Coup bas", vocation="voleur"),
    ]


def test_competences_apprenables_filtre_vocation_niveau_et_connues(monkeypatch):
    monkeypatch.setattr(character_stats, "COMPETENCE_COUT_COEFF", 2)
    perso = _perso(competences_connues=["competence:maitrise"])
    ids = [c["id"] for c in competences_apprenables(perso, _find_docs)]
    # Vocation d'un autre (voleur) exclue, niveau 3 hors de portée, déjà connue exclue.
    assert ids == ["competence:frappe"]
    assert competences_apprenables(perso, _find_docs)[0]["cout_points"] == 2

    # Niveau de vocation 3 → la compétence de niveau 3 devient accessible.
    perso["vocations_niveaux"] = {"guerrier": 3}
    ids = [c["id"] for c in competences_apprenables(perso, _find_docs)]
    assert set(ids) == {"competence:frappe", "competence:maitre_darmes"}


def test_competences_depart_par_vocation():
    depart = competences_depart_par_vocation(_find_docs)
    # Seulement le niveau 0, groupé par vocation.
    assert set(depart) == {"guerrier", "voleur"}
    assert {c["id"] for c in depart["guerrier"]} == {"competence:maitrise", "competence:frappe"}
    assert {c["mode"] for c in depart["guerrier"]} == {"passive", "active"}


def test_liste_competences_payload_contextes():
    perso = _perso(competences_connues=["competence:maitrise", "competence:frappe"])
    # Exploration = catalogue complet (passive incluse), drapeau `utilisable`.
    explo = liste_competences_payload(perso, _get_doc, "exploration")
    assert [c["competence_id"] for c in explo] == ["competence:maitrise", "competence:frappe"]
    assert [c["utilisable"] for c in explo] == [False, False]  # passive / ciblée ennemi
    # Combat = seulement les actives à part instantanée.
    combat = liste_competences_payload(perso, _get_doc, "combat")
    assert [c["competence_id"] for c in combat] == ["competence:frappe"]


# ── resolve_action "competence" (combat) ─────────────────────────────────────────

def _monstre(mid, x, y, **extra):
    m = {"id": mid, "nom": "Loup", "vivant": True, "pos": {"x": x, "y": y},
         "currentPV": 20, "pv_max": 20, "pa": 5, "ag": 30, "pm_def": 30,
         "initiative": 20, "deplacement": 3, "xp_reward": 5}
    m.update(extra)
    return m


def _combat(joueur_extra=None, monstres=None):
    w, h = 7, 7
    joueur = {
        "id": "joueur_0", "nom": "Frida", "vivant": True,
        "currentPV": 60, "pv_max": 80, "currentPM": 20, "pm_max": 30,
        "actions_restantes": 3, "actions_max": 3,
        "cells_moved": 0, "attaques": 0, "ramasses": 0, "consommes": 0, "sorts": 0,
        "competences": 0,
        "pos": {"x": 3, "y": 5}, "portee": 1,
        "charge": 10.0, "charge_max": 100.0,
        "deplacement": 4, "deplacement_base": 4,
        "cc": 50, "cd": 40, "ag": 30, "pa": 5, "pm_def": 20,
        "toucher_magique": 50, "initiative": 30,
    }
    joueur.update(joueur_extra or {})
    if monstres is None:
        monstres = [_monstre("monstre_0", 3, 4)]   # adjacent (mêlée)
    return {
        "type": "combat", "status": "active", "tour": 1, "log": [],
        "ordre_initiative": ["joueur_0"] + [m["id"] for m in monstres],
        "acteur_courant_index": 0,
        "joueurs": [joueur], "monstres": monstres,
        "grid": {"dims": {"x": w, "y": h},
                 "cells": [[1] * w for _ in range(h)], "nav": {}},
    }


def test_competence_consomme_une_action(monkeypatch):
    # Le piège à éviter : sans le compteur dans _refresh_actions, une active serait gratuite.
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 1)
    combat = _combat()
    resolve_action(combat, "competence", cible_id="monstre_0",
                   competence=normaliser_competence(_comp()))
    assert combat["joueurs"][0]["competences"] == 1
    assert combat["joueurs"][0]["actions_restantes"] == 2


def test_competence_martiale_soustrait_les_pa(monkeypatch):
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 1)   # hit + dés à 1
    combat = _combat()
    res = resolve_action(combat, "competence", cible_id="monstre_0",
                         competence=normaliser_competence(_comp()))
    # 2D6 à 1 → 2 bruts − 5 PA → plancher à 1 (une frappe reste une frappe).
    assert res["hit"] is True and res["dmg"] == 1
    assert combat["monstres"][0]["currentPV"] == 19


def test_competence_magique_ignore_les_pa(monkeypatch):
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 1)
    combat = _combat()
    res = resolve_action(combat, "competence", cible_id="monstre_0",
                         competence=normaliser_competence(_comp(jet="magique", cout_pm=4)))
    # Jet magique → pas de soustraction des PA (miroir des sorts) : 2 dégâts pleins.
    assert res["dmg"] == 2
    assert combat["joueurs"][0]["currentPM"] == 16


def test_competence_pm_insuffisants():
    combat = _combat(joueur_extra={"currentPM": 3})
    res = resolve_action(combat, "competence", cible_id="monstre_0",
                         competence=normaliser_competence(_comp(cout_pm=8)))
    assert "error" in res
    assert combat["joueurs"][0]["currentPM"] == 3
    assert combat["joueurs"][0]["competences"] == 0


def test_competence_ratee_debite_les_pm(monkeypatch):
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 100)  # miss garanti
    combat = _combat()
    res = resolve_action(combat, "competence", cible_id="monstre_0",
                         competence=normaliser_competence(_comp(cout_pm=4)))
    assert res["hit"] is False
    assert combat["joueurs"][0]["currentPM"] == 16   # la compétence part même ratée
    assert combat["monstres"][0]["currentPV"] == 20


def test_competence_sur_soi_soigne_et_perd_le_buff(monkeypatch):
    combat = _combat()
    comp = normaliser_competence(_comp(
        cible="soi", cout_pm=6, effets={"pv": 12, "buffs": {"R": 6}, "duree": 4}))
    res = resolve_action(combat, "competence", cible_id=None, competence=comp)
    assert res["pv_rendu"] == 12
    assert combat["joueurs"][0]["currentPV"] == 72
    assert combat["joueurs"][0]["currentPM"] == 14
    # La part buffs/durée est PERDUE en combat (pas de tick) — règle des consommables.
    assert "effets_actifs" not in combat["joueurs"][0]


def test_competence_sans_effet_instantane_refusee():
    combat = _combat()
    comp = normaliser_competence(_comp(cible="soi", effets={"buffs": {"F": 8}, "duree": 3}))
    res = resolve_action(combat, "competence", cible_id=None, competence=comp)
    assert "error" in res
    assert combat["joueurs"][0]["competences"] == 0


def test_competence_ranged_exige_une_ligne_de_vue_libre():
    # Portée > 1 → règles à distance : interdit si un ennemi est au contact.
    combat = _combat(monstres=[_monstre("monstre_0", 3, 4), _monstre("monstre_1", 3, 1)])
    comp = normaliser_competence(_comp(jet="cd", portee=6))
    res = resolve_action(combat, "competence", cible_id="monstre_1", competence=comp)
    assert "error" in res and "corps à corps" in res["error"]
