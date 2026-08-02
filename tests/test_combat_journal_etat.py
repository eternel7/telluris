"""Clé `etat` du journal de combat — ce que chaque ligne vient de changer.

Le serveur résout tout d'un bloc (un tour de monstre entier arrive dans UNE réponse) et le
journal ne porte aucun id : sans cette charge, le client ne peut pas savoir quelle ligne
explique quelle perte de PV, et doit donc tout appliquer AVANT les animations — le joueur
voit le résultat avant le coup. Même canal, même motif et mêmes garanties que `vfx` :
clé absente ⇒ comportement d'avant, aucune migration.
"""
import pytest

from utils import combat as combat_mod


def _character():
    return {
        "_id": "character:test_1", "nom": "Frida", "voc": "guerrier", "race": "humain",
        "caracteristiques_current": {"V": 5, "F": 40, "R": 30, "Ag": 40,
                                     "Vol": 30, "Int": 20, "Cha": 20, "Ch": 20},
        "vocations_niveaux": {"guerrier": 1},
        "currentPV": 100, "currentPM": 20, "inventaire": [], "slots": {},
    }


def _espece(**extra):
    base = {"_id": "espece:loup", "nom": "Loup", "tags": [],
            "base_attributes": {c: {"min": v, "max": v} for c, v in
                                (("V", 4), ("F", 30), ("R", 30), ("Ag", 40),
                                 ("Vol", 20), ("Int", 10), ("Cha", 10), ("Ch", 10))}}
    base.update(extra)
    return base


def _combat(joueur, monstres):
    joueur["pos"] = {"x": 3, "y": 5}
    joueur["vivant"] = True
    for m in monstres:
        m["pos"] = {"x": 3, "y": 4}
    return {
        "_id": "combat:test", "type": "combat", "status": "active", "tour": 1, "log": [],
        "ordre_initiative": ["joueur_0"] + [m["id"] for m in monstres],
        "acteur_courant_index": 0,
        "joueurs": [joueur], "monstres": monstres,
        "grid": {"dims": {"x": 7, "y": 7},
                 "cells": [[1] * 7 for _ in range(7)], "nav": {}},
    }


def _scene(monkeypatch, roll=50):
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: roll)
    joueur = combat_mod.build_joueur_snapshot(_character(), 0)
    monstre = combat_mod.build_monster_snapshot(_espece(), None, 0)
    return _combat(joueur, [monstre])


def _ligne(combat, *kinds):
    return next(e for e in combat["log"] if e["kind"] in kinds)


# ── Ce qu'une ligne porte ────────────────────────────────────────────────────────

def test_attaque_qui_touche_porte_les_pv_de_la_cible(monkeypatch):
    combat = _scene(monkeypatch, roll=1)          # 1 = réussite critique : le coup porte
    combat_mod.resolve_action(combat, "attaquer", cible_id="monstre_0")
    monstre = combat["monstres"][0]
    etat = _ligne(combat, "hit", "crit", "kill")["etat"]
    assert etat["monstre_0"]["currentPV"] == monstre["currentPV"]
    assert etat["monstre_0"]["vivant"] is monstre["vivant"]


def test_coup_fatal_porte_la_mort(monkeypatch):
    combat = _scene(monkeypatch, roll=1)
    combat["monstres"][0]["currentPV"] = 1
    combat_mod.resolve_action(combat, "attaquer", cible_id="monstre_0")
    etat = _ligne(combat, "kill")["etat"]
    assert etat["monstre_0"]["currentPV"] == 0
    assert etat["monstre_0"]["vivant"] is False


def test_deplacement_porte_la_case_darrivee_en_COPIE(monkeypatch):
    combat = _scene(monkeypatch)
    joueur = combat["joueurs"][0]
    depart = dict(joueur["pos"])
    combat_mod.resolve_action(combat, "deplacer", dx=1, dy=0)
    etat = _ligne(combat, "move")["etat"]
    assert etat["joueur_0"]["pos"] == {"x": depart["x"] + 1, "y": depart["y"]}
    # ⚠️ COPIE : le snapshot garde son dict d'un pas à l'autre, une référence partagée
    # ferait dériver une ligne déjà écrite.
    joueur["pos"]["x"] = 99
    assert etat["joueur_0"]["pos"]["x"] != 99


