# tests/test_invocations.py
#
# INVOCATIONS (bloc `invocation` d'un doc `sort:*`) : normalisation et bornes dans
# utils/sorts.py, apparition / tour d'IA / dissipation dans utils/combat.py.
#
# Ce que ces tests verrouillent en priorité, parce que c'est ce qui casse en silence :
#   · `ordre_initiative` et `acteur_courant_index` restent cohérents quand une créature
#     entre en plein combat PUIS en sort (insertion et purge décalent la liste) ;
#   · la créature ne laisse RIEN derrière elle (pas de `character_id` ⇒ finalize la saute).
#
# Logique pure : la seule lecture DB (`espece:*` / `profil:*`) est monkeypatchée.

import pytest

from utils import combat as combat_mod
from utils.combat import (
    build_invocation_snapshot, invoquer, resolve_action, _purger_invocations,
    _run_invocation_turn, build_joueur_snapshot, build_monster_snapshot,
)
from utils.sorts import (
    INVOCATION_DUREE_DEFAUT, INVOCATION_NOMBRE_MAX, est_invocation, invocation_de,
    normaliser_sort, sort_utilisable_combat, sort_utilisable_exploration,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────────

SERVANT = {
    "_id": "espece:demon_servant", "type": "espece", "nom": "Démon Servant",
    "image": "demon_servant_transparent.png",
    "base_attributes": {
        "V": {"min": 5, "max": 5}, "F": {"min": 30, "max": 30}, "R": {"min": 25, "max": 25},
        "Ag": {"min": 30, "max": 30}, "Vol": {"min": 20, "max": 20},
        "Int": {"min": 10, "max": 10}, "Cha": {"min": 0, "max": 0}, "Ch": {"min": 0, "max": 0},
    },
    "tags": ["demon", "infernal"],
}


def _character(nom="Vadim", **overrides):
    char = {
        "_id": "character:test_1", "nom": nom, "voc": "demoniste", "race": "humain",
        "caracteristiques_current": {"V": 5, "F": 40, "R": 30, "Ag": 40,
                                     "Vol": 40, "Int": 60, "Cha": 20, "Ch": 20},
        "vocations_niveaux": {"demoniste": 1},
        "currentPV": 100, "currentPM": 60,
        "inventaire": [], "slots": {},
    }
    char.update(overrides)
    return char


def _monstre(idx=0, pos=(7, 5), pv=40):
    m = build_monster_snapshot(SERVANT, None, idx)
    m["nom"] = "Gobelin"
    m["pos"] = {"x": pos[0], "y": pos[1]}
    m["currentPV"] = pv
    m["pv_max"] = max(pv, 1)
    return m


def _combat(joueurs, monstres=None, idx=0):
    monstres = monstres or []
    return {
        "_id": "combat:test", "type": "combat", "status": "active", "tour": 1, "log": [],
        "ordre_initiative": [j["id"] for j in joueurs] + [m["id"] for m in monstres],
        "acteur_courant_index": idx,
        "character_id": "character:test_1",
        "joueurs": joueurs, "monstres": monstres,
        "grid": {"dims": {"x": 11, "y": 11},
                 "cells": [[1] * 11 for _ in range(11)], "nav": {}},
    }


def _sort_invocation(nombre=1, duree=3, **overrides):
    doc = {
        "_id": "sort:pacte", "type": "sort", "nom": "Pacte mineur", "icon": "😈",
        "vocation": "demoniste", "magie": "Démonologie", "famille": "invocation",
        "niveau": 0, "cout_pm": 12, "cible": "soi", "portee": 0, "effets": {},
        "invocation": {"espece": "espece:demon_servant", "nombre": nombre, "duree": duree},
    }
    doc.update(overrides)
    return doc


@pytest.fixture
def db(monkeypatch):
    """Bestiaire minimal servi à `invoquer` (seule lecture DB de la feature)."""
    catalogue = {"espece:demon_servant": SERVANT}
    monkeypatch.setattr(combat_mod, "get_doc", lambda i: catalogue.get(i))
    return catalogue


# ── Normalisation et bornes (utils/sorts.py) ─────────────────────────────────────

def test_invocation_de_exige_une_espece():
    assert invocation_de(None) is None
    assert invocation_de({}) is None
    assert invocation_de({"invocation": {}}) is None
    assert invocation_de({"invocation": {"espece": "  "}}) is None


def test_invocation_de_borne_nombre_et_duree():
    inv = invocation_de({"invocation": {"espece": "espece:x", "nombre": 99, "duree": 7}})
    assert inv == {"espece": "espece:x", "profil": "", "nombre": INVOCATION_NOMBRE_MAX,
                   "duree": 7}
    # Durée absente ⇒ défaut explicite, jamais « illimitée » ; nombre plancher à 1.
    inv = invocation_de({"invocation": {"espece": "espece:x", "nombre": 0}})
    assert inv["duree"] == INVOCATION_DUREE_DEFAUT
    assert inv["nombre"] == 1


def test_le_bloc_traverse_la_normalisation_du_sort():
    sort = normaliser_sort(_sort_invocation())
    assert est_invocation(sort) is True
    assert sort["invocation"]["espece"] == "espece:demon_servant"
    assert sort["famille"] == "invocation"
    # Un sort ordinaire n'invoque rien.
    assert est_invocation(normaliser_sort(_sort_invocation(invocation=None))) is False


def test_une_invocation_est_lancable_en_combat_et_nulle_part_ailleurs():
    """Elle n'a AUCUN `effets` : sans exception explicite, le moteur la refuserait en
    combat. Et hors combat il n'existe pas de grille où la poser."""
    sort = normaliser_sort(_sort_invocation())
    assert sort["effets"]["degats"] == "" and not sort["effets"]["buffs"]
    assert sort_utilisable_combat(sort) is True
    assert sort_utilisable_exploration(sort) is False


def test_invocation_refusee_en_exploration_meme_avec_un_effet_applicable():
    sort = normaliser_sort(_sort_invocation(effets={"pv": 10}))
    assert sort_utilisable_exploration(sort) is False


# ── Snapshot de la créature ──────────────────────────────────────────────────────

def test_snapshot_est_un_allie_sans_doc_ni_attributs_d_ennemi():
    snap = build_invocation_snapshot(SERVANT, None, 2, duree=3)
    assert snap["id"] == "joueur_2"          # id côté JOUEUR : c'est ce qui le range au camp
    assert snap["jouable"] is False          # il ne se pilote pas
    assert snap["est_invocation"] is True
    assert snap["invocation_restants"] == 3
    assert "character_id" not in snap        # ⇒ finalize_combat le saute de lui-même
    for cle in ("vivant", "detecte", "xp_reward"):
        assert cle not in snap
    assert snap["pm_max"] == 0 and snap["currentPM"] == 0
    assert snap["attaque_profils"][0]["mode"] == "cac"


def test_snapshot_sans_profil_est_deterministe():
    """`profil is None` ⇒ point médian de l'espèce : deux appels donnent le même monstre
    (le tirage d'un `profil:*` passerait par random)."""
    a = build_invocation_snapshot(SERVANT, None, 1, duree=2)
    b = build_invocation_snapshot(SERVANT, None, 1, duree=2)
    assert a["pv_max"] == b["pv_max"] and a["cc"] == b["cc"]


# ── Apparition ───────────────────────────────────────────────────────────────────

def _lanceur(pos=(3, 5), pm=60):
    j = build_joueur_snapshot(_character(), joueur_index=0)
    j["pos"] = {"x": pos[0], "y": pos[1]}
    j["currentPM"] = pm
    return j


def test_invoquer_pose_les_creatures_autour_du_lanceur(db):
    lanceur = _lanceur()
    doc = _combat([lanceur], [_monstre()])
    grid = combat_mod.get_combat_grid(doc)
    crees = invoquer(doc, lanceur, normaliser_sort(_sort_invocation(nombre=2)), grid)

    assert len(crees) == 2
    assert all(max(abs(c["pos"]["x"] - 3), abs(c["pos"]["y"] - 5)) == 1 for c in crees)
    assert [c["pos"] for c in crees] != [lanceur["pos"], lanceur["pos"]]   # jamais empilées
    assert len({(c["pos"]["x"], c["pos"]["y"]) for c in crees}) == 2
    assert [j["id"] for j in doc["joueurs"]] == ["joueur_0", "joueur_1", "joueur_2"]


def test_invoquer_insere_juste_apres_l_acteur_courant(db):
    """Insérer à leur rang d'initiative décalerait les entrées AVANT l'index courant :
    `acteur_courant_index` désignerait brusquement un autre acteur, en plein tour."""
    lanceur = _lanceur()
    autre = build_joueur_snapshot(_character("Borin"), joueur_index=1)
    autre["pos"] = {"x": 1, "y": 1}
    doc = _combat([autre, lanceur], [_monstre()], idx=1)   # le lanceur joue, en 2e position
    grid = combat_mod.get_combat_grid(doc)
    invoquer(doc, lanceur, normaliser_sort(_sort_invocation()), grid)

    assert doc["ordre_initiative"] == ["joueur_1", "joueur_0", "joueur_2", "monstre_0"]
    # L'acteur courant est TOUJOURS le lanceur.
    assert doc["ordre_initiative"][doc["acteur_courant_index"]] == lanceur["id"]


def test_invoquer_sans_espece_resoluble_ne_cree_rien(db):
    lanceur = _lanceur()
    doc = _combat([lanceur], [_monstre()])
    grid = combat_mod.get_combat_grid(doc)
    sort = normaliser_sort(_sort_invocation(invocation={"espece": "espece:inexistante"}))
    assert invoquer(doc, lanceur, sort, grid) == []
    assert len(doc["joueurs"]) == 1


def test_invoquer_encercle_ne_cree_rien(db):
    """Grille d'une seule case libre, déjà occupée par le lanceur."""
    lanceur = _lanceur(pos=(0, 0))
    doc = _combat([lanceur], [])
    doc["grid"] = {"dims": {"x": 1, "y": 1}, "cells": [[1]], "nav": {}}
    grid = combat_mod.get_combat_grid(doc)
    assert invoquer(doc, lanceur, normaliser_sort(_sort_invocation()), grid) == []


# ── L'action « sort » dans resolve_action ────────────────────────────────────────

def _action_invoquer(doc, sort_doc):
    sort = normaliser_sort(sort_doc)
    return resolve_action(doc, "sort", sort={"doc": sort, "effets": sort["effets"]})


def test_action_sort_invocation_debite_pm_et_action(db):
    lanceur = _lanceur(pm=60)
    doc = _combat([lanceur], [_monstre()])
    avant = lanceur["actions_restantes"]
    res = _action_invoquer(doc, _sort_invocation(nombre=2, duree=4))

    assert "error" not in res
    assert [i["nom"] for i in res["invoques"]] == ["Démon Servant", "Démon Servant"]
    assert res["invoques"][0]["restants"] == 4
    assert lanceur["currentPM"] == 60 - 12
    assert lanceur["actions_restantes"] == avant - 1
    assert len(doc["joueurs"]) == 3


def test_action_sort_invocation_sans_place_ne_coute_rien(db):
    """Le seul échec de cette branche qui ne doit rien à un jet de dés : ni PM, ni action."""
    lanceur = _lanceur(pos=(0, 0), pm=60)
    doc = _combat([lanceur], [])
    doc["grid"] = {"dims": {"x": 1, "y": 1}, "cells": [[1]], "nav": {}}
    avant = lanceur["actions_restantes"]
    res = _action_invoquer(doc, _sort_invocation())

    assert "error" in res
    assert lanceur["currentPM"] == 60
    assert lanceur["actions_restantes"] == avant


def test_action_sort_invocation_refusee_sans_pm(db):
    lanceur = _lanceur(pm=3)
    doc = _combat([lanceur], [_monstre()])
    res = _action_invoquer(doc, _sort_invocation())
    assert res == {"error": "PM insuffisants."}
    assert len(doc["joueurs"]) == 1


def test_invocation_n_applique_jamais_ses_effets(db):
    """Exclusif des trois autres branches : la créature EST l'effet du sort."""
    lanceur = _lanceur(pm=60)
    lanceur["currentPV"] = 50
    doc = _combat([lanceur], [_monstre()])
    _action_invoquer(doc, _sort_invocation(effets={"pv": 30, "buffs": {"F": 20}, "duree": 5}))
    assert lanceur["currentPV"] == 50
    assert lanceur["effets_actifs"] == []


# ── Tour d'IA ────────────────────────────────────────────────────────────────────

def test_la_creature_fonce_sur_l_ennemi_et_frappe(db, monkeypatch):
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 5)   # touche toujours
    lanceur = _lanceur()
    monstre = _monstre(pos=(6, 5), pv=200)
    doc = _combat([lanceur], [monstre])
    grid = combat_mod.get_combat_grid(doc)
    invoc = invoquer(doc, lanceur, normaliser_sort(_sort_invocation()), grid)[0]
    invoc["pos"] = {"x": 2, "y": 5}
    doc["acteur_courant_index"] = doc["ordre_initiative"].index(invoc["id"])

    _run_invocation_turn(doc, invoc, grid)

    assert invoc["pos"] != {"x": 2, "y": 5}            # elle a avancé
    assert monstre["currentPV"] < 200                   # et frappé
    assert any(e["kind"] == "move" for e in doc["log"])


