# tests/test_combat_deux_armes.py
#
# Typologie de précision des armes (lourde / équilibrée / légère, tags `lourde`/`legere`)
# et combat à DEUX ARMES : un jet par arme, mêmes règles pour les deux (précision de SA
# typologie, dé et bonus de F, ses propres dés), furtivité pour toute l'attaque, une seule
# pénalité d'échec critique, second coup perdu si le premier tue.
#
# `_weapon_attacks` et `recompute_equipment_bonus` lisent le `get_doc` GLOBAL de leur
# module : les deux sont servis depuis un dict en mémoire, aucun accès DB.

import pytest

from models import character_stats as cs
from models.character_stats import BaseStats, compute_derived_stats
from utils import characters as characters_mod
from utils import combat as combat_mod
from utils import simulateur
from utils.combat import build_joueur_snapshot, build_monster_snapshot, resolve_action


# ── Fixtures ─────────────────────────────────────────────────────────────────────

KATANA = {
	"_id": "item:Katana", "type": "item", "nom": "Katana", "categorie": "arme",
	"slots": ["main_droite", "main_gauche"], "poids": 1.1, "tags": ["cac", "tranchant"],
	"portee": 1, "bonus_cc": 4, "bonus_degats": 3, "bonus_degats_dice": 8,
}
WAKIZASHI = {
	"_id": "item:Wakizashi", "type": "item", "nom": "Wakizashi", "categorie": "arme",
	"slots": ["main_droite", "main_gauche"], "poids": 0.9, "tags": ["cac", "legere"],
	"portee": 1, "bonus_cc": 4, "bonus_degats": 2, "bonus_degats_dice": 6,
}
MAILLET = {
	"_id": "item:Maillet", "type": "item", "nom": "Maillet de guerre", "categorie": "arme",
	"slots": ["main_droite"], "poids": 5.0, "tags": ["cac", "lourde"], "portee": 1,
	"deux_mains": True, "bonus_degats": 5, "bonus_degats_dice": 8,
}
PILUM = {
	"_id": "item:Pilum", "type": "item", "nom": "Pilum", "categorie": "arme",
	"slots": ["main_droite", "main_gauche"], "poids": 1.8, "tags": ["jet", "lourde"],
	"portee": 3, "bonus_degats": 4, "bonus_degats_dice": 6,
}
ARC = {
	"_id": "item:Arc", "type": "item", "nom": "Arc", "categorie": "arme",
	"slots": ["main_droite"], "poids": 0.85, "tags": ["tir", "legere"], "portee": 6,
	"deux_mains": True, "bonus_cd": 6, "bonus_degats": 2, "bonus_degats_dice": 4,
}
DOCS = {d["_id"]: d for d in (KATANA, WAKIZASHI, MAILLET, PILUM, ARC)}
DAISHO = {"main_droite": "item:Katana", "main_gauche": "item:Wakizashi"}

F, AG = 30, 50


@pytest.fixture(autouse=True)
def _items_en_memoire(monkeypatch):
	monkeypatch.setattr(combat_mod, "get_doc", DOCS.get)
	monkeypatch.setattr(characters_mod, "get_doc", DOCS.get)


def _character(slots):
	return {
		"_id": "character:test_1", "nom": "Hanzo", "voc": "guerrier", "race": "humain",
		"caracteristiques_current": {"V": 5, "F": F, "R": 30, "Ag": AG,
									 "Vol": 30, "Int": 30, "Cha": 20, "Ch": 20},
		"vocations_niveaux": {"guerrier": 1},
		"currentPV": 100, "currentPM": 20,
		"inventaire": [], "slots": dict(slots),
	}


def _espece():
	return {
		"_id": "espece:ours", "nom": "Ours", "tags": [],
		"base_attributes": {c: {"min": v, "max": v} for c, v in
							(("V", 4), ("F", 40), ("R", 40), ("Ag", 40),
							 ("Vol", 20), ("Int", 10), ("Cha", 10), ("Ch", 10))},
	}


def _scene(slots, pv=500):
	joueur = build_joueur_snapshot(_character(slots))
	joueur["pos"] = {"x": 3, "y": 5}
	joueur["vivant"] = True
	monstre = build_monster_snapshot(_espece(), None, 0)
	monstre["pos"] = {"x": 3, "y": 4}
	monstre["currentPV"] = monstre["pv_max"] = pv
	doc = {
		"_id": "combat:test", "type": "combat", "status": "active", "tour": 1, "log": [],
		"ordre_initiative": ["joueur_0", monstre["id"]], "acteur_courant_index": 0,
		"joueurs": [joueur], "monstres": [monstre],
		"grid": {"dims": {"x": 7, "y": 7}, "cells": [[1] * 7 for _ in range(7)], "nav": {}},
	}
	return doc, joueur, monstre


def _jets(monkeypatch, valeur):
	"""d100 figé ; tout autre dé rend 2 (localisation et dégâts déterministes)."""
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: valeur if b == 100 else 2)


