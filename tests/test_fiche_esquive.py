# tests/test_fiche_esquive.py
#
# Ligne « Esquive » des dérivées de la fiche (`fiche.derivees_affichees`) : Ag bufée +
# bonus d'esquive, la MÊME difficulté que `combat._defense_physique` oppose en combat à un
# jet physique. Aucun accès DB : aucun objet porté, `get_doc` servi par un dict vide.

import pytest

from utils import characters as characters_mod
from utils import combat as combat_mod
from utils import fiche
from utils.combat import build_joueur_snapshot


@pytest.fixture(autouse=True)
def _sans_db(monkeypatch):
	monkeypatch.setattr(combat_mod, "get_doc", {}.get)
	monkeypatch.setattr(characters_mod, "get_doc", {}.get)


def _character(effets=None):
	return {
		"_id": "character:test_1", "nom": "Hanzo", "voc": "guerrier", "race": "humain",
		"caracteristiques_current": {"V": 5, "F": 30, "R": 30, "Ag": 40,
									 "Vol": 30, "Int": 30, "Cha": 20, "Ch": 20},
		"vocations_niveaux": {"guerrier": 1},
		"currentPV": 100, "currentPM": 20,
		"inventaire": [], "slots": {},
		"effets_actifs": list(effets or []),
	}


def test_sans_bonus_l_esquive_est_l_agilite():
	derived = fiche.derived_de(_character())
	assert derived["esquive_bonus"] == 0
	assert derived["defense_physique"] == 40


def test_effet_actif_d_esquive_et_buff_d_ag_comptent_comme_en_combat():
	perso = _character([{"nom": "Potion de souplesse", "icon": "🧪", "buffs": {"Ag": 5},
						 "regen_pv": 0, "regen_pm": 0, "esquive": 3, "restants": 4}])
	derived = fiche.derived_de(perso)
	assert derived["esquive_bonus"] == 3
	assert derived["defense_physique"] == 40 + 5 + 3
	# Même somme que la difficulté réellement opposée en combat.
	snap = build_joueur_snapshot(perso)
	assert derived["defense_physique"] == combat_mod._defense_physique(snap)
