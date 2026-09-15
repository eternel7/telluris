# tests/test_sorts_temps.py
#
# LES TROIS NOTIONS DU TEMPS MAGIQUE, au niveau de la DONNÉE (utils/sorts.py, pur) :
#   `incantation` → PA de lancement · `cout_pm` → PM de lancement · `maintien` → PM/round.
# Plus les six clés d'effet qui les accompagnent (degats_pm, cout_pv, drain_*, saut,
# lien_vie) et les deux portes d'éligibilité qui doivent les laisser passer.
#
# Ce que ce fichier verrouille avant tout : la LISTE BLANCHE de `normaliser_sort`. Trois
# fois déjà (animation, zone, invocation) un champ ajouté au doc n'a jamais atteint le
# moteur faute d'y figurer — sans erreur, sans trace.

import pytest

from models import character_stats
from utils.competences import (
	competence_utilisable_combat, competence_utilisable_exploration, normaliser_competence,
)
from utils.sorts import (
	INCANTATION_PA_DEFAUT, INCANTATION_PA_MAX, MAINTIEN_PM_MAX, SAUT_DISTANCE_MAX,
	est_incantation_longue, est_maintenu, fusionner_effets, liste_sorts_payload,
	normaliser_sort, pm_par_pa, seuil_concentration, sort_utilisable_combat,
	sort_utilisable_exploration,
)


def _sort(**champs):
	doc = {"_id": "sort:essai", "type": "sort", "vocation": "mage", "nom": "Essai",
		   "cout_pm": 10, "cible": "soi", "effets": {}}
	doc.update(champs)
	return normaliser_sort(doc)


# ── Liste blanche : les deux champs neufs atteignent bien le moteur ──────────────

def test_incantation_et_maintien_traversent_la_normalisation():
	s = _sort(incantation=6, maintien=3)
	assert s["incantation"] == 6
	assert s["maintien"] == 3


def test_champs_absents_valent_le_comportement_d_avant():
	"""Aucune migration : un doc déjà en base se lance instantanément et gratuitement."""
	s = _sort()
	assert s["incantation"] == INCANTATION_PA_DEFAUT == 1
	assert s["maintien"] == 0
	assert not est_incantation_longue(s)
	assert not est_maintenu(s)


@pytest.mark.parametrize("brut, attendu", [
	(0, 1), (-5, 1), (1, 1), (99, INCANTATION_PA_MAX),
])
def test_incantation_bornee_et_planchee_a_un(brut, attendu):
	"""Plancher à 1 : 0 PA n'a aucun sens et ferait diviser par zéro `pm_par_pa`."""
	assert _sort(incantation=brut)["incantation"] == attendu


def test_maintien_borne():
	assert _sort(maintien=999)["maintien"] == MAINTIEN_PM_MAX
	assert _sort(maintien=-4)["maintien"] == 0


# ── Les six clés d'effet neuves ─────────────────────────────────────────────────

def test_les_six_cles_d_effet_sont_normalisees():
	eff = _sort(effets={"degats_pm": " 2D6 ", "cout_pv": 10, "drain_pv": 50,
						"drain_pm": 25, "drain_max": 12, "saut": 4,
						"lien_vie": {"part": 50, "reduction": 20}})["effets"]
	assert eff["degats_pm"] == "2D6"
	assert eff["cout_pv"] == 10
	assert (eff["drain_pv"], eff["drain_pm"], eff["drain_max"]) == (50, 25, 12)
	assert eff["saut"] == 4
	assert eff["lien_vie"] == {"part": 50, "reduction": 20}


def test_les_six_cles_ont_un_defaut_neutre():
	eff = _sort()["effets"]
	assert eff["degats_pm"] == ""
	assert eff["cout_pv"] == eff["drain_pv"] == eff["drain_pm"] == 0
	assert eff["drain_max"] == eff["saut"] == 0
	assert eff["lien_vie"] is None


def test_drain_et_saut_sont_bornes():
	eff = _sort(effets={"drain_pv": 500, "drain_pm": 300, "saut": 99})["effets"]
	assert eff["drain_pv"] == eff["drain_pm"] == 100
	assert eff["saut"] == SAUT_DISTANCE_MAX


