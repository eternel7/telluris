"""Jetons de taille variable dans le MOTEUR de combat (utils/combat.py + utils/jetons.py).

Portée et ligne de vue entre emprises, cases bloquées, traversée d'un grand allié non jouable,
tour d'un grand monstre, zones d'effet, placement, invocation et monture.

Tests purs : docs à la main, aucune DB (`random` neutralisé, `get_doc` remplacé), fixtures
reprises de tests/test_combat_echange.py.
"""
import random

from utils import combat as combat_mod
from utils import simulateur
from utils.zones_effet import normaliser_zone


def _character(nom="Frida", cid="character:test_1"):
	return {
		"_id": cid, "user_id": "user:test", "nom": nom, "voc": "guerrier", "race": "humain",
		"caracteristiques_current": {"V": 5, "F": 40, "R": 30, "Ag": 40,
									 "Vol": 30, "Int": 20, "Cha": 20, "Ch": 20},
		"vocations_niveaux": {"guerrier": 1},
		"currentPV": 100, "currentPM": 20, "inventaire": [], "slots": {},
	}


def _espece(eid="espece:loup", nom="Loup", jeton=None):
	espece = {"_id": eid, "type": "espece", "nom": nom, "tags": [],
			  "base_attributes": {c: {"min": v, "max": v} for c, v in
								  (("V", 4), ("F", 30), ("R", 30), ("Ag", 40),
								   ("Vol", 20), ("Int", 10), ("Cha", 10), ("Ch", 10))}}
	if jeton:
		espece["jeton"] = jeton
	return espece


DRAGON = _espece("espece:dragon", "Dragon", {"taille": "3x2", "forme": "triangle"})


def _joueur(monkeypatch, index=0, nom="Frida", **champs):
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)
	snap = combat_mod.build_joueur_snapshot(_character(nom, f"character:test_{index + 1}"), index)
	snap["vivant"] = True
	snap.update(champs)
	return snap


def _hors_tour(monkeypatch, index, nom="Âne", jeton=None, **champs):
	snap = _joueur(monkeypatch, index, nom)
	snap.update({"jouable": False, "est_monture": True, "deplacement": 0, "deplacement_base": 0})
	if jeton:
		snap["jeton"] = jeton
	snap.update(champs)
	return snap


def _monstre(monkeypatch, x, y, idx=0, espece=None, cap=None):
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)
	m = combat_mod.build_monster_snapshot(espece or _espece(), None, idx)
	m["pos"] = {"x": x, "y": y}
	if cap:
		m["cap"] = cap
	return m


def _combat(joueurs, monstres=(), w=9, h=9, cells=None):
	return {
		"_id": "combat:test", "type": "combat", "status": "active", "tour": 1, "log": [],
		"ordre_initiative": ["joueur_0"] + [m["id"] for m in monstres],
		"acteur_courant_index": 0,
		"joueurs": list(joueurs), "monstres": list(monstres),
		"grid": {"dims": {"x": w, "y": h},
				 "cells": cells if cells is not None else [[1] * w for _ in range(h)],
				 "nav": {}},
	}


def _toutes_cases(acteurs):
	cases = []
	for a in acteurs:
		cases.extend(combat_mod.jetons.cases_emprise(a))
	return cases


# ── Snapshots ────────────────────────────────────────────────────────────────────

def test_le_snapshot_porte_le_jeton_de_lespece(monkeypatch):
	assert _monstre(monkeypatch, 0, 0, espece=DRAGON)["jeton"] == {
		"largeur": 3, "profondeur": 2, "forme": "triangle"}
	# Espèce sans gabarit : le snapshot d'avant, à la lettre (aucune clé ajoutée).
	assert "jeton" not in _monstre(monkeypatch, 0, 0)


def test_cap_fait_partie_de_letat_revele():
	assert "cap" in combat_mod.CHAMPS_ETAT


# ── Portée et ligne de vue ───────────────────────────────────────────────────────

