# tests/test_combat_saut.py
#
# SAUT (téléportation tactique) : « Le déplacement est instantané : les cases situées entre
# le départ et l'arrivée ne sont pas parcourues. Le saut peut permettre de franchir des
# obstacles, des créatures ou certains terrains infranchissables par un déplacement normal. »
#
# D'où ce qui n'est PAS vérifié, et qui fait tout l'intérêt du sort : ni `nav`, ni chemin
# praticable, ni ligne de vue. On franchit le mur, on ne le contourne pas. Restent la
# portée, le terrain d'ARRIVÉE et la place.

import pytest

from utils import combat as combat_mod
from utils.combat import resolve_action
from _fixtures_magie import combat, joueur, monstre, sort, textes


@pytest.fixture(autouse=True)
def _des_fixes(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)


def _saut(distance=4, cible="soi"):
	return sort(cout_pm=4, cible=cible, portee=6, nom="Saut", icon="💨",
				effets={"saut": distance})


# ── Le saut ordinaire ───────────────────────────────────────────────────────────

def test_le_lanceur_se_teleporte_sur_la_case_designee():
	mage = joueur(x=3, y=5)
	doc = combat([mage], [monstre(x=10, y=8)])

	res = resolve_action(doc, "sort", dx=6, dy=5, sort=_saut())
	assert mage["pos"] == {"x": 6, "y": 5}
	assert res["saut"]["de"] == {"x": 3, "y": 5}
	assert res["saut"]["vers"] == {"x": 6, "y": 5}


def test_le_saut_franchit_un_mur():
	"""⚠️ La raison d'être du sort : aucune ligne de vue, aucun chemin praticable exigé."""
	mage = joueur(x=3, y=5)
	doc = combat([mage], [monstre(x=10, y=8)])
	for y in range(9):                        # un mur plein sur toute la colonne 5
		doc["grid"]["cells"][y][5] = 0

	resolve_action(doc, "sort", dx=6, dy=5, sort=_saut())
	assert mage["pos"] == {"x": 6, "y": 5}, "le mur ne doit pas arrêter une téléportation"


def test_le_saut_franchit_une_creature():
	mage = joueur(x=3, y=5)
	doc = combat([mage], [monstre(x=4, y=5), monstre(1, x=10, y=8)])
	resolve_action(doc, "sort", dx=5, dy=5, sort=_saut())
	assert mage["pos"] == {"x": 5, "y": 5}


def test_une_seule_ligne_de_journal_porte_tout_l_ecart():
	"""C'est elle qui fait glisser le jeton d'un trait, sans une ligne de client."""
	mage = joueur(x=3, y=5)
	doc = combat([mage], [monstre(x=10, y=8)])
	resolve_action(doc, "sort", dx=6, dy=5, sort=_saut())

	moves = [e for e in doc["log"] if e["kind"] == "move"]
	assert len(moves) == 1
	assert moves[0]["etat"][mage["id"]]["pos"] == {"x": 6, "y": 5}
	assert "disparaît et reparaît" in moves[0]["texte"]


# ── Les trois refus ─────────────────────────────────────────────────────────────

def test_hors_de_portee():
	mage = joueur(x=3, y=5)
	doc = combat([mage], [monstre(x=10, y=8)])
	res = resolve_action(doc, "sort", dx=11, dy=5, sort=_saut(distance=4))
	assert res["error"] == "Destination hors de portée du saut."
	assert mage["pos"] == {"x": 3, "y": 5}


def test_terrain_infranchissable_a_l_arrivee():
	"""On franchit un mur, on n'atterrit pas dessus."""
	mage = joueur(x=3, y=5)
	doc = combat([mage], [monstre(x=10, y=8)])
	doc["grid"]["cells"][5][6] = 0
	res = resolve_action(doc, "sort", dx=6, dy=5, sort=_saut())
	assert res["error"] == "Terrain infranchissable à l'arrivée."


def test_case_occupee():
	mage = joueur(x=3, y=5)
	doc = combat([mage], [monstre(x=6, y=5)])
	res = resolve_action(doc, "sort", dx=6, dy=5, sort=_saut())
	assert res["error"] == "Case occupée."


def test_hors_de_la_grille():
	mage = joueur(x=3, y=5)
	doc = combat([mage], [monstre(x=10, y=8)])
	assert resolve_action(doc, "sort", dx=-1, dy=5, sort=_saut())["error"] == "Hors de la zone."


def test_sans_case_designee():
	mage = joueur(x=3, y=5)
	doc = combat([mage], [monstre(x=10, y=8)])
	res = resolve_action(doc, "sort", sort=_saut())
	assert res["error"] == "Aucune case de destination désignée."


