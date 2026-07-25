# tests/test_sorts.py
#
# Tests du système de sorts (PM + composants + apprentissage). Logique pure :
# utils/sorts.py (normalisation, fusion, composants, grimoires) + la branche
# "sort" de resolve_action (utils/combat.py) sur un doc combat artisanal.

import pytest

from models import character_stats
from models.character_stats import BaseStats, compute_derived_stats
from utils.sorts import (
    normaliser_sort, effets_de_sort, fusionner_effets, composants_etat,
    effets_effectifs, sort_utilisable_combat, sort_utilisable_exploration,
    empiler_effet_sort, cout_apprentissage, grimoire_pour, sorts_apprenables,
    sorts_epingles_effectifs,
    ecole_native, magie_de_sort, niveau_ecole, magies_pratiquees,
    ecoles_du_monde, peut_apprendre_magie, ecoles_achetables, cout_ecole,
    ecoles_de_grimoire,
)


# rules:vocations minimal (map vocation → école de magie) pour les tests d'école.
_RULES_VOCS = {"_id": "rules:vocations", "type": "rules", "value": [
    {"id": "elementaliste", "magie": "Élémentaire"},
    {"id": "pretre", "magie": "Sainte"},
    {"id": "necromancien", "magie": "Noire"},
    {"id": "demoniste", "magie": "Noire"},
    {"id": "illusionniste", "magie": "Illusoire"},
    {"id": "lettre", "magie": "Illusoire"},
    {"id": "guerrier", "magie": ""},
]}
from utils import combat as combat_mod
from utils.combat import _magic_hit_threshold, resolve_action, roll_dice


def _sort(**overrides):
    doc = {
        "_id": "sort:test", "type": "sort", "nom": "Trait", "icon": "🔥",
        "vocation": "elementaliste", "niveau": 0, "cout_pm": 4,
        "cible": "ennemi", "portee": 3,
        "effets": {"degats": "2D6"},
        "composants": [
            {"item": "item:soufre", "consomme": True, "bonus": {"degats": "1D6"}},
            {"item": "item:cristal", "consomme": False, "bonus": {"degats": "2"}},
        ],
    }
    doc.update(overrides)
    return doc


# ── Normalisation ────────────────────────────────────────────────────────────────

def test_normaliser_rejette_docs_invalides():
    assert normaliser_sort(None) is None
    assert normaliser_sort({"type": "item"}) is None
    assert normaliser_sort(_sort(vocation=None)) is None
    assert normaliser_sort(_sort(cout_pm=0)) is None      # un sort coûte TOUJOURS des PM
    assert normaliser_sort(_sort(cout_pm=-3)) is None


def test_normaliser_defauts_et_champs():
    s = normaliser_sort({"_id": "sort:x", "type": "sort", "vocation": "mage", "cout_pm": 2})
    assert s["cible"] == "soi" and s["portee"] == 0 and s["niveau"] == 0
    assert s["effets"]["degats"] == "" and s["effets"]["buffs"] == {}
    assert s["composants"] == []


def test_normaliser_conserve_buff_V_et_purge_composant_sans_item():
    # V n'est plus filtrée : elle se buffe à SON échelle (1-10), y compris via un
    # composant. Le filtre historique protégeait d'une faute d'échelle, mais il rendait
    # inexprimable tout effet portant sur le déplacement (entrave, hâte).
    s = normaliser_sort(_sort(
        effets={"buffs": {"V": 3, "F": 10}, "duree": 4},
        composants=[{"consomme": True, "bonus": {"pv": 5}},  # pas d'item → ignoré
                    {"item": "item:os", "bonus": {"buffs": {"V": 2, "Vol": 5}}}],
    ))
    assert s["effets"]["buffs"] == {"V": 3, "F": 10}
    assert len(s["composants"]) == 1
    assert s["composants"][0]["bonus"]["buffs"] == {"V": 2, "Vol": 5}


# ── Fusion des effets + bonus ────────────────────────────────────────────────────

def test_fusionner_effets_additif():
    base = effets_de_sort(_sort(effets={"degats": "2D6", "pv": 5, "buffs": {"F": 10}, "duree": 3}))
    out = fusionner_effets(base, [
        {"degats": "1D6", "pv": 8, "buffs": {"F": 5, "Ag": 5}, "duree": 2},
        {"degats": "2"},
    ])
    assert out["degats"] == "2D6+1D6+2"
    assert out["pv"] == 13 and out["duree"] == 5
    assert out["buffs"] == {"F": 15, "Ag": 5}


