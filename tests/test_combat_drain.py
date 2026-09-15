# tests/test_combat_drain.py
#
# SORTS DE DRAIN : « pour chaque quantité de dégâts de PV infligée par le sort, une
# quantité correspondante de PV ou de PM est récupérée par le jeteur selon le type de
# drain, dans la limite éventuellement fixée par le sort. »
#
# La phrase qui décide de tout : « Le drain ne récupère donc que sur les dégâts
# EFFECTIVEMENT infligés à la cible, et non sur les dégâts théoriques du sort. » Un coup de
# 40 sur une cible à 5 PV ne nourrit le lanceur que de 5 — sans quoi l'overkill deviendrait
# la meilleure source de soin du jeu.
#
# Second point verrouillé : `drain_max` est le plafond DU LANCEMENT, pas celui de chaque
# victime — sinon le sort le plus large serait aussi le plus nourrissant.

import pytest

from utils import combat as combat_mod
from utils.combat import resolve_action
from _fixtures_magie import combat, joueur, monstre, sort


@pytest.fixture(autouse=True)
def _des_fixes(monkeypatch):
	"""d100 à 50 (touche, pas de critique) et chaque dé à 6 : dégâts prévisibles."""
	monkeypatch.setattr(combat_mod.random, "randint",
						lambda a, b: 50 if b == 100 else 6)


def _vampirique(**effets):
	base = {"degats": "1D6", "drain_pv": 50}
	base.update(effets)
	return sort(cout_pm=5, cible="ennemi", portee=6, nom="Baiser du vampire",
				effets=base)


def _mage_blesse(pm=60):
	# Marge large sous les max : le clamp ne doit pas masquer l'arithmétique du drain.
	return joueur(pm=pm, pv=200, pv_max=200, currentPV=20, currentPM=10, pm_max=200)


# ── Le drain nourrit sur les dégâts RÉELS ───────────────────────────────────────

def test_le_drain_rend_une_part_des_degats_infliges():
	mage = _mage_blesse()
	loup = monstre(x=8, y=5, pv=500)
	doc = combat([mage], [loup])

	res = resolve_action(doc, "sort", cible_id="monstre_0", sort=_vampirique())
	inflige = 500 - loup["currentPV"]
	assert inflige > 0
	assert res["drain"]["pv"] == inflige // 2
	assert mage["currentPV"] == 20 + inflige // 2


def test_le_drain_ne_compte_pas_l_exces_d_un_coup_mortel():
	"""⚠️ LA règle du drain : 500 dégâts annoncés sur une cible à 5 PV ne rendent que 5."""
	mage = _mage_blesse()
	loup = monstre(x=8, y=5, pv=5)
	doc = combat([mage], [loup])

	res = resolve_action(doc, "sort", cible_id="monstre_0",
						 sort=_vampirique(degats="50D6", drain_pv=100))
	assert res["dmg"] > 5, "le sort inflige bien plus que ce qu'il reste à la cible"
	assert loup["currentPV"] == 0
	assert res["drain"]["pv"] == 5, "on ne draine que les 5 PV réellement pris"
	assert mage["currentPV"] == 25


def test_un_sort_qui_manque_ne_draine_rien(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "randint",
						lambda a, b: 95 if b == 100 else 6)
	mage = _mage_blesse()
	loup = monstre(x=8, y=5, pv=500)
	# ⚠️ Un sort se résout en `magique` par défaut : c'est la `pm_def` qui le pare, jamais
	# l'Ag (qui n'oppose que les jets martiaux `cc`/`cd`).
	loup["pm_def"] = 500
	doc = combat([mage], [loup])

	res = resolve_action(doc, "sort", cible_id="monstre_0", sort=_vampirique())
	assert res["hit"] is False
	assert "drain" not in res
	assert mage["currentPV"] == 20


