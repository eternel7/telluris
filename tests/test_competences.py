# tests/test_competences.py
#
# Tests du système de compétences de vocation (miroir des sorts). Logique pure :
# utils/competences.py (normalisation, passives, apprentissage, choix de départ),
# le repli des passives dans utils/consommables.caracts_avec_buffs / regen_bonus,
# et la branche "competence" de resolve_action (utils/combat.py).

import pytest

from models import character_stats
from utils.consommables import caracts_avec_buffs, regen_bonus, esquive_bonus
from utils.competences import (
    normaliser_competence, est_passive, est_active,
    competence_utilisable_combat, competence_utilisable_exploration,
    empiler_effet_competence, bonus_passifs, recompute_competences_bonus,
    cout_apprentissage, vocation_choisit_competence, competences_apprenables,
    competences_depart_par_vocation, liste_competences_payload,
    condition_remplie, furtivite_passive, competences_epinglees_effectives,
    competences_bonus_perime,
)
from utils import combat as combat_mod
from utils.combat import (
    resolve_action, _detection_threshold, _run_monster_turn, _do_attack_on,
    get_combat_grid,
)


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


def test_buff_sur_v_conserve_a_son_echelle():
    # V passe désormais comme les autres (règle partagée avec sorts/consommables), MAIS
    # sur son échelle 1-10 : ici +3 V = +3 cases de déplacement, là où +5 F est un
    # cinquième de F. C'est la donnée qui porte l'ordre de grandeur, pas le normaliseur —
    # l'ancien filtre rendait toute entrave (bolas) impossible à exprimer.
    comp = normaliser_competence(_passive(effets={"buffs": {"V": 3, "F": 5}}))
    assert comp["effets"]["buffs"] == {"V": 3, "F": 5}


def test_buff_negatif_conserve():
    comp = normaliser_competence(_comp(effets={"buffs": {"F": 8, "Ag": -4}, "duree": 3}))
    assert comp["effets"]["buffs"] == {"F": 8, "Ag": -4}


# ── Éligibilité combat / exploration ─────────────────────────────────────────────

def test_utilisable_combat_exige_un_effet_instantane_ou_duratif():
    assert competence_utilisable_combat(normaliser_competence(_comp())) is True
    assert competence_utilisable_combat(
        normaliser_competence(_comp(effets={"pv": 10}))) is True
    # Buff à durée : utilisable en combat (le snapshot le porte et le décrémente).
    assert competence_utilisable_combat(
        normaliser_competence(_comp(effets={"buffs": {"F": 5}, "duree": 3}))) is True
    # Sans durée, rien à empiler.
    assert competence_utilisable_combat(
        normaliser_competence(_comp(effets={"buffs": {"F": 5}}))) is False
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
    assert perso["competences_bonus"] == {
        "buffs": {"F": 4}, "regen_pv": 0, "regen_pm": 0, "esquive": 0,
        # Détail nommé du même agrégat (tooltip « Profil modifié » de la fiche).
        "buffs_sources": [{"nom": "Maîtrise martiale", "icon": "🗡️", "buffs": {"F": 4}}],
    }


def test_competences_bonus_perime_detecte_un_agregat_sans_sources():
    # Agrégat écrit avant `buffs_sources` : le tooltip de la fiche n'aurait aucun nom de
    # source à afficher → à recalculer (réparation paresseuse dans get_selected_character).
    perso = _perso(competences_connues=["competence:maitrise"],
                   competences_bonus={"buffs": {"F": 4}, "regen_pv": 0, "regen_pm": 0,
                                      "esquive": 0})
    assert competences_bonus_perime(perso) is True
    recompute_competences_bonus(perso, _get_doc)
    assert competences_bonus_perime(perso) is False


def test_competences_bonus_perime_faux_sans_competence_ni_buff():
    # Rien à recalculer pour un perso sans compétence…
    assert competences_bonus_perime(_perso()) is False
    # …ni pour une passive sans buff (régén seule) : l'agrégat porte quand même la clé,
    # avec une liste de sources vide — ce n'est pas un agrégat périmé.
    docs = {"competence:souffle": _passive(_id="competence:souffle", nom="Second souffle",
                                           effets={"regen_pv": 1})}
    perso = _perso(competences_connues=["competence:souffle"])
    recompute_competences_bonus(perso, docs.get)
    assert perso["competences_bonus"]["buffs_sources"] == []
    assert competences_bonus_perime(perso) is False


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
    # d100 à 50 = touche ORDINAIRE (seuil 70) : un critique doublerait les dégâts et
    # masquerait ce que ce test vérifie. Dés à 1.
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50 if b == 100 else 1)
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


