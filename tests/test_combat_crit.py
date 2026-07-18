# tests/test_combat_crit.py
#
# Critiques en combat pilotés par la Chance (utils/combat.py) : les fenêtres de réussite
# et d'échec critique glissent de (Ch attaquant − Ch cible) // CRIT_CHANCE_DIVISEUR, sans
# jamais passer sous/au-dessus des bornes génériques CRIT_REUSSITE_MAX / CRIT_ECHEC_MIN.
# Une réussite critique force la touche et double les dégâts ; un échec critique force le
# raté et coûte une action de plus (reportée au tour suivant s'il n'en restait aucune).
# Docs à la main, monkeypatch DB sur les modules (pattern test_combat_groupe).

import pytest

from models import character_stats
from utils import combat as combat_util
from utils import characters as characters_util

from tests.test_combat_groupe import (
	character, joueur_snap, monstre_snap, combat_doc, db,   # noqa: F401 (fixture db)
)


# ── Outils de forçage du d100 ────────────────────────────────────────────────────

def _force_roll(monkeypatch, valeur):
	"""d100 forcé à `valeur` ; les dés de dégâts rendent leur maximum."""
	monkeypatch.setattr(combat_util.random, "randint",
						lambda a, b: valeur if b == 100 else b)


# ── _seuils_critiques ────────────────────────────────────────────────────────────

def test_delta_nul_rend_les_bornes_de_base():
	att = joueur_snap("joueur_0", "character:u_1", ch=30)
	cib = monstre_snap(ch=30)
	assert combat_util._seuils_critiques(att, cib) == (
		character_stats.CRIT_REUSSITE_MAX, character_stats.CRIT_ECHEC_MIN)


def test_chance_superieure_elargit_le_crit_sans_bouger_le_fumble(monkeypatch):
	"""delta = +40, W = 10 → +4 : réussite à 9, échec CLAMPÉ à sa borne de base."""
	monkeypatch.setattr(character_stats, "CRIT_CHANCE_DIVISEUR", 10)
	att = joueur_snap("joueur_0", "character:u_1", ch=60)
	cib = monstre_snap(ch=20)
	ok, ko = combat_util._seuils_critiques(att, cib)
	assert ok == character_stats.CRIT_REUSSITE_MAX + 4
	assert ko == character_stats.CRIT_ECHEC_MIN   # jamais au-dessus de la borne


def test_chance_inferieure_rapproche_le_fumble_sans_reduire_le_crit(monkeypatch):
	"""delta = −40 → −4 : échec dès 92, réussite CLAMPÉE à sa borne de base."""
	monkeypatch.setattr(character_stats, "CRIT_CHANCE_DIVISEUR", 10)
	att = joueur_snap("joueur_0", "character:u_1", ch=20)
	cib = monstre_snap(ch=60)
	ok, ko = combat_util._seuils_critiques(att, cib)
	assert ok == character_stats.CRIT_REUSSITE_MAX   # jamais sous la borne
	assert ko == character_stats.CRIT_ECHEC_MIN - 4


def test_diviseur_nul_desactive_la_mecanique(monkeypatch):
	monkeypatch.setattr(character_stats, "CRIT_CHANCE_DIVISEUR", 0)
	att = joueur_snap("joueur_0", "character:u_1", ch=99)
	cib = monstre_snap(ch=0)
	assert combat_util._seuils_critiques(att, cib) == (
		character_stats.CRIT_REUSSITE_MAX, character_stats.CRIT_ECHEC_MIN)


def test_snapshot_legacy_sans_ch_reste_sur_les_bornes_de_base(monkeypatch):
	"""Combat créé avant la feature : aucun `ch` de part ni d'autre → delta 0."""
	monkeypatch.setattr(character_stats, "CRIT_CHANCE_DIVISEUR", 10)
	assert combat_util._seuils_critiques({}, {}) == (
		character_stats.CRIT_REUSSITE_MAX, character_stats.CRIT_ECHEC_MIN)


# ── _resoudre_jet ────────────────────────────────────────────────────────────────

def test_jet_minimal_est_une_reussite_critique(monkeypatch):
	_force_roll(monkeypatch, 1)
	jet = combat_util._resoudre_jet({}, {}, seuil=50)
	assert jet["critique"] and jet["touche"] and jet["mult_degats"] == 2


def test_le_crit_force_la_touche_meme_sous_le_seuil(monkeypatch):
	"""Fenêtre élargie à 9, seuil de toucher à 5, jet 8 → touché quand même."""
	monkeypatch.setattr(character_stats, "CRIT_CHANCE_DIVISEUR", 10)
	_force_roll(monkeypatch, 8)
	att, cib = {"ch": 60}, {"ch": 20}
	jet = combat_util._resoudre_jet(att, cib, seuil=5)
	assert jet["critique"] and jet["touche"]


def test_le_fumble_force_le_rate_meme_au_dessus_du_seuil(monkeypatch):
	_force_roll(monkeypatch, 100)
	jet = combat_util._resoudre_jet({}, {}, seuil=95)
	assert jet["fumble"] and not jet["touche"] and jet["mult_degats"] == 1


def test_jet_ordinaire_suit_le_seuil(monkeypatch):
	_force_roll(monkeypatch, 50)
	assert combat_util._resoudre_jet({}, {}, seuil=60)["touche"]
	assert not combat_util._resoudre_jet({}, {}, seuil=40)["touche"]


# ── Dégâts doublés en situation ──────────────────────────────────────────────────

