"""Garde de cohérence `dimensions` ↔ `cells` de `PUT /api/update_cells`.

`update_cells` est la SEULE écriture du jeu capable de changer la FORME d'une carte (l'éditeur
`/admin/editor` sait redimensionner une grille). Deux champs liés par une identité finissent
toujours par diverger si rien ne la contrôle — et la divergence est muette : le joueur se déplace
hors de l'image, `borner_position` recale les cibles de chasse ailleurs, et l'éditeur lui-même
dessine une grille dont les cases n'existent pas. D'où ce contrôle, et ces tests.
"""

import pytest
from fastapi import HTTPException

from utils.lieux import dimensions_coherentes


def _cells(x, y):
	return [[1] * x for _ in range(y)]


def test_dimensions_coherentes_renvoie_le_dict_normalise():
	assert dimensions_coherentes({"x": 3, "y": 2}, _cells(3, 2)) == {"x": 3, "y": 2}


def test_les_valeurs_textuelles_sont_acceptees_et_normalisees():
	"""Un client HTML envoie volontiers des chaînes : on normalise, on ne refuse pas."""
	assert dimensions_coherentes({"x": "3", "y": "2"}, _cells(3, 2)) == {"x": 3, "y": 2}


@pytest.mark.parametrize("dimensions", [
	{"x": 4, "y": 2},          # une colonne de trop
	{"x": 3, "y": 3},          # une ligne de trop
	{"x": 2, "y": 3},          # les deux axes intervertis
])
def test_une_taille_qui_contredit_les_cells_est_refusee(dimensions):
	with pytest.raises(HTTPException) as e:
		dimensions_coherentes(dimensions, _cells(3, 2))
	assert e.value.status_code == 422


def test_une_ligne_de_longueur_differente_est_refusee():
	"""Le contrôle porte sur TOUTES les lignes : une matrice en dents de scie passerait le seul
	test `len(cells[0])`, et l'éditeur lirait plus tard un `undefined` sur la ligne courte."""
	cells = _cells(3, 2)
	cells[1] = [1, 1]
	with pytest.raises(HTTPException) as e:
		dimensions_coherentes({"x": 3, "y": 2}, cells)
	assert e.value.status_code == 422


@pytest.mark.parametrize("dimensions", [
	{"x": 0, "y": 2},
	{"x": 3, "y": -1},
	{"x": None, "y": 2},
	{"x": "large", "y": 2},
	{},
	"3x2",
	None,
])
def test_une_taille_illisible_ou_nulle_est_refusee(dimensions):
	"""FAIL-CLOSED : une taille qu'on ne sait pas lire ne doit jamais laisser passer l'écriture —
	le symptôme bruyant vaut mieux qu'une carte 0×0 silencieusement enregistrée."""
	with pytest.raises(HTTPException) as e:
		dimensions_coherentes(dimensions, _cells(3, 2))
	assert e.value.status_code == 422


@pytest.mark.parametrize("cells", [[], None, "grille", [1, 2, 3]])
def test_sans_matrice_exploitable_on_refuse(cells):
	with pytest.raises(HTTPException) as e:
		dimensions_coherentes({"x": 3, "y": 2}, cells)
	assert e.value.status_code == 422
