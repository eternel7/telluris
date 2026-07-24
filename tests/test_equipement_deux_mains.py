# tests/test_equipement_deux_mains.py
#
# Tests des helpers purs des armes à deux mains (blocage de l'autre main). Import de
# utils.* → dépend de db.config (connexion CouchDB à l'import) : à lancer dans le
# conteneur, comme le reste.

import pytest

from utils.characters import (
    autre_main, main_occupee_par_deux_mains, liberer_pour_deux_mains,
)


# ── autre_main ───────────────────────────────────────────────────────────────────

def test_autre_main_droite_vers_gauche():
    assert autre_main("main_droite") == "main_gauche"


def test_autre_main_gauche_vers_droite():
    assert autre_main("main_gauche") == "main_droite"


# ── main_occupee_par_deux_mains ───────────────────────────────────────────────────

def test_main_occupee_autre_main_vide():
    assert main_occupee_par_deux_mains({}, lambda r: None, "main_droite") is None


def test_main_occupee_occupant_pas_deux_mains():
    slots = {"main_gauche": "item:Dague"}
    resolve = lambda r: {"_id": r, "deux_mains": False}
    assert main_occupee_par_deux_mains(slots, resolve, "main_droite") is None


def test_main_occupee_occupant_deux_mains_bloque():
    slots = {"main_gauche": "item:Arc"}
    arc = {"_id": "item:Arc", "nom": "Arc", "deux_mains": True}
    resolve = lambda r: arc if r == "item:Arc" else None
    assert main_occupee_par_deux_mains(slots, resolve, "main_droite") == arc


def test_main_occupee_slot_pas_une_main():
    slots = {"main_gauche": "item:Arc"}
    resolve = lambda r: {"deux_mains": True}
    assert main_occupee_par_deux_mains(slots, resolve, "torse") is None


# ── liberer_pour_deux_mains ───────────────────────────────────────────────────────

def test_liberer_objet_pas_deux_mains():
    assert liberer_pour_deux_mains({}, {"deux_mains": False}, "main_droite") is None
    assert liberer_pour_deux_mains({}, {}, "main_droite") is None


def test_liberer_slot_pas_une_main():
    assert liberer_pour_deux_mains({}, {"deux_mains": True}, "torse") is None


def test_liberer_equipe_main_droite_libere_gauche():
    assert liberer_pour_deux_mains({}, {"deux_mains": True}, "main_droite") == "main_gauche"


def test_liberer_equipe_main_gauche_libere_droite():
    assert liberer_pour_deux_mains({}, {"deux_mains": True}, "main_gauche") == "main_droite"