def test_fusion_degats_base_vide():
    out = fusionner_effets({"degats": ""}, [{"degats": "1D4"}])
    assert out["degats"] == "1D4"


def test_notation_concatenee_lancable(monkeypatch):
    # La notation composite issue de la fusion doit être évaluable par roll_dice.
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: b)
    assert roll_dice("2D6+1D6+2") == 12 + 6 + 2


# ── Composants : consommé (sac) vs catalyseur (porté) ────────────────────────────

def _perso(**extra):
    base = {
        "caracteristiques_current": {"V": 5, "F": 40, "R": 40, "Ag": 30,
                                     "Vol": 40, "Int": 60, "Cha": 20, "Ch": 20},
        "currentPV": 100, "currentPM": 50,
        "voc": "elementaliste",
        "inventaire": [], "slots": {},
        "vocations_niveaux": {"elementaliste": 0},
        "sorts_connus": [],
    }
    base.update(extra)
    return base


def test_composants_etat_consomme_exige_le_sac():
    sort = normaliser_sort(_sort())
    # Soufre seulement ÉQUIPÉ (main) → non consommable ; cristal équipé = catalyseur OK.
    perso = _perso(inventaire=[], slots={"main_droite": "item:soufre", "cou": "item:cristal"})
    etat = {c["item"]: c["disponible"] for c in composants_etat(sort, perso)}
    assert etat == {"item:soufre": False, "item:cristal": True}


def test_composants_etat_refs_string_et_objet():
    sort = normaliser_sort(_sort())
    perso = _perso(inventaire=[{"item": "item:soufre", "poids": 0.2}, "item:cristal"])
    etat = {c["item"]: c["disponible"] for c in composants_etat(sort, perso)}
    assert etat == {"item:soufre": True, "item:cristal": True}


def test_effets_effectifs_engages_partiels():
    sort = normaliser_sort(_sort())
    assert effets_effectifs(sort, [])["degats"] == "2D6"
    assert effets_effectifs(sort, ["item:soufre"])["degats"] == "2D6+1D6"
    assert effets_effectifs(sort, ["item:soufre", "item:cristal"])["degats"] == "2D6+1D6+2"
    assert effets_effectifs(sort, ["item:inconnu"])["degats"] == "2D6"


# ── Éligibilité combat / exploration ─────────────────────────────────────────────

def test_sort_utilisable_combat():
    assert sort_utilisable_combat(normaliser_sort(_sort()))                       # dégâts
    assert sort_utilisable_combat(normaliser_sort(_sort(cible="soi", effets={"pv": 10})))
    # Buff pur (« Armure de givre ») : utilisable en combat, le snapshot porte l'effet
    # vivant et le décrémente au tour de son porteur.
    assert sort_utilisable_combat(normaliser_sort(
        _sort(cible="soi", effets={"buffs": {"F": 10}, "duree": 3})))
    assert sort_utilisable_combat(normaliser_sort(
        _sort(cible="soi", effets={"esquive": 10, "duree": 3})))
    # Sans durée, un buff n'a rien à empiler : toujours refusé.
    assert not sort_utilisable_combat(normaliser_sort(
        _sort(cible="soi", effets={"buffs": {"F": 10}})))


def test_sort_utilisable_exploration():
    assert not sort_utilisable_exploration(normaliser_sort(_sort()))              # ennemi
    assert sort_utilisable_exploration(normaliser_sort(_sort(cible="soi", effets={"pv": 10})))
    assert sort_utilisable_exploration(normaliser_sort(
        _sort(cible="soi", effets={"buffs": {"F": 10}, "duree": 3})))
    assert not sort_utilisable_exploration(normaliser_sort(
        _sort(cible="soi", effets={"buffs": {"F": 10}})))                         # durée 0


