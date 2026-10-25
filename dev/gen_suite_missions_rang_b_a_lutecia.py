#!/usr/bin/env python
# dev/gen_suite_missions_rang_b_a_lutecia.py
# Suite des épreuves des rangs B et A de Lutecia (PR 184), posée sur les docs déjà en jeu :
#   · images DÉFINITIVES — image des lieux neufs, portrait de leurs PNJ (doc `pnj:*` et entrée
#     `pnj` du lieu), grille du labyrinthe, portrait des protégés des escortes de Maëlys ;
#   · puits de Chartres ouvert à tout rang B ou plus de Lutecia, mission ou non (Auteur, 25/10) :
#     barrière `acces` du labyrinthe et dialogue du Templier de la crypte.
#
# Source unique des valeurs : dev/gen_missions_rang_b_a_lutecia.py (`IMAGES`, `PORTRAITS`,
# `GRILLE_LABY`, images des `PROTEGES_*`, docs générés pour `acces` et `dialogue`). Ce script n'en
# recopie aucune : il relit le DERNIER dump et n'injecte que ces champs. Tout le reste du doc vient
# du dump : une porte recalée dans /admin/editor depuis l'import de la PR 184 n'est pas ramenée à
# sa position générée (PUT complet, CLAUDE.md §11).
#
# ⚠️ UN SEUL FICHIER À IMPORTER (CLAUDE.md §18), le DELTA seul : les docs que l'injection change.
# Rejoué sur un dump qui porte déjà ces champs : rien à écrire.
#
# Usage : python dev/gen_suite_missions_rang_b_a_lutecia.py [jsons/telluris-dump-….json]

import copy
import importlib.util
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "suite_missions_rang_b_a_lutecia_a_importer.json")


def _gen():
	chemin = os.path.join(RACINE, "dev", "gen_missions_rang_b_a_lutecia.py")
	spec = importlib.util.spec_from_file_location("gen_missions_rang_b_a_lutecia", chemin)
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod


GEN = _gen()
LIEUX = (GEN.HOTEL, GEN.CHAPELLE, GEN.PORTE_MARS, GEN.ENCLOS, GEN.CRYPTE)
PROTEGES = [GEN.PROTEGE_HUGUES] + GEN.PROTEGES_AMPOULE + GEN.PROTEGES_DELEGATION


def _portraits_des_entrees(lieu):
	for entree in lieu.get("pnj") or []:
		if entree.get("character") in GEN.PORTRAITS:
			entree["portrait"] = GEN.PORTRAITS[entree["character"]]


def _images_des_proteges(maelys):
	images = {(p["prenom"], p["nom"]): p["image"] for p in PROTEGES}
	for entree in (maelys.get("services") or {}).get("escorte", {}).get("offres") or []:
		for protege in entree.get("offre", {}).get("proteges") or []:
			cle = (protege.get("prenom"), protege.get("nom"))
			if cle in images:
				protege["image"] = images[cle]


def appliquer(par_id):
	"""Docs du dump modifiés par l'injection (copies, sans `_rev`), dans un ordre stable."""
	requis = (GEN.MAELYS, GEN.LABYRINTHE) + LIEUX + tuple(GEN.PORTRAITS)
	absents = [i for i in requis if i not in par_id]
	if absents:
		sys.exit("ERREUR : absents du dump (importer d'abord la PR 184) : " + ", ".join(absents))
	generes = {d["_id"]: d for d in GEN.generer(par_id)}
	sortie = []

	def garder(avant, apres):
		if apres != avant:
			sortie.append(GEN.sans_rev(apres))

	for lid in LIEUX:
		lieu = copy.deepcopy(par_id[lid])
		lieu["image"] = GEN.IMAGES[lid]
		_portraits_des_entrees(lieu)
		garder(par_id[lid], lieu)

	laby = copy.deepcopy(par_id[GEN.LABYRINTHE])
	laby["image"] = GEN.IMAGES[GEN.LABYRINTHE]
	# ⚠️ `dimensions` / `cells` ne sont plus posés ici : le puits devenu donjon à étages (Auteur,
	# 25/10) a rouvert la fosse, et c'est dev/gen_portail_notre_dame.py qui porte la grille —
	# un seul fichier par demande (CLAUDE.md §18). Cette suite-ci est importée (dump du 25/10).
	# `nav` non plus : remis à {} à la migration 30×20 → 30×16, il porte depuis les murs peints
	# dans /admin/editor — le réécrire les effacerait.
	laby["acces"] = copy.deepcopy(generes[GEN.LABYRINTHE]["acces"])
	garder(par_id[GEN.LABYRINTHE], laby)

	for pid, portrait in GEN.PORTRAITS.items():
		pnj = copy.deepcopy(par_id[pid])
		pnj["portrait"] = portrait
		# Le dialogue du Templier de la crypte (descente au treuil) : dev/gen_portail_notre_dame.py.
		garder(par_id[pid], pnj)

	maelys = copy.deepcopy(par_id[GEN.MAELYS])
	_images_des_proteges(maelys)
	garder(par_id[GEN.MAELYS], maelys)
	return sortie


def main(argv):
	dump = GEN.charger(GEN.dernier_dump(argv))
	docs = appliquer({d["_id"]: d for d in dump["docs"]})
	GEN.ecrire(SORTIE, docs)
	print(f"{len(docs)} docs → {os.path.relpath(SORTIE, RACINE)}")
	for d in docs:
		print("  ", d["_id"])


if __name__ == "__main__":
	main(sys.argv)