def test_un_debuff_pur_ne_draine_rien():
	"""Sans dégâts de PV, il n'y a rien à convertir."""
	mage = _mage_blesse()
	doc = combat([mage], [monstre(x=8, y=5, pv=500)])
	res = resolve_action(doc, "sort", cible_id="monstre_0",
						 sort=sort(cout_pm=5, cible="ennemi", portee=6,
								   effets={"buffs": {"Ag": -10}, "duree": 2,
										   "drain_pv": 100}))
	assert "drain" not in res


# ── Drain de PM ─────────────────────────────────────────────────────────────────

def test_le_drain_peut_nourrir_les_pm():
	mage = _mage_blesse()
	loup = monstre(x=8, y=5, pv=500)
	doc = combat([mage], [loup])

	res = resolve_action(doc, "sort", cible_id="monstre_0",
						 sort=_vampirique(drain_pv=0, drain_pm=100))
	inflige = 500 - loup["currentPV"]
	assert res["drain"]["pm"] == inflige
	assert res["drain"]["pv"] == 0


def test_un_sort_peut_drainer_les_deux():
	mage = _mage_blesse()
	loup = monstre(x=8, y=5, pv=500)
	doc = combat([mage], [loup])
	res = resolve_action(doc, "sort", cible_id="monstre_0",
						 sort=_vampirique(drain_pv=50, drain_pm=50))
	assert res["drain"]["pv"] > 0 and res["drain"]["pm"] > 0


# ── Plafond et clamps ───────────────────────────────────────────────────────────

def test_drain_max_plafonne_le_gain():
	mage = _mage_blesse()
	doc = combat([mage], [monstre(x=8, y=5, pv=500)])
	res = resolve_action(doc, "sort", cible_id="monstre_0",
						 sort=_vampirique(degats="20D6", drain_pv=100, drain_max=6))
	assert res["drain"]["pv"] == 6


def test_le_gain_est_clampe_aux_max_du_lanceur():
	"""Un drain ne fait pas déborder une jauge."""
	mage = joueur(pm=60, pv=200, pv_max=200, currentPV=198)
	doc = combat([mage], [monstre(x=8, y=5, pv=500)])
	resolve_action(doc, "sort", cible_id="monstre_0",
				   sort=_vampirique(degats="20D6", drain_pv=100))
	assert mage["currentPV"] == 200


# ── Zones : un seul plafond pour tout le lancement ──────────────────────────────

def _trois_loups():
	return [monstre(idx, x=7 + (idx % 2), y=4 + idx, pv=500) for idx in range(3)]


def test_une_zone_cumule_le_drain_de_toutes_ses_victimes():
	"""Le gain d'une nappe est la SOMME de ce qu'elle prend à chacun."""
	mage = _mage_blesse()
	loups = _trois_loups()
	doc = combat([mage], loups)
	arg = sort(cout_pm=5, cible="ennemi", portee=8, nom="Nappe avide",
			   effets={"degats": "1D6", "drain_pv": 100},
			   zone={"forme": "cercle", "origine": "cible", "rayon": 3})

	res = resolve_action(doc, "sort", cible_id="monstre_0", sort=arg)
	touches = res.get("cibles", [])
	assert len(touches) > 1, "la zone doit bien toucher plusieurs loups"
	inflige_total = sum(500 - m["currentPV"] for m in loups)
	assert res["drain"]["pv"] == inflige_total


def test_drain_max_vaut_une_fois_par_lancement_pas_par_victime():
	"""⚠️ Sinon une zone de cinq ennemis rendrait cinq fois le plafond, et le sort le plus
	large serait aussi le plus nourrissant."""
	mage = _mage_blesse()
	loups = _trois_loups()
	doc = combat([mage], loups)
	arg = sort(cout_pm=5, cible="ennemi", portee=8, nom="Nappe avide",
			   effets={"degats": "20D6", "drain_pv": 100, "drain_max": 10},
			   zone={"forme": "cercle", "origine": "cible", "rayon": 3})

	res = resolve_action(doc, "sort", cible_id="monstre_0", sort=arg)
	assert len(res.get("cibles", [])) > 1, "la zone doit bien toucher plusieurs loups"
	assert res["drain"]["pv"] == 10, "le plafond est celui du SORT"
