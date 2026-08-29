# tests/test_simulateur.py
# Simulateur de duel 1D (utils/simulateur) + règles de potentiel (utils/potentiel).
# Tests purs : docs en dicts, get_doc_fn = lambda, jets monkeypatchés dans utils.combat
# (le simulateur appelle combat._resoudre_jet / combat.roll_dice à l'exécution).

import math
import random

import pytest

from utils import combat, potentiel, simulateur


# ── Fixtures ─────────────────────────────────────────────────────────────────────────

def _attrs(**kwargs):
	"""base_attributes déterministes (min == max)."""
	defauts = {"V": 1, "F": 0, "R": 0, "Ag": 0, "Vol": 0, "Int": 0, "Cha": 0, "Ch": 0}
	defauts.update(kwargs)
	return {k: {"min": v, "max": v} for k, v in defauts.items()}


ESPECE_FORTE = {
	"_id": "espece:ours_test", "type": "espece", "nom": "Ours", "image": "ours.png",
	# pv_max 160, cc 40, pa 2, actions_max 3, deplacement 4, initiative 40, degats 1D6+2
	"base_attributes": _attrs(V=4, F=40, R=40, Ag=40),
	"tags": ["monstre"],
}

ESPECE_FAIBLE = {
	"_id": "espece:rat_test", "type": "espece", "nom": "Rat",
	# pv_max 40, cc 17, pa 0, actions_max 2, deplacement 2, initiative 20
	"base_attributes": _attrs(V=2, F=10, R=10, Ag=20),
	"tags": ["monstre"],
}

PROFIL_VARIABLE = {
	"_id": "profil:test", "type": "profil", "nom": "Vétéran", "niveau": 3,
	"attributs_modifier": {"F": {"min": 0, "max": 20}, "Ag": {"min": 2, "max": 8}},
}

ESPECE_VARIABLE = {
	"_id": "espece:loup_test", "type": "espece", "nom": "Loup",
	"base_attributes": {k: {"min": v, "max": v + 20} for k, v in
						{"F": 20, "R": 20, "Ag": 30, "Vol": 10, "Int": 5, "Cha": 0, "Ch": 0}.items()}
	| {"V": {"min": 3, "max": 5}},
	"tags": ["monstre"],
}

SORT_SOIN = {
	"_id": "sort:soin_test", "type": "sort", "nom": "Soin léger", "vocation": "clerc",
	"niveau": 0, "cout_pm": 5, "cible": "soi", "portee": 0, "effets": {"pv": 20},
}

# Miroir de competence:furtivite_sylvestre — LA raison d'être du choix de terrain.
COMP_FURTIVE = {
	"_id": "competence:furtivite_test", "type": "competence", "nom": "Furtivité sylvestre",
	"vocation": "forestier", "mode": "passive", "niveau": 0,
	"condition": {"battle_map_tags": ["foret", "bois"]}, "effets": {"furtivite": 1},
}

SORT_RACINES = {
	"_id": "sort:racines_test", "type": "sort", "nom": "Racines gardiennes",
	"vocation": "forestier", "niveau": 0, "cout_pm": 5, "cible": "soi", "portee": 0,
	"condition": {"battle_map_tags": ["foret", "bois"]},
	"effets": {"buffs": {"F": 10}, "duree": 3},
}

POTION = {
	"_id": "item:potion_test", "type": "item", "nom": "Potion", "categorie": "consommable",
	"poids": 0.5, "effets": {"pv": 15},
}

CHARACTER = {
	"_id": "character:user:test_abc", "type": "character",
	"prenom": "Aria", "nom": "Duval", "voc": "clerc", "race": "humain",
	"xp_total": 516,
	"vocations_niveaux": {"clerc": 2},
	"caracteristiques_current": {"V": 3, "F": 30, "R": 30, "Ag": 30,
								 "Vol": 40, "Int": 30, "Cha": 20, "Ch": 20},
	"currentPV": 5, "currentPM": 5,     # état de jeu bas → le banc force la pleine forme
	"slots": {},
	"inventaire": [{"item": "item:potion_test", "poids": 0.5},
				   {"item": "item:potion_test", "poids": 0.5}],
	"sorts_connus": ["sort:soin_test", "sort:racines_test"],
	"competences_connues": ["competence:furtivite_test"],
	"slots_actions": [
		{"type": "attaque", "ref": "cac"}, {"type": "ramasser"}, {"type": "fuir"},
		{"type": "sort", "ref": "sort:soin_test", "composants": True},
		{"type": "sort", "ref": "sort:soin_test", "composants": False},   # doublon → 1 option
		{"type": "sort", "ref": "sort:racines_test", "composants": True},  # conditionné forêt
		{"type": "consommable", "ref": "item:potion_test"},
	],
}