def test_empiler_effet_sort_meme_forme_que_consommables():
    perso = _perso()
    sort = normaliser_sort(_sort(cible="soi"))
    eff = fusionner_effets({"buffs": {"F": 10}, "duree": 3, "regen_pv": 1}, [])
    entry = empiler_effet_sort(perso, sort, eff)
    assert entry["restants"] == 3 and entry["buffs"] == {"F": 10} and entry["regen_pv"] == 1
    assert perso["effets_actifs"] == [entry]
    # Part instantanée seule → rien à empiler.
    assert empiler_effet_sort(perso, sort, fusionner_effets({"pv": 10}, [])) is None


# ── Apprentissage : coût, grimoire, apprenables ──────────────────────────────────

def test_cout_apprentissage(monkeypatch):
    monkeypatch.setattr(character_stats, "SORT_COUT_COEFF", 2)
    assert cout_apprentissage(normaliser_sort(_sort(niveau=0))) == 2
    assert cout_apprentissage(normaliser_sort(_sort(niveau=3))) == 8


_GRIMOIRES = {
    "item:grimoire_trait": {"_id": "item:grimoire_trait", "sous_categorie": "grimoire",
                            "sorts": ["sort:test"]},
    "item:soufre": {"_id": "item:soufre", "categorie": "composant"},
}


def _resolve(ref):
    rid = ref.get("item") if isinstance(ref, dict) else ref
    return _GRIMOIRES.get(rid)


def test_grimoire_pour_sac_slot_absent():
    assert grimoire_pour(_perso(inventaire=["item:grimoire_trait"]), "sort:test", _resolve)
    assert grimoire_pour(_perso(slots={"main_gauche": "item:grimoire_trait"}), "sort:test", _resolve)
    assert grimoire_pour(_perso(inventaire=["item:soufre"]), "sort:test", _resolve) is None
    assert grimoire_pour(_perso(inventaire=["item:grimoire_trait"]), "sort:autre", _resolve) is None


def test_sorts_apprenables_gates(monkeypatch):
    monkeypatch.setattr(character_stats, "SORT_COUT_COEFF", 2)
    docs = [
        _sort(_id="sort:a", niveau=0),
        _sort(_id="sort:b", niveau=2),                       # niveau voc insuffisant
        _sort(_id="sort:c", niveau=0, vocation="pretre"),    # vocation non pratiquée
        _sort(_id="sort:connu", niveau=0),                   # déjà connu
        {"_id": "sort:invalide", "type": "sort", "vocation": "elementaliste", "cout_pm": 0},
    ]
    for d in docs:
        d["_id"] = d.get("_id", "sort:x")
    find_docs = lambda sel: docs
    perso = _perso(vocations_niveaux={"elementaliste": 1}, sorts_connus=["sort:connu"],
                   inventaire=["item:grimoire_trait"])
    out = sorts_apprenables(perso, find_docs, _resolve, _RULES_VOCS)
    assert [s["id"] for s in out] == ["sort:a"]
    assert out[0]["cout_points"] == 2
    assert out[0]["grimoire_ok"] is False   # le grimoire porté n'enseigne que sort:test


# ── Écoles de magie : accès par école, achat (lettré), niveau par école ───────────

def test_ecole_native_et_fallback_magie():
    assert ecole_native("elementaliste", _RULES_VOCS) == "Élémentaire"
    assert ecole_native("guerrier", _RULES_VOCS) is None      # vocation non magique
    # Sort avec champ magie explicite → utilisé tel quel.
    s = normaliser_sort(_sort(magie="Noire", vocation="elementaliste"))
    assert magie_de_sort(s, _RULES_VOCS) == "Noire"
    # Sort sans champ magie → école dérivée de la vocation (rétro-compat).
    s2 = normaliser_sort(_sort(vocation="pretre"))
    assert s2["magie"] is None
    assert magie_de_sort(s2, _RULES_VOCS) == "Sainte"


