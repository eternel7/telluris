# tests/test_competences_aura.py
#
# AURAS : une passive qui porte une `zone` (competences.est_aura). Elle sort du repli
# inconditionnel des passives et ne vaut que pour ceux qu'elle couvre :
#   - EXPLORATION : tout le groupe (`auras_recues`, origine « aura » de consommables) ;
#   - COMBAT : selon les positions, entrée `aura` d'`effets_actifs` posée par
#     `combat._recalculer_auras` sur chaque allié que la zone couvre.
# Non-cumul : deux auras (ou une aura et un effet à durée) → la meilleure seule.
#
# Aucun accès DB : get_doc injecté, grille en ligne dans le doc de combat.

from utils import combat as combat_mod
from utils import consommables
from utils.combat import build_joueur_snapshot
from utils.competences import (
	appliquer_auras_groupe, auras_du_groupe, bonus_passifs, competences_bonus_perime,
	est_aura, normaliser_competence, recompute_competences_bonus,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────────

AURA_SAINTE = {
	"_id": "competence:pretre_aura_sainte", "type": "competence", "vocation": "pretre",
	"nom": "Aura sainte", "icon": "🕊️", "mode": "passive", "niveau": 0,
	"effets": {"regen_pv": 1}, "zone": {"forme": "carre", "rayon": 1},
}
AURA_FERVEUR = {
	"_id": "competence:pretre_aura_ferveur", "type": "competence", "vocation": "pretre",
	"nom": "Aura de ferveur", "icon": "🔥", "mode": "passive", "niveau": 0,
	"effets": {"buffs": {"Vol": 10}, "esquive": 2}, "zone": {"forme": "carre", "rayon": 1},
}
VIGUEUR = {
	"_id": "competence:vigueur", "type": "competence", "vocation": "pretre",
	"nom": "Vigueur", "mode": "passive", "effets": {"regen_pv": 2},
}
DOCS = {d["_id"]: d for d in (AURA_SAINTE, AURA_FERVEUR, VIGUEUR)}


def _character(_id="character:test_1", nom="Aldric", competences=(), **overrides):
	char = {
		"_id": _id, "nom": nom, "voc": "pretre", "race": "humain",
		"caracteristiques_current": {"V": 5, "F": 30, "R": 30, "Ag": 30,
									 "Vol": 40, "Int": 40, "Cha": 20, "Ch": 20},
		"vocations_niveaux": {"pretre": 1},
		"currentPV": 10, "currentPM": 10,
		"inventaire": [], "slots": {},
		"competences_connues": list(competences),
	}
	char.update(overrides)
	recompute_competences_bonus(char, DOCS.get)
	return char


def _snap(idx, x, y, **kw):
	s = build_joueur_snapshot(_character(_id=f"character:test_{idx}", nom=f"J{idx}", **kw), idx)
	s["pos"] = {"x": x, "y": y}
	s["vivant"] = True
	return s


def _combat(joueurs, cells=None):
	return {
		"_id": "combat:test", "type": "combat", "status": "active", "tour": 1, "log": [],
		"ordre_initiative": [j["id"] for j in joueurs], "acteur_courant_index": 0,
		"joueurs": joueurs, "monstres": [],
		"grid": {"dims": {"x": 7, "y": 7},
				 "cells": cells or [[1] * 7 for _ in range(7)], "nav": {}},
	}


def _auras(snap):
	return [e for e in snap.get("effets_actifs") or [] if e.get("aura")]


# ── Modèle ───────────────────────────────────────────────────────────────────────

def test_une_passive_a_zone_est_une_aura_et_sort_du_bonus_global():
	assert est_aura(normaliser_competence(AURA_SAINTE))
	assert not est_aura(normaliser_competence(VIGUEUR))
	perso = _character(competences=[AURA_SAINTE["_id"], VIGUEUR["_id"]])
	bonus = bonus_passifs(perso, DOCS.get)
	# Seule la passive SANS zone est sommée ; l'aura est listée à part.
	assert bonus["regen_pv"] == 2
	assert [a["id"] for a in bonus["auras"]] == [AURA_SAINTE["_id"]]
	assert bonus["auras"][0]["regen_pv"] == 1
	assert bonus["auras"][0]["zone"]["forme"] == "carre"


def test_agregat_sans_cle_auras_est_perime():
	perso = _character(competences=[AURA_SAINTE["_id"]])
	del perso["competences_bonus"]["auras"]
	assert competences_bonus_perime(perso) is True


# ── Exploration : tout le groupe ─────────────────────────────────────────────────

def test_exploration_tout_le_groupe_recoit_l_aura():
	pretre = _character(competences=[AURA_SAINTE["_id"]])
	compagnon = _character(_id="aventurier:a1", nom="Bran")
	changes = appliquer_auras_groupe([pretre, compagnon])
	assert changes == [pretre, compagnon]
	# Le porteur en profite aussi, et la régén du tour de monde la lit.
	assert consommables.regen_bonus(pretre) == (1, 0)
	assert consommables.regen_bonus(compagnon) == (1, 0)
	# Rejouer ne change rien (l'appelant ne réécrit personne).
	assert appliquer_auras_groupe([pretre, compagnon]) == []


def test_exploration_deux_auras_ne_se_cumulent_pas():
	p1 = _character(competences=[AURA_SAINTE["_id"]])
	p2 = _character(_id="aventurier:a2", nom="Soeur", competences=[AURA_SAINTE["_id"]])
	appliquer_auras_groupe([p1, p2])
	assert len(auras_du_groupe([p1, p2])) == 2
	assert consommables.regen_bonus(p1) == (1, 0)   # meilleure seule, pas 2


def test_exploration_aura_de_buff_dans_le_detail_des_caracts():
	pretre = _character(competences=[AURA_FERVEUR["_id"]])
	compagnon = _character(_id="aventurier:a1", nom="Bran")
	appliquer_auras_groupe([pretre, compagnon])
	detail = consommables.caracts_detail(compagnon)["Vol"]
	assert detail["delta"] == 10
	assert [s["origine"] for s in detail["sources"]] == ["aura"]
	assert consommables.esquive_bonus(compagnon) == 2
	# Chip visible, marquée aura (pas de compte à rebours).
	assert consommables.effets_actifs_payload(compagnon)[0]["aura"] is True


def test_l_aura_de_groupe_n_entre_pas_en_combat_telle_quelle():
	pretre = _character(competences=[AURA_FERVEUR["_id"]])
	compagnon = _character(_id="aventurier:a1", nom="Bran")
	appliquer_auras_groupe([pretre, compagnon])
	sans = build_joueur_snapshot(_character(_id="aventurier:a1", nom="Bran"), 1)
	snap = build_joueur_snapshot(compagnon, 1)
	# Le snapshot ignore `auras_recues` : en combat, l'aura est positionnelle.
	assert snap["caracts_base"]["Vol"] == sans["caracts_base"]["Vol"] == 40
	assert snap["esquive"] == sans["esquive"]
	assert not _auras(snap)


# ── Combat : positionnelle ───────────────────────────────────────────────────────

def test_combat_allie_adjacent_recoit_l_aura_et_regenere():
	pretre = _snap(0, 3, 3, competences=[AURA_SAINTE["_id"]])
	voisin = _snap(1, 4, 4)
	loin = _snap(2, 6, 6)
	doc = _combat([pretre, voisin, loin])
	combat_mod._recalculer_auras(doc)
	assert [e["nom"] for e in _auras(pretre)] == ["Aura sainte"]   # porteur compris
	assert [e["nom"] for e in _auras(voisin)] == ["Aura sainte"]
	assert _auras(loin) == []
	avant = voisin["currentPV"]
	combat_mod._reset_turn_budget(voisin, doc)
	assert voisin["currentPV"] == avant + 1
	# Une aura ne se décrémente pas.
	assert _auras(voisin)[0]["restants"] == 0


def test_combat_s_eloigner_retire_l_aura_et_ses_buffs():
	pretre = _snap(0, 3, 3, competences=[AURA_FERVEUR["_id"]])
	voisin = _snap(1, 3, 4)
	doc = _combat([pretre, voisin])
	combat_mod._recalculer_auras(doc)
	base_esquive = voisin["esquive_base"]
	assert voisin["esquive"] == base_esquive + 2
	pm_max_buffe = voisin["pm_max"]
	voisin["pos"] = {"x": 3, "y": 6}
	combat_mod._recalculer_auras(doc)
	assert _auras(voisin) == []
	assert voisin["esquive"] == base_esquive
	assert voisin["pm_max"] < pm_max_buffe   # le +10 Vol ne compte plus


def test_combat_idempotent():
	pretre = _snap(0, 3, 3, competences=[AURA_SAINTE["_id"]])
	voisin = _snap(1, 3, 4)
	doc = _combat([pretre, voisin])
	combat_mod._recalculer_auras(doc)
	fige = [list(j["effets_actifs"]) for j in doc["joueurs"]]
	ids = [id(j["effets_actifs"]) for j in doc["joueurs"]]
	combat_mod._recalculer_auras(doc)
	assert [j["effets_actifs"] for j in doc["joueurs"]] == fige
	assert [id(j["effets_actifs"]) for j in doc["joueurs"]] == ids   # rien réécrit


def test_combat_un_mur_bloque_l_aura():
	cells = [[1] * 7 for _ in range(7)]
	cells[3][4] = -1                      # mur en (4,3), à l'est du prêtre
	pretre = _snap(0, 3, 3, competences=[AURA_SAINTE["_id"]])
	pretre["auras"][0]["zone"] = {"forme": "carre", "rayon": 2}
	derriere = _snap(1, 5, 3)             # dans le carré de rayon 2, mais derrière le mur
	a_decouvert = _snap(2, 3, 5)          # même distance, ligne de vue libre
	doc = _combat([pretre, derriere, a_decouvert], cells)
	combat_mod._recalculer_auras(doc)
	assert _auras(derriere) == []
	assert _auras(a_decouvert)


def test_combat_porteur_a_terre_n_emet_plus():
	pretre = _snap(0, 3, 3, competences=[AURA_SAINTE["_id"]])
	voisin = _snap(1, 3, 4)
	doc = _combat([pretre, voisin])
	combat_mod._recalculer_auras(doc)
	assert _auras(voisin)
	pretre["currentPV"] = 0
	combat_mod._recalculer_auras(doc)
	assert _auras(voisin) == [] and _auras(pretre) == []


def test_combat_deux_pretres_une_seule_regen():
	p1 = _snap(0, 3, 3, competences=[AURA_SAINTE["_id"]])
	p2 = _snap(1, 5, 3, competences=[AURA_SAINTE["_id"]])
	milieu = _snap(2, 4, 3)
	doc = _combat([p1, p2, milieu])
	combat_mod._recalculer_auras(doc)
	assert len(_auras(milieu)) == 2       # deux chips…
	avant = milieu["currentPV"]
	combat_mod._reset_turn_budget(milieu, doc)
	assert milieu["currentPV"] == avant + 1   # …une seule régén


def test_aura_jamais_reversee_apres_le_combat():
	pretre = _snap(0, 3, 3, competences=[AURA_SAINTE["_id"]])
	doc = _combat([pretre])
	combat_mod._recalculer_auras(doc)
	assert _auras(pretre)
	assert combat_mod._effets_a_reverser(pretre) == []


def test_simulateur_le_porteur_est_dans_sa_propre_aura():
	snap = build_joueur_snapshot(_character(competences=[AURA_FERVEUR["_id"]]), 0)
	esquive = snap["esquive"]
	combat_mod.poser_auras_propres(snap)
	assert [e["nom"] for e in _auras(snap)] == ["Aura de ferveur"]
	assert snap["esquive"] == esquive + 2