DOCS = {d["_id"]: d for d in (ESPECE_FORTE, ESPECE_FAIBLE, PROFIL_VARIABLE,
							  ESPECE_VARIABLE, SORT_SOIN, COMP_FURTIVE, SORT_RACINES,
							  POTION, CHARACTER)}


def get_doc(doc_id):
	return DOCS.get(doc_id)


@pytest.fixture
def jets_surs(monkeypatch):
	"""Toujours touché, jamais critique, dés figés à 10 → duel entièrement déterministe."""
	monkeypatch.setattr(combat, "_resoudre_jet", lambda a, d, s: {
		"roll": 50, "seuil": s, "touche": True, "critique": False,
		"fumble": False, "mult_degats": 1})
	monkeypatch.setattr(combat, "roll_dice", lambda notation: 10)


# ── moyenne_de_des ───────────────────────────────────────────────────────────────────

def test_moyenne_de_des():
	assert simulateur.moyenne_de_des("2D8+1D4+3") == 14.5
	assert simulateur.moyenne_de_des("1D6-1") == 2.5
	assert simulateur.moyenne_de_des("D4") == 2.5
	assert simulateur.moyenne_de_des("") == 1.0
	assert simulateur.moyenne_de_des("1D6+1D6") == 7.0


# ── Construction des belligérants ────────────────────────────────────────────────────

def test_belligerant_espece_normalise_le_snapshot():
	bel = simulateur.construire_belligerant({"type": "espece", "id": "espece:ours_test"}, get_doc)
	snap = bel["fabrique"]()
	# Champs absents du snapshot monstre, comblés à la lecture :
	assert snap["cd"] == 0 and snap["currentPM"] == 0 and snap["pm_max"] == 0
	assert snap["toucher_magique"] == 0 and snap["esquive"] == 0
	profils = snap["attaque_profils"]
	assert len(profils) == 1 and profils[0]["mode"] == "cac" and profils[0]["portee"] == 1
	assert bel["label"] == "Ours"
	assert bel["arsenal"]["soutiens"] == []


def test_belligerant_espece_refuse_id_et_doc_invalides():
	with pytest.raises(ValueError):
		simulateur.construire_belligerant({"type": "espece", "id": "item:potion_test"}, get_doc)
	with pytest.raises(LookupError):
		simulateur.construire_belligerant({"type": "espece", "id": "espece:absent"}, get_doc)
	with pytest.raises(ValueError):
		simulateur.construire_belligerant({"type": "autre", "id": "espece:ours_test"}, get_doc)


def test_belligerant_character_pleine_forme_et_arsenal_de_barre():
	bel = simulateur.construire_belligerant({"type": "character", "id": CHARACTER["_id"]}, get_doc)
	snap = bel["fabrique"]()
	# Pleine forme forcée, malgré currentPV/PM bas sur le doc :
	assert snap["currentPV"] == snap["pv_max"] > 5
	assert snap["currentPM"] == snap["pm_max"] > 5
	# Le sort de soin (2 cases → 1 option) et la potion (stock 2) sont des soutiens :
	soutiens = bel["arsenal"]["soutiens"]
	assert [s["kind"] for s in soutiens].count("sort") == 1
	potion = next(s for s in soutiens if s["kind"] == "consommable")
	assert potion["stock"] == 2
	assert snap["_sim_stocks"] == {"item:potion_test": 2}
	assert bel["label"] == "Aria Duval"
	# Niveaux affichés par l'écran : race + niveau global (dérivé de l'XP) + vocations.
	from models.character_stats import compute_character_level
	assert bel["niveaux"] == {"niveau": compute_character_level(516), "race": "humain",
							  "vocations": {"clerc": 2}}
	# Une espèce n'a pas de niveaux.
	bel_espece = simulateur.construire_belligerant({"type": "espece", "id": "espece:ours_test"}, get_doc)
	assert "niveaux" not in bel_espece


# ── Duel déterministe ────────────────────────────────────────────────────────────────