def test_ecoles_de_grimoire():
    sorts = {
        "sort:feu":   _sort(_id="sort:feu", magie="Élémentaire"),
        "sort:givre": _sort(_id="sort:givre", magie="Élémentaire"),
        # Sans champ `magie` → école dérivée de la vocation (rétro-compat).
        "sort:soin":  _sort(_id="sort:soin", vocation="pretre"),
        # Vocation non magique → aucune école à annoncer.
        "sort:cri":   _sort(_id="sort:cri", vocation="guerrier"),
    }
    get_doc = lambda i: sorts.get(i)
    grim = lambda ids: {"_id": "item:g", "sous_categorie": "grimoire", "sorts": ids}

    # Union triée, dédupliquée, ids morts ignorés.
    assert ecoles_de_grimoire(grim(["sort:feu", "sort:givre"]), get_doc, _RULES_VOCS) == ["Élémentaire"]
    assert ecoles_de_grimoire(grim(["sort:feu", "sort:soin"]), get_doc, _RULES_VOCS) \
        == ["Sainte", "Élémentaire"]
    assert ecoles_de_grimoire(grim(["sort:feu", "sort:mort"]), get_doc, _RULES_VOCS) == ["Élémentaire"]
    # École non résoluble, grimoire vide, item qui n'est pas un grimoire → [].
    assert ecoles_de_grimoire(grim(["sort:cri"]), get_doc, _RULES_VOCS) == []
    assert ecoles_de_grimoire(grim([]), get_doc, _RULES_VOCS) == []
    assert ecoles_de_grimoire({"_id": "item:epee", "sorts": ["sort:feu"]}, get_doc, _RULES_VOCS) == []
    assert ecoles_de_grimoire(None, get_doc, _RULES_VOCS) == []


def test_niveau_ecole_native_achetee_absente():
    perso = _perso(voc="lettre", vocations_niveaux={"lettre": 3},
                   magies_apprises={"Noire": 1})
    assert niveau_ecole(perso, "Illusoire", _RULES_VOCS) == 3    # native (via vocations_niveaux)
    assert niveau_ecole(perso, "Noire", _RULES_VOCS) == 1        # achetée
    assert niveau_ecole(perso, "Sainte", _RULES_VOCS) is None    # non pratiquée
    assert magies_pratiquees(perso, _RULES_VOCS) == {"Illusoire": 3, "Noire": 1}


def test_peut_apprendre_magie_et_achetables(monkeypatch):
    monkeypatch.setattr(character_stats, "MAGIE_POLYVALENTE_VOCATIONS", ["lettre"])
    lettre = _perso(voc="lettre", vocations_niveaux={"lettre": 0})
    elem = _perso(voc="elementaliste")
    assert peut_apprendre_magie(lettre) is True
    assert peut_apprendre_magie(elem) is False
    assert peut_apprendre_magie(_perso(voc="guerrier")) is False
    # Le lettré peut acheter toutes les écoles sauf sa native (Illusoire).
    achet = ecoles_achetables(lettre, _RULES_VOCS)
    assert "Illusoire" not in achet
    assert set(achet) == set(ecoles_du_monde(_RULES_VOCS)) - {"Illusoire"}
    # Le spécialiste n'a aucune école achetable.
    assert ecoles_achetables(elem, _RULES_VOCS) == []


def test_cout_ecole(monkeypatch):
    monkeypatch.setattr(character_stats, "MAGIE_ECOLE_COUT_COEFF", 2)
    assert cout_ecole(0) == 2
    assert cout_ecole(3) == 8


def test_lettre_apprend_sort_ecole_achetee(monkeypatch):
    """Un lettré ayant acheté l'école Noire peut apprendre un sort nécromancien niveau 0."""
    monkeypatch.setattr(character_stats, "SORT_COUT_COEFF", 2)
    docs = [_sort(_id="sort:necro", niveau=0, vocation="necromancien")]   # magie fallback → Noire
    find_docs = lambda sel: docs
    lettre = _perso(voc="lettre", vocations_niveaux={"lettre": 0},
                    magies_apprises={"Noire": 0})
    out = sorts_apprenables(lettre, find_docs, _resolve, _RULES_VOCS)
    assert [s["id"] for s in out] == ["sort:necro"]
    assert out[0]["magie"] == "Noire"
    # Sans l'achat de l'école, rien n'est apprenable.
    lettre_sans = _perso(voc="lettre", vocations_niveaux={"lettre": 0})
    assert sorts_apprenables(lettre_sans, find_docs, _resolve, _RULES_VOCS) == []


# ── Jet magique + dérivée toucher_magique ────────────────────────────────────────

def test_magic_hit_threshold():
    assert _magic_hit_threshold(50, 50) == 50
    assert _magic_hit_threshold(200, 0) == 95
    assert _magic_hit_threshold(0, 200) == 5