def _profil_cac(joueur):
	return next(p for p in joueur["attaque_profils"] if p["mode"] == "cac")


def _lignes(doc, *kinds):
	return [e for e in doc["log"] if e.get("kind") in kinds]


# ── Typologie : formules et lecture des tags ─────────────────────────────────────

def test_trois_formules_de_precision():
	assert cs.precision_typologie(40, 20, "lourde") == (3 * 40 + 20) // 4
	assert cs.precision_typologie(40, 20, "equilibree") == (2 * 40 + 2 * 20) // 4
	assert cs.precision_typologie(40, 20, "legere") == (40 + 3 * 20) // 4
	# Typologie inconnue ⇒ légère (jamais d'exception sur une donnée exotique).
	assert cs.precision_typologie(40, 20, "?") == cs.precision_typologie(40, 20, "legere")


def test_la_legere_est_le_cc_d_avant_la_typologie():
	base = BaseStats(v=5, f=F, r=30, ag=AG, vol=30, int_=30, cha=20, ch=20)
	d = compute_derived_stats(base, niveau=1)
	assert d.cc == (F + 3 * AG) // 4
	assert d.cc_equilibree == (2 * F + 2 * AG) // 4
	assert d.cc_lourde == (3 * F + AG) // 4


def test_typologie_lue_dans_les_tags():
	assert cs.typologie_arme(MAILLET) == "lourde"
	assert cs.typologie_arme(WAKIZASHI) == "legere"
	assert cs.typologie_arme(KATANA) == "equilibree"   # aucun tag ⇒ équilibrée
	assert cs.typologie_arme({}) == "equilibree"


def test_retirer_les_des_d_une_arme():
	# F 30 → 1D6 ; katana 1D8+3 et wakizashi 1D6+2 additionnés par _format_damage.
	assert cs.retirer_des_arme("2D6+1D8+6", "1D6", 2) == "1D6+1D8+4"
	assert cs.retirer_des_arme("2D6+1D8+6", "1D8", 3) == "2D6+3"
	assert cs.retirer_des_arme("1D6+1", "", 0) == "1D6+1"


# ── Profils d'attaque ────────────────────────────────────────────────────────────

def test_une_arme_seule_touche_sous_sa_typologie():
	joueur = build_joueur_snapshot(_character({"main_droite": "item:Maillet"}))
	profil = _profil_cac(joueur)
	assert profil["toucher"] == "cc_lourde"
	assert "coups" not in profil   # arme à deux mains : un seul coup
	assert combat_mod.skill_du_profil(joueur, profil) == joueur["cc_lourde"]


def test_mains_nues_restent_sous_cc():
	joueur = build_joueur_snapshot(_character({}))
	profil = _profil_cac(joueur)
	assert profil["toucher"] == "cc" and "coups" not in profil


def test_le_jet_suit_la_typologie_et_le_tir_reste_sous_cd():
	joueur = build_joueur_snapshot(_character({"main_droite": "item:Pilum"}))
	assert next(p for p in joueur["attaque_profils"] if p["mode"] == "jet")["toucher"] == "cc_lourde"
	joueur = build_joueur_snapshot(_character({"main_droite": "item:Arc"}))
	assert next(p for p in joueur["attaque_profils"] if p["mode"] == "tir")["toucher"] == "cd"


def test_le_daisho_donne_deux_coups_main_droite_d_abord():
	joueur = build_joueur_snapshot(_character(DAISHO))
	coups = _profil_cac(joueur)["coups"]
	assert [c["item_id"] for c in coups] == ["item:Katana", "item:Wakizashi"]
	assert [c["toucher"] for c in coups] == ["cc_equilibree", "cc"]


def test_memes_regles_pour_les_deux_armes():
	joueur = build_joueur_snapshot(_character(DAISHO))
	(katana, s_k, n_k), (waki, s_w, n_w) = combat_mod.coups_du_profil(joueur, _profil_cac(joueur))
	# Précision : SA typologie + SON bonus_cc (le snapshot additionne les deux bonus).
	assert s_k == cs.precision_typologie(F, AG, "equilibree") + KATANA["bonus_cc"]
	assert s_w == cs.precision_typologie(F, AG, "legere") + WAKIZASHI["bonus_cc"]
	# Dégâts : dé et bonus de F pour CHACUNE, plus ses propres dés et son plat.
	# ⚠️ Dé de F (1D5 à F 30) distinct de 1D6/1D8 : les notations restent lisibles telles quelles.
	de_f = cs._caract_to_dice_(F)
	assert de_f not in (6, 8)
	bonus_f = F // cs.facteur_degats_armure()
	assert n_k == f"1D{de_f}+1D8{bonus_f + KATANA['bonus_degats']:+d}"
	assert n_w == f"1D{de_f}+1D6{bonus_f + WAKIZASHI['bonus_degats']:+d}"


def test_snapshot_sans_cle_de_typologie_retombe_sur_cc():
	"""Combat déjà en base : un profil qui nomme `cc_lourde` sur un snapshot qui ne la
	porte pas touche sous `cc` (aucune migration)."""
	assert combat_mod.skill_du_profil({"cc": 42}, {"toucher": "cc_lourde"}) == 42


