# tests/test_fiche_esquive.py
#
# Ligne « Esquive » des dérivées de la fiche (`fiche.derivees_affichees`) : Ag bufée +
# bonus d'esquive, la MÊME difficulté que `combat._defense_physique` oppose en combat à un
# jet physique. Aucun accès DB : aucun objet porté, `get_doc` servi par un dict vide.

import pytest

from utils import characters as characters_mod
from utils import combat as combat_mod
from models import character_stats
from utils import consommables
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


# ── Autres lignes ajoutées par `derivees_affichees` ──────────────────────────────

def test_actions_par_tour_comme_le_snapshot_de_combat():
	perso = _character([{"nom": "Hâte", "icon": "💨", "buffs": {"V": 2, "Ag": 20},
						 "regen_pv": 0, "regen_pm": 0, "esquive": 0, "restants": 4}])
	derived = fiche.derived_de(perso)
	assert derived["actions_tour"] == build_joueur_snapshot(perso)["actions_max"]


def test_regen_du_tour_inclut_le_bonus_et_peut_etre_negative():
	sans = fiche.derived_de(_character())
	poison = _character([{"nom": "Venin", "icon": "🐍", "buffs": {},
						  "regen_pv": -9, "regen_pm": 2, "esquive": 0, "restants": 3}])
	avec = fiche.derived_de(poison)
	assert (sans["regen_pv_tour"], sans["regen_pm_tour"]) == consommables.regen_par_tour(_character())
	assert avec["regen_pv_tour"] == sans["regen_pv_tour"] - 9
	assert avec["regen_pm_tour"] == sans["regen_pm_tour"] + 2


def test_canalisation_plafonnee_et_nulle_par_defaut():
	assert fiche.derived_de(_character())["canalisation"] == 0
	plafond = int(character_stats.CANALISATION_REDUCTION_MAX)
	perso = _character([{"nom": "Robe", "icon": "🧥", "buffs": {}, "regen_pv": 0,
						 "regen_pm": 0, "esquive": 0, "canalisation": plafond + 50, "restants": 3}])
	assert fiche.derived_de(perso)["canalisation"] == plafond


def test_toucher_magique_et_degats_a_distance_sont_servis():
	derived = fiche.derived_de(_character())
	assert "toucher_magique" in derived and "degats_cd" in derived