def test_toucher_magique_derive():
    derived = compute_derived_stats(BaseStats(int=60, vol=40), niveau=0)
    assert derived.toucher_magique == (60 * 3 + 40) // 4  # 55


# ── resolve_action "sort" (combat) ───────────────────────────────────────────────

def _combat(joueur_extra=None, monstres=None, cells=None):
    w, h = 7, 7
    joueur = {
        "id": "joueur_0", "nom": "Frida", "vivant": True,
        "currentPV": 60, "pv_max": 80, "currentPM": 20, "pm_max": 30,
        "actions_restantes": 3, "actions_max": 3,
        "cells_moved": 0, "attaques": 0, "ramasses": 0, "consommes": 0, "sorts": 0,
        "pos": {"x": 3, "y": 5}, "portee": 1,
        "charge": 10.0, "charge_max": 100.0,
        "deplacement": 4, "deplacement_base": 4,
        "toucher_magique": 50, "initiative": 30,
    }
    joueur.update(joueur_extra or {})
    if monstres is None:
        monstres = [_monstre("monstre_0", 3, 2)]
    return {
        "type": "combat", "status": "active", "tour": 1, "log": [],
        "ordre_initiative": ["joueur_0"] + [m["id"] for m in monstres],
        "acteur_courant_index": 0,
        "joueurs": [joueur], "monstres": monstres,
        "grid": {"dims": {"x": w, "y": h},
                 "cells": cells or [[1] * w for _ in range(h)], "nav": {}},
    }


def _monstre(mid, x, y, **extra):
    m = {"id": mid, "nom": "Loup", "vivant": True, "pos": {"x": x, "y": y},
         "currentPV": 20, "pv_max": 20, "pa": 5, "ag": 30, "pm_def": 30,
         "initiative": 20, "deplacement": 3, "xp_reward": 5}
    m.update(extra)
    return m


def _sort_arg(sort_doc, engages=None, poids=0.0):
    s = normaliser_sort(sort_doc)
    return {"doc": s, "effets": effets_effectifs(s, engages or []),
            "composants_engages": engages or [], "poids_consommes": poids}


def test_sort_pm_insuffisants():
    combat = _combat(joueur_extra={"currentPM": 3})
    res = resolve_action(combat, "sort", cible_id="monstre_0",
                         sort=_sort_arg(_sort(cout_pm=4)))
    assert "error" in res
    assert combat["joueurs"][0]["currentPM"] == 3
    assert combat["joueurs"][0]["sorts"] == 0


def test_sort_rate_debite_les_pm(monkeypatch):
    # 90 > seuil 70 = raté ORDINAIRE : sous CRIT_ECHEC_MIN, donc sans perte d'action
    # supplémentaire (un échec critique, lui, coûterait une action de plus).
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 90)
    combat = _combat()
    res = resolve_action(combat, "sort", cible_id="monstre_0", sort=_sort_arg(_sort()))
    assert res["hit"] is False
    assert combat["joueurs"][0]["currentPM"] == 16      # 20 − 4 : le sort part même raté
    assert combat["monstres"][0]["currentPV"] == 20
    assert combat["joueurs"][0]["sorts"] == 1
    assert combat["joueurs"][0]["actions_restantes"] == 2


def test_sort_touche_sans_soustraire_les_pa(monkeypatch):
    # d100 à 50 (touche ORDINAIRE sous seuil 70, pas un critique qui doublerait les
    # dégâts) et dés à 1.
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50 if b == 100 else 1)
    combat = _combat()
    res = resolve_action(combat, "sort", cible_id="monstre_0", sort=_sort_arg(_sort()))
    # 2D6 à 1 → 2 dégâts PLEINS malgré pa=5 (l'armure n'arrête pas la magie).
    assert res["hit"] is True and res["dmg"] == 2
    assert combat["monstres"][0]["currentPV"] == 18