def test_attaque_au_contact_de_nimporte_quel_bord(monkeypatch):
	"""Dragon 3x2 en (2,2) : x 2..4 × y 2..3. Depuis (5,3) il est au contact, alors que sa
	`pos` est à 3 cases."""
	joueur = _joueur(monkeypatch, 0, pos={"x": 5, "y": 3})
	dragon = _monstre(monkeypatch, 2, 2, espece=DRAGON, cap="bas")
	combat = _combat([joueur], [dragon])

	assert combat_mod._cheby(joueur, dragon) == 1
	res = combat_mod.resolve_action(combat, "attaquer", cible_id=dragon["id"], mode="cac")
	assert "error" not in res


def test_hors_de_portee_une_case_plus_loin(monkeypatch):
	joueur = _joueur(monkeypatch, 0, pos={"x": 6, "y": 3})
	dragon = _monstre(monkeypatch, 2, 2, espece=DRAGON, cap="bas")
	combat = _combat([joueur], [dragon])

	assert combat_mod.resolve_action(combat, "attaquer", cible_id=dragon["id"], mode="cac") == {
		"error": "Cible hors de portée."}


def test_ligne_de_vue_par_au_moins_une_paire():
	"""Un mur couvre le haut de la bête : la ligne passe tant qu'une de ses cases dépasse."""
	cells = [[1] * 9 for _ in range(9)]
	for y in range(0, 3):
		cells[y][4] = 0
	tireur = {"pos": {"x": 6, "y": 3}}
	bete = {"pos": {"x": 1, "y": 2}, "jeton": {"largeur": 2, "profondeur": 2, "forme": "ellipse"}}
	assert combat_mod._vue_acteurs(cells, tireur, bete) is True
	cells[3][4] = 0
	assert combat_mod._vue_acteurs(cells, tireur, bete) is False


# ── Cases occupées et traversée ──────────────────────────────────────────────────

def test_toutes_les_cases_dun_monstre_bloquent(monkeypatch):
	joueur = _joueur(monkeypatch, 0, pos={"x": 5, "y": 3})
	dragon = _monstre(monkeypatch, 2, 2, espece=DRAGON, cap="bas")
	combat = _combat([joueur], [dragon])

	assert combat_mod.resolve_action(combat, "deplacer", dx=-1, dy=0) == {"error": "Case occupée."}
	assert joueur["pos"] == {"x": 5, "y": 3}


def test_le_joueur_traverse_une_grande_monture(monkeypatch):
	"""Une monture 2x2 ne s'échange pas (géométriquement impossible) : on passe au travers."""
	joueur = _joueur(monkeypatch, 0, pos={"x": 2, "y": 2})
	cheval = _hors_tour(monkeypatch, 1, "Cheval", pos={"x": 3, "y": 2},
						jeton={"largeur": 2, "profondeur": 2, "forme": "ellipse"})
	combat = _combat([joueur, cheval])

	for attendu in ({"x": 3, "y": 2}, {"x": 4, "y": 2}, {"x": 5, "y": 2}):
		assert combat_mod.resolve_action(combat, "deplacer", dx=1, dy=0)["moved"] is True
		assert joueur["pos"] == attendu
	assert cheval["pos"] == {"x": 3, "y": 2}, "la monture n'a pas bougé"


def test_un_monstre_ne_traverse_jamais_la_monture(monkeypatch):
	joueur = _joueur(monkeypatch, 0, pos={"x": 0, "y": 0})
	cheval = _hors_tour(monkeypatch, 1, "Cheval", pos={"x": 3, "y": 2},
						jeton={"largeur": 2, "profondeur": 2, "forme": "ellipse"})
	loup = _monstre(monkeypatch, 7, 7)
	combat = _combat([joueur, cheval], [loup])

	assert (4, 3) in combat_mod._occupied_set(combat, exclude=loup)
	assert (4, 3) not in combat_mod._occupied_set(combat, traversant=joueur)


