# tests/test_combat_concentration.py
#
# TEST DE CONCENTRATION : « Lorsqu'un lanceur subit une attaque pendant une incantation, il
# effectue un test de concentration. »
#
#   Réussite critique → l'incantation continue normalement.
#   Réussite          → elle continue, avec une pénalité en PM.
#   Échec             → incantation interrompue.
#   Échec critique    → interrompue ET perte d'une action.
#
# C'est ce qui fait du mage un artilleur que ses alliés doivent protéger — et donc le
# contrepoids de tout le système : sans lui, une incantation longue serait un pur gain.
#
# ⚠️ UN JET PAR OBJET TENU (l'incantation, puis chaque sort maintenu), à l'inverse de la
# règle des zones d'effet où un seul fumble est possible. La multiplication du risque est
# ici la contrepartie ASSUMÉE d'entretenir plusieurs sorts à la fois.

import pytest

from utils import combat as combat_mod
from utils.combat import _armer_incantation, _do_attack_on, _tester_concentration
from _fixtures_magie import combat, joueur, monstre, sort, textes


METEORE = dict(cout_pm=15, incantation=6, cible="ennemi", portee=8, nom="Météore",
			   effets={"degats": "4D6"})
BOUCLIER = dict(cout_pm=5, maintien=4, cible="soi", nom="Bouclier", icon="🛡",
				effets={"buffs": {"R": 10}})


def _jets(monkeypatch, *valeurs):
	"""Force la suite des d100 — le dernier se répète ensuite."""
	suite = list(valeurs)
	def _tirage(a, b):
		return suite.pop(0) if len(suite) > 1 else suite[0]
	monkeypatch.setattr(combat_mod.random, "randint", _tirage)


def _mage_qui_incante(pm=60):
	mage = joueur(pm=pm)
	mage["actions_max"] = mage["actions_restantes"] = 1
	doc = combat([mage], [monstre(x=9, y=5)])
	sdoc = sort(**METEORE)["doc"]
	_armer_incantation(doc, mage, sdoc, sdoc["effets"], "monstre_0", None, None)
	return mage, doc


# ── Les quatre issues, sur une INCANTATION ──────────────────────────────────────

def test_reussite_critique_ne_coute_rien(monkeypatch):
	mage, doc = _mage_qui_incante()
	pm_avant = mage["currentPM"]
	_jets(monkeypatch, 1)                     # dans la fenêtre de réussite critique
	_tester_concentration(doc, mage, monstre(), 10)

	assert mage.get("incantation") is not None
	assert mage["currentPM"] == pm_avant


def test_reussite_tient_au_prix_d_une_tranche_de_pm(monkeypatch):
	"""La pénalité vaut `ceil(cout_pm / incantation)` — 3 PM pour un Météore 15/6 — et non
	le coût entier : un seul coup ne doit pas coûter plus que le sort lui-même."""
	mage, doc = _mage_qui_incante()
	pm_avant = mage["currentPM"]
	_jets(monkeypatch, 50)                    # ni critique, ni fumble, sous le seuil
	_tester_concentration(doc, mage, monstre(), 0)

	assert mage.get("incantation") is not None
	assert mage["currentPM"] == pm_avant - 3
	assert any("tient son incantation" in t for t in textes(doc))


def test_echec_interrompt_l_incantation(monkeypatch):
	mage, doc = _mage_qui_incante()
	_jets(monkeypatch, 90)                    # au-dessus du seuil, sous le fumble
	_tester_concentration(doc, mage, monstre(), 30)

	assert mage.get("incantation") is None
	assert any("perd le fil" in t for t in textes(doc))


def test_echec_critique_interrompt_et_coute_une_action(monkeypatch):
	mage, doc = _mage_qui_incante()
	mage["actions_restantes"] = 2
	_jets(monkeypatch, 100)                   # fenêtre d'échec critique
	_tester_concentration(doc, mage, monstre(), 10)

	assert mage.get("incantation") is None
	assert any("perd pied" in t for t in textes(doc))


def test_les_pm_verses_sont_perdus_a_l_interruption(monkeypatch):
	mage, doc = _mage_qui_incante()
	pm_apres_versement = mage["currentPM"]
	_jets(monkeypatch, 90)
	_tester_concentration(doc, mage, monstre(), 30)
	assert mage["currentPM"] == pm_apres_versement, "aucun remboursement"


# ── Les quatre issues, sur un SORT MAINTENU ─────────────────────────────────────

def _mage_qui_entretient(pm=60):
	from utils.combat import resolve_action
	mage = joueur(pm=pm)
	doc = combat([mage], [monstre(x=9, y=5)])
	resolve_action(doc, "sort", sort=sort(**BOUCLIER))
	return mage, doc


