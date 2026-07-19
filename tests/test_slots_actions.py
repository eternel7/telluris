# tests/test_slots_actions.py
#
# Tests de la barre d'action de combat à slots (utils/slots_actions.py). Logique pure :
# migration à la lecture depuis les anciens épinglés, bornes de position, appartenance
# des entrées, purge des refs caduques, et surtout l'INVARIANTE des trois actions
# obligatoires (mêlée, ramasser, fuir) qui se déplacent mais ne disparaissent jamais.

import pytest

from models import character_stats
from utils import slots_actions as sa


# ── Base de docs injectée ────────────────────────────────────────────────────────

DOCS = {
    "sort:trait": {"_id": "sort:trait", "type": "sort", "nom": "Trait de feu",
                   "icon": "🔥", "vocation": "elementaliste", "niveau": 0, "cout_pm": 2,
                   "cible": "ennemi", "portee": 4, "effets": {"degats": "1D6"}},
    "sort:soin": {"_id": "sort:soin", "type": "sort", "nom": "Petit soin",
                  "icon": "💚", "vocation": "pretre", "niveau": 0, "cout_pm": 3,
                  "cible": "soi", "portee": 0, "effets": {"pv": 5}},
    "competence:frappe": {"_id": "competence:frappe", "type": "competence",
                          "nom": "Frappe puissante", "icon": "⚔️", "vocation": "guerrier",
                          "niveau": 0, "mode": "active", "cout_pm": 0, "cible": "ennemi",
                          "jet": "cc", "portee": 1, "effets": {"degats": "2D6"}},
    "competence:maitrise": {"_id": "competence:maitrise", "type": "competence",
                            "nom": "Maîtrise", "icon": "🗡️", "vocation": "guerrier",
                            "niveau": 0, "mode": "passive", "effets": {"buffs": {"F": 4}}},
    "item:potion": {"_id": "item:potion", "type": "item", "nom": "Potion de soin",
                    "icon": "🧪", "categorie": "consommable", "poids": 0.5,
                    "effets": {"pv": 10}},
    "item:epee": {"_id": "item:epee", "type": "item", "nom": "Épée", "categorie": "arme"},
}


def get_doc(doc_id):
    return DOCS.get(doc_id)


def _perso(**overrides):
    doc = {
        "_id": "character:test",
        "sorts_connus": ["sort:trait", "sort:soin"],
        "competences_connues": ["competence:frappe", "competence:maitrise"],
        "inventaire": ["item:epee", {"item": "item:potion", "poids": 0.5}],
    }
    doc.update(overrides)
    return doc


CAC = {"type": "attaque", "ref": "cac"}
RAMASSER = {"type": "ramasser", "ref": ""}
FUIR = {"type": "fuir", "ref": ""}


def _sort(ref, composants=True):
    """Entrée de sort NORMALISÉE (le flag `composants` est toujours posé à la lecture)."""
    return {"type": "sort", "ref": ref, "composants": composants}


# ── Taille de la barre (world-var) ───────────────────────────────────────────────

def test_slots_max_lu_via_le_module(monkeypatch):
    """La world-var doit être relue à chaud, pas capturée à l'import."""
    monkeypatch.setattr(character_stats, "COMBAT_SLOTS_MAX", 12)
    assert sa.slots_max() == 12
    assert len(sa.slots_effectifs(_perso(), get_doc)) == 12


def test_slots_max_planche_au_socle_obligatoire(monkeypatch):
    """Une barre plus courte que ⚔🫳🏃 serait injouable : le plancher la protège."""
    monkeypatch.setattr(character_stats, "COMBAT_SLOTS_MAX", 1)
    assert sa.slots_max() == 3


# ── Migration à la lecture (champ absent) ────────────────────────────────────────