def test_competence_sur_soi_soigne_et_empile_le_buff(monkeypatch):
    combat = _combat()
    comp = normaliser_competence(_comp(
        cible="soi", cout_pm=6, effets={"pv": 12, "buffs": {"R": 6}, "duree": 4}))
    res = resolve_action(combat, "competence", cible_id=None, competence=comp)
    assert res["pv_rendu"] == 12
    assert combat["joueurs"][0]["currentPM"] == 14
    # La part à durée est empilée sur les effets vivants du snapshot.
    effets = combat["joueurs"][0]["effets_actifs"]
    assert [(e["buffs"], e["restants"]) for e in effets] == [({"R": 6}, 4)]


def test_competence_buff_pur_acceptee_en_combat():
    combat = _combat()
    comp = normaliser_competence(_comp(cible="soi", effets={"buffs": {"F": 8}, "duree": 3}))
    res = resolve_action(combat, "competence", cible_id=None, competence=comp)
    assert "error" not in res
    assert combat["joueurs"][0]["competences"] == 1
    assert [e["buffs"] for e in combat["joueurs"][0]["effets_actifs"]] == [{"F": 8}]


def test_competence_ranged_exige_une_ligne_de_vue_libre():
    # Portée > 1 → règles à distance : interdit si un ennemi est au contact.
    combat = _combat(monstres=[_monstre("monstre_0", 3, 4), _monstre("monstre_1", 3, 1)])
    comp = normaliser_competence(_comp(jet="cd", portee=6))
    res = resolve_action(combat, "competence", cible_id="monstre_1", competence=comp)
    assert "error" in res and "corps à corps" in res["error"]


# ── Nouvelles clés d'effets : esquive / furtivite ────────────────────────────────

def test_normalisation_esquive_et_furtivite():
    comp = normaliser_competence(_comp(effets={"esquive": 10, "furtivite": 3}))
    assert comp["effets"]["esquive"] == 10
    assert comp["effets"]["furtivite"] == 3
    # Absentes → normalisées à 0 (clés toujours présentes).
    comp = normaliser_competence(_comp())
    assert comp["effets"]["esquive"] == 0 and comp["effets"]["furtivite"] == 0


def test_fusionner_effets_additionne_esquive_et_furtivite():
    from utils.sorts import fusionner_effets
    out = fusionner_effets({"esquive": 5, "furtivite": 1},
                           [{"esquive": 3}, {"furtivite": 2}])
    assert out["esquive"] == 8 and out["furtivite"] == 3


def test_empiler_effet_competence_porte_l_esquive():
    perso = {"effets_actifs": []}
    comp = normaliser_competence(_comp(cible="soi", effets={"esquive": 10, "duree": 3}))
    entry = empiler_effet_competence(perso, comp)
    # Un effet à durée dont la seule substance est l'esquive doit s'empiler.
    assert entry is not None and entry["esquive"] == 10 and entry["restants"] == 3


# ── condition (battle_map_tags) ──────────────────────────────────────────────────

def test_condition_remplie():
    comp = normaliser_competence(_comp(condition={"battle_map_tags": ["foret", "bois"]}))
    assert condition_remplie(comp, ["chemin", "foret"]) is True
    assert condition_remplie(comp, ["desert"]) is False
    assert condition_remplie(comp, []) is False
    # Condition absente = toujours active.
    assert condition_remplie(normaliser_competence(_comp()), []) is True


_DOCS_FURTIF = {
    "competence:furtivite_sylvestre": _passive(
        _id="competence:furtivite_sylvestre", nom="Furtivité sylvestre",
        condition={"battle_map_tags": ["foret", "bois"]}, effets={"furtivite": 1}),
    "competence:esquive": _passive(
        _id="competence:esquive", nom="Esquive", vocation="voleur",
        effets={"esquive": 10}),
    "competence:maitrise": _passive(),
}


def test_passive_conditionnee_exclue_du_repli_inconditionnel():
    # La furtivité sylvestre ne vaut qu'en forêt : elle ne doit JAMAIS fuiter dans
    # competences_bonus (qui s'applique partout, exploration comprise).
    perso = _perso(competences_connues=["competence:furtivite_sylvestre", "competence:esquive"])
    bonus = bonus_passifs(perso, _DOCS_FURTIF.get)
    assert bonus["esquive"] == 10
    assert bonus["buffs"] == {}