def test_duel_joue_d_avance(jets_surs):
	"""Ours (160 PV, 3 att. × 10 dégâts) vs Rat (40 PV, 2 att. × (10−2)=8) à distance 1 :
	le Rat tombe à la 1re attaque du round 2, l'Ours garde 160 − 16 = 144 PV."""
	res = simulateur.simuler_duel(
		{"type": "espece", "id": "espece:ours_test"},
		{"type": "espece", "id": "espece:rat_test"},
		distance=1, passes=5, get_doc_fn=get_doc)
	assert res["a"]["taux"] == 1.0 and res["b"]["victoires"] == 0 and res["nuls"] == 0
	assert res["rounds"]["min"] == res["rounds"]["max"] == 2
	assert res["a"]["pv_restants_moyens"] == 144
	assert res["b"]["pv_restants_moyens"] is None
	assert res["journal"]           # la passe 1 est journalisée
	# Le profil affiché par l'écran = caracts + dérivées du snapshot de référence :
	assert res["a"]["profil"]["pv_max"] == 160
	assert res["a"]["profil"]["caracts"]["F"] == 40
	assert res["a"]["profil"]["actions_max"] == 3
	assert res["b"]["profil"]["pv_max"] == 40
	# L'image est une route SERVEUR (mount /monsters) ; espèce sans image → vide.
	assert res["a"]["image_route"] == "/monsters/ours.png"
	assert res["b"]["image_route"] == ""


def test_approche_1d_coute_le_deplacement(jets_surs):
	"""À distance 5, l'Ours (dép. 4, 3 actions) brûle son round 1 à approcher (3 cases =
	3 AP) : son premier coup tombe au round 2. Le Rat, arrivé à 1 case à son tour du
	round 1, frappe dès le round 1."""
	res = simulateur.simuler_duel(
		{"type": "espece", "id": "espece:ours_test"},
		{"type": "espece", "id": "espece:rat_test"},
		distance=5, passes=1, get_doc_fn=get_doc)
	hits_a = [l for l in res["journal"] if l["kind"] == "hit" and l["acteur"].startswith("[A]")]
	hits_b = [l for l in res["journal"] if l["kind"] == "hit" and l["acteur"].startswith("[B]")]
	assert hits_a and hits_a[0]["tour"] == 2
	assert hits_b and hits_b[0]["tour"] == 1


def test_plafond_de_rounds_donne_un_nul(monkeypatch):
	monkeypatch.setattr(combat, "_resoudre_jet", lambda a, d, s: {
		"roll": 50, "seuil": s, "touche": False, "critique": False,
		"fumble": False, "mult_degats": 1})
	res = simulateur.simuler_duel(
		{"type": "espece", "id": "espece:ours_test"},
		{"type": "espece", "id": "espece:rat_test"},
		distance=1, passes=3, get_doc_fn=get_doc, plafond_rounds=3)
	assert res["nuls"] == 3
	assert res["rounds"]["max"] == 3
	assert res["a"]["victoires"] == res["b"]["victoires"] == 0


def test_soin_part_avant_l_attaque(jets_surs):
	"""PV sous le seuil → le soin (PM débités) passe avant toute attaque du tour."""
	bel = simulateur.construire_belligerant({"type": "character", "id": CHARACTER["_id"]}, get_doc)
	actor = bel["fabrique"]()
	cible = simulateur._normaliser_snapshot({
		"id": "monstre_0", "nom": "Cible", "currentPV": 500, "pv_max": 500,
		"ag": 0, "pa": 0, "pm_def": 0, "ch": 0, "vivant": True,
		"initiative": 0, "deplacement": 1, "actions_max": 1, "actions_restantes": 1,
		"degats_cc": "1D4", "cc": 10, "effets_actifs": [], "caracts_base": {},
		"pos": {"x": 0, "y": 0},
	})
	# Juste sous le seuil de 40 % (pv_max 120 → seuil 48) : UN soin suffit à repasser
	# au-dessus, le reste du tour part en attaques.
	actor["currentPV"] = 45
	pm_avant = actor["currentPM"]
	pseudo = {"tour": 2, "log": []}
	etat = {"distance": 1, "pseudo": pseudo}
	simulateur._jouer_tour(actor, cible, bel["arsenal"], etat, round_no=2)
	sys_lines = [l for l in pseudo["log"] if l["kind"] == "sys" and "Soin léger" in l["texte"]]
	assert len(sys_lines) == 1
	assert actor["currentPM"] == pm_avant - SORT_SOIN["cout_pm"]
	assert actor["currentPV"] == 65
	# Les actions restantes sont bien parties en attaques après le soin :
	assert any(l["kind"] == "hit" for l in pseudo["log"])


# ── Objets autorisés ou non ──────────────────────────────────────────────────────────