def test_la_duree_se_decompte_a_chaque_tour_puis_dissipe(db):
    lanceur = _lanceur()
    doc = _combat([lanceur], [_monstre(pos=(10, 10))])   # hors de portée : elle ne fait que marcher
    grid = combat_mod.get_combat_grid(doc)
    invoc = invoquer(doc, lanceur, normaliser_sort(_sort_invocation(duree=2)), grid)[0]
    doc["acteur_courant_index"] = doc["ordre_initiative"].index(invoc["id"])

    _run_invocation_turn(doc, invoc, grid)
    assert invoc["invocation_restants"] == 1
    assert not invoc.get("dissipe")

    doc["acteur_courant_index"] = doc["ordre_initiative"].index(invoc["id"])
    _run_invocation_turn(doc, invoc, grid)
    assert invoc["invocation_restants"] == 0
    assert invoc["dissipe"] is True
    assert invoc["currentPV"] == 0        # sa case se libère, les monstres cessent de la viser


# ── Purge ────────────────────────────────────────────────────────────────────────

def test_purge_retire_la_creature_des_deux_listes(db):
    lanceur = _lanceur()
    doc = _combat([lanceur], [_monstre()])
    grid = combat_mod.get_combat_grid(doc)
    invoc = invoquer(doc, lanceur, normaliser_sort(_sort_invocation()), grid)[0]
    invoc["dissipe"] = True
    invoc["currentPV"] = 0

    _purger_invocations(doc)
    assert [j["id"] for j in doc["joueurs"]] == ["joueur_0"]
    assert doc["ordre_initiative"] == ["joueur_0", "monstre_0"]


