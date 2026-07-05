# tests/test_combat_terrain.py
#
# Falaises (terrain cells==3) : infranchissables au déplacement pour les non-volants,
# mais transparentes à la ligne de vue. Tests purs (pas de DB) — db.config tolère
# l'absence de CouchDB à l'import, donc collectables en local.

from utils.combat import (
    TERRAIN_FALAISE,
    _walkable,
    _line_of_sight,
    _find_path,
    _reachable_region,
)


def _open(w, h):
    return [[1] * w for _ in range(h)]


# ── _walkable : falaise infranchissable sauf vol ────────────────────────────────

def test_walkable_sol_normal():
    cells = _open(3, 3)
    assert _walkable(cells, 1, 1) is True


def test_walkable_falaise_bloque_non_volant():
    cells = _open(3, 3)
    cells[1][1] = TERRAIN_FALAISE
    assert _walkable(cells, 1, 1) is False
    assert _walkable(cells, 1, 1, flying=True) is True


def test_walkable_mur_bloque_meme_en_vol():
    cells = _open(3, 3)
    cells[1][1] = 0
    assert _walkable(cells, 1, 1) is False
    assert _walkable(cells, 1, 1, flying=True) is False
    cells[1][1] = -1
    assert _walkable(cells, 1, 1, flying=True) is False


def test_walkable_hors_grille():
    cells = _open(3, 3)
    assert _walkable(cells, -1, 0) is False
    assert _walkable(cells, 0, 3) is False


# ── _line_of_sight : une falaise ne bloque pas la vision, un mur oui ─────────────

def test_los_falaise_transparente():
    cells = _open(5, 1)
    cells[0][2] = TERRAIN_FALAISE  # falaise au milieu de la ligne (0,0)→(4,0)
    assert _line_of_sight(cells, 0, 0, 4, 0) is True


def test_los_mur_bloque_pas_falaise():
    cells = _open(5, 1)
    cells[0][2] = 0  # mur au même endroit
    assert _line_of_sight(cells, 0, 0, 4, 0) is False


# ── _find_path : contournement au sol, traversée en vol ─────────────────────────

def _falaise_wall(w, h, col, rows):
    cells = _open(w, h)
    for y in rows:
        cells[y][col] = TERRAIN_FALAISE
    return cells


def test_find_path_contourne_la_falaise():
    # Mur de falaises en colonne 2 sur y=0,1 ; passage libre en bas (y=2).
    dims = {"x": 5, "y": 3}
    cells = _falaise_wall(5, 3, col=2, rows=(0, 1))
    path = _find_path(cells, dims, (0, 0), (4, 0), set())
    assert path is not None
    assert path[0] == (0, 0) and path[-1] == (4, 0)
    # Le chemin non-volant ne pose jamais le pied sur une falaise.
    assert all(cells[y][x] != TERRAIN_FALAISE for (x, y) in path)


def test_find_path_vol_traverse_la_falaise():
    dims = {"x": 5, "y": 3}
    cells = _falaise_wall(5, 3, col=2, rows=(0, 1))
    path = _find_path(cells, dims, (0, 0), (4, 0), set(), flying=True)
    assert path is not None
    # En vol, le trajet direct traverse la colonne de falaises.
    assert any(cells[y][x] == TERRAIN_FALAISE for (x, y) in path)


def test_find_path_enclos_par_falaises():
    # Colonne 2 entièrement en falaise → aucun passage au sol, mais possible en vol.
    dims = {"x": 5, "y": 3}
    cells = _falaise_wall(5, 3, col=2, rows=(0, 1, 2))
    assert _find_path(cells, dims, (0, 1), (4, 1), set()) is None
    assert _find_path(cells, dims, (0, 1), (4, 1), set(), flying=True) is not None


# ── _reachable_region : falaise hors région au sol, dans la région en vol ────────

def test_reachable_region_exclut_falaise():
    dims = {"x": 3, "y": 3}
    cells = _open(3, 3)
    cells[1][1] = TERRAIN_FALAISE
    region = _reachable_region(cells, dims, {}, (0, 0))
    assert (1, 1) not in region
    region_vol = _reachable_region(cells, dims, {}, (0, 0), flying=True)
    assert (1, 1) in region_vol