def test_crit_double_les_des_avant_les_pa(db, monkeypatch):
	"""1D10 max = 10, doublé = 20, PA 3 soustraits APRÈS → 17 (et non (10−3)×2 = 14)."""
	_force_roll(monkeypatch, 1)
	j = joueur_snap("joueur_0", "character:u_1", x=0, y=0, cc=50, degats_cc="1D10")
	m = monstre_snap(x=1, y=0, pa=3, currentPV=100, pv_max=100)
	doc = combat_doc([j], [m])
	res = combat_util.resolve_action(doc, "attaquer", cible_id="monstre_0")
	assert res["critique"] and res["dmg"] == 17


def test_crit_de_sort_double_sans_soustraire_les_pa(db, monkeypatch):
	"""La magie ignore l'armure : 1D10 max doublé = 20, PA 3 non soustraits."""
	_force_roll(monkeypatch, 1)
	j = joueur_snap("joueur_0", "character:u_1", x=0, y=0, toucher_magique=50)
	m = monstre_snap(x=1, y=0, pa=3, currentPV=100, pv_max=100)
	doc = combat_doc([j], [m])
	sort = {"doc": {"nom": "Trait de feu", "cible": "ennemi", "cout_pm": 0},
			"effets": {"degats": "1D10"}, "composants_engages": [], "poids_consommes": 0}
	res = combat_util.resolve_action(doc, "sort", cible_id="monstre_0", sort=sort)
	assert res["critique"] and res["dmg"] == 20


def test_crit_dun_monstre_double_ses_degats(db, monkeypatch):
	_force_roll(monkeypatch, 1)
	j = joueur_snap("joueur_0", "character:u_1", x=0, y=0, pa=0, pv=100, pv_max=100)
	m = monstre_snap(x=1, y=0, degats_cc="1D10")
	doc = combat_doc([j], [m])
	combat_util._do_attack_on(doc, m, j)
	assert j["currentPV"] == 80          # 100 − (10 × 2)
	assert doc["log"][-1]["kind"] == "crit"


# ── Échec critique : perte d'action ──────────────────────────────────────────────

def test_fumble_consomme_une_action_de_plus(db, monkeypatch):
	_force_roll(monkeypatch, 100)
	j = joueur_snap("joueur_0", "character:u_1", x=0, y=0,
					actions_restantes=3, actions_max=3)
	m = monstre_snap(x=1, y=0)
	doc = combat_doc([j], [m])
	res = combat_util.resolve_action(doc, "attaquer", cible_id="monstre_0")
	assert res["fumble"] is True
	assert j["penalites"] == 1
	assert j["actions_restantes"] == 1   # 3 − 1 (l'attaque) − 1 (la pénalité)
	assert j.get("dette_actions", 0) == 0


def test_fumble_sans_action_restante_cree_une_dette(db):
	"""Rien à perdre ce tour-ci : la pénalité devient une dette (pas de perte sèche)."""
	j = joueur_snap("joueur_0", "character:u_1", actions_restantes=0, actions_max=1)
	doc = combat_doc([j], [monstre_snap()])
	combat_util._appliquer_fumble(doc, j)
	assert j["dette_actions"] == 1
	assert j.get("penalites", 0) == 0


def test_la_dette_est_payee_au_debut_du_tour_suivant(db):
	j = joueur_snap("joueur_0", "character:u_1", actions_restantes=0, actions_max=2,
					dette_actions=1)
	combat_util._reset_turn_budget(j)
	assert j["dette_actions"] == 0        # la dette est soldée
	assert j["penalites"] == 1
	assert j["actions_restantes"] == 1    # actions_max (2) − la dette (1)


def test_la_dette_ne_se_reporte_pas_deux_fois(db, monkeypatch):
	"""Un seul tour puni : le reset suivant rend le budget plein."""
	j = joueur_snap("joueur_0", "character:u_1", actions_restantes=2, actions_max=2,
					dette_actions=1)
	combat_util._reset_turn_budget(j)
	assert j["actions_restantes"] == 1
	combat_util._reset_turn_budget(j)
	assert j["actions_restantes"] == 2
	assert j["penalites"] == 0


def test_fumble_dun_monstre_lui_coute_une_action(db, monkeypatch):
	_force_roll(monkeypatch, 100)
	j = joueur_snap("joueur_0", "character:u_1", x=0, y=0)
	m = monstre_snap(x=1, y=0, actions_restantes=3, actions_max=3)
	doc = combat_doc([j], [m])
	combat_util._do_attack_on(doc, m, j)
	assert m["penalites"] == 1
	assert m["actions_restantes"] == 1    # 3 − 1 (l'attaque) − 1 (la pénalité)
	assert doc["log"][-2]["kind"] == "fumble"


def test_la_penalite_ampute_aussi_le_deplacement(db):
	"""Une action perdue doit mordre sur la distance parcourable, pas seulement sur les
	attaques — sinon le fumble serait indolore pour qui se contente d'avancer. Les AP de
	déplacement et la pénalité puisent bien dans le même budget."""
	sain = joueur_snap("joueur_0", "character:u_1", actions_max=2, deplacement=2,
					   cells_moved=1)
	combat_util._refresh_actions(sain)
	assert sain["actions_restantes"] == 1        # une case parcourue, une action libre

	puni = joueur_snap("joueur_0", "character:u_1", actions_max=2, deplacement=2,
					   cells_moved=1, penalites=1)
	combat_util._refresh_actions(puni)
	assert puni["actions_restantes"] == 0        # la pénalité a mangé l'action libre