# ── Résolution en jeu ────────────────────────────────────────────────────────────

def test_deux_jets_deux_soustractions_d_armure(monkeypatch):
	doc, joueur, monstre = _scene(DAISHO)
	_jets(monkeypatch, 50)
	pv_avant = monstre["currentPV"]
	result = resolve_action(doc, "attaquer", cible_id=monstre["id"], mode="cac")
	assert len(_lignes(doc, "hit", "crit")) == 2
	assert len(result["coups"]) == 2
	assert result["dmg"] == pv_avant - monstre["currentPV"]
	# UNE seule action consommée pour les deux coups.
	assert joueur["attaques"] == 1


def test_le_second_coup_est_perdu_si_le_premier_tue(monkeypatch):
	doc, joueur, monstre = _scene(DAISHO, pv=1)
	_jets(monkeypatch, 50)
	resolve_action(doc, "attaquer", cible_id=monstre["id"], mode="cac")
	assert len(_lignes(doc, "hit", "crit", "kill")) == 1


def test_une_seule_penalite_d_echec_critique(monkeypatch):
	doc, joueur, monstre = _scene(DAISHO)
	_jets(monkeypatch, 100)   # échec critique aux deux jets
	resolve_action(doc, "attaquer", cible_id=monstre["id"], mode="cac")
	assert len(_lignes(doc, "fumble")) == 2
	assert joueur.get("penalites", 0) + joueur.get("dette_actions", 0) == 1


def test_la_furtivite_profite_aux_deux_jets(monkeypatch):
	doc, joueur, monstre = _scene(DAISHO)
	joueur["furtif"] = True
	monstre["detecte"] = False
	_jets(monkeypatch, 50)
	resolve_action(doc, "attaquer", cible_id=monstre["id"], mode="cac")
	assert len(_lignes(doc, "crit")) == 2   # coup furtif touché = critique automatique


def test_un_monstre_humanoide_a_deux_armes_frappe_deux_fois(monkeypatch):
	doc, joueur, monstre = _scene({})
	joueur["currentPV"] = joueur["pv_max"] = 500
	monstre["attaques"] = 0
	monstre["actions_max"] = monstre["actions_restantes"] = 2
	arme = build_joueur_snapshot(_character(DAISHO))
	monstre["attaque_profils"] = arme["attaque_profils"]
	for cle in ("cc_equilibree", "cc", "degats_cc"):
		monstre[cle] = arme[cle]
	_jets(monkeypatch, 20)   # sous les deux seuils (Ag 50 du joueur), hors fenêtre critique
	combat_mod._do_attack_on(doc, monstre, joueur, _profil_cac(monstre))
	assert len(_lignes(doc, "hit", "crit")) == 2
	assert monstre["attaques"] == 1


# ── Simulateur / potentiels : espérance sur les deux coups ──────────────────────

def test_l_esperance_somme_les_deux_coups():
	joueur = build_joueur_snapshot(_character(DAISHO))
	cible = {"pa": 0, "ag": 40, "esquive": 0, "pm_def": 0, "caracts_base": {}}
	option = {"jet": "cc", "notation": "1D4", "coups": simulateur._coups_option(joueur, _profil_cac(joueur))}
	seuil = lambda coup: combat_mod._hit_threshold(coup["skill"], 40)
	total = simulateur.esperance_option(joueur, cible, option, seuil)
	parts = [simulateur.esperance_option(joueur, cible, dict(option, coups=[c]), seuil)
			 for c in option["coups"]]
	assert len(parts) == 2 and total == pytest.approx(sum(parts))


# ── Compétences martiales : arme de la main droite ───────────────────────────────

FRAPPE = {"nom": "Frappe", "jet": "cc", "effets": {"degats": "1D4"}}


def test_une_competence_martiale_touche_sous_la_typologie_de_l_arme():
	joueur = build_joueur_snapshot(_character({"main_droite": "item:Maillet"}))
	assert combat_mod.skill_capacite(joueur, FRAPPE, FRAPPE["effets"], "cc", "competence") \
		== joueur["cc_lourde"]
	# Un sort « au toucher » n'emprunte pas l'arme : il garde `cc`.
	assert combat_mod.skill_capacite(joueur, FRAPPE, FRAPPE["effets"], "cc", "sort") == joueur["cc"]


def test_une_competence_au_daisho_frappe_avec_la_seule_main_droite():
	joueur = build_joueur_snapshot(_character(DAISHO))
	(_, skill_k, notation_k), _ = combat_mod.coups_du_profil(joueur, _profil_cac(joueur))
	assert combat_mod.skill_capacite(joueur, FRAPPE, FRAPPE["effets"], "cc", "competence") == skill_k
	assert combat_mod._degats_competence(joueur, FRAPPE, FRAPPE["effets"]) \
		== combat_mod.concat_degats(notation_k, "1D4")
