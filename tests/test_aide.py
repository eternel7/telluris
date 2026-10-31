"""Tests de l'aide au démarrage (`utils/aide.py`) : les chiffres affichés sont RELUS du code."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import aide  # noqa: E402
from models import character_stats  # noqa: E402
from models.character_stats import _caract_to_dice_  # noqa: E402


def test_table_des_reproduit_caract_to_dice():
	"""Chaque valeur sondée retombe dans la tranche qui donne le même dé que la fonction."""
	tranches = aide.table_des()
	assert tranches[-1]["max"] is None
	for v in range(0, aide._SONDE_MAX + 1):
		tranche = next(t for t in tranches if t["max"] is None or v <= t["max"])
		assert tranche["de"] == _caract_to_dice_(v), v


def test_table_des_tranches_croissantes():
	tranches = aide.table_des()
	bornes = [t["max"] for t in tranches[:-1]]
	assert bornes == sorted(bornes)
	assert len({t["de"] for t in tranches}) == len(tranches)


def test_regles_aide_suit_le_facteur_simule():
	"""Le facteur affiché est le facteur EFFECTIF (variable de monde ou simulation)."""
	voulu = character_stats.facteur_degats_armure() + 7
	with character_stats.facteur_degats_armure_simule(voulu):
		assert aide.regles_aide()["facteur_armure"] == voulu
	assert aide.regles_aide()["facteur_armure"] == character_stats.facteur_degats_armure()
