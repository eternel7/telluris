# tests/test_capacites_formules.py
#
# Quatre extensions du moteur des capacités (sorts ET compétences) :
#   · PROVOCATION — `effets.provocation` posé sur un monstre touché le force à viser son
#     provocateur (`combat._cible_joueur`, seul point de choix de cible de l'IA) ;
#   · FORMULES sur `maintien` et `incantation` — résolues au LANCEMENT par
#     `sorts.resoudre_temps`, sans jamais changer la NATURE de la capacité ;
#   · FORMULES sur `saut` et `lien_vie.part` — résolues par `sorts.resoudre_effets` ;
#   · PASSIVES À FORMULE — l'agrégat garde la formule, résolue à la LECTURE sur la caract
#     BRUTE (`consommables.competences_bonus_resolu`).
# Caracts de la fixture : F 40, R 30, Ag 40, Vol 60, Int 60, Cha 20, Ch 20.

import pytest

from utils import combat as combat_mod
from utils import consommables
from utils.combat import _cible_joueur, get_combat_grid, _run_monster_turn, resolve_action
from utils.competences import (
	bonus_passifs, synchroniser_competences_bonus, competence_utilisable_exploration,
	normaliser_competence, recompute_competences_bonus,
)
from utils.sorts import (
	SAUT_DISTANCE_MAX, _bonus_dict, capacite_utilisable_combat, est_incantation_longue,
	est_maintenu, fusionner_effets, resoudre_effets, resoudre_temps,
)
from _fixtures_magie import combat, joueur, monstre


@pytest.fixture(autouse=True)
def _des_fixes(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)


def comp(**champs):
	doc = {"_id": "competence:essai", "type": "competence", "vocation": "guerrier",
		   "nom": "Essai", "mode": "active", "cout_pm": 0, "portee": 1, **champs}
	return normaliser_competence(doc)


CARACTS = {"V": 5, "F": 40, "R": 30, "Ag": 40, "Vol": 60, "Int": 60, "Cha": 20, "Ch": 20}
DEFI = dict(cible="ennemi", portee=8, effets={"provocation": 1, "duree": 2})


# ── PROVOCATION ─────────────────────────────────────────────────────────────────

def _provocation(**garde):
	"""A au contact du loup, B loin : sans provocation, le loup vise A."""
	a = joueur(0, x=5, y=5, nom="Aldo")
	b = joueur(1, x=1, y=5, nom="Bruna", **garde)
	loup = monstre(x=6, y=5)
	doc = combat([a, b], [loup])
	doc["acteur_courant_index"] = 1
	return a, b, loup, doc


def test_sans_provocation_le_monstre_vise_le_plus_proche():
	a, b, loup, doc = _provocation()
	assert _cible_joueur(doc, loup) is a


def test_un_monstre_provoque_vise_son_provocateur():
	a, b, loup, doc = _provocation()
	res = resolve_action(doc, "competence", cible_id=loup["id"], competence=comp(**DEFI))
	assert "error" not in res
	entree = next(e for e in loup["effets_actifs"] if e.get("provocation"))
	assert entree["provocateur_id"] == b["id"] and entree["restants"] == 2
	assert _cible_joueur(doc, loup) is b


def test_le_tour_du_monstre_provoque_marche_vers_le_provocateur():
	a, b, loup, doc = _provocation()
	resolve_action(doc, "competence", cible_id=loup["id"], competence=comp(**DEFI))
	_run_monster_turn(doc, loup, get_combat_grid(doc))
	assert loup["pos"]["x"] < 5, "il quitte le contact d'Aldo pour aller chercher Bruna"
	assert a["currentPV"] == a["pv_max"]


def test_on_ne_provoque_pas_en_restant_cache():
	"""Un provocateur furtif reste la cible : provoquer, c'est se montrer."""
	a, b, loup, doc = _provocation()
	resolve_action(doc, "competence", cible_id=loup["id"], competence=comp(**DEFI))
	b["furtif"] = True
	assert _cible_joueur(doc, loup) is b


def test_provocateur_a_terre_le_monstre_reprend_son_ciblage():
	a, b, loup, doc = _provocation()
	resolve_action(doc, "competence", cible_id=loup["id"], competence=comp(**DEFI))
	b["currentPV"] = 0
	assert _cible_joueur(doc, loup) is a


def test_une_provocation_ratee_ne_pose_rien():
	a, b, loup, doc = _provocation(cc=0)
	resolve_action(doc, "competence", cible_id=loup["id"], competence=comp(**DEFI))
	assert not any(e.get("provocation") for e in loup.get("effets_actifs") or [])
	assert _cible_joueur(doc, loup) is a


