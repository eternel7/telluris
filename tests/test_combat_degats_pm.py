# tests/test_combat_degats_pm.py
#
# DÉGÂTS AUX PM : « Certains sorts infligent des dégâts directement aux Points de Mana de
# leur cible plutôt qu'à ses PV. Ils ne réduisent pas directement les PV. Un sort peut
# cependant infliger simultanément des dégâts aux PV et aux PM. »
#
# ⚠️ Le préalable de toute la mécanique : jusqu'ici un snapshot de MONSTRE ne portait ni
# `currentPM` ni `pm_max` — seulement `pm_def`. Des dégâts aux PM auraient donc été inertes
# sur la seule cible qu'un sort offensif puisse viser, et toute la famille « anti-lanceur »
# n'aurait existé que sur le papier.

import pytest

from utils import combat as combat_mod
from utils.combat import build_monster_snapshot, resolve_action
from _fixtures_magie import combat, espece, joueur, monstre, sort, textes


@pytest.fixture(autouse=True)
def _des_fixes(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "randint",
						lambda a, b: 50 if b == 100 else 6)


def _siphon(**effets):
	base = {"degats_pm": "1D6"}
	base.update(effets)
	return sort(cout_pm=5, cible="ennemi", portee=6, nom="Éclair siphonnant",
				effets=base)


# ── Les monstres ont enfin une réserve de mana ──────────────────────────────────

def test_un_monstre_porte_desormais_une_reserve_de_pm():
	m = build_monster_snapshot(espece(), None, 0)
	assert "currentPM" in m and "pm_max" in m
	assert m["currentPM"] == m["pm_max"]


def test_la_reserve_suit_la_formule_des_joueurs():
	"""Vol×2 + Int×2 — une bête sans volonté ni intelligence n'a rien à siphonner."""
	brute = build_monster_snapshot(
		espece(base_attributes={c: {"min": v, "max": v} for c, v in
							   (("V", 4), ("F", 30), ("R", 30), ("Ag", 40),
								("Vol", 0), ("Int", 0), ("Cha", 10), ("Ch", 10))}),
		None, 0)
	assert brute["pm_max"] == 0

	savante = build_monster_snapshot(
		espece(base_attributes={c: {"min": v, "max": v} for c, v in
								(("V", 4), ("F", 30), ("R", 30), ("Ag", 40),
								 ("Vol", 40), ("Int", 60), ("Cha", 10), ("Ch", 10))}),
		None, 0)
	assert savante["pm_max"] == 200


# ── Les dégâts de PM ────────────────────────────────────────────────────────────

def test_les_degats_de_pm_vident_la_reserve_de_la_cible():
	mage = joueur(pm=60)
	loup = monstre(x=8, y=5)
	pm_avant = loup["currentPM"]
	doc = combat([mage], [loup])

	res = resolve_action(doc, "sort", cible_id="monstre_0", sort=_siphon())
	assert res["dmg_pm"] > 0
	assert loup["currentPM"] == pm_avant - res["dmg_pm"]


def test_les_degats_de_pm_ne_touchent_pas_les_pv():
	mage = joueur(pm=60)
	loup = monstre(x=8, y=5)
	doc = combat([mage], [loup])

	resolve_action(doc, "sort", cible_id="monstre_0", sort=_siphon())
	assert loup["currentPV"] == 200, "une siphonie ne blesse pas le corps"


def test_un_sort_peut_frapper_les_deux_a_la_fois():
	"""« Éclair siphonnant : inflige 10 dégâts aux PV et 5 dégâts aux PM. »"""
	mage = joueur(pm=60)
	loup = monstre(x=8, y=5)
	doc = combat([mage], [loup])

	res = resolve_action(doc, "sort", cible_id="monstre_0",
						 sort=_siphon(degats="2D6"))
	assert res["dmg"] > 0 and res["dmg_pm"] > 0
	assert loup["currentPV"] < 200
	assert loup["currentPM"] < loup["pm_max"]


def test_la_reserve_ne_descend_jamais_sous_zero():
	mage = joueur(pm=60)
	loup = monstre(x=8, y=5)
	loup["currentPM"] = 3
	doc = combat([mage], [loup])

	res = resolve_action(doc, "sort", cible_id="monstre_0",
						 sort=_siphon(degats_pm="20D6"))
	assert loup["currentPM"] == 0
	assert res["dmg_pm"] == 3, "on ne siphonne que ce qui restait"


def test_l_armure_n_arrete_pas_une_siphonie():
	"""⚠️ AUCUNE soustraction des PA : c'est pour cela que le jet ne passe pas par
	`calculer_degats`. Une cible cuirassée perd exactement autant de mana qu'une cible nue."""
	mage = joueur(pm=60)
	nu, cuirasse = monstre(0, x=8, y=5), monstre(1, x=8, y=6)
	cuirasse["pa"] = 500
	doc = combat([mage], [nu, cuirasse])

	r1 = resolve_action(doc, "sort", cible_id="monstre_0", sort=_siphon())
	mage["sorts"] = 0                        # on rend l'action pour le second tir
	combat_mod._refresh_actions(mage)
	r2 = resolve_action(doc, "sort", cible_id="monstre_1", sort=_siphon())
	assert r1["dmg_pm"] == r2["dmg_pm"]


def test_un_sort_qui_manque_ne_siphonne_rien(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "randint",
						lambda a, b: 95 if b == 100 else 6)
	mage = joueur(pm=60)
	loup = monstre(x=8, y=5)
	loup["pm_def"] = 500
	pm_avant = loup["currentPM"]
	doc = combat([mage], [loup])

	resolve_action(doc, "sort", cible_id="monstre_0", sort=_siphon())
	assert loup["currentPM"] == pm_avant


def test_une_ligne_de_journal_propre_annonce_la_perte():
	"""⚠️ Ligne SÉPARÉE : `currentPM` est dans `CHAMPS_ETAT`, donc l'anneau de mana ne
	bouge qu'à la révélation de CETTE ligne. Fondue dans la ligne de dégâts, les deux
	jauges tomberaient ensemble sans dire pourquoi."""
	mage = joueur(pm=60)
	doc = combat([mage], [monstre(x=8, y=5)])
	resolve_action(doc, "sort", cible_id="monstre_0", sort=_siphon(degats="2D6"))
	assert any("sa magie se vider" in t for t in textes(doc))


def test_un_sort_sans_degats_pm_ne_touche_pas_la_reserve():
	"""Non-régression : le champ absent doit valoir le comportement d'avant."""
	mage = joueur(pm=60)
	loup = monstre(x=8, y=5)
	pm_avant = loup["currentPM"]
	doc = combat([mage], [loup])
	resolve_action(doc, "sort", cible_id="monstre_0",
				   sort=sort(cout_pm=5, cible="ennemi", portee=6,
							 effets={"degats": "2D6"}))
	assert loup["currentPM"] == pm_avant