def test_objets_interdits_retire_les_consommables_seulement():
	"""Décocher « objets » prive des potions, PAS des sorts, compétences ni armes."""
	avec = simulateur.construire_belligerant(
		{"type": "character", "id": CHARACTER["_id"]}, get_doc)
	sans = simulateur.construire_belligerant(
		{"type": "character", "id": CHARACTER["_id"]}, get_doc, objets=False)

	assert [c["id"] for c in avec["arsenal"]["consommables"]] == ["item:potion_test"]
	assert sans["arsenal"]["consommables"] == []
	# Le soin par SORT, lui, reste disponible dans les deux cas.
	assert [s["kind"] for s in avec["arsenal"]["soutiens"]].count("consommable") == 1
	assert [s["kind"] for s in sans["arsenal"]["soutiens"]].count("consommable") == 0
	assert [s["kind"] for s in sans["arsenal"]["soutiens"]].count("sort") == 1
	# Les armes viennent du snapshot, jamais de l'arsenal : intactes.
	assert sans["fabrique"]()["attaque_profils"] == avec["fabrique"]()["attaque_profils"]
	# Plus aucun stock à porter dans le snapshot.
	assert sans["fabrique"]()["_sim_stocks"] == {}


def test_une_espece_ignore_le_reglage_des_objets():
	"""Une espèce n'a pas de sac : le réglage ne peut rien lui retirer."""
	for objets in (True, False):
		bel = simulateur.construire_belligerant(
			{"type": "espece", "id": "espece:ours_test"}, get_doc, objets=objets)
		assert bel["arsenal"]["consommables"] == []


# ── Bornes de l'espèce (le pire / le meilleur spécimen) ──────────────────────────────

def test_bornes_donnent_les_extremes_de_la_fourchette():
	"""ESPECE_VARIABLE : chaque caract va de v à v+20 (V de 3 à 5). `min` doit rendre
	toutes les bornes basses, `max` toutes les hautes."""
	bas = simulateur.construire_belligerant(
		{"type": "espece", "id": "espece:loup_test", "borne": "min"}, get_doc)
	haut = simulateur.construire_belligerant(
		{"type": "espece", "id": "espece:loup_test", "borne": "max"}, get_doc)
	attrs = ESPECE_VARIABLE["base_attributes"]
	assert bas["fabrique"]()["caracts_base"] == {k: b["min"] for k, b in attrs.items()}
	assert haut["fabrique"]()["caracts_base"] == {k: b["max"] for k, b in attrs.items()}
	assert bas["label"] == "Loup (minimum)" and haut["label"] == "Loup (maximum)"
	# La référence des potentiels est le snapshot BORNÉ, pas le médian.
	assert haut["snapshot_reference"]["caracts_base"] == haut["fabrique"]()["caracts_base"]


def test_borne_est_deterministe_passe_apres_passe():
	bel = simulateur.construire_belligerant(
		{"type": "espece", "id": "espece:loup_test", "borne": "max"}, get_doc)
	assert bel["fabrique"]()["caracts_base"] == bel["fabrique"]()["caracts_base"]


def test_borne_illisible_ou_combinee_a_un_profil_refuse():
	with pytest.raises(ValueError):
		simulateur.construire_belligerant(
			{"type": "espece", "id": "espece:loup_test", "borne": "moyen"}, get_doc)
	with pytest.raises(ValueError):
		simulateur.construire_belligerant(
			{"type": "espece", "id": "espece:loup_test",
			 "borne": "max", "profil": "profil:test"}, get_doc)


# ── Terrain : furtivité d'entrée + filtre de condition ───────────────────────────────

def test_terrain_pose_la_furtivite_et_ouvre_l_arsenal_conditionne():
	# En forêt : la passive conditionnée rend furtif, le sort conditionné entre à l'arsenal.
	bel = simulateur.construire_belligerant(
		{"type": "character", "id": CHARACTER["_id"]}, get_doc, map_tags=("foret",))
	snap = bel["fabrique"]()
	assert snap["furtif"] is True and snap["furtivite_bonus"] == 1
	assert [s["kind"] for s in bel["arsenal"]["soutiens"]].count("sort") == 2

	# Terrain nu : pas de furtivité, sort conditionné écarté (le soin reste).
	bel_nu = simulateur.construire_belligerant(
		{"type": "character", "id": CHARACTER["_id"]}, get_doc)
	assert bel_nu["fabrique"]()["furtif"] is False
	assert [s["kind"] for s in bel_nu["arsenal"]["soutiens"]].count("sort") == 1