def test_champ_absent_derive_du_socle_et_des_anciens_epingles():
    perso = _perso(sorts_epingles=["sort:trait"],
                   competences_epinglees=["competence:frappe"])
    slots = sa.slots_effectifs(perso, get_doc)

    assert slots[0] == CAC
    assert slots[1] == RAMASSER
    assert slots[2] == FUIR
    assert slots[3] == _sort("sort:trait")
    assert slots[4] == {"type": "competence", "ref": "competence:frappe"}
    assert all(s is None for s in slots[5:])


def test_champ_absent_sans_epingles_auto_pin_historique():
    """Sans champ d'épinglage non plus, l'auto-pin d'avant la refonte s'applique :
    premier sort connu + première compétence ACTIVE (la passive est sautée)."""
    slots = sa.slots_effectifs(_perso(), get_doc)
    assert slots[3] == _sort("sort:trait")
    assert slots[4] == {"type": "competence", "ref": "competence:frappe"}


def test_champ_present_vide_ne_repeuple_pas_les_libres():
    """Liste vide = choix explicite du joueur : seules les obligatoires reviennent."""
    perso = _perso(slots_actions=[], sorts_epingles=["sort:trait"])
    slots = sa.slots_effectifs(perso, get_doc)
    assert [s for s in slots if s is not None] == [CAC, RAMASSER, FUIR]


# ── Normalisation & purge ────────────────────────────────────────────────────────

def test_flag_composants_defaut_true_et_sorts_seulement():
    """Défaut True = comportement historique de l'accès rapide (« engager tout le
    disponible »), donc une barre dérivée des anciens épinglés ne change pas de jeu."""
    assert sa.normaliser_entree({"type": "sort", "ref": "sort:trait"})["composants"] is True
    assert sa.normaliser_entree({"type": "sort", "ref": "sort:trait", "composants": False})["composants"] is False
    # Les autres types n'ont pas de composants à engager : la clé est écartée.
    assert "composants" not in sa.normaliser_entree({"type": "competence", "ref": "competence:frappe"})
    assert "composants" not in sa.normaliser_entree({"type": "consommable", "ref": "item:potion"})
    assert "composants" not in sa.normaliser_entree(CAC)


def test_entree_legacy_egale_a_composants_true():
    """Une entrée d'avant le flag est DÉPLACÉE, pas dupliquée : la normalisation pose le
    défaut, donc `_memes_entrees` les reconnaît comme la même action."""
    perso = _perso(slots_actions=[CAC, RAMASSER, FUIR, {"type": "sort", "ref": "sort:trait"}])
    slots = sa.poser_slot(perso, 8, {"type": "sort", "ref": "sort:trait", "composants": True}, get_doc)
    assert slots[7] == {"type": "sort", "ref": "sort:trait", "composants": True}
    assert slots[3] is None
    assert sum(1 for s in slots if s and s.get("ref") == "sort:trait") == 1


def test_meme_sort_avec_et_sans_composants_coexistent():
    """Deux cases pour un même sort : une qui dépense ses composants, une qui les
    économise — c'est tout l'intérêt du flag."""
    perso = _perso(slots_actions=[CAC, RAMASSER, FUIR])
    sa.poser_slot(perso, 5, {"type": "sort", "ref": "sort:trait", "composants": True}, get_doc)
    slots = sa.poser_slot(perso, 6, {"type": "sort", "ref": "sort:trait", "composants": False}, get_doc)
    assert slots[4]["composants"] is True
    assert slots[5]["composants"] is False


def test_payload_expose_le_reglage_composants():
    perso = _perso(slots_actions=[CAC, RAMASSER, FUIR,
                                  {"type": "sort", "ref": "sort:trait", "composants": False}])
    assert sa.slots_payload(perso, get_doc)[3]["composants"] is False


def test_entrees_invalides_ignorees():
    assert sa.normaliser_entree({"type": "poney", "ref": "x"}) is None
    assert sa.normaliser_entree({"type": "attaque", "ref": "morsure"}) is None
    assert sa.normaliser_entree({"type": "sort"}) is None          # ref manquante
    assert sa.normaliser_entree(None) is None
    assert sa.normaliser_entree({"type": "fuir"}) == FUIR          # ref facultative