def test_pas_dechange_en_sortant_dune_grande_monture(monkeypatch):
	"""Le joueur se tient DANS le cheval : l'âne échangé atterrirait sur le cheval."""
	joueur = _joueur(monkeypatch, 0, pos={"x": 3, "y": 2})
	cheval = _hors_tour(monkeypatch, 1, "Cheval", pos={"x": 3, "y": 2},
						jeton={"largeur": 2, "profondeur": 2, "forme": "ellipse"})
	ane = _hors_tour(monkeypatch, 2, "Âne", pos={"x": 2, "y": 2})
	combat = _combat([joueur, cheval, ane])

	assert combat_mod.resolve_action(combat, "deplacer", dx=-1, dy=0) == {
		"error": "Âne ne peut pas tenir sur votre case."}
	assert ane["pos"] == {"x": 2, "y": 2}


def test_lechange_1x1_reste_inchange(monkeypatch):
	joueur = _joueur(monkeypatch, 0, pos={"x": 3, "y": 5})
	ane = _hors_tour(monkeypatch, 1, pos={"x": 4, "y": 5})
	combat = _combat([joueur, ane])

	assert combat_mod.resolve_action(combat, "deplacer", dx=1, dy=0)["moved"] is True
	assert ane["pos"] == {"x": 3, "y": 5}


# ── Tour d'un grand monstre ──────────────────────────────────────────────────────

def test_un_grand_monstre_savance_sans_chevaucher(monkeypatch):
	joueur = _joueur(monkeypatch, 0, pos={"x": 9, "y": 3})
	ours = _monstre(monkeypatch, 0, 2, espece=_espece("espece:ours", "Ours",
													  {"taille": "2x2"}), cap="droite")
	combat = _combat([joueur], [ours], w=11, h=7)
	grid = combat_mod.get_combat_grid(combat)
	avant = combat_mod._cheby(ours, joueur)

	combat["acteur_courant_index"] = 1
	combat_mod._run_monster_turn(combat, ours, grid)

	assert ours["cells_moved"] >= 1
	assert combat_mod._cheby(ours, joueur) == avant - ours["cells_moved"]
	assert (9, 3) not in combat_mod.jetons.cases_emprise(ours)
	ligne = next(e for e in combat["log"] if e["kind"] == "move")
	assert "cap" in ligne["etat"][ours["id"]]


def test_un_monstre_1x1_vient_au_contact_dun_grand_allie(monkeypatch):
	"""Il vise la case de l'emprise la plus proche, pas le coin `pos` de la bête."""
	joueur = _joueur(monkeypatch, 0, pos={"x": 0, "y": 0}, currentPV=0)
	cheval = _hors_tour(monkeypatch, 1, "Cheval", pos={"x": 4, "y": 4},
						jeton={"largeur": 2, "profondeur": 2, "forme": "ellipse"})
	loup = _monstre(monkeypatch, 8, 8)
	combat = _combat([joueur, cheval], [loup])
	grid = combat_mod.get_combat_grid(combat)

	while combat_mod._cheby(loup, cheval) > 1:
		loup["cells_moved"] = 0
		loup["attaques"] = 0
		assert combat_mod._monster_step_toward(combat, loup, cheval, grid) is True
	assert not combat_mod.jetons.couvre(cheval, loup["pos"]["x"], loup["pos"]["y"])


# ── Zones d'effet ────────────────────────────────────────────────────────────────

def test_une_zone_prend_un_grand_monstre_par_une_seule_case(monkeypatch):
	joueur = _joueur(monkeypatch, 0, pos={"x": 1, "y": 4})
	vise = _monstre(monkeypatch, 4, 4, idx=0)
	dragon = _monstre(monkeypatch, 5, 5, idx=1, espece=DRAGON, cap="bas")   # x 5..7, y 5..6
	loin = _monstre(monkeypatch, 8, 8, idx=2)
	combat = _combat([joueur], [vise, dragon, loin])
	zone = normaliser_zone({"forme": "carre", "rayon": 1})

	touches = combat_mod.cibles_de_zone(combat, joueur, vise, zone, combat_mod.get_combat_grid(combat))
	assert [m["id"] for m in touches] == [vise["id"], dragon["id"]]