def test_purge_recale_l_index_quand_la_creature_jouait_avant_lui(db):
    """Retrait AVANT l'index courant : sans recalage, l'acteur courant changerait tout seul."""
    lanceur = _lanceur()
    doc = _combat([lanceur], [_monstre()])
    grid = combat_mod.get_combat_grid(doc)
    invoc = invoquer(doc, lanceur, normaliser_sort(_sort_invocation()), grid)[0]
    # ordre = [joueur_0, joueur_1(invoc), monstre_0] ; c'est au monstre de jouer.
    doc["acteur_courant_index"] = 2
    invoc["dissipe"] = True

    _purger_invocations(doc)
    assert doc["ordre_initiative"] == ["joueur_0", "monstre_0"]
    assert doc["ordre_initiative"][doc["acteur_courant_index"]] == "monstre_0"


def test_purge_de_l_acteur_courant_passe_au_suivant(db):
    lanceur = _lanceur()
    doc = _combat([lanceur], [_monstre()])
    grid = combat_mod.get_combat_grid(doc)
    invoc = invoquer(doc, lanceur, normaliser_sort(_sort_invocation()), grid)[0]
    doc["acteur_courant_index"] = 1        # la créature a la main au moment où elle part
    invoc["dissipe"] = True

    _purger_invocations(doc)
    assert doc["ordre_initiative"] == ["joueur_0", "monstre_0"]
    assert doc["ordre_initiative"][doc["acteur_courant_index"]] == "monstre_0"