def test_ref_caduque_purgee_a_la_lecture():
    """Sort désappris / compétence oubliée → la case se vide, elle ne plante pas."""
    perso = _perso(slots_connus=[], slots_actions=[
        CAC, RAMASSER, FUIR,
        {"type": "sort", "ref": "sort:disparu"},
        {"type": "competence", "ref": "competence:jamais_apprise"},
    ])
    slots = sa.slots_effectifs(perso, get_doc)
    assert slots[3] is None
    assert slots[4] is None


def test_competence_passive_purgee():
    """Une passive n'a pas d'usage en barre d'action : son bonus est permanent."""
    perso = _perso(slots_actions=[CAC, RAMASSER, FUIR,
                                  {"type": "competence", "ref": "competence:maitrise"}])
    assert sa.slots_effectifs(perso, get_doc)[3] is None


def test_consommable_absent_du_sac_garde_sa_case():
    """Le slot référence un TYPE : sac vide = case grisée, jamais case perdue —
    sinon racheter des potions obligerait à reconfigurer la barre."""
    perso = _perso(inventaire=[], slots_actions=[
        CAC, RAMASSER, FUIR, {"type": "consommable", "ref": "item:potion"}])
    slots = sa.slots_effectifs(perso, get_doc)
    assert slots[3] == {"type": "consommable", "ref": "item:potion"}
    assert sa.slots_payload(perso, get_doc)[3]["disponible"] is False


# ── Invariante des obligatoires ──────────────────────────────────────────────────

def test_obligatoire_manquante_replacee_a_la_lecture():
    """Doc bricolé sans 🏃 : la lecture le remet, la barre ne peut pas enfermer le joueur."""
    perso = _perso(slots_actions=[CAC, RAMASSER, None, None])
    slots = sa.slots_effectifs(perso, get_doc)
    assert FUIR in slots
    assert slots.count(FUIR) == 1


def test_obligatoire_en_double_dedupliquee():
    perso = _perso(slots_actions=[CAC, RAMASSER, FUIR, CAC, FUIR])
    slots = sa.slots_effectifs(perso, get_doc)
    assert slots.count(CAC) == 1
    assert slots.count(FUIR) == 1
    assert slots[3] is None and slots[4] is None


def test_obligatoire_replacee_meme_barre_pleine(monkeypatch):
    """Dernier recours : on écrase une entrée libre plutôt que de perdre la fuite."""
    monkeypatch.setattr(character_stats, "COMBAT_SLOTS_MAX", 4)
    perso = _perso(slots_actions=[CAC, RAMASSER, {"type": "sort", "ref": "sort:trait"},
                                  {"type": "sort", "ref": "sort:soin"}])
    slots = sa.slots_effectifs(perso, get_doc)
    assert FUIR in slots


def test_vider_une_obligatoire_est_refuse():
    perso = _perso()
    with pytest.raises(ValueError):
        sa.vider_slot(perso, 1, get_doc)      # ⚔ mêlée
    with pytest.raises(ValueError):
        sa.vider_slot(perso, 3, get_doc)      # 🏃 fuite


def test_vider_une_case_libre_fonctionne():
    perso = _perso(sorts_epingles=["sort:trait"])
    slots = sa.vider_slot(perso, 4, get_doc)
    assert slots[3] is None
    assert perso["slots_actions"][3] is None


# ── Poser / déplacer ─────────────────────────────────────────────────────────────

def test_poser_un_sort_dans_une_case_libre():
    perso = _perso(slots_actions=[CAC, RAMASSER, FUIR])
    slots = sa.poser_slot(perso, 7, {"type": "sort", "ref": "sort:soin"}, get_doc)
    assert slots[6] == _sort("sort:soin")