def test_sort_portee_et_engagement():
    # Cible à distance 3, portée 2 → hors de portée.
    combat = _combat()
    res = resolve_action(combat, "sort", cible_id="monstre_0",
                         sort=_sort_arg(_sort(portee=2)))
    assert res["error"] == "Cible hors de portée."
    # Un ennemi adjacent interdit l'incantation à distance (portée > 1)…
    combat = _combat(monstres=[_monstre("monstre_0", 3, 2), _monstre("monstre_1", 4, 5)])
    res = resolve_action(combat, "sort", cible_id="monstre_0", sort=_sort_arg(_sort()))
    assert "corps à corps" in res["error"]
    # … mais un sort de CONTACT (portée 1) reste lançable en mêlée.
    res = resolve_action(combat, "sort", cible_id="monstre_1",
                         sort=_sort_arg(_sort(portee=1)))
    assert "error" not in res


def test_sort_ligne_de_vue_obstruee():
    cells = [[1] * 7 for _ in range(7)]
    cells[3][3] = -1  # mur entre le joueur (3,5) et la cible (3,2)
    combat = _combat(cells=cells)
    res = resolve_action(combat, "sort", cible_id="monstre_0", sort=_sort_arg(_sort()))
    assert res["error"] == "Ligne de vue obstruée."


def test_sort_soin_sur_soi_clampe(monkeypatch):
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 1)
    combat = _combat(joueur_extra={"currentPV": 75})
    sort_doc = _sort(cible="soi", portee=0, cout_pm=3, effets={"pv": 12, "pm": 2})
    res = resolve_action(combat, "sort", sort=_sort_arg(sort_doc))
    joueur = combat["joueurs"][0]
    assert joueur["currentPV"] == 80 and res["pv_rendu"] == 5          # clamp pv_max
    assert joueur["currentPM"] == 19 and res["pm_rendu"] == 2          # 20 − 3 + 2
    assert joueur["sorts"] == 1


def test_sort_composants_consommes_baissent_la_charge(monkeypatch):
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 1)
    combat = _combat()
    res = resolve_action(combat, "sort", cible_id="monstre_0",
                         sort=_sort_arg(_sort(), engages=["item:soufre"], poids=0.5))
    assert combat["joueurs"][0]["charge"] == 9.5
    assert res["charge"] == 9.5


def test_sort_retro_compat_pm_def_absent(monkeypatch):
    # Combat créé avant la feature : monstre sans pm_def → traité comme 0.
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 95)
    monstre = _monstre("monstre_0", 3, 2)
    del monstre["pm_def"]
    combat = _combat(monstres=[monstre])
    res = resolve_action(combat, "sort", cible_id="monstre_0", sort=_sort_arg(_sort()))
    # toucher 50 vs pm_def 0 → seuil 95 : le jet 95 touche encore.
    assert res["hit"] is True


def test_sort_buff_pur_accepte_en_combat():
    # Un sort à durée pure s'empile sur les effets vivants du snapshot et coûte ses PM.
    combat = _combat()
    sort_doc = _sort(cible="soi", effets={"buffs": {"F": 10}, "duree": 3})
    res = resolve_action(combat, "sort", sort=_sort_arg(sort_doc))
    assert "error" not in res
    assert combat["joueurs"][0]["currentPM"] < 20
    effets = combat["joueurs"][0]["effets_actifs"]
    assert [e["restants"] for e in effets] == [3]
    assert effets[0]["buffs"] == {"F": 10}


# ── Sorts épinglés (accès rapide en combat) ──────────────────────────────────────

def test_epingles_champ_absent_auto_premier_sort():
    # Perso d'avant la feature : le premier sort connu est auto-épinglé.
    char = {"sorts_connus": ["sort:a", "sort:b"]}
    assert sorts_epingles_effectifs(char) == ["sort:a"]


def test_epingles_champ_absent_sans_sort():
    assert sorts_epingles_effectifs({}) == []
    assert sorts_epingles_effectifs(None) == []


def test_epingles_champ_present_filtre_aux_connus():
    # Sort désappris/retiré → purgé de la liste effective, ordre conservé.
    char = {"sorts_connus": ["sort:a", "sort:c"],
            "sorts_epingles": ["sort:c", "sort:oublie", "sort:a"]}
    assert sorts_epingles_effectifs(char) == ["sort:c", "sort:a"]


def test_epingles_champ_present_vide_pas_de_fallback():
    # Le joueur a explicitement tout désépinglé : on respecte son choix.
    char = {"sorts_connus": ["sort:a"], "sorts_epingles": []}
    assert sorts_epingles_effectifs(char) == []
