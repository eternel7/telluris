# tests/test_potentiel_magie.py
# MAGIE dans le potentiel d'une espèce (`potentiel.offense_magique`, `valeur_sort_monstre`) :
# un spécimen tire `k` sorts parmi ceux que son IA sait lancer et en lance un par round ;
# son offense est l'ESPÉRANCE, sur le tirage, du meilleur round possible — sort + actions
# restantes à l'arme, jamais moins que l'arme seule. Le rang, l'XP et les planchers de quête
# lisent tous `potentiel_menace`, donc ce calcul.

import math

import pytest

from utils import characters, combat, potentiel, simulateur
from utils.sorts import normaliser_sort


def _attrs(**kw):
	base = {"V": 4, "F": 30, "R": 40, "Ag": 30, "Vol": 60, "Int": 60, "Cha": 10, "Ch": 10}
	base.update(kw)
	return {c: {"min": v, "max": v} for c, v in base.items()}


TRAIT = {"_id": "sort:trait_pm", "type": "sort", "nom": "Trait", "magie": "Nécromancie",
		 "niveau": 1, "cout_pm": 5, "cible": "ennemi", "portee": 6, "effets": {"degats": "3D6"}}
FOUDRE = dict(TRAIT, _id="sort:foudre_pm", nom="Foudre", effets={"degats": "6D6"})
RITUEL = dict(TRAIT, _id="sort:rituel_pm", nom="Rituel", incantation=12, effets={"degats": "6D6"})
RUINE = dict(TRAIT, _id="sort:ruine_pm", nom="Ruine", cout_pm=10_000, effets={"degats": "20D6"})
LOUP = {"_id": "espece:loup_pm", "type": "espece", "nom": "Loup", "tags": ["monstre"],
		"base_attributes": _attrs(F=40, Vol=0, Int=0)}
APPEL = {"_id": "sort:appel_pm", "type": "sort", "nom": "Appel", "magie": "Nature", "niveau": 1,
		 "cout_pm": 5, "cible": "soi", "effets": {},
		 "invocation": {"espece": LOUP["_id"], "nombre": 2, "duree": 2}}


def _mage(eid, sorts):
	return {"_id": eid, "type": "espece", "nom": "Mage", "tags": ["monstre"],
			"sorts": list(sorts), "base_attributes": _attrs()}


SANS = {"_id": "espece:sans_pm", "type": "espece", "nom": "Brute", "tags": ["monstre"],
		"base_attributes": _attrs()}
PROFIL_1 = {"_id": "profil:un_pm", "type": "profil", "nom": "Un", "niveau": 1, "attributs_modifier": {}}
PROFIL_2 = dict(PROFIL_1, _id="profil:deux_pm", nom="Deux", niveau=2)
DOCS = {d["_id"]: d for d in (TRAIT, FOUDRE, RITUEL, RUINE, LOUP, APPEL, SANS, PROFIL_1, PROFIL_2)}


@pytest.fixture(autouse=True)
def db(monkeypatch):
	monkeypatch.setattr(characters, "get_doc", DOCS.get)
	monkeypatch.setattr(combat, "get_doc", DOCS.get)
	monkeypatch.setattr(combat, "find_docs", lambda *a, **k: [])


def _reference(espece):
	DOCS[espece["_id"]] = espece
	bel = simulateur.construire_belligerant({"type": "espece", "id": espece["_id"]}, DOCS.get)
	snap = bel["snapshot_reference"]
	return snap, potentiel.potentiel_combat(snap, bel["arsenal"])


def test_sans_sort_tirable_l_offense_reste_celle_de_l_arme():
	snap, pc = _reference(SANS)
	m = potentiel.offense_magique(snap, pc["offense"], SANS, PROFIL_2, DOCS.get)
	assert m == {"offense": pc["offense"], "pool": 0, "tires": 0}