def test_lien_vie_sans_part_est_ignore():
	"""Un lien à 0 % serait inerte tout en se faisant payer chaque round."""
	assert _sort(effets={"lien_vie": {"part": 0, "reduction": 80}})["effets"]["lien_vie"] is None


def test_composants_additionnent_les_cles_neuves_mais_pas_le_lien():
	"""⚠️ `lien_vie` est ÉCRASÉ, jamais fusionné : deux `part` additionnés dépasseraient
	100 % et transféreraient plus que le coup reçu."""
	base = _sort(effets={"drain_pv": 40, "degats_pm": "1D6",
						 "lien_vie": {"part": 30, "reduction": 0}})["effets"]
	bonus = _sort(effets={"drain_pv": 30, "degats_pm": "1D4",
						  "lien_vie": {"part": 50, "reduction": 10}})["effets"]
	out = fusionner_effets(base, [bonus])
	assert out["drain_pv"] == 70
	assert out["degats_pm"] == "1D6+1D4"
	assert out["lien_vie"] == {"part": 50, "reduction": 10}


def test_le_drain_fusionne_reste_borne_a_cent_pour_cent():
	base = _sort(effets={"drain_pv": 60})["effets"]
	bonus = _sort(effets={"drain_pv": 60})["effets"]
	assert fusionner_effets(base, [bonus])["drain_pv"] == 100


# ── `pm_par_pa` : l'exemple du livre de règles, à la virgule ─────────────────────

def test_tranche_de_pm_par_pa_exemple_du_meteore():
	"""15 PM en 6 PA ⇒ 3 PM par PA (arrondi AU SUPÉRIEUR)."""
	assert pm_par_pa(_sort(cout_pm=15, incantation=6)) == 3


@pytest.mark.parametrize("cout_pm, incantation, attendu", [
	(15, 6, 3),   # l'exemple du livre de règles
	(10, 3, 4),   # 3,33 → 4 : l'arrondi joue en défaveur du lanceur
	(8, 2, 4),    # division exacte
	(1, 1, 1),    # sort ordinaire : la tranche EST le coût
	(1, 4, 1),    # coût minuscule étalé : jamais 0, sinon le sort serait gratuit
])
def test_tranche_de_pm_arrondie_au_superieur(cout_pm, incantation, attendu):
	assert pm_par_pa(_sort(cout_pm=cout_pm, incantation=incantation)) == attendu


def test_tranche_ne_divise_jamais_par_zero():
	assert pm_par_pa({"cout_pm": 9, "incantation": 0}) == 9
	assert pm_par_pa({}) == 0


# ── Seuil de concentration ──────────────────────────────────────────────────────

def test_seuil_de_concentration_monte_avec_la_volonte_et_descend_avec_le_coup():
	assert seuil_concentration(60, 0) > seuil_concentration(20, 0)
	assert seuil_concentration(60, 30) < seuil_concentration(60, 0)


def test_seuil_de_concentration_clampe_comme_les_deux_autres_seuils():
	"""[5, 95] : aucun mage n'est incassable, aucun coup n'interrompt à coup sûr."""
	assert seuil_concentration(10_000, 0) == 95
	assert seuil_concentration(0, 10_000) == 5


def test_seuil_de_concentration_suit_la_variable_de_monde(monkeypatch):
	monkeypatch.setattr(character_stats, "CONCENTRATION_VOL_DIV", 1)
	large = seuil_concentration(60, 0)
	monkeypatch.setattr(character_stats, "CONCENTRATION_VOL_DIV", 4)
	assert seuil_concentration(60, 0) < large


def test_diviseur_nul_ne_casse_pas(monkeypatch):
	monkeypatch.setattr(character_stats, "CONCENTRATION_VOL_DIV", 0)
	assert seuil_concentration(60, 0) == 95


# ── Éligibilité : les deux portes JUMELLES ──────────────────────────────────────

