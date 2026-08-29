# tests/test_facteur_simule.py
# Facteur dégâts/armure ESSAYÉ par le banc d'essai (/admin/simulateur) : il doit changer
# les dérivées le temps d'un run et RIEN d'autre — ni la globale du monde, ni le doc
# CouchDB, ni les combats des joueurs qui tournent en parallèle.

import threading

from models import character_stats
from models.character_stats import BaseStats, compute_derived_stats


def _base(**kwargs):
	defauts = {"v": 5, "f": 40, "r": 40, "ag": 30, "vol": 20, "int_": 20, "cha": 10, "ch": 10}
	defauts.update(kwargs)
	return BaseStats(**defauts)


# ── L'accesseur ──────────────────────────────────────────────────────────────────────

def test_sans_simulation_c_est_la_valeur_du_monde():
	assert character_stats.facteur_degats_armure() == character_stats.FACTEUR_DEGATS_ARMURE


def test_le_bloc_de_simulation_change_la_valeur_puis_la_rend():
	reel = character_stats.FACTEUR_DEGATS_ARMURE
	with character_stats.facteur_degats_armure_simule(10):
		assert character_stats.facteur_degats_armure() == 10
	assert character_stats.facteur_degats_armure() == reel


def test_la_globale_du_monde_n_est_JAMAIS_touchee():
	"""Le cœur de la demande : essayer un facteur ne modifie ni la base ni le jeu.
	`current_world_variables()` (ce que publie /admin) doit rester sur la valeur réelle
	même PENDANT la simulation."""
	reel = character_stats.FACTEUR_DEGATS_ARMURE
	with character_stats.facteur_degats_armure_simule(3):
		assert character_stats.FACTEUR_DEGATS_ARMURE == reel
		assert character_stats.current_world_variables()["FACTEUR_DEGATS_ARMURE"] == reel
	assert character_stats.FACTEUR_DEGATS_ARMURE == reel


def test_une_exception_rend_quand_meme_la_valeur():
	reel = character_stats.FACTEUR_DEGATS_ARMURE
	try:
		with character_stats.facteur_degats_armure_simule(2):
			raise RuntimeError("le run a échoué")
	except RuntimeError:
		pass
	assert character_stats.facteur_degats_armure() == reel


def test_valeurs_inertes_ne_posent_rien():
	"""None, 0, illisible ou la valeur du monde ⇒ comportement d'avant, à l'identique."""
	reel = character_stats.FACTEUR_DEGATS_ARMURE
	for valeur in (None, 0, "", "abc", reel):
		with character_stats.facteur_degats_armure_simule(valeur):
			assert character_stats.facteur_degats_armure() == reel


def test_facteur_nul_ne_divise_jamais_par_zero(monkeypatch):
	"""Deux protections distinctes contre le 0, qui serait une division par zéro dans les
	trois dérivées : le bloc de simulation ne pose rien (testé au-dessus), et l'accesseur
	planche à 1 — y compris si c'est la world-var elle-même qui a été mal saisie."""
	monkeypatch.setattr(character_stats, "FACTEUR_DEGATS_ARMURE", 0)
	assert character_stats.facteur_degats_armure() == 1
	assert compute_derived_stats(_base(), niveau=1).pa >= 0


# ── Effet sur les dérivées ───────────────────────────────────────────────────────────

def test_les_trois_derivees_suivent_le_facteur_simule():
	"""PA, dégâts cc et dégâts cd sont les trois seules dérivées concernées."""
	normal = compute_derived_stats(_base(r=40, f=40, ag=30), niveau=1)
	with character_stats.facteur_degats_armure_simule(10):
		letal = compute_derived_stats(_base(r=40, f=40, ag=30), niveau=1)
	# Facteur deux fois plus petit → bonus et armure deux fois plus gros.
	assert normal.pa == 2 and letal.pa == 4
	assert normal.degats_cc.endswith("+2") and letal.degats_cc.endswith("+4")
	assert normal.degats_cd.endswith("+1") and letal.degats_cd.endswith("+3")


# ── Isolation entre exécutions concurrentes ──────────────────────────────────────────

def test_un_run_ne_contamine_pas_un_combat_parallele():
	"""LE risque que le ContextVar écarte : un joueur qui résout un combat pendant la
	simulation ne doit pas voir ses dégâts changer. Chaque thread a sa copie de contexte
	(un endpoint `def` tourne dans le threadpool), donc le facteur simulé reste chez lui."""
	reel = character_stats.FACTEUR_DEGATS_ARMURE
	vu_par_le_joueur = []
	demarre, fini = threading.Event(), threading.Event()

	def _joueur():
		demarre.wait(timeout=2)
		vu_par_le_joueur.append(character_stats.facteur_degats_armure())
		fini.set()

	fil = threading.Thread(target=_joueur)
	fil.start()
	with character_stats.facteur_degats_armure_simule(3):
		demarre.set()
		fini.wait(timeout=2)
	fil.join(timeout=2)

	assert vu_par_le_joueur == [reel]
