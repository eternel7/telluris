# tests/test_combat_ranged.py
#
# Tests des helpers d'attaque à distance. Import de utils.* → dépend de db.config
# (connexion CouchDB à l'import) : à lancer dans le conteneur, comme le reste.

import pytest


# ── restriction_satisfaite (prérequis d'équipement, sémantique ET) ──────────────

from utils.characters import restriction_satisfaite


def test_restriction_absente_ou_vide():
    assert restriction_satisfaite(None, {"F": 10}) == (True, {})
    assert restriction_satisfaite({}, {"F": 10}) == (True, {})


def test_restriction_et_toutes_satisfaites():
    ok, manque = restriction_satisfaite({"F": 30, "Ag": 25}, {"F": 30, "Ag": 40})
    assert ok and manque == {}


def test_restriction_et_une_seule_manquante_bloque():
    ok, manque = restriction_satisfaite({"F": 30, "Ag": 25}, {"F": 30, "Ag": 20})
    assert not ok
    assert manque == {"Ag": 25}


def test_restriction_caract_absente_compte_comme_zero():
    ok, manque = restriction_satisfaite({"F": 30}, {})
    assert not ok and manque == {"F": 30}


# ── _line_of_sight (ligne de vue : un mur cells<1 bloque) ───────────────────────

from utils.combat import _line_of_sight


def _open(w, h):
    return [[1] * w for _ in range(h)]


def test_los_terrain_ouvert():
    cells = _open(5, 5)
    assert _line_of_sight(cells, 0, 0, 4, 4) is True
    assert _line_of_sight(cells, 0, 2, 4, 2) is True


def test_los_mur_intermediaire_bloque():
    cells = _open(5, 1)
    cells[0][2] = -1  # mur au milieu de la ligne (0,0)→(4,0)
    assert _line_of_sight(cells, 0, 0, 4, 0) is False


def test_los_mur_sur_extremite_ne_bloque_pas():
    # Un mur SUR la case cible/source n'est pas un obstacle intermédiaire.
    cells = _open(5, 1)
    cells[0][4] = 0
    assert _line_of_sight(cells, 0, 0, 4, 0) is True
