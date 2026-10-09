# tests/test_vol.py
#
# VOL MAGIQUE (`effets.vol`, utils/vol.py) : un effet à durée qui fait léviter son porteur.
#   • combat      : franchit les falaises (3), MÊME sous couvert (lévitation, pas d'ailes) ;
#   • exploration : la règle de case passe de `=== 1` à `>= 1` (client : `accesExploration`) ;
#   • fin du vol au-dessus d'une case interdite à pied ⇒ CHUTE sur la case sûre la plus
#     proche, UN DÉ PAR CASE parcourue : D20 depuis une falaise, D6 dans l'eau (règle de
#     l'Auteur) — jamais mortelle hors combat.

import json
import os

import pytest

from utils import combat as combat_mod
from utils import sorts as sorts_util
from utils import vol as vol_util
from utils.combat import (
	TERRAIN_FALAISE, _appliquer_couvert, _can_fly, _empiler_effet_combat, _rompre_concentration,
	_tick_effets_combat, build_joueur_snapshot, resolve_action,
)
from _fixtures_magie import character, combat, joueur, monstre, sort, textes

RACINE = os.path.join(os.path.dirname(__file__), "..")
CONTENU = os.path.join(RACINE, "jsons", "sort_vol_a_importer.json")


@pytest.fixture(autouse=True)
def _des_fixes(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)


def _des(valeur, notations=None):
	"""`des_fn` / `roll_dice` déterministe : toute notation vaut `valeur` ; `notations`, si
	fournie, reçoit chaque notation tirée — on affirme sur le DÉ, pas seulement le total."""
	def tirer(notation):
		if notations is not None:
			notations.append(notation)
		return valeur
	return tirer


def _vol(duree=3, **champs):
	return sort(cout_pm=5, nom="Voile d'Icare", icon="🪽", effets={"vol": 1, "duree": duree},
				**champs)


# ── Schéma des effets ───────────────────────────────────────────────────────────

def test_vol_est_une_cle_normalisee_bornee_a_1():
	assert sorts_util._bonus_dict({"vol": 3})["vol"] == 1
	assert sorts_util._bonus_dict({})["vol"] == 0


def test_vol_est_une_part_a_duree():
	"""Un vol pur (aucun buff) est lançable : sans quoi le sort serait refusé « sans effet »."""
	assert sorts_util.part_durative({"vol": 1, "duree": 2})
	assert not sorts_util.part_durative({"vol": 1, "duree": 0})
	doc = sorts_util.normaliser_sort({"_id": "sort:v", "type": "sort", "nom": "V", "cout_pm": 5,
									  "cible": "soi", "effets": {"vol": 1, "duree": 2}})
	assert sorts_util.capacite_utilisable_combat(doc)
	assert sorts_util.capacite_utilisable_exploration(doc)


def test_un_composant_peut_donner_le_vol_sans_le_cumuler():
	fus = sorts_util.fusionner_effets({"vol": 1, "duree": 2}, [{"vol": 1, "duree": 1}])
	assert fus["vol"] == 1 and fus["duree"] == 3
	assert sorts_util.fusionner_effets({"duree": 2}, [{"vol": 1}])["vol"] == 1


def test_l_entree_d_exploration_porte_le_vol():
	perso = character()
	sorts_util.empiler_effet_sort(perso, {"id": "sort:v", "nom": "V"}, {"vol": 1, "duree": 2})
	assert vol_util.vol_actif(perso)
	sans = character()
	sorts_util.empiler_effet_sort(sans, {"id": "sort:b", "nom": "B"}, {"buffs": {"F": 5}, "duree": 2})
	assert not vol_util.vol_actif(sans)
	assert "vol" not in sans["effets_actifs"][0], "aucune clé neuve sur une entrée ordinaire"


# ── Case d'atterrissage ─────────────────────────────────────────────────────────

def test_case_la_plus_proche_premier_anneau_puis_vol_d_oiseau():
	ok = {(5, 3), (4, 4)}                     # (4,4) : diagonale ; (5,3) : orthogonale
	assert vol_util.case_la_plus_proche(4, 3, 10, 10, lambda x, y: (x, y) in ok) == (5, 3)


def test_case_la_plus_proche_deterministe_entre_ex_aequo():
	"""Même distance des deux côtés : (y, x) départage — même chute, même atterrissage."""
	ok = {(3, 3), (5, 3)}
	assert vol_util.case_la_plus_proche(4, 3, 10, 10, lambda x, y: (x, y) in ok) == (3, 3)


def test_case_la_plus_proche_none_sans_candidate():
	assert vol_util.case_la_plus_proche(1, 1, 3, 3, lambda x, y: False) is None


# ── Dés de chute : un dé par case, D20 falaise, D6 eau ──────────────────────────

def test_notation_chute_un_de_par_case_selon_le_terrain():
	assert vol_util.notation_chute(vol_util.TERRAIN_FALAISE, 3) == "3D20"
	assert vol_util.notation_chute(vol_util.TERRAIN_EAU, 2) == "2D6"
	assert vol_util.notation_chute(2, 1) == f"1D{vol_util.CHUTE_FACES_DEFAUT}"
	assert vol_util.notation_chute(vol_util.TERRAIN_EAU, 0) == "1D6", "au moins un dé"