def test_une_zone_sur_un_grand_monstre_sancre_sur_sa_case_proche(monkeypatch):
	joueur = _joueur(monkeypatch, 0, pos={"x": 1, "y": 5})
	dragon = _monstre(monkeypatch, 5, 5, idx=0, espece=DRAGON, cap="bas")
	voisin = _monstre(monkeypatch, 4, 6, idx=1)
	loin = _monstre(monkeypatch, 8, 5, idx=2)
	combat = _combat([joueur], [dragon, voisin, loin])
	zone = normaliser_zone({"forme": "carre", "rayon": 1})

	touches = combat_mod.cibles_de_zone(combat, joueur, dragon, zone, combat_mod.get_combat_grid(combat))
	assert [m["id"] for m in touches] == [dragon["id"], voisin["id"]]


# ── Placement, invocation, monture ───────────────────────────────────────────────

def test_placement_sans_chevauchement(monkeypatch):
	for graine in range(20):
		random.seed(graine)
		joueur = _joueur(monkeypatch, 0)
		dragons = [_monstre(monkeypatch, 0, 0, idx=i, espece=DRAGON) for i in range(2)]
		combat = _combat([joueur], dragons, w=13, h=11)
		combat_mod._place_actors(combat, combat_mod._open_grid(13, 11))

		cases = _toutes_cases([joueur] + dragons)
		assert len(cases) == len(set(cases)) == 13, f"graine {graine}"
		assert all(0 <= x < 13 and 0 <= y < 11 for (x, y) in cases)
		assert all(d.get("jeton") and d.get("cap") for d in dragons)


def test_placement_carte_trop_petite_repli_en_1x1(monkeypatch):
	random.seed(0)
	joueur = _joueur(monkeypatch, 0)
	dragon = _monstre(monkeypatch, 0, 0, espece=DRAGON)
	combat = _combat([joueur], [dragon], w=3, h=2)
	combat_mod._place_actors(combat, combat_mod._open_grid(3, 2))

	assert "jeton" not in dragon
	assert dragon["pos"] != joueur["pos"]


def test_invocation_dune_grande_espece(monkeypatch):
	monkeypatch.setattr(combat_mod, "get_doc", lambda i: DRAGON if i == DRAGON["_id"] else None)
	joueur = _joueur(monkeypatch, 0, pos={"x": 4, "y": 4})
	combat = _combat([joueur], w=11, h=11)
	sort = {"invocation": {"espece": DRAGON["_id"], "nombre": 2, "duree": 2}}

	crees = combat_mod.invoquer(combat, joueur, sort, combat_mod.get_combat_grid(combat))

	assert len(crees) == 2
	assert all(c.get("jeton") and c.get("cap") for c in crees)
	cases = _toutes_cases([joueur] + crees)
	assert len(cases) == len(set(cases)) == 13


def test_la_monture_lit_son_gabarit_sur_lespece(monkeypatch):
	cheval = _espece("espece:cheval", "Cheval", {"taille": "1x2"})
	lire = lambda i: cheval if i == cheval["_id"] else None
	monkeypatch.setattr(combat_mod, "get_doc", lire)
	monkeypatch.setattr(combat_mod.montures_util, "get_doc", lire)
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)
	random.seed(3)
	monture = dict(_character("Cheval", "monture:cheval_1"), type="monture",
				   espece=cheval["_id"], jouable=False)

	combat = combat_mod.create_combat_doc(_character(), [], [], "", montures=[monture])

	snap = combat["joueurs"][1]
	assert snap["jeton"] == {"largeur": 1, "profondeur": 2, "forme": "ellipse"}
	assert snap.get("cap")
	cases = _toutes_cases(combat["joueurs"])
	assert len(cases) == len(set(cases)) == 3


def test_simulateur_garde_la_distance_saisie():
	actor = {"jeton": {"largeur": 3, "profondeur": 2, "forme": "ellipse"}}
	adversaire = {}
	simulateur._poser_positions(actor, adversaire, 4)
	assert combat_mod._cheby(actor, adversaire) == 4