def test_esperance_exacte_du_meilleur_sort_tire():
	espece = _mage("espece:mage_pm", [TRAIT["_id"], FOUDRE["_id"]])
	snap, pc = _reference(espece)
	arme, actions = pc["offense"], snap["actions_max"]

	def round_avec(sort):
		v, prises = potentiel.valeur_sort_monstre(snap, sort, DOCS.get)
		return max(arme, v + arme / actions * max(0, actions - prises))

	r_trait, r_foudre = round_avec(TRAIT), round_avec(FOUDRE)
	assert r_foudre > r_trait > arme
	# Un sort tiré sur deux : la moyenne des deux rounds ; deux tirés : toujours le meilleur.
	un = potentiel.offense_magique(snap, arme, espece, PROFIL_1, DOCS.get)
	deux = potentiel.offense_magique(snap, arme, espece, PROFIL_2, DOCS.get)
	assert (un["pool"], un["tires"], deux["tires"]) == (2, 1, 2)
	assert math.isclose(un["offense"], (r_trait + r_foudre) / 2)
	assert math.isclose(deux["offense"], r_foudre)


def test_un_sort_hors_de_portee_de_ses_pm_ne_vaut_rien():
	snap, _ = _reference(_mage("espece:pauvre_pm", [RUINE["_id"]]))
	assert potentiel.valeur_sort_monstre(snap, normaliser_sort(RUINE), DOCS.get)[0] == 0


def test_une_incantation_longue_compte_pour_ses_rounds():
	snap, _ = _reference(_mage("espece:rituel_pm", [RITUEL["_id"]]))
	foudre, _ = potentiel.valeur_sort_monstre(snap, normaliser_sort(FOUDRE), DOCS.get)
	rituel, prises = potentiel.valeur_sort_monstre(snap, normaliser_sort(RITUEL), DOCS.get)
	rounds = math.ceil(RITUEL["incantation"] / snap["actions_max"])
	assert rounds > 1 and prises == snap["actions_max"]
	assert math.isclose(rituel, foudre / rounds)


def test_une_invocation_vaut_la_frappe_de_ses_creatures():
	snap, _ = _reference(_mage("espece:druide_pm", [APPEL["_id"]]))
	_, pc_loup = _reference(LOUP)
	valeur, prises = potentiel.valeur_sort_monstre(snap, normaliser_sort(APPEL), DOCS.get)
	horizon = potentiel.REGLES_POTENTIEL["tours_reference"]
	inv = APPEL["invocation"]
	assert prises == 1
	assert math.isclose(valeur, pc_loup["offense"] * inv["nombre"] * min(horizon, inv["duree"]) / horizon)


def test_la_magie_releve_le_potentiel_d_une_espece():
	brute = potentiel.potentiel_espece(SANS["_id"], PROFIL_2["_id"], DOCS.get)
	mage = _mage("espece:mage2_pm", [FOUDRE["_id"]])
	DOCS[mage["_id"]] = mage
	pe = potentiel.potentiel_espece(mage["_id"], PROFIL_2["_id"], DOCS.get)
	assert pe["magie"]["offense"] > pe["magie"]["offense_arme"]
	assert pe["total"] > brute["total"]


def test_la_magie_ne_mange_pas_le_gain_de_l_equipement():
	"""Les gains d'équipement se mesurent contre le nu SANS magie : sinon un mage dont la
	magie dépasse ce qu'apporte une arme verrait son équipement compter pour rien."""
	arme = {"_id": "item:baton_pm", "type": "item", "nom": "Bâton", "categorie": "arme",
			"slots": ["main_droite"], "portee": 1, "bonus_degats": 6}
	nu = dict(_mage("espece:mage_nu_pm", [FOUDRE["_id"]]), tags=["monstre", "humanoide"])
	arme_e = dict(nu, _id="espece:mage_arme_pm", items=[arme["_id"]])
	for d in (arme, nu, arme_e):
		DOCS[d["_id"]] = d
	pe_nu = potentiel.potentiel_espece(nu["_id"], PROFIL_2["_id"], DOCS.get)
	pe_arme = potentiel.potentiel_espece(arme_e["_id"], PROFIL_2["_id"], DOCS.get)
	bel = simulateur.construire_belligerant({"type": "espece", "id": arme_e["_id"]}, DOCS.get)
	snap = bel["snapshot_reference"]
	sans = potentiel.potentiel_combat(snap, bel["arsenal"])["total"]
	equipe = potentiel.potentiel_combat(
		simulateur._equiper_snapshot(snap, {"main_droite": arme["_id"]}), bel["arsenal"])["total"]
	assert equipe > sans
	assert pe_arme["equipement"] > 0 and pe_arme["nu"] == pe_nu["nu"]