def _engage():
	"""Bruna au contact d'un loup, un second loup à 4 cases : elle est ENGAGÉE."""
	b = joueur(0, x=3, y=5, nom="Bruna")
	contact, loin = monstre(0, x=4, y=5), monstre(1, x=7, y=5)
	return b, contact, loin, combat([b], [contact, loin])


def test_une_provocation_pure_se_lance_a_distance_meme_engage():
	b, contact, loin, doc = _engage()
	res = resolve_action(doc, "competence", cible_id=loin["id"],
						 competence=comp(cible="ennemi", portee=5, effets={"provocation": 1, "duree": 2}))
	assert "error" not in res, res
	assert _cible_joueur(doc, loin) is b


def test_une_provocation_qui_blesse_reste_interdite_engage():
	"""Sinon toute frappe à distance contournerait l'engagement en portant une provocation."""
	b, contact, loin, doc = _engage()
	res = resolve_action(doc, "competence", cible_id=loin["id"], competence=comp(
		cible="ennemi", jet="magique", portee=5,
		effets={"degats": "1D6", "provocation": 1, "duree": 2}))
	assert "corps à corps" in res.get("error", "")


def test_une_provocation_pure_exige_la_ligne_de_vue():
	b, contact, loin, doc = _engage()
	for y in range(9):
		doc["grid"]["cells"][y][5] = 0
	res = resolve_action(doc, "competence", cible_id=loin["id"],
						 competence=comp(cible="ennemi", portee=5, effets={"provocation": 1, "duree": 2}))
	assert res.get("error") == "Ligne de vue obstruée."


def test_la_provocation_est_un_debuff_a_duree():
	"""Part à durée (`part_durative`) : une provocation PURE est lançable, et sans durée
	elle n'aurait rien à poser."""
	assert capacite_utilisable_combat(comp(**DEFI))
	assert not capacite_utilisable_combat(comp(cible="ennemi", effets={"provocation": 1}))


# ── SAUT et LIEN DE VIE à formule ───────────────────────────────────────────────

def test_saut_a_formule_resolu_sur_le_lanceur():
	competence = comp(cible="soi", effets={"saut": "1+{Int/20}"})   # Int 60 ⇒ 4
	assert capacite_utilisable_combat(competence)
	assert not competence_utilisable_exploration(competence)
	perso = joueur(x=3, y=5)
	doc = combat([perso], [monstre(x=10, y=8)])
	assert "error" in resolve_action(doc, "competence", dx=8, dy=5, competence=competence)
	assert "error" not in resolve_action(doc, "competence", dx=7, dy=5, competence=competence)
	assert perso["pos"] == {"x": 7, "y": 5}


def test_saut_a_formule_borne_par_le_moteur():
	eff = resoudre_effets(_bonus_dict({"saut": "{Int}"}), CARACTS)
	assert eff["saut"] == SAUT_DISTANCE_MAX


def test_part_du_lien_de_vie_a_formule():
	protecteur = joueur(0, x=3, y=5, nom="Paladin")
	protege = joueur(1, x=4, y=5, nom="Écuyer")
	doc = combat([protecteur, protege], [monstre(x=9, y=5)])
	res = resolve_action(doc, "competence", cible_id="joueur_1", competence=comp(
		cible="allie", portee=4, effets={"lien_vie": {"part": "20+{Vol/2}", "reduction": 10}}))
	assert "error" not in res
	assert (protege["lien_vie"]["part"], protege["lien_vie"]["reduction"]) == (50, 10)


def test_part_du_lien_resolue_a_zero_le_lien_n_existe_pas():
	eff = resoudre_effets(_bonus_dict({"lien_vie": {"part": "{Cha/100}"}}), CARACTS)
	assert eff["lien_vie"] is None


def test_un_lien_de_composant_ecrase_aussi_la_part_formulee():
	base = _bonus_dict({"lien_vie": {"part": "20+{Vol/2}"}})
	fusion = fusionner_effets(base, [_bonus_dict({"lien_vie": {"part": 30}})])
	assert resoudre_effets(fusion, CARACTS)["lien_vie"]["part"] == 30


# ── MAINTIEN et INCANTATION à formule ───────────────────────────────────────────

def test_maintien_formule_reste_maintenu_quel_que_soit_le_lanceur():
	"""La nature de la capacité ne dépend pas de qui la lance : part constante planchée à 1."""
	competence = comp(cible="soi", maintien="{Vol/100}", effets={"buffs": {"R": 5}})
	assert est_maintenu(competence)
	assert resoudre_temps(competence, {"Vol": 0})["maintien"] == 1


