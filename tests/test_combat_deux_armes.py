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


def test_la_premiere_arme_garde_la_force_la_seconde_non():
	joueur = build_joueur_snapshot(_character(DAISHO))
	(katana, s_k, n_k), (waki, s_w, n_w) = combat_mod.coups_du_profil(joueur, _profil_cac(joueur))
	# Précision : SA typologie + SON bonus_cc (le snapshot additionne les deux bonus) ; la
	# seconde arme prend le malus de seconde arme.
	assert s_k == cs.precision_typologie(F, AG, "equilibree") + KATANA["bonus_cc"]
	assert s_w == (cs.precision_typologie(F, AG, "legere") + WAKIZASHI["bonus_cc"]
				   - cs.DEUX_ARMES_MALUS_SECOND)
	# Dégâts : la première arme a le dé et le bonus de F ; la seconde ses seuls dés et plat.
	# ⚠️ Dé de F (1D5 à F 30) distinct de 1D6/1D8 : les notations restent lisibles telles quelles.
	de_f = cs._caract_to_dice_(F)
	assert de_f not in (6, 8)
	bonus_f = F // cs.facteur_degats_armure()
	assert n_k == f"1D{de_f}+1D8{bonus_f + KATANA['bonus_degats']:+d}"
	assert n_w == f"1D6{WAKIZASHI['bonus_degats']:+d}"


def test_l_ambidextre_ne_prend_pas_le_malus_de_seconde_arme():
	joueur = build_joueur_snapshot(_character(DAISHO))
	sans = combat_mod.coups_du_profil(joueur, _profil_cac(joueur))
	joueur["ambidextre"] = 1
	avec = combat_mod.coups_du_profil(joueur, _profil_cac(joueur))
	assert avec[0][1] == sans[0][1]
	assert avec[1][1] == sans[1][1] + cs.DEUX_ARMES_MALUS_SECOND
	# L'ambidextrie lève le malus de PRÉCISION, jamais la règle de la Force.
	assert avec[1][2] == sans[1][2]


def test_l_ambidextrie_vient_d_une_passive_jusqu_au_snapshot(monkeypatch):
	passive = {"_id": "competence:ambidextre", "type": "competence", "nom": "Ambidextre",
			   "vocation": "guerrier", "mode": "passive", "niveau": 1, "cout_pm": 0,
			   "effets": {"ambidextre": 1}}
	from utils import competences as competences_util
	perso = _character(DAISHO)
	perso["competences_connues"] = ["competence:ambidextre"]
	docs = dict(DOCS, **{passive["_id"]: passive})
	bonus = competences_util.bonus_passifs(perso, docs.get)
	assert bonus["ambidextre"] == 1
	# Sans la passive, la clé n'est pas posée : les agrégats déjà en base restent égaux à
	# leur recalcul (aucune réécriture de masse par `synchroniser_competences_bonus`).
	assert "ambidextre" not in competences_util.bonus_passifs(_character(DAISHO), docs.get)
	perso["competences_bonus"] = bonus
	assert build_joueur_snapshot(perso)["ambidextre"] == 1


def test_un_malus_de_seconde_arme_a_zero_desactive_la_regle(monkeypatch):
	joueur = build_joueur_snapshot(_character(DAISHO))
	monkeypatch.setattr(cs, "DEUX_ARMES_MALUS_SECOND", 0)
	assert combat_mod.coups_du_profil(joueur, _profil_cac(joueur))[1][1] \
		== cs.precision_typologie(F, AG, "legere") + WAKIZASHI["bonus_cc"]


def test_snapshot_sans_caracts_base_garde_la_force_au_second_coup():
	"""Combat déjà en base (snapshot sans `caracts_base`) : la part de Force ne peut pas
	se retrouver, le second coup la garde — comportement d'avant (aucune migration)."""
	joueur = build_joueur_snapshot(_character(DAISHO))
	joueur.pop("caracts_base")
	n_w = combat_mod.coups_du_profil(joueur, _profil_cac(joueur))[1][2]
	assert n_w.startswith(f"1D{cs._caract_to_dice_(F)}+1D6")


def test_snapshot_sans_cle_de_typologie_retombe_sur_cc():
	"""Combat déjà en base : un profil qui nomme `cc_lourde` sur un snapshot qui ne la
	porte pas touche sous `cc` (aucune migration)."""
	assert combat_mod.skill_du_profil({"cc": 42}, {"toucher": "cc_lourde"}) == 42


# ── Résolution en jeu ────────────────────────────────────────────────────────────

def test_deux_jets_deux_soustractions_d_armure(monkeypatch):
	doc, joueur, monstre = _scene(DAISHO)
	_jets(monkeypatch, 20)   # sous les deux seuils, malus de seconde arme compris
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
	_jets(monkeypatch, 20)   # sous les deux seuils, malus de seconde arme compris
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