def test_un_refus_ne_coute_ni_pm_ni_action():
	mage = joueur(x=3, y=5, pm=60)
	doc = combat([mage], [monstre(x=10, y=8)])
	actions = mage["actions_restantes"]
	resolve_action(doc, "sort", dx=11, dy=5, sort=_saut(distance=4))
	assert mage["currentPM"] == 60
	assert mage["actions_restantes"] == actions


# ── Grands jetons ───────────────────────────────────────────────────────────────

def test_une_grande_creature_doit_tenir_tout_entiere_a_l_arrivee():
	mage = joueur(x=3, y=5)
	mage["jeton"] = {"largeur": 2, "profondeur": 2, "forme": "ellipse"}
	mage["cap"] = "haut"
	doc = combat([mage], [monstre(x=10, y=8)])
	doc["grid"]["cells"][5][7] = 0            # une seule case de l'emprise est bloquée

	res = resolve_action(doc, "sort", dx=6, dy=5, sort=_saut())
	assert res["error"] == "Terrain infranchissable à l'arrivée."


def test_une_grande_creature_saute_quand_toute_son_emprise_tient():
	mage = joueur(x=3, y=5)
	mage["jeton"] = {"largeur": 2, "profondeur": 2, "forme": "ellipse"}
	mage["cap"] = "haut"
	doc = combat([mage], [monstre(x=10, y=8)])
	resolve_action(doc, "sort", dx=6, dy=5, sort=_saut())
	assert mage["pos"] == {"x": 6, "y": 5}


def test_un_saut_court_ne_se_bloque_pas_sur_ses_propres_cases():
	"""⚠️ Le sauteur quitte son emprise : elle ne doit pas se compter comme occupée."""
	mage = joueur(x=3, y=5)
	mage["jeton"] = {"largeur": 2, "profondeur": 2, "forme": "ellipse"}
	mage["cap"] = "haut"
	doc = combat([mage], [monstre(x=10, y=8)])
	resolve_action(doc, "sort", dx=4, dy=5, sort=_saut())
	assert mage["pos"] == {"x": 4, "y": 5}, "l'emprise d'arrivée recouvre l'ancienne"


# ── Saut sur un allié ───────────────────────────────────────────────────────────

def test_on_peut_teleporter_un_allie():
	mage = joueur(0, x=3, y=5)
	brann = joueur(1, x=4, y=5, nom="Brann")
	doc = combat([mage, brann], [monstre(x=10, y=8)])

	res = resolve_action(doc, "sort", cible_id="joueur_1", dx=6, dy=5,
						 sort=_saut(cible="allie"))
	assert brann["pos"] == {"x": 6, "y": 5}
	assert mage["pos"] == {"x": 3, "y": 5}, "le lanceur, lui, ne bouge pas"
	assert res["saut"]["acteur_id"] == "joueur_1"


def test_la_portee_du_saut_se_mesure_depuis_le_SAUTEUR():
	"""Et non depuis le lanceur : c'est l'allié qui se téléporte."""
	mage = joueur(0, x=3, y=5)
	brann = joueur(1, x=4, y=5, nom="Brann")
	doc = combat([mage, brann], [monstre(x=10, y=8)])
	# Brann est en x=4 : la case x=9 est à 5 de LUI (et à 6 du mage). Un saut de portée 4
	# la refuse — s'il se mesurait depuis le lanceur, le refus tomberait au même endroit,
	# d'où le second cas juste en dessous, qui les départage vraiment.
	res = resolve_action(doc, "sort", cible_id="joueur_1", dx=9, dy=5,
						 sort=_saut(distance=4, cible="allie"))
	assert res["error"] == "Destination hors de portée du saut."

	# x=8 est à 4 de Brann (accepté) mais à 5 du mage (qui refuserait).
	assert "error" not in resolve_action(doc, "sort", cible_id="joueur_1", dx=8, dy=5,
										 sort=_saut(distance=4, cible="allie"))
	assert brann["pos"] == {"x": 8, "y": 5}


# ── Non-régression ──────────────────────────────────────────────────────────────

def test_un_sort_sans_saut_ignore_les_coordonnees():
	"""Champ absent ⇒ comportement d'avant, à la lettre."""
	mage = joueur(x=3, y=5)
	doc = combat([mage], [monstre(x=10, y=8)])
	resolve_action(doc, "sort", dx=6, dy=5,
				   sort=sort(cout_pm=5, cible="soi", effets={"pv": 10}))
	assert mage["pos"] == {"x": 3, "y": 5}