def test_esquive_bonus_somme_passives_et_effets_actifs():
    perso = _perso(competences_connues=["competence:esquive"],
                   effets_actifs=[{"esquive": 5, "restants": 2}])
    recompute_competences_bonus(perso, _DOCS_FURTIF.get)
    assert esquive_bonus(perso) == 15


def test_furtivite_passive_selon_les_tags_du_terrain():
    perso = _perso(competences_connues=["competence:furtivite_sylvestre"])
    assert furtivite_passive(perso, _DOCS_FURTIF.get, ["foret", "chemin"]) == 1
    assert furtivite_passive(perso, _DOCS_FURTIF.get, ["desert"]) == 0
    # Une passive sans condition (Esquive) ne confère pas de furtivité.
    perso = _perso(competences_connues=["competence:esquive"])
    assert furtivite_passive(perso, _DOCS_FURTIF.get, ["foret"]) == 0


# ── Détection & tour des monstres ────────────────────────────────────────────────

def test_detection_threshold_et_replis():
    joueur = {"ag": 30, "furtivite_bonus": 0}
    # Vol prioritaire : 50 + 40 − 30 = 60.
    assert _detection_threshold({"vol": 40, "int": 60, "ag": 80}, joueur) == 60
    # Sans Vol → Int−10 : 50 + (60−10) − 30 = 70.
    assert _detection_threshold({"vol": 0, "int": 60, "ag": 80}, joueur) == 70
    # Sans Vol ni Int → Ag−30 : 50 + (80−30) − 30 = 70.
    assert _detection_threshold({"vol": 0, "int": 0, "ag": 80}, joueur) == 70
    # Le bonus de furtivité gonfle la difficulté : 50 + 40 − (30+20) = 40.
    joueur = {"ag": 30, "furtivite_bonus": 20}
    assert _detection_threshold({"vol": 40, "int": 0, "ag": 0}, joueur) == 40
    # Clamp [5, 95].
    assert _detection_threshold({"vol": 0, "int": 0, "ag": 0}, {"ag": 100}) == 5


def test_detection_malus_de_distance(monkeypatch):
    # DETECTION_DISTANCE_FACTEUR points de difficulté par case (Chebyshev) : le même
    # monstre repère moins bien de loin. Lu via le module (variable de monde réglable).
    monkeypatch.setattr(character_stats, "DETECTION_DISTANCE_FACTEUR", 5)
    joueur = {"ag": 30, "furtivite_bonus": 0, "pos": {"x": 3, "y": 5}}
    proche = {"vol": 40, "int": 0, "ag": 0, "pos": {"x": 3, "y": 4}}   # 1 case  : 50+40−(30+5)  = 55
    loin = {"vol": 40, "int": 0, "ag": 0, "pos": {"x": 9, "y": 5}}     # 6 cases : 50+40−(30+30) = 30
    assert _detection_threshold(proche, joueur) == 55
    assert _detection_threshold(loin, joueur) == 30
    # Facteur 0 = malus désactivé : la distance ne joue plus.
    monkeypatch.setattr(character_stats, "DETECTION_DISTANCE_FACTEUR", 0)
    assert _detection_threshold(loin, joueur) == _detection_threshold(proche, joueur) == 60


def _monstre_actif(mid, x, y, **extra):
    """Monstre complet pour faire tourner _run_monster_turn (pas seulement une cible)."""
    m = _monstre(mid, x, y, cc=50, degats_cc="1D4",
                 actions_max=2, actions_restantes=2, cells_moved=0, attaques=0,
                 portee=1, vol=0, tags=[], detecte=False)
    m["int"] = 0
    m.update(extra)
    return m


def _avancer_tour(combat, monstre):
    grid = get_combat_grid(combat)
    _run_monster_turn(combat, monstre, grid)


def test_monstre_non_detecte_ne_vient_pas_au_joueur(monkeypatch):
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 100)  # détection ratée
    # Monstre adjacent au joueur, immobile (deplacement 0) : sans furtivité il frapperait.
    m = _monstre_actif("monstre_0", 3, 4, deplacement=0)
    combat = _combat(joueur_extra={"furtif": True, "furtivite_bonus": 1}, monstres=[m])
    combat["acteur_courant_index"] = 1
    pv_avant = combat["joueurs"][0]["currentPV"]
    _avancer_tour(combat, m)
    assert combat["joueurs"][0]["currentPV"] == pv_avant   # pas attaqué
    assert m["detecte"] is False
    assert m["pos"] == {"x": 3, "y": 4}                    # pas bougé (deplacement 0)


