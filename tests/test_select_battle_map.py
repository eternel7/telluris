# tests/test_select_battle_map.py
#
# Choix du DÉCOR d'un combat. Le bug d'origine : `select_battle_map` était nourri avec
# les `tags` de l'événement de zone tiré, qui pour un événement `combat` sont des noms
# de CRÉATURES (loup, brigand…), là où les battle maps sont taguées TERRAIN (foret,
# chemin, falaise…). Zéro recoupement possible → tous les poids au plancher → tirage
# uniforme → la mine aux cristaux (salle de donjon) sortait en pleine forêt 1 fois sur 4.
#
# Tests purs : `utils.combat.find_docs` est monkeypatché, aucune DB.

import random

import pytest

from utils import combat as combat_util
from utils.combat import select_battle_map
from utils.zones import terrain_tags_actifs


def _map(_id, tags, cells=True):
	return {
		"_id": _id, "type": "lieu", "categorie": "battle_map",
		"tags": list(tags),
		"cells": [[1, 1], [1, 1]] if cells else None,
	}


FORET = _map("lieu:chemin1", ["chemin", "foret", "bois"])
FALAISE = _map("lieu:chemin2", ["chemin", "foret", "falaise", "bois"])
CLAIRIERE = _map("lieu:clariere01", ["chemin", "foret", "bois", "clariere", "camp"])
MINE = _map("lieu:la_mine_aux_cristaux", ["mine", "cristaux", "donjon"])


@pytest.fixture
def base(monkeypatch):
	"""Installe un pool de battle maps ; renvoie un setter pour le changer."""
	pool = []

	def _find(_selector):
		return list(pool)

	monkeypatch.setattr(combat_util, "find_docs", _find)

	def _set(*maps):
		pool[:] = list(maps)

	_set(FORET, FALAISE, CLAIRIERE, MINE)
	return _set


def _tirages(n, *args, **kwargs):
	"""Compte les ids tirés sur n appels (graine fixée : test déterministe)."""
	random.seed(1234)
	compte: dict = {}
	for _ in range(n):
		choisi = select_battle_map(*args, **kwargs)
		cle = choisi["_id"] if choisi else None
		compte[cle] = compte.get(cle, 0) + 1
	return compte


# ── 1. Exclusion des salles de donjon ──────────────────────────────────────────

def test_une_salle_de_donjon_n_est_jamais_tiree(base):
	compte = _tirages(300, ["foret", "bois"], None)
	assert "lieu:la_mine_aux_cristaux" not in compte


def test_donjon_exclu_meme_s_il_est_le_seul_a_matcher(base):
	# La mine est la seule carte au tag `mine` : elle reste écartée, et le repli joue.
	base(FORET, MINE)
	compte = _tirages(200, ["mine", "cristaux"], None)
	assert set(compte) == {"lieu:chemin1"}


def test_donjon_seule_carte_du_pool_renvoie_none(base):
	# Plus aucun décor tirable → None, l'appelant retombe sur la grille ouverte.
	base(MINE)
	assert select_battle_map(["foret"], None) is None


# ── 2. Au moins un tag commun exigé ────────────────────────────────────────────

def test_un_tag_commun_est_exige(base):
	# `camp` n'est porté que par la clairière : les deux chemins sont écartés.
	compte = _tirages(200, ["camp"], None)
	assert set(compte) == {"lieu:clariere01"}


def test_tags_sans_aucun_recoupement_ne_selectionnent_pas_au_hasard(base):
	# Le bug historique : des noms de créatures en entrée. Aucun match → repli, mais
	# JAMAIS la mine (c'est tout l'objet du correctif).
	compte = _tirages(300, ["loup", "brigand"], None)
	assert "lieu:la_mine_aux_cristaux" not in compte
	assert set(compte) == {"lieu:chemin1", "lieu:chemin2", "lieu:clariere01"}


# ── 3. Pondération par le nombre de tags communs ───────────────────────────────

def test_plus_de_tags_communs_pese_plus_lourd(base):
	# zone:campement_bandit → camp, clariere, foret, bois
	#   clariere01 : camp+clariere+foret+bois = 4  |  chemin1/chemin2 : foret+bois = 2
	compte = _tirages(600, ["camp", "clariere", "foret", "bois"], None)
	assert compte["lieu:clariere01"] > compte["lieu:chemin1"]
	assert compte["lieu:clariere01"] > compte["lieu:chemin2"]


def test_la_falaise_est_favorisee_en_montagne(base):
	# zone:montagne → montagne, falaise, pierre, chemin
	#   chemin2 : chemin+falaise = 2  |  chemin1, clariere01 : chemin = 1
	compte = _tirages(600, ["montagne", "falaise", "pierre", "chemin"], None)
	assert compte["lieu:chemin2"] > compte["lieu:chemin1"]
	assert compte["lieu:chemin2"] > compte["lieu:clariere01"]


# ── 4. Repli et non-régression ─────────────────────────────────────────────────

def test_repli_uniforme_quand_rien_ne_matche(base):
	# Zone urbaine : aucune carte de ville en base → tout le pool hors donjon.
	compte = _tirages(400, ["ville", "urbain", "rue"], None)
	assert set(compte) == {"lieu:chemin1", "lieu:chemin2", "lieu:clariere01"}
	assert min(compte.values()) > 0


def test_terrain_vide_et_lieu_sans_tags_repli(base):
	# Comportement historique préservé (hors mine) pour un lieu non tagué.
	compte = _tirages(300, [], {"_id": "lieu:foret", "tags": []})
	assert set(compte) == {"lieu:chemin1", "lieu:chemin2", "lieu:clariere01"}


def test_les_tags_du_lieu_de_depart_comptent_aussi(base):
	# Le second terme du pool : taguer un lieu d'exploration surcharge son décor.
	compte = _tirages(200, [], {"_id": "lieu:x", "tags": ["camp"]})
	assert set(compte) == {"lieu:clariere01"}


def test_carte_sans_cells_ignoree(base):
	base(_map("lieu:vide", ["foret"], cells=False), FORET)
	compte = _tirages(100, ["foret"], None)
	assert set(compte) == {"lieu:chemin1"}


def test_aucune_carte_renvoie_none(base):
	base()
	assert select_battle_map(["foret"], None) is None


# ── 5. terrain_tags_actifs (pur) ───────────────────────────────────────────────

DEFS = {
	"zone:foret_dense": {"_id": "zone:foret_dense", "terrain_tags": ["foret", "bois", "chemin"]},
	"zone:riviere": {"_id": "zone:riviere", "terrain_tags": ["riviere", "eau", "bois"]},
	"zone:sans": {"_id": "zone:sans"},
}


def test_terrain_tags_union_des_zones_actives():
	actifs = [{"zone": "zone:foret_dense"}, {"zone": "zone:riviere"}]
	assert terrain_tags_actifs(actifs, DEFS) == ["foret", "bois", "chemin", "riviere", "eau"]


def test_terrain_tags_zone_def_sans_champ_ignoree():
	assert terrain_tags_actifs([{"zone": "zone:sans"}], DEFS) == []


def test_terrain_tags_placement_sans_def_ignore():
	assert terrain_tags_actifs([{"zone": "zone:inconnue"}], DEFS) == []


def test_terrain_tags_aucun_placement_actif():
	assert terrain_tags_actifs([], DEFS) == []
	assert terrain_tags_actifs(None, None) == []