def test_une_competence_au_daisho_porte_ses_des_par_la_main_droite():
	joueur = build_joueur_snapshot(_character(DAISHO))
	(_, skill_k, notation_k), second = combat_mod.coups_du_profil(joueur, _profil_cac(joueur))
	assert combat_mod.skill_capacite(joueur, FRAPPE, FRAPPE["effets"], "cc", "competence") == skill_k
	assert combat_mod._degats_competence(joueur, FRAPPE, FRAPPE["effets"]) \
		== combat_mod.concat_degats(notation_k, "1D4")
	# … puis la seconde arme frappe, sans les dés de la compétence (même coup qu'`attaquer`).
	assert combat_mod.coups_seconde_arme_competence(joueur, FRAPPE, FRAPPE["effets"]) == [second]


def test_pas_de_seconde_arme_sans_deux_armes_ni_sans_des():
	seule = build_joueur_snapshot(_character({"main_droite": "item:Katana"}))
	assert combat_mod.coups_seconde_arme_competence(seule, FRAPPE, FRAPPE["effets"]) == []
	daisho = build_joueur_snapshot(_character(DAISHO))
	entrave = {"nom": "Entrave", "jet": "cc", "effets": {"buffs": {"V": -2}, "duree": 2}}
	assert combat_mod.coups_seconde_arme_competence(daisho, entrave, entrave["effets"]) == []
	magique = {"nom": "Onde", "jet": "magique", "effets": {"degats": "1D6"}}
	assert combat_mod.coups_seconde_arme_competence(daisho, magique, magique["effets"]) == []


def _competence_frappe():
	from utils.competences import normaliser_competence
	return normaliser_competence({
		"_id": "competence:frappe", "type": "competence", "vocation": "guerrier",
		"nom": "Frappe", "mode": "active", "cout_pm": 0, "portee": 1, "jet": "cc",
		"cible": "ennemi", "effets": {"degats": "1D4"}})


def test_une_competence_au_daisho_frappe_puis_la_seconde_arme_suit(monkeypatch):
	doc, joueur, monstre = _scene(DAISHO)
	_jets(monkeypatch, 20)   # sous les deux seuils, hors fenêtre critique
	pv_avant = monstre["currentPV"]
	result = resolve_action(doc, "competence", cible_id=monstre["id"],
							competence=_competence_frappe())
	assert "error" not in result
	assert len(_lignes(doc, "hit", "crit")) == 2
	assert len(result["coups_arme"]) == 1 and result["coups_arme"][0]["hit"]
	assert result["dmg"] + result["coups_arme"][0]["dmg"] == pv_avant - monstre["currentPV"]
	# UNE action pour la compétence ET la seconde arme ; aucune attaque comptée en plus.
	assert joueur.get("competences", 0) == 1 and joueur.get("attaques", 0) == 0


def test_competence_une_seule_penalite_d_echec_critique(monkeypatch):
	doc, joueur, monstre = _scene(DAISHO)
	_jets(monkeypatch, 100)   # échec critique à la compétence ET à la seconde arme
	resolve_action(doc, "competence", cible_id=monstre["id"], competence=_competence_frappe())
	assert len(_lignes(doc, "fumble")) == 2
	assert joueur.get("penalites", 0) + joueur.get("dette_actions", 0) == 1


def test_competence_pas_de_seconde_arme_sur_une_cible_abattue(monkeypatch):
	doc, joueur, monstre = _scene(DAISHO, pv=1)
	_jets(monkeypatch, 20)
	result = resolve_action(doc, "competence", cible_id=monstre["id"],
							competence=_competence_frappe())
	assert "coups_arme" not in result
	assert len(_lignes(doc, "hit", "crit", "kill")) == 1


def test_le_simulateur_joue_aussi_la_seconde_arme_d_une_competence():
	joueur = build_joueur_snapshot(_character(DAISHO))
	comp = dict(_competence_frappe(), cout_pm=0)
	options = [o for o in simulateur._options_jouables(joueur, {"competences": [comp]}, 1)
			   if o["kind"] == "competence"]
	assert len(options) == 1 and len(options[0]["coups"]) == 2
	premier, second = options[0]["coups"]
	assert premier["notation"] == options[0]["notation"]
	_, skill_w, notation_w = combat_mod.coups_du_profil(joueur, _profil_cac(joueur))[1]
	assert (second["skill"], second["notation"]) == (skill_w, notation_w)


# ── Affichage : un terme par arme, séparés par « / » ────────────────────────────

def test_affichage_des_degats_par_arme():
	joueur = build_joueur_snapshot(_character(DAISHO))
	attendu = " / ".join(n for _, _, n in combat_mod.coups_du_profil(joueur, _profil_cac(joueur)))
	base = BaseStats(f=F)
	assert combat_mod.degats_cc_par_arme(_character(DAISHO), base, joueur["degats_cc"]) == attendu
	assert simulateur.fiche_snapshot(joueur)["degats_cc"] == attendu
	# Une seule arme : rien de neuf, `degats_cc` dit déjà le vrai.
	seule = _character({"main_droite": "item:Katana"})
	assert combat_mod.degats_cc_par_arme(seule, base, "1D5+1D8+4") is None
	assert simulateur.fiche_snapshot(build_joueur_snapshot(seule))["degats_cc"] \
		== build_joueur_snapshot(seule)["degats_cc"]