def test_purge_en_fin_d_ordre_passe_au_tour_suivant(db):
    lanceur = _lanceur()
    doc = _combat([lanceur], [])
    grid = combat_mod.get_combat_grid(doc)
    invoc = invoquer(doc, lanceur, normaliser_sort(_sort_invocation()), grid)[0]
    doc["acteur_courant_index"] = 1        # dernière entrée de l'ordre
    invoc["dissipe"] = True

    _purger_invocations(doc)
    assert doc["ordre_initiative"] == ["joueur_0"]
    assert doc["acteur_courant_index"] == 0
    assert doc["tour"] == 2


def test_purge_ne_touche_jamais_un_compagnon_a_terre(db):
    """Un compagnon KO reste dans le combat (il peut être relevé) : seul ce qui porte
    `est_invocation` est retiré."""
    lanceur = _lanceur()
    compagnon = build_joueur_snapshot(_character("Borin"), joueur_index=1)
    compagnon["pos"] = {"x": 1, "y": 1}
    compagnon["currentPV"] = 0
    doc = _combat([lanceur, compagnon], [_monstre()])

    _purger_invocations(doc)
    assert [j["id"] for j in doc["joueurs"]] == ["joueur_0", "joueur_1"]


# ── Elle n'empêche pas la défaite ────────────────────────────────────────────────