def test_adversaire_furtif_non_detecte_fait_errer(jets_surs, monkeypatch):
	"""Rat aveugle face au forestier furtif : il erre au lieu d'approcher, jusqu'à ce
	que le corps à corps du personnage brise la furtivité (comme au moteur)."""
	monkeypatch.setattr(combat, "_tenter_detection",
						lambda doc, m, j, echec_texte=None: False)
	res = simulateur.simuler_duel(
		{"type": "character", "id": CHARACTER["_id"]},
		{"type": "espece", "id": "espece:rat_test"},
		distance=5, passes=1, get_doc_fn=get_doc, map_tags=("foret",))
	journal = res["journal"]
	assert any("erre sans trouver" in l["texte"] and l["tour"] == 1 for l in journal)
	assert any("sort de l'ombre" in l["texte"] for l in journal)
	# Aveugle, le Rat n'a rien frappé au round 1.
	assert not any(l["kind"] in ("hit", "crit") and l["acteur"].startswith("[B]")
				   and l["tour"] == 1 for l in journal)


# ── Potentiels ───────────────────────────────────────────────────────────────────────

REGLES_TEST = {
	"defense_reference": 50, "pm_def_reference": 50, "pa_reference": 0,
	"poids_offense": 1.0, "poids_survie": 1.0,
	"facteur_pa": 0.0, "facteur_esquive": 0.0, "bonus_portee": 0.0,
	"poids_soin": 1.0, "poids_pm_rendus": 0.0, "poids_regen": 0.0,
	"poids_buff": 0.0, "poids_esquive_octroyee": 0.0, "poids_furtivite": 0.0,
}


def _snapshot_simple():
	return {
		"actions_max": 2, "pm_max": 30, "pv_max": 100, "pa": 5, "ag": 40, "esquive": 0,
		"cc": 50, "cd": 0, "toucher_magique": 0, "degats_cc": "1D6+2",
		"attaque_profils": [{"mode": "cac", "portee": 1, "ranged": False,
							 "toucher": "cc", "degats": "degats_cc", "label": "Épée"}],
	}


def test_potentiel_combat_valeurs_a_la_main():
	res = potentiel.potentiel_combat(_snapshot_simple(), {"sorts": [], "competences": []},
									 regles=REGLES_TEST)
	# seuil = 50 + 50 − 50 = 50 → p 0.5 ; E("1D6+2") = 5.5 ; ×2 actions = 5.5/round.
	assert res["offense"] == 5.5
	assert res["survie"] == 100
	assert res["total"] == round(math.sqrt(5.5 * 100), 1)
	assert res["option_retenue"] == "Épée"


def test_potentiel_support_soin_et_espece_a_zero():
	soutien = {"kind": "sort", "id": "sort:soin_test", "label": "Soin léger", "icon": "",
			   "cout_pm": 5, "effets": {"pv": 20, "pm": 0, "regen_pv": 0, "regen_pm": 0,
										"buffs": {}, "duree": 0, "esquive": 0, "furtivite": 0},
			   "compteur": "sorts", "source": {}}
	res = potentiel.potentiel_support({"pm_max": 30}, {"soutiens": [soutien]}, regles=REGLES_TEST)
	assert res["total"] == 20.0
	assert res["detail"][0]["label"] == "Soin léger"

	bel = simulateur.construire_belligerant({"type": "espece", "id": "espece:ours_test"}, get_doc)
	res_espece = potentiel.potentiel_support(bel["snapshot_reference"], bel["arsenal"],
											 regles=REGLES_TEST)
	assert res_espece["total"] == 0.0


def test_snapshot_median_est_deterministe():
	a = simulateur._snapshot_median(ESPECE_VARIABLE, PROFIL_VARIABLE)
	b = simulateur._snapshot_median(ESPECE_VARIABLE, PROFIL_VARIABLE)
	assert a["caracts_base"] == b["caracts_base"]
	# Milieu du modificateur de F : min 20 + (0+20)//2 = 30, clampé dans [20, 40].
	assert a["caracts_base"]["F"] == 30


# ── Reproductibilité Monte Carlo ─────────────────────────────────────────────────────

def test_monte_carlo_reproductible_par_seed():
	def run():
		random.seed(42)
		return simulateur.simuler_duel(
			{"type": "espece", "id": "espece:loup_test", "profil": "profil:test"},
			{"type": "espece", "id": "espece:rat_test"},
			distance=3, passes=40, get_doc_fn=get_doc)
	r1, r2 = run(), run()
	assert r1["a"]["victoires"] == r2["a"]["victoires"]
	assert r1["rounds"] == r2["rounds"]
	assert r1["a"]["pv_restants_moyens"] == r2["a"]["pv_restants_moyens"]