@pytest.mark.parametrize("champs", [
	{"maintien": 4, "effets": {"buffs": {"R": 10}}},        # entretien sans `duree`
	{"effets": {"saut": 4}},                                 # tout l'effet est une case
	{"cible": "allie", "effets": {"lien_vie": {"part": 50}}},  # effet sur un AUTRE corps
	{"cible": "ennemi", "effets": {"degats_pm": "2D6"}},     # siphonie pure
])
def test_les_capacites_sans_effet_pose_restent_lancables_en_combat(champs):
	"""Sans ces quatre exceptions, `sort_utilisable_combat` les refuserait comme « sans
	effet » — un sort accepté par le router puis inerte dans le moteur."""
	assert sort_utilisable_combat(_sort(**champs))


def test_un_sort_vraiment_sans_effet_reste_refuse():
	assert not sort_utilisable_combat(_sort(effets={}))


@pytest.mark.parametrize("champs", [
	{"incantation": 4, "effets": {"pv": 10}},
	{"maintien": 3, "effets": {"pv": 10}},
	{"effets": {"saut": 4, "pv": 10}},
	{"cible": "allie", "effets": {"lien_vie": {"part": 50}, "pv": 10}},
])
def test_les_mecaniques_de_round_et_de_grille_sont_refusees_hors_combat(champs):
	"""Il n'y a NI round NI grille en exploration : rien à quoi rattacher un PA reporté,
	un prélèvement par tour, une case d'arrivée ou un coup à rediriger."""
	assert not sort_utilisable_exploration(_sort(**champs))


def test_le_cout_en_pv_reste_applicable_hors_combat():
	"""`cout_pv` n'est qu'un COÛT, pas une règle de tour."""
	assert sort_utilisable_exploration(_sort(effets={"cout_pv": 10, "pv": 5}))


def test_un_sort_ordinaire_reste_lancable_hors_combat():
	assert sort_utilisable_exploration(_sort(effets={"pv": 10}))


# ── Miroir des compétences ──────────────────────────────────────────────────────

def _comp(**champs):
	doc = {"_id": "competence:essai", "type": "competence", "vocation": "guerrier",
		   "nom": "Essai", "mode": "active", "cout_pm": 0, "cible": "soi", "effets": {}}
	doc.update(champs)
	return normaliser_competence(doc)


def test_les_competences_portent_l_entretien():
	assert _comp(maintien=2)["maintien"] == 2
	assert _comp()["maintien"] == 0
	assert _comp(maintien=999)["maintien"] == MAINTIEN_PM_MAX


def test_les_competences_ne_portent_PAS_l_incantation():
	"""⚠️ DÉLIBÉRÉ : la canalisation multi-round n'a qu'un chemin de résolution
	(`_avancer_incantation` → `_lancer_sort`), propre aux sorts. Normaliser le champ sans
	le brancher afficherait « ⏱ 4 PA » sur une compétence qui partirait quand même du
	premier coup — un champ qui ment est pire qu'un champ absent."""
	assert "incantation" not in _comp(incantation=4)


def test_les_deux_portes_des_competences_suivent_celles_des_sorts():
	assert competence_utilisable_combat(_comp(maintien=2, effets={"buffs": {"F": 10}}))
	assert competence_utilisable_combat(_comp(effets={"degats_pm": "2D6"}))
	assert not competence_utilisable_exploration(_comp(maintien=2, effets={"pv": 5}))
	assert not competence_utilisable_exploration(_comp(effets={"saut": 3, "pv": 5}))


# ── Payload : le client doit VOIR la facture avant de cliquer ────────────────────

def test_le_payload_publie_les_trois_notions():
	doc = {"_id": "sort:mur", "type": "sort", "vocation": "mage", "nom": "Mur de feu",
		   "cout_pm": 5, "incantation": 2, "maintien": 3, "cible": "ennemi",
		   "effets": {"degats": "2D6"}}
	char = {"sorts_connus": ["sort:mur"], "inventaire": [], "slots": {}}
	payload = liste_sorts_payload(char, lambda i: doc if i == "sort:mur" else None, "combat")
	assert len(payload) == 1
	assert payload[0]["cout_pm"] == 5
	assert payload[0]["incantation"] == 2
	assert payload[0]["maintien"] == 3