def test_monstre_detecte_puis_attaque(monkeypatch):
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 1)   # détection + coups réussis
    m = _monstre_actif("monstre_0", 3, 4, deplacement=0, vol=40)
    combat = _combat(joueur_extra={"furtif": True, "furtivite_bonus": 1}, monstres=[m])
    combat["acteur_courant_index"] = 1
    pv_avant = combat["joueurs"][0]["currentPV"]
    _avancer_tour(combat, m)
    assert m["detecte"] is True
    assert combat["joueurs"][0]["currentPV"] < pv_avant    # repéré → frappé
    # La détection PERSISTE : le tour suivant attaque directement même si le jet raterait.
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 100)
    combat["acteur_courant_index"] = 1
    pv = combat["joueurs"][0]["currentPV"]
    _avancer_tour(combat, m)
    # (roll 100 = miss sur l'attaque, mais il a bien tenté : detecte est resté True)
    assert m["detecte"] is True


def test_attaquer_brise_la_furtivite(monkeypatch):
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 100)
    combat = _combat(joueur_extra={
        "furtif": True, "furtivite_bonus": 1,
        "attaque_profils": [{"mode": "cac", "portee": 1, "ranged": False,
                             "toucher": "cc", "degats": "degats_cc"}],
        "degats_cc": "1D4",
    })
    resolve_action(combat, "attaquer", cible_id="monstre_0", mode="cac")
    assert combat["joueurs"][0]["furtif"] is False
    assert combat["joueurs"][0]["furtivite_bonus"] == 0


# ── Attaques à DISTANCE depuis l'ombre : pas de rupture, la cible seule tente un jet ──

_PROFIL_TIR = [{"mode": "tir", "portee": 6, "ranged": True,
                "toucher": "cd", "degats": "degats_cd"}]


def _combat_embuscade(**joueur_extra):
    """Joueur furtif à l'arc, deux monstres LOIN (aucun engagement au corps à corps) :
    la cible en (3, 1), un témoin en (0, 0). Grille 7×7 ouverte = ligne de vue dégagée."""
    cible = _monstre_actif("monstre_0", 3, 1)
    temoin = _monstre_actif("monstre_1", 0, 0)
    joueur = {"furtif": True, "furtivite_bonus": 1,
              "attaque_profils": _PROFIL_TIR, "degats_cd": "1D4"}
    joueur.update(joueur_extra)
    return _combat(joueur_extra=joueur, monstres=[cible, temoin]), cible, temoin


def test_attaque_a_distance_ne_brise_pas_la_furtivite(monkeypatch):
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 100)  # tir raté, détection ratée
    combat, cible, temoin = _combat_embuscade()
    resolve_action(combat, "attaquer", cible_id="monstre_0", mode="tir")
    assert combat["joueurs"][0]["furtif"] is True          # l'archer reste dans l'ombre
    assert combat["joueurs"][0]["furtivite_bonus"] == 1
    assert cible["detecte"] is False
    assert temoin["detecte"] is False


def test_attaque_a_distance_peut_alerter_la_cible(monkeypatch):
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 1)    # tir touché, détection réussie
    combat, cible, temoin = _combat_embuscade()
    cible["pv_max"] = cible["currentPV"] = 200            # survit à la flèche → elle peut chercher
    resolve_action(combat, "attaquer", cible_id="monstre_0", mode="tir")
    assert cible["detecte"] is True                        # la victime, elle, vous a repéré
    assert temoin["detecte"] is False                      # les autres n'ont rien vu
    assert combat["joueurs"][0]["furtif"] is True          # la furtivité tient pour eux


def test_kill_a_distance_reste_silencieux(monkeypatch):
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 1)    # tir touché + détection réussirait
    combat, cible, temoin = _combat_embuscade()
    cible["currentPV"] = cible["pa"] = 1                   # la flèche l'abat
    resolve_action(combat, "attaquer", cible_id="monstre_0", mode="tir")
    assert cible["vivant"] is False
    assert cible["detecte"] is False                       # une cible abattue ne repère plus rien
    assert combat["joueurs"][0]["furtif"] is True


