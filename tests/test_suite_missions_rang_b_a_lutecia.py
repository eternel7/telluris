# tests/test_suite_missions_rang_b_a_lutecia.py
# Suite des épreuves des rangs B et A de Lutecia (dev/gen_suite_missions_rang_b_a_lutecia.py) : images
# définitives et puits ouvert au rang B, rejoués contre le DERNIER dump — delta seul, idempotent,
# fichiers présents, labyrinthe jouable, porte au rang B.

import importlib.util
import json
import os
import random

from utils import acces, combat

RACINE = os.path.join(os.path.dirname(__file__), "..")
RESSOURCES = os.path.join(RACINE, "templates", "resources")


def _gen():
	chemin = os.path.join(RACINE, "dev", "gen_suite_missions_rang_b_a_lutecia.py")
	spec = importlib.util.spec_from_file_location("gen_suite_missions_rang_b_a_lutecia", chemin)
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod


GEN = _gen()
MISSIONS = GEN.GEN
with open(MISSIONS.dernier_dump([]), encoding="utf-8") as _f:
	DUMP = {d["_id"]: d for d in json.load(_f)["docs"]}
DOCS = {d["_id"]: d for d in GEN.appliquer(DUMP)}
LABY = {**DUMP[MISSIONS.LABYRINTHE], **DOCS.get(MISSIONS.LABYRINTHE, {})}


def test_le_fichier_est_a_jour():
	with open(GEN.SORTIE, encoding="utf-8") as f:
		fichier = {d["_id"]: d for d in json.load(f)}
	if DOCS:   # dump d'avant l'import : le fichier est le delta
		assert fichier == DOCS, "relancer dev/gen_suite_missions_rang_b_a_lutecia.py"


def test_regeneration_idempotente():
	apres_import = dict(DUMP)
	apres_import.update(DOCS)
	assert GEN.appliquer(apres_import) == []


def test_le_delta_est_le_doc_genere_par_la_pr():
	"""Mêmes valeurs que le générateur des missions : aucune n'est recopiée ici."""
	generes = {d["_id"]: d for d in MISSIONS.generer(DUMP)}
	for doc_id, doc in DOCS.items():
		assert doc == generes[doc_id], doc_id


def _fichiers(doc):
	if isinstance(doc, dict):
		for cle, val in doc.items():
			if cle in ("image", "portrait") and isinstance(val, str) and val:
				yield val
			else:
				yield from _fichiers(val)
	elif isinstance(doc, list):
		for val in doc:
			yield from _fichiers(val)


def test_chaque_image_existe():
	presents = {f for _r, _d, fs in os.walk(RESSOURCES) for f in fs}
	for doc in list(DOCS.values()) + [LABY]:
		manquants = [f for f in _fichiers(doc) if f not in presents]
		assert not manquants, (doc["_id"], manquants)


def test_cinq_proteges_ont_un_portrait_dans_pnj():
	for p in MISSIONS.PROTEGES_AMPOULE + MISSIONS.PROTEGES_DELEGATION + [MISSIONS.PROTEGE_HUGUES]:
		assert os.path.isfile(os.path.join(RESSOURCES, "pnj", p["image"])), p["prenom"]


def _regions(cells, dims):
	vues, regions = set(), []
	for y in range(dims["y"]):
		for x in range(dims["x"]):
			if cells[y][x] == 1 and (x, y) not in vues:
				r = combat._reachable_region(cells, dims, {}, (x, y))
				vues |= r
				regions.append(r)
	return regions


def test_le_labyrinthe_n_a_qu_une_region_praticable():
	regions = _regions(LABY["cells"], LABY["dimensions"])
	assert len(regions) == 1
	# Deux Minotaures et un groupe plein y tiennent largement (plancher voulu : 100 cases).
	assert len(regions[0]) >= 100


def test_le_puits_et_sa_fosse_ne_sont_pas_du_sol():
	cells = LABY["cells"]
	assert cells[8][14] == 0   # le puits
	assert cells[6][13] == 3   # la fosse violette : falaise, nul n'y naît


def test_placement_du_combat_toujours_dans_la_region():
	grid = {"cells": LABY["cells"], "dims": LABY["dimensions"], "nav": LABY.get("nav") or {}}
	etat = random.getstate()
	try:
		for graine in range(50):
			random.seed(graine)
			doc = {"joueurs": [{"id": f"j{i}"} for i in range(4)],
				   "monstres": [{"id": "m1"}, {"id": "m2"}]}
			combat._place_actors(doc, grid)
			central = (doc["joueurs"][0]["pos"]["x"], doc["joueurs"][0]["pos"]["y"])
			region = combat._reachable_region(grid["cells"], grid["dims"], {}, central)
			poses = [(a["pos"]["x"], a["pos"]["y"]) for a in doc["joueurs"] + doc["monstres"]]
			assert len(set(poses)) == len(poses)
			assert all(p in region and grid["cells"][p[1]][p[0]] == 1 for p in poses)
	finally:
		random.setstate(etat)


def test_le_puits_s_ouvre_au_rang_b_de_lutecia_sans_mission():
	def perso(rang):
		return {"rangs_guilde": {MISSIONS.LUTECIA: rang}, "quetes_actives": [], "quetes_terminees": []}
	assert not acces.acces_autorise(perso("C"), LABY, DUMP.get)[0]
	assert acces.acces_autorise(perso("B"), LABY, DUMP.get)[0]
	assert acces.acces_autorise(perso("S+"), LABY, DUMP.get)[0]