# ── Exploration : chute ─────────────────────────────────────────────────────────

def _lieu_riviere():
	"""5×3, une rivière (5) en colonne 2."""
	return {"cells": [[1, 1, 5, 1, 1] for _ in range(3)]}


def test_chute_exploration_pose_sur_le_sol_et_blesse():
	perso = character(position={"x": 2, "y": 1}, currentPV=20)
	notations = []
	chute = vol_util.chute_exploration(perso, _lieu_riviere(), des_fn=_des(4, notations))
	assert chute == {"degats": 4, "notation": "1D6", "eau": True,
					 "de": {"x": 2, "y": 1}, "vers": {"x": 1, "y": 1}}
	assert notations == ["1D6"]
	assert perso["position"] == {"x": 1, "y": 1}
	assert perso["currentPV"] == 16


def test_chute_dans_l_eau_un_d6_par_case_jusqu_a_la_terre_ferme():
	lac = {"cells": [[1, 5, 5, 5, 5, 5, 1]]}      # milieu du lac : 3 cases de chaque rive
	perso = character(position={"x": 3, "y": 0}, currentPV=50)
	notations = []
	chute = vol_util.chute_exploration(perso, lac, des_fn=_des(7, notations))
	assert notations == ["3D6"] and chute["eau"] and perso["currentPV"] == 43


def test_chute_d_une_falaise_en_exploration_un_d20_par_case():
	gorge = {"cells": [[1, 3, 3, 1]]}
	perso = character(position={"x": 1, "y": 0}, currentPV=50)
	notations = []
	chute = vol_util.chute_exploration(perso, gorge, des_fn=_des(12, notations))
	assert notations == ["1D20"] and not chute["eau"] and perso["currentPV"] == 38


def test_chute_exploration_ne_tue_jamais():
	perso = character(position={"x": 2, "y": 1}, currentPV=3)
	chute = vol_util.chute_exploration(perso, _lieu_riviere(), des_fn=_des(6))
	assert perso["currentPV"] == 1 and chute["degats"] == 2


def test_pas_de_chute_en_vol_ni_sur_le_sol_ni_sans_grille():
	en_vol = character(position={"x": 2, "y": 1},
					   effets_actifs=[{"sort_id": "sort:v", "vol": 1, "restants": 2}])
	assert vol_util.chute_exploration(en_vol, _lieu_riviere(), des_fn=_des(4)) is None
	au_sol = character(position={"x": 0, "y": 1})
	assert vol_util.chute_exploration(au_sol, _lieu_riviere(), des_fn=_des(4)) is None
	assert vol_util.chute_exploration(character(position={"x": 2, "y": 1}), {},
									  des_fn=_des(4)) is None


# ── Combat ─────────────────────────────────────────────────────────────────────

def _falaise_en(doc, x, y):
	doc["grid"]["cells"][y][x] = TERRAIN_FALAISE


def test_lancer_le_vol_ouvre_la_falaise():
	mage = joueur(x=3, y=5)
	doc = combat([mage], [monstre(x=10, y=8)])
	_falaise_en(doc, 4, 5)
	assert resolve_action(doc, "deplacer", dx=1, dy=0).get("error")
	assert not resolve_action(doc, "sort", sort=_vol()).get("error")
	assert mage.get("vol_magique") is True and _can_fly(mage)
	assert not resolve_action(doc, "deplacer", dx=1, dy=0).get("error")
	assert mage["pos"] == {"x": 4, "y": 5}


def test_la_levitation_ignore_le_couvert():
	"""⚠️ Choix de l'Auteur : un mage qui lévite n'a pas d'ailes à replier."""
	mage = joueur()
	_empiler_effet_combat(mage, {"_id": "sort:v", "nom": "V"}, {"vol": 1, "duree": 3}, 1)
	mage["vol_espece"] = True                 # pire cas : ailes ET lévitation
	_appliquer_couvert(mage, True)
	assert mage["volant"] is False and _can_fly(mage)


def test_le_snapshot_herite_du_vol_d_exploration():
	char = character(effets_actifs=[{"sort_id": "sort:v", "nom": "V", "vol": 1, "restants": 2}])
	assert build_joueur_snapshot(char, 0).get("vol_magique") is True
	assert "vol_magique" not in build_joueur_snapshot(character(), 0)