def test_sort_distant_ne_brise_pas_mais_sort_de_contact_brise(monkeypatch):
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 100)  # tout raté
    sort_distant = {"doc": {"nom": "Trait d'ombre", "cout_pm": 0, "cible": "ennemi", "portee": 5},
                    "effets": {"degats": "1D4"}}
    combat, cible, _ = _combat_embuscade()
    resolve_action(combat, "sort", cible_id="monstre_0", sort=sort_distant)
    assert combat["joueurs"][0]["furtif"] is True
    assert cible["detecte"] is False

    # Un sort de CONTACT (portée 1) révèle le lanceur, touché ou raté.
    sort_contact = {"doc": {"nom": "Griffe spectrale", "cout_pm": 0, "cible": "ennemi", "portee": 1},
                    "effets": {"degats": "1D4"}}
    combat = _combat(joueur_extra={"furtif": True, "furtivite_bonus": 1})   # monstre adjacent
    resolve_action(combat, "sort", cible_id="monstre_0", sort=sort_contact)
    assert combat["joueurs"][0]["furtif"] is False


def test_competence_distante_ne_brise_pas(monkeypatch):
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 100)
    comp = normaliser_competence(_comp(jet="cd", portee=5, cout_pm=0))
    combat, cible, _ = _combat_embuscade()
    resolve_action(combat, "competence", cible_id="monstre_0", competence=comp)
    assert combat["joueurs"][0]["furtif"] is True
    assert cible["detecte"] is False


def test_active_furtivite_refurtive_et_efface_la_detection():
    m1 = _monstre_actif("monstre_0", 3, 4, detecte=True)
    m2 = _monstre_actif("monstre_1", 0, 0, detecte=True)
    combat = _combat(monstres=[m1, m2])
    comp = normaliser_competence(_comp(cible="soi", cout_pm=0, effets={"furtivite": 1}))
    res = resolve_action(combat, "competence", cible_id=None, competence=comp)
    assert res.get("furtif") is True
    assert combat["joueurs"][0]["furtif"] is True
    assert combat["joueurs"][0]["furtivite_bonus"] == 1
    assert m1["detecte"] is False and m2["detecte"] is False
    assert combat["joueurs"][0]["competences"] == 1        # coûte bien 1 action


def test_predateur_chasse_la_proie(monkeypatch):
    rolls = iter([100, 1, 1, 1, 1, 1, 1])   # détection ratée, puis coups réussis (dés à 1)
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: next(rolls, 1))
    predateur = _monstre_actif("monstre_0", 3, 4, tags=["predateur"], deplacement=2)
    proie = _monstre_actif("monstre_1", 2, 4, tags=["proie"], pa=0, currentPV=1, pv_max=20)
    combat = _combat(joueur_extra={"furtif": True, "furtivite_bonus": 1},
                     monstres=[predateur, proie])
    combat["acteur_courant_index"] = 1
    pv_joueur = combat["joueurs"][0]["currentPV"]
    _avancer_tour(combat, predateur)
    assert combat["joueurs"][0]["currentPV"] == pv_joueur  # le joueur n'a pas été visé
    assert proie["vivant"] is False                        # la proie est abattue
    assert proie["tue_par_monstre"] is True
    assert proie["xp_reward"] == 0                         # pas d'XP pour un kill de monstre


def test_esquive_reduit_le_seuil_physique(monkeypatch):
    # cc 50 vs Ag 30 → seuil 70. Jet forcé à 65 : touche SANS esquive, rate AVEC esquive 10.
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 65)
    attaquant = _monstre_actif("monstre_0", 3, 4)
    combat = _combat(monstres=[attaquant])
    joueur = combat["joueurs"][0]

    joueur["esquive"] = 0
    pv = joueur["currentPV"]
    _do_attack_on(combat, attaquant, joueur)
    assert joueur["currentPV"] < pv                        # 65 ≤ 70 : touché

    joueur["esquive"] = 10
    pv = joueur["currentPV"]
    _do_attack_on(combat, attaquant, joueur)
    assert joueur["currentPV"] == pv                       # 65 > 60 : esquivé


# ── Épinglage des compétences actives ────────────────────────────────────────────

def test_competences_epinglees_auto_pin_premiere_active():
    perso = _perso(competences_connues=["competence:maitrise", "competence:frappe"])
    # Champ absent → auto-épingle la première ACTIVE (la passive est sautée).
    assert competences_epinglees_effectives(perso, _get_doc) == ["competence:frappe"]
    # Champ présent → choix explicite respecté (y compris vide) et ids inconnus filtrés.
    perso["competences_epinglees"] = []
    assert competences_epinglees_effectives(perso, _get_doc) == []
    perso["competences_epinglees"] = ["competence:frappe", "competence:disparue"]
    assert competences_epinglees_effectives(perso, _get_doc) == ["competence:frappe"]
