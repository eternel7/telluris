# tests/test_exigence_caract.py
#
# EXIGENCE DE CARACTÉRISTIQUE d'une compétence (utils/exigence_caract.py) : seuils, normalisation,
# manques, libellé — et ses branchements : passives (`bonus_passifs`), apprenables, payload ⚡,
# simulateur ; plus le barème des passives de dev/gen_equilibrage_competences.py (fonctions pures).

import importlib.util
import os

from utils import exigence_caract as ec
from utils.competences import (bonus_passifs, competences_apprenables, exigence_remplie,
							   liste_competences_payload, normaliser_competence)

_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
	"gen_equilibrage_competences", os.path.join(_RACINE, "dev", "gen_equilibrage_competences.py"))
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


# ── Seuils ───────────────────────────────────────────────────────────────────────

def test_seuil_physique_et_mental_plafonne_au_niveau_10():
	assert ec.seuil("F", 0) == ec.BASE_PHYSIQUE
	assert ec.seuil("Ag", 5) == ec.BASE_PHYSIQUE + 5 * ec.PAS_PAR_NIVEAU
	assert ec.seuil("Int", 5) == ec.BASE_MENTALE + 5 * ec.PAS_PAR_NIVEAU
	# niv + 4 au-delà de 10 : plafonné au seuil du niv10 (jamais hors d'atteinte).
	assert ec.seuil("F", 14) == ec.seuil("F", ec.NIVEAU_MAX)
	assert ec.seuil("Vol", 10, secondaire=True) == int(ec.BASE_MENTALE + ec.PAS_PAR_NIVEAU / 2 * 10)


def test_normaliser_ignore_cles_et_valeurs_invalides():
	assert ec.normaliser(None) == {}
	assert ec.normaliser("Ag 30") == {}
	assert ec.normaliser({"Ag": "38", "Mana": 10, "F": 0, "R": "x"}) == {"Ag": 38}


def test_manquantes_satisfaite_libelle():
	comp = {"exigences": {"Ag": 38, "F": 29}}
	assert ec.manquantes(comp, {"Ag": 38, "F": 20}) == {"F": 29}
	assert ec.satisfaite(comp, {"Ag": 40, "F": 29})
	assert ec.satisfaite({"exigences": {}}, {})
	assert ec.libelle(comp["exigences"]) == "Ag 38 · F 29"
	assert ec.libelle({}) == ""


# ── Branchements ─────────────────────────────────────────────────────────────────

_MAITRE = {"_id": "competence:maitre", "type": "competence", "nom": "Maître", "vocation": "assassin",
		   "niveau": 6, "mode": "passive", "exigences": {"Ag": 50}, "effets": {"buffs": {"Ag": 5}}}
_LIBRE = {"_id": "competence:libre", "type": "competence", "nom": "Libre", "vocation": "assassin",
		  "niveau": 0, "mode": "passive", "effets": {"buffs": {"F": 1}}}
_FRAPPE = {"_id": "competence:frappe", "type": "competence", "nom": "Frappe", "vocation": "assassin",
		   "niveau": 0, "mode": "active", "cible": "soi", "exigences": {"Ag": 26},
		   "effets": {"esquive": 3, "duree": 2}}
_DOCS = {d["_id"]: d for d in (_MAITRE, _LIBRE, _FRAPPE)}


def _perso(ag, connues=None):
	return {"caracteristiques_current": {"V": 5, "F": 30, "R": 30, "Ag": ag, "Vol": 30,
										 "Int": 30, "Cha": 30, "Ch": 20},
			"currentPV": 50, "currentPM": 20, "voc": "assassin", "inventaire": [], "slots": {},
			"vocations_niveaux": {"assassin": 10},
			"competences_connues": list(connues if connues is not None else _DOCS), "effets_actifs": []}


def test_normaliser_competence_porte_les_exigences():
	assert normaliser_competence(_MAITRE)["exigences"] == {"Ag": 50}
	assert normaliser_competence(_LIBRE)["exigences"] == {}


def test_passive_inactive_tant_que_l_exigence_brute_manque():
	assert bonus_passifs(_perso(49), _DOCS.get)["buffs"] == {"F": 1}
	assert bonus_passifs(_perso(50), _DOCS.get)["buffs"] == {"F": 1, "Ag": 5}


def test_buff_temporaire_n_ouvre_pas_l_exigence():
	# Convention 3 : la caract BRUTE seule compte, un effet actif n'y change rien.
	perso = dict(_perso(40), effets_actifs=[{"source": "potion", "buffs": {"Ag": 20}, "restants": 3}])
	assert not exigence_remplie(perso, normaliser_competence(_MAITRE))