def test_un_sort_maintenu_tient_sur_une_reussite_critique(monkeypatch):
	mage, doc = _mage_qui_entretient()
	pm_avant = mage["currentPM"]
	_jets(monkeypatch, 1)
	_tester_concentration(doc, mage, monstre(), 10)
	assert mage["concentrations"]
	assert mage["currentPM"] == pm_avant


def test_un_sort_maintenu_tient_au_prix_de_son_entretien(monkeypatch):
	mage, doc = _mage_qui_entretient()
	pm_avant = mage["currentPM"]
	_jets(monkeypatch, 50)
	_tester_concentration(doc, mage, monstre(), 0)
	assert mage["concentrations"]
	assert mage["currentPM"] == pm_avant - 4


def test_un_sort_maintenu_tombe_sur_un_echec(monkeypatch):
	mage, doc = _mage_qui_entretient()
	_jets(monkeypatch, 90)
	_tester_concentration(doc, mage, monstre(), 30)
	assert not mage.get("concentrations")
	assert not mage["effets_actifs"]
	assert any("se rompt sous le coup" in t for t in textes(doc))


# ── Un jet PAR objet tenu ───────────────────────────────────────────────────────

def test_un_jet_par_sort_maintenu(monkeypatch):
	"""⚠️ Choix de conception, à l'inverse de la règle des zones : un mage qui tient trois
	sorts est trois fois plus exposé. Ici le premier jet échoue, le second réussit."""
	from utils.combat import resolve_action
	mage = joueur(pm=100)
	doc = combat([mage], [monstre(x=9, y=5)])
	resolve_action(doc, "sort", sort=sort(cout_pm=5, maintien=2, cible="soi",
										  _id="sort:a", nom="Alpha",
										  effets={"buffs": {"R": 5}}))
	resolve_action(doc, "sort", sort=sort(cout_pm=5, maintien=2, cible="soi",
										  _id="sort:b", nom="Beta",
										  effets={"buffs": {"Ag": 5}}))
	assert len(mage["concentrations"]) == 2

	_jets(monkeypatch, 90, 50)                # échec puis réussite
	_tester_concentration(doc, mage, monstre(), 30)
	assert [c["sort_id"] for c in mage["concentrations"]] == ["sort:b"]


def test_rien_a_concentrer_ne_jette_aucun_de(monkeypatch):
	"""Sortie en tête : un combattant ordinaire ne doit pas payer un jet à chaque coup."""
	mage = joueur()
	doc = combat([mage])
	def _interdit(a, b):
		raise AssertionError("aucun jet ne doit être tiré")
	monkeypatch.setattr(combat_mod.random, "randint", _interdit)
	_tester_concentration(doc, mage, monstre(), 10)


# ── Branchement réel : un coup encaissé déclenche le test ───────────────────────

def test_un_coup_de_monstre_menace_l_incantation(monkeypatch):
	"""Branché dans `_do_attack_on`, le seul endroit où un acteur du camp du joueur perd
	des PV sous un coup."""
	mage, doc = _mage_qui_incante()
	loup = doc["monstres"][0]
	loup["pos"] = {"x": 4, "y": 5}
	loup["cc"] = 200                          # le coup porte à coup sûr
	loup["degats_cc"] = "3D6"
	_jets(monkeypatch, 50, 90)                # le coup touche, la concentration lâche

	_do_attack_on(doc, loup, mage)
	assert mage.get("incantation") is None


def test_un_coup_manque_ne_menace_rien(monkeypatch):
	mage, doc = _mage_qui_incante()
	loup = doc["monstres"][0]
	loup["pos"] = {"x": 4, "y": 5}
	mage["ag"] = 500                          # imparable : le monstre ne touchera pas
	_jets(monkeypatch, 90)

	_do_attack_on(doc, loup, mage)
	assert mage.get("incantation") is not None, "pas de coup, pas de test"


def test_un_cout_en_pv_ne_declenche_aucun_test(monkeypatch):
	"""⚠️ Des PV dépensés volontairement ne sont PAS des dégâts subis : c'est un prix payé,
	pas un coup reçu."""
	from utils.combat import _payer_cout_pv
	mage, doc = _mage_qui_incante()
	def _interdit(a, b):
		raise AssertionError("aucun jet de concentration ne doit être tiré")
	monkeypatch.setattr(combat_mod.random, "randint", _interdit)

	_payer_cout_pv(doc, mage, {"nom": "Pacte"}, 10)
	assert mage.get("incantation") is not None