def test_poser_une_obligatoire_ailleurs_la_deplace_sans_dupliquer():
    perso = _perso(slots_actions=[CAC, RAMASSER, FUIR])
    slots = sa.poser_slot(perso, 20, CAC, get_doc)
    assert slots[19] == CAC
    assert slots[0] is None            # l'ancienne case s'est libérée
    assert slots.count(CAC) == 1


def test_poser_sur_la_case_d_une_obligatoire_les_echange():
    """Sinon déposer un sort sur 🏃 supprimerait la fuite, que la réparation
    replacerait ailleurs à l'insu du joueur."""
    perso = _perso(slots_actions=[CAC, RAMASSER, FUIR])
    slots = sa.poser_slot(perso, 3, {"type": "sort", "ref": "sort:trait"}, get_doc)
    assert slots[2] == _sort("sort:trait")
    assert FUIR in slots
    assert slots.count(FUIR) == 1


def test_echanger_deux_obligatoires():
    perso = _perso(slots_actions=[CAC, RAMASSER, FUIR])
    slots = sa.poser_slot(perso, 1, FUIR, get_doc)
    assert slots[0] == FUIR
    assert slots[2] == CAC             # l'évincée a pris la place libérée
    assert slots.count(CAC) == 1 and slots.count(FUIR) == 1


def test_deplacer_echange_deux_cases():
    perso = _perso(slots_actions=[CAC, RAMASSER, FUIR,
                                  {"type": "sort", "ref": "sort:trait"}])
    slots = sa.deplacer_slot(perso, 4, 1, get_doc)
    assert slots[0] == _sort("sort:trait")
    assert slots[3] == CAC


def test_positions_hors_barre_refusees():
    perso = _perso()
    for position in (0, -1, sa.slots_max() + 1, "abc", None):
        with pytest.raises(ValueError):
            sa.poser_slot(perso, position, {"type": "sort", "ref": "sort:trait"}, get_doc)


def test_poser_une_entree_non_possedee_est_refuse():
    perso = _perso()
    with pytest.raises(ValueError):
        sa.poser_slot(perso, 5, {"type": "sort", "ref": "sort:inconnu"}, get_doc)
    with pytest.raises(ValueError):
        sa.poser_slot(perso, 5, {"type": "competence", "ref": "competence:maitrise"}, get_doc)
    with pytest.raises(ValueError):
        sa.poser_slot(perso, 5, {"type": "consommable", "ref": "item:epee"}, get_doc)
    with pytest.raises(ValueError):
        sa.poser_slot(perso, 5, {"type": "attaque", "ref": "morsure"}, get_doc)


def test_les_trois_modes_d_attaque_sont_assignables():
    perso = _perso(slots_actions=[CAC, RAMASSER, FUIR])
    sa.poser_slot(perso, 5, {"type": "attaque", "ref": "tir"}, get_doc)
    slots = sa.poser_slot(perso, 6, {"type": "attaque", "ref": "jet"}, get_doc)
    assert slots[4] == {"type": "attaque", "ref": "tir"}
    assert slots[5] == {"type": "attaque", "ref": "jet"}


# ── Payload UI ───────────────────────────────────────────────────────────────────

def test_payload_expose_nom_icone_et_index_de_consommable():
    perso = _perso(slots_actions=[CAC, RAMASSER, FUIR,
                                  {"type": "consommable", "ref": "item:potion"},
                                  {"type": "sort", "ref": "sort:trait"}])
    payload = sa.slots_payload(perso, get_doc)

    assert payload[0]["icon"] == "⚔" and payload[0]["obligatoire"] is True
    potion = payload[3]
    assert potion["nom"] == "Potion de soin"
    assert potion["index"] == 1          # position réelle dans le sac, résolue à la volée
    assert potion["disponible"] is True
    assert payload[4]["nom"] == "Trait de feu" and payload[4]["obligatoire"] is False


def test_payload_case_vide():
    perso = _perso(slots_actions=[CAC, RAMASSER, FUIR])
    vide = sa.slots_payload(perso, get_doc)[5]
    assert vide["type"] is None and vide["disponible"] is False
    assert vide["position"] == 6