def test_pouvoir_d_objet_exempt():
	comp = normaliser_competence(_MAITRE)
	perso = _perso(10, connues=[])
	assert exigence_remplie(perso, {**comp, "accorde_par": "Anneau"})
	# Pas apprise ⇒ c'est un pouvoir d'objet : exempt…
	assert exigence_remplie(perso, comp)
	# …sauf pour la liste des apprenables, qui teste l'accès.
	assert not exigence_remplie(perso, comp, apprise=False)


def test_payload_flag_inactive_et_libelle():
	par_id = {c["competence_id"]: c for c in liste_competences_payload(
		_perso(30), _DOCS.get, "exploration", etat_charge=(0, 0))}
	assert par_id["competence:frappe"]["exigence_ok"] is True
	assert par_id["competence:frappe"]["exigence_requise"] == "Ag 26"
	assert par_id["competence:maitre"]["exigence_ok"] is False
	assert par_id["competence:libre"]["exigence_requise"] == ""
	combat = {c["competence_id"]: c for c in liste_competences_payload(
		_perso(20), _DOCS.get, "combat", etat_charge=(0, 0))}
	assert combat["competence:frappe"]["utilisable"] is False


def test_apprenables_listees_avec_l_objectif():
	perso = _perso(30, connues=[])
	out = {c["id"]: c for c in competences_apprenables(perso, lambda q: list(_DOCS.values()))}
	assert out["competence:maitre"]["exigence_ok"] is False
	assert out["competence:maitre"]["exigence_requise"] == "Ag 50"
	assert out["competence:libre"]["exigence_ok"] is True


# ── Barème des passives (générateur) ─────────────────────────────────────────────

def test_bareme_principale_et_secondaire():
	assert [gen.bareme_principale(n, True) for n in range(6)] == [2, 3, 4, 5, 5, 5]
	assert [gen.bareme_principale(n, False) for n in range(6)] == [1, 2, 3, 4, 4, 5]
	assert [gen.bareme_secondaire(n) for n in range(11)] == [0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 5]


def test_reecrire_passive_plafonne_a_5_et_ajoute_une_secondaire():
	doc = {"vocation": "guerrier", "niveau": 10, "effets": {"buffs": {"F": 16, "R": 6}}}
	assert gen.reecrire_passive(doc) == {"F": 5, "R": 5}
	seul = {"vocation": "assassin", "niveau": 9, "effets": {"buffs": {"Ag": 5}}}
	assert gen.reecrire_passive(seul) == {"Ag": 5, "F": 5}
	bas = {"vocation": "guerrier", "niveau": 0, "effets": {"buffs": {"F": 1, "R": 1}}}
	assert gen.reecrire_passive(bas) == {"F": 1, "R": 1}
	vitesse = {"vocation": "forestier", "niveau": 6, "effets": {"buffs": {"Ag": 10, "V": 1}}}
	assert gen.reecrire_passive(vitesse) == {"Ag": 5, "V": 1}


def test_formule_bornee_au_plafond_humain_de_la_source():
	doc = {"vocation": "barbare", "niveau": 7, "effets": {"buffs": {"F": "{R/12}"}}}
	assert gen.reecrire_passive(doc)["F"] == "{R/%d}" % -(-gen.PLAFOND_SOURCE["R"] // 5)


def test_esquive_plafonnee_jamais_relevee():
	assert gen.plafond_esquive({"niveau": 0, "effets": {"esquive": 10}}) == 4 * gen.bareme_principale(0, True)
	assert gen.plafond_esquive({"niveau": 2, "effets": {"esquive": 3}}) == 3
	assert gen.plafond_esquive({"niveau": 1, "effets": {"buffs": {"F": 1}}}) is None


def test_passive_au_bareme_jamais_hors_norme():
	# Les caracs d'une passive suivent le barème : seul ce qui s'y AJOUTE est mesuré.
	pure = {"mode": "passive", "niveau": 1, "effets": {"buffs": {"F": 3}}}
	assert gen.puissance(pure)[1] == 0
	esquive = {"mode": "passive", "niveau": 1, "effets": {"buffs": {"F": 3}, "esquive": 4}}
	assert gen.puissance(esquive)[1] == gen.puissance({"mode": "passive", "niveau": 1,
														"effets": {"esquive": 4}})[1] > 0
	# Aura : la part « groupe » de ses caracs compte.
	assert gen.puissance(dict(pure, zone={"forme": "cercle", "rayon": 2}))[1] > 0