def test_la_creature_ne_compte_pas_dans_les_combattants_vivants(db):
    """`jouable: False` : un groupe entièrement à terre perd même si elle tient debout —
    sinon plus personne ne pourrait jouer et le combat resterait bloqué."""
    lanceur = _lanceur()
    doc = _combat([lanceur], [_monstre()])
    grid = combat_mod.get_combat_grid(doc)
    invoquer(doc, lanceur, normaliser_sort(_sort_invocation()), grid)
    lanceur["currentPV"] = 0
    assert combat_mod._combattants_vivants(doc) == []
    # …mais elle reste CIBLABLE tant qu'elle est debout.
    assert [j["id"] for j in combat_mod._joueurs_vivants(doc)] == ["joueur_1"]


# ── Intégration : le tour de la créature est joué par `_resolve_until_player` ─────

def test_le_moteur_joue_la_creature_puis_rend_la_main_au_joueur(db, monkeypatch):
    """La main ne doit JAMAIS s'arrêter sur une invocation : elle n'a pas de budget que
    le client puisse dépenser, le combat se figerait là."""
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 5)
    lanceur = _lanceur()
    monstre = _monstre(pos=(4, 5), pv=500)
    doc = _combat([lanceur], [monstre])
    grid = combat_mod.get_combat_grid(doc)
    invoc = invoquer(doc, lanceur, normaliser_sort(_sort_invocation(duree=1)), grid)[0]
    pv_avant = monstre["currentPV"]

    combat_mod._advance_and_resolve(doc, grid)

    assert monstre["currentPV"] < pv_avant                    # la créature a frappé
    # Durée 1 ⇒ elle s'est dissipée dans la foulée et a quitté le combat.
    assert [j["id"] for j in doc["joueurs"]] == ["joueur_0"]
    assert doc["ordre_initiative"] == ["joueur_0", "monstre_0"]
    # La main est revenue au joueur (le monstre a joué entre-temps).
    assert doc["ordre_initiative"][doc["acteur_courant_index"]] == "joueur_0"


def test_une_creature_abattue_quitte_le_combat(db, monkeypatch):
    """Tuée par un monstre, elle est marquée `dissipe` à l'impact — sans quoi elle
    traînerait à 0 PV : son propre tour, qui la retirerait, est justement sauté."""
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 5)
    lanceur = _lanceur()
    monstre = _monstre(pos=(4, 5), pv=500)
    monstre["degats_cc"] = "50D10"                            # un coup suffit
    doc = _combat([lanceur], [monstre])
    grid = combat_mod.get_combat_grid(doc)
    invoc = invoquer(doc, lanceur, normaliser_sort(_sort_invocation(duree=9)), grid)[0]
    invoc["pos"] = {"x": 4, "y": 4}                           # au contact du monstre

    combat_mod._do_attack_on(doc, monstre, invoc)
    assert invoc["currentPV"] == 0 and invoc["dissipe"] is True
    assert any("se dissipe" in e["texte"] for e in doc["log"])

    _purger_invocations(doc)
    assert [j["id"] for j in doc["joueurs"]] == ["joueur_0"]


def test_un_indice_de_snapshot_n_est_jamais_reattribue(db):
    """Une invocation purgée libère sa place dans `joueurs` — mais pas son id. Le réutiliser
    ferait s'appliquer à la nouvelle créature les entrées de journal (`etat`) de l'ancienne."""
    lanceur = _lanceur()
    doc = _combat([lanceur], [_monstre()])
    grid = combat_mod.get_combat_grid(doc)

    premiere = invoquer(doc, lanceur, normaliser_sort(_sort_invocation()), grid)[0]
    assert premiere["id"] == "joueur_1"
    premiere["dissipe"] = True
    _purger_invocations(doc)
    assert [j["id"] for j in doc["joueurs"]] == ["joueur_0"]

    doc["acteur_courant_index"] = 0
    seconde = invoquer(doc, lanceur, normaliser_sort(_sort_invocation()), grid)[0]
    assert seconde["id"] == "joueur_2"        # et non « joueur_1 » recyclé


def test_l_indice_repart_du_plus_grand_present_sur_un_combat_deja_en_base(db):
    """Doc d'avant la feature : aucun compteur, mais aucune invocation purgée non plus —
    le plus grand indice présent + 1 est donc exact (aucune migration)."""
    lanceur = _lanceur()
    compagnon = build_joueur_snapshot(_character("Borin"), joueur_index=4)
    compagnon["pos"] = {"x": 1, "y": 1}
    doc = _combat([lanceur, compagnon], [_monstre()])
    assert "prochain_joueur_index" not in doc
    grid = combat_mod.get_combat_grid(doc)

    invoc = invoquer(doc, lanceur, normaliser_sort(_sort_invocation()), grid)[0]
    assert invoc["id"] == "joueur_5"