def test_consommer_porte_les_vitaux_du_buveur(monkeypatch):
    combat = _scene(monkeypatch)
    joueur = combat["joueurs"][0]
    joueur["currentPV"] = 1
    potion = {"_id": "item:potion", "nom": "Potion", "categorie": "consommable",
              "poids": 0.2, "effets": {"pv": 5}}
    combat_mod.resolve_action(combat, "consommer", item=potion)
    etat = combat["log"][-1]["etat"]
    assert etat["joueur_0"]["currentPV"] == joueur["currentPV"] == 6


# ── Ce qu'une ligne NE porte pas ─────────────────────────────────────────────────

def test_ligne_sans_consequence_na_pas_la_cle(monkeypatch):
    """Un acteur qu'aucune ligne ne nomme n'est jamais gelé côté client : il suit l'état
    final tout de suite. Ne rien poser est donc la bonne réponse, pas un oubli."""
    combat = _scene(monkeypatch)
    combat_mod.resolve_action(combat, "passer")
    # (le tour passé enchaîne sur celui des monstres, dont les lignes en portent bien une)
    passe = next(e for e in combat["log"] if "passe son tour" in e["texte"])
    assert "etat" not in passe


def test_attaque_ratee_du_joueur_ne_ressuscite_personne(monkeypatch):
    combat = _scene(monkeypatch, roll=90)         # au-dessus du seuil : raté franc
    combat_mod.resolve_action(combat, "attaquer", cible_id="monstre_0")
    assert "etat" not in _ligne(combat, "miss")


# ── LE cas qui justifie tout : un tour de monstre résolu côté serveur ────────────

def test_tour_de_monstre_pose_dabord_la_position_puis_le_coup(monkeypatch):
    """Le jeton ne saute plus à sa case d'arrivée dès la réponse : il y glisse sur sa
    ligne « avance vers… », et ne frappe qu'ensuite."""
    combat = _scene(monkeypatch, roll=1)
    monstre = combat["monstres"][0]
    # Deux cases à faire : un pas, puis il lui reste des actions pour frapper.
    monstre["pos"] = {"x": 3, "y": 3}
    monstre["deplacement"] = 3
    combat_mod._run_monster_turn(combat, monstre, combat_mod.get_combat_grid(combat))

    move = _ligne(combat, "move")
    assert move["etat"]["monstre_0"]["pos"] == monstre["pos"]

    coup = _ligne(combat, "hit", "crit")
    # L'ATTAQUANT est en état lui aussi : un prédateur qui fond sur sa proie n'écrit
    # aucune ligne de déplacement, cette ligne-ci est la seule où il puisse arriver.
    assert set(coup["etat"]) == {"monstre_0", "joueur_0"}
    assert coup["etat"]["joueur_0"]["currentPV"] < 100


def test_ko_dun_membre_porte_letat_du_defenseur(monkeypatch):
    combat = _scene(monkeypatch, roll=1)
    joueur = combat["joueurs"][0]
    joueur["currentPV"] = 1
    combat_mod._do_attack_on(combat, combat["monstres"][0], joueur)
    terre = next(e for e in combat["log"] if "à terre" in e["texte"])
    assert terre["etat"]["joueur_0"]["currentPV"] == 0


def test_dissipation_dun_effet_porte_les_vitaux_reclampes(monkeypatch):
    """La ligne de dissipation est écrite APRÈS _refresh_snapshot_stats : un buff de R qui
    expire abaisse pv_max, donc re-clampe les PV — l'état posé doit être celui d'après."""
    combat = _scene(monkeypatch)
    joueur = combat["joueurs"][0]
    joueur["effets_actifs"] = [{"source_id": "sort:vigueur", "nom": "Vigueur", "icon": "💪",
                                "buffs": {"R": 20}, "regen_pv": 0, "regen_pm": 0,
                                "esquive": 0, "restants": 1, "pose_tour": 0}]
    combat_mod._refresh_snapshot_stats(joueur)
    joueur["currentPV"] = joueur["pv_max"]
    combat["tour"] = 2
    combat_mod._tick_effets_combat(combat, joueur)
    fin = next(e for e in combat["log"] if "se dissipe" in e["texte"])
    assert fin["etat"]["joueur_0"]["currentPV"] == joueur["currentPV"] == joueur["pv_max"]