def test_maintien_formule_resolu_au_lancement():
	perso = joueur(x=3, y=5, pm=60)
	doc = combat([perso], [monstre(x=10, y=8)])
	resolve_action(doc, "competence", competence=comp(
		cible="soi", cout_pm=5, maintien="6-{Vol/20}", effets={"buffs": {"R": 5}}))
	assert perso["concentrations"][0]["maintien"] == 3      # 6 − 60/20


def test_reduction_de_composant_rejouee_sur_le_maintien_resolu():
	competence = comp(cible="soi", maintien="2+{Vol/10}", effets={"buffs": {"R": 5}})
	assert resoudre_temps(competence, CARACTS, {"maintien_reduction": 3})["maintien"] == 5
	assert resoudre_temps(competence, CARACTS, {"maintien_reduction": 30})["maintien"] == 1


def test_incantation_formulee_est_longue_tant_qu_elle_n_est_pas_resolue():
	competence = comp(cible="ennemi", incantation="4-{Int/30}", effets={"degats": "1D6"})
	assert est_incantation_longue(competence)
	assert not est_incantation_longue(resoudre_temps(competence, {"Int": 90}))
	assert resoudre_temps(competence, CARACTS)["incantation"] == 2


def test_incantation_formulee_s_arme_sur_la_valeur_du_lanceur():
	archer = joueur(0, x=3, y=5, pm=60)
	second = joueur(1, x=3, y=6)
	doc = combat([archer, second], [monstre(x=8, y=5)])
	res = resolve_action(doc, "competence", cible_id="monstre_0", competence=comp(
		cible="ennemi", portee=8, cout_pm=12, incantation="12-{Int/20}", effets={"degats": "2D8"}))
	assert res["incantation"]["pa_total"] == 9                  # 12 − 60/20


# ── PASSIVES À FORMULE ──────────────────────────────────────────────────────────

PASSIVE = {"_id": "competence:nerfs", "type": "competence", "vocation": "guerrier",
		   "nom": "Nerfs d'acier", "icon": "🧠", "mode": "passive",
		   "effets": {"buffs": {"R": "{Vol/10}", "F": 2}, "esquive": "{Ag/20}"}}


def _perso_passif(vol=60):
	perso = {"voc": "guerrier", "competences_connues": ["competence:nerfs"],
			 "caracteristiques_current": dict(CARACTS, Vol=vol), "effets_actifs": []}
	recompute_competences_bonus(perso, lambda i: PASSIVE if i == PASSIVE["_id"] else None)
	return perso


def test_l_agregat_garde_la_formule_pas_sa_valeur():
	bonus = bonus_passifs(_perso_passif(), lambda i: PASSIVE)
	assert bonus["buffs"] == {"F": 2}
	assert bonus["formules"] == {"buffs": {"R": "{Vol/10}"}, "esquive": "{Ag/20}"}


def test_la_passive_suit_la_caracteristique_sans_recalcul():
	perso = _perso_passif(vol=60)
	assert consommables.caracts_avec_buffs(perso)["R"] == 30 + 6
	perso["caracteristiques_current"]["Vol"] = 80             # montée d'XP, agrégat intact
	assert consommables.caracts_avec_buffs(perso)["R"] == 30 + 8
	assert consommables.esquive_bonus(perso) == 2


def test_la_passive_lit_la_caracteristique_BRUTE():
	"""Une potion de Vol ne gonfle pas la passive (CLAUDE.md §3, et pas de boucle)."""
	perso = _perso_passif(vol=60)
	perso["effets_actifs"] = [{"source_id": "potion", "buffs": {"Vol": 40}, "restants": 3}]
	assert consommables.caracts_avec_buffs(perso)["R"] == 30 + 6


def test_l_infobulle_nomme_la_valeur_resolue():
	detail = consommables.competences_bonus_resolu(_perso_passif())
	assert detail["buffs_sources"][0]["buffs"] == {"F": 2, "R": 6}


def test_un_agregat_sans_formules_est_resynchronise():
	perso = _perso_passif()
	get_doc = lambda i: PASSIVE if i == PASSIVE["_id"] else None
	assert not synchroniser_competences_bonus(perso, get_doc)
	del perso["competences_bonus"]["formules"]
	assert synchroniser_competences_bonus(perso, get_doc)
	assert perso["competences_bonus"]["formules"] == {"buffs": {"R": "{Vol/10}"}, "esquive": "{Ag/20}"}
