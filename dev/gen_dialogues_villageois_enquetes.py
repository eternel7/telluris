#!/usr/bin/env python
# dev/gen_dialogues_villageois_enquetes.py
# Villageois d'Escolives et de Dun-les-Places : leurs répliques sur l'enquête ne s'ouvrent que
# quête EN COURS ; AVANT, un simple bonjour ; APRÈS, ce que la quête a changé (Auteur, 15/10).
#
# Les six docs `pnj:*` sont construits par `gen_enquete_escolives` / `gen_enquete_morvan` (source
# unique) ; ce script n'en sort que le DELTA (CLAUDE.md §18) → jsons/dialogues_villageois_enquetes_a_importer.json,
# et les recopie dans les deux fichiers d'import complets des enquêtes, sans régénérer leurs
# autres docs (le bestiaire des vampires a bougé depuis : hors de cette demande).
#
# Usage : python dev/gen_dialogues_villageois_enquetes.py

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_enquete_escolives as escolives  # noqa: E402
import gen_enquete_morvan as morvan  # noqa: E402

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "dialogues_villageois_enquetes_a_importer.json")


def recopier(chemin, docs):
	"""Remplace en place, dans un fichier d'import complet, les docs de même `_id`."""
	with open(chemin, encoding="utf-8") as f:
		contenu = json.load(f)
	par_id = {d["_id"]: d for d in docs}
	manquants = set(par_id) - {d["_id"] for d in contenu}
	if manquants:
		sys.exit(f"ERREUR : {sorted(manquants)} absents de {chemin}")
	escolives.ecrire(chemin, [par_id.get(d["_id"], d) for d in contenu])


def main():
	d_escolives = [escolives.fossoyeur(), escolives.guerisseuse(), escolives.veuve()]
	d_morvan = [morvan.meneuse(), morvan.bergere(), morvan.charbonnier()]
	recopier(escolives.SORTIE, d_escolives)
	recopier(morvan.SORTIE, d_morvan)
	escolives.ecrire(SORTIE, d_escolives + d_morvan)
	print(f"{len(d_escolives) + len(d_morvan)} docs → {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
	main()