def test_expiration_au_dessus_d_une_falaise_chute(monkeypatch):
	notations = []
	monkeypatch.setattr(combat_mod, "roll_dice", _des(5, notations))
	mage = joueur(x=4, y=5, pv=30)
	doc = combat([mage], [monstre(x=10, y=8)])
	_falaise_en(doc, 4, 5)
	_empiler_effet_combat(mage, {"_id": "sort:v", "nom": "Voile"}, {"vol": 1, "duree": 1}, 0)
	doc["tour"] = 2
	_tick_effets_combat(doc, mage)

	assert "vol_magique" not in mage
	# Anneau 1, distance 1 : (4,4) et (3,5) ex æquo, la ligne la plus haute l'emporte.
	assert mage["pos"] == {"x": 4, "y": 4}, "posé sur la case praticable la plus proche"
	assert mage["currentPV"] == 25 and notations == ["1D20"], "falaise : un D20 par case"
	chute = [e for e in doc["log"] if "chute" in e["texte"]]
	assert "(1D20)" in chute[0]["texte"]
	assert len(chute) == 1 and chute[0]["kind"] == "move"
	assert chute[0]["etat"][mage["id"]]["pos"] == {"x": 4, "y": 4}
	assert textes(doc).index(chute[0]["texte"]) > next(
		i for i, t in enumerate(textes(doc)) if "se dissipe" in t), "dissipation PUIS chute"


def test_chute_au_milieu_d_un_plateau_de_falaise(monkeypatch):
	"""Plateau de falaise 5×5, le mage au centre : trois cases jusqu'au sol, trois D20."""
	notations = []
	monkeypatch.setattr(combat_mod, "roll_dice", _des(10, notations))
	mage = joueur(x=5, y=4, pv=60)
	doc = combat([mage], [monstre(x=11, y=8)])
	for y in range(2, 7):
		for x in range(3, 8):
			_falaise_en(doc, x, y)
	_empiler_effet_combat(mage, {"_id": "sort:v", "nom": "V"}, {"vol": 1, "duree": 1}, 0)
	_tick_effets_combat(doc, mage)
	assert notations == ["3D20"] and mage["currentPV"] == 50


def test_l_atterrissage_evite_une_case_occupee(monkeypatch):
	monkeypatch.setattr(combat_mod, "roll_dice", _des(1))
	mage = joueur(x=4, y=5)
	doc = combat([mage], [monstre(x=3, y=5)])
	_falaise_en(doc, 4, 5)
	_empiler_effet_combat(mage, {"_id": "sort:v", "nom": "V"}, {"vol": 1, "duree": 1}, 0)
	_tick_effets_combat(doc, mage)
	assert mage["pos"] != {"x": 3, "y": 5}
	assert combat_mod._walkable(doc["grid"]["cells"], mage["pos"]["x"], mage["pos"]["y"])


def test_expiration_sur_le_sol_ne_fait_rien():
	mage = joueur(x=4, y=5, pv=30)
	doc = combat([mage], [monstre(x=10, y=8)])
	_empiler_effet_combat(mage, {"_id": "sort:v", "nom": "V"}, {"vol": 1, "duree": 1}, 0)
	_tick_effets_combat(doc, mage)
	assert mage["pos"] == {"x": 4, "y": 5} and mage["currentPV"] == 30


def test_la_chute_peut_mettre_a_terre(monkeypatch):
	monkeypatch.setattr(combat_mod, "roll_dice", _des(6))
	mage = joueur(x=4, y=5, pv=4)
	doc = combat([mage], [monstre(x=10, y=8)])
	_falaise_en(doc, 4, 5)
	_empiler_effet_combat(mage, {"_id": "sort:v", "nom": "V"}, {"vol": 1, "duree": 1}, 0)
	_tick_effets_combat(doc, mage)
	assert mage["currentPV"] == 0


def test_rompre_un_vol_maintenu_fait_chuter(monkeypatch):
	monkeypatch.setattr(combat_mod, "roll_dice", _des(2))
	mage = joueur(x=4, y=5, pv=30)
	doc = combat([mage], [monstre(x=10, y=8)])
	_falaise_en(doc, 4, 5)
	source = {"_id": "sort:v", "nom": "V", "maintien": 2}
	entree = _empiler_effet_combat(mage, source, {"vol": 1}, 1)
	assert _can_fly(mage)
	_rompre_concentration(doc, mage, {"sort_id": entree["source_id"]}, "Le voile se déchire.")
	assert not _can_fly(mage)
	assert mage["pos"] == {"x": 4, "y": 4} and mage["currentPV"] == 28


# ── Contenu ────────────────────────────────────────────────────────────────────

def _contenu():
	with open(CONTENU, encoding="utf-8") as f:
		return json.load(f)


def test_le_voile_d_icare_est_un_sort_illusoire_de_vol_valide():
	(doc,) = _contenu()
	norm = sorts_util.normaliser_sort(doc)
	assert norm and doc["magie"] == "Illusoire" and doc["cible"] == "soi"
	assert norm["effets"]["vol"] == 1
	assert sorts_util.sort_utilisable_combat(norm)
	assert sorts_util.sort_utilisable_exploration(norm)


def test_le_voile_d_icare_respecte_la_paire_de_composants():
	"""Règle de contenu (telluris-magie) : un consommé ET un catalyseur, le catalyseur moins fort."""
	(doc,) = _contenu()
	conso = [c for c in doc["composants"] if c["consomme"]]
	cata = [c for c in doc["composants"] if not c["consomme"]]
	assert len(conso) == 1 and len(cata) == 1
	assert cata[0]["bonus"]["duree"] < conso[0]["bonus"]["duree"]
