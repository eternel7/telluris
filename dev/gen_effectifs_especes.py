#!/usr/bin/env python
# dev/gen_effectifs_especes.py
# FOURCHETTE D'EFFECTIF des espèces (Auteur, 16/11) : champ `effectif` [min, max] du doc
# `espece:*`, lu par `composition.fourchette` (`combat._instantiate_groupes_composes`) — la NATURE
# de l'espèce fixe la taille du groupe, le budget de menace n'en règle plus que les grades.
#
# Heuristique PAR TAGS (la première règle qui correspond, motif suffixé compris) :
#   boss / géant 1-1 · meute 3-6 · rôdeur (embuscade, furtif) 1-2 · petite taille / vermine 3-8 ·
#   humanoïde 3-6 · sinon 2-3 ; légendaire : au plus 2 ; puis le RANG resserre le max
#   (`RESSERREMENT`, jamais sous le min). Rang = `potentiel.rang_espece` (celui de /admin/table).
#
# Sortie UNIQUE (CLAUDE.md §18) : les espèces dont le champ diffère + `rules:affinites_especes`
# (`gen_affinites_especes.construire`) s'il diffère du dump — la fourchette n'est lue qu'avec lui.
# ⚠️ PUT COMPLET (CLAUDE.md §11) : chaque espèce part ENTIÈRE, relue du dump le plus récent.
# Rejeu sur un dump à jour : plus rien à importer.
#
# Usage : python dev/gen_effectifs_especes.py [--dump jsons/telluris-dump-….json] [--sortie …]

import argparse
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for chemin in (RACINE, os.path.join(RACINE, "dev")):
	if chemin not in sys.path:
		sys.path.insert(0, chemin)
from utils import composition_rencontre as composition  # noqa: E402

SORTIE = "jsons/effectifs_rencontres_a_importer.json"
CHAMP = "effectif"

REGLES = [
	(["boss", "geant"], (1, 1)),
	(["ia_meute"], (3, 6)),
	(["ia_embuscade", "furtif"], (1, 2)),
	(["petite_taille", "vermine"], (3, 8)),
	(["humanoide"], (3, 6)),
]
DEFAUT = (2, 3)
LEGENDAIRE_MAX = 2
# Crans retirés au MAX selon le rang : une bête de haut rang vient moins nombreuse.
RESSERREMENT = {"B": 1, "A": 2, "S": 3, "S+": 3}


def fourchette_pour(tags, rang: str | None) -> list:
	"""[min, max] voulu pour une espèce de ces tags et de ce rang (None : pas de resserrement)."""
	mn, mx = DEFAUT
	for motifs, f in REGLES:
		if composition.tag_correspond(tags or [], motifs):
			mn, mx = f
			break
	if mx > 1 and composition.tag_correspond(tags or [], ["legendaire"]):
		mx = min(mx, LEGENDAIRE_MAX)
		mn = min(mn, mx)
	mx = max(mn, mx - RESSERREMENT.get(rang, 0))
	return [mn, mx]


def delta(especes: list, rangs: dict) -> list:
	"""Espèces dont le champ diffère de la règle, ENTIÈRES, champ posé."""
	out = []
	for doc in especes:
		voulu = fourchette_pour(doc.get("tags"), rangs.get(doc["_id"]))
		if doc.get(CHAMP) != voulu:
			out.append({**doc, CHAMP: voulu})
	return out


def affinites_a_importer(docs: list) -> list:
	"""`[rules:affinites_especes]` s'il diffère de celui du dump (hors `_rev`), sinon []."""
	import gen_affinites_especes as gen_aff
	voulu = gen_aff.construire()
	actuel = next((d for d in docs if d.get("_id") == voulu["_id"]), None)
	if actuel and {k: v for k, v in actuel.items() if k != "_rev"} == voulu:
		return []
	manquantes = gen_aff.controler(voulu, {d.get("_id") for d in docs})
	if manquantes:
		sys.exit(f"Espèces de bande inconnues du dump : {', '.join(manquantes)}")
	return [voulu]


def main() -> None:
	ap = argparse.ArgumentParser()
	ap.add_argument("--dump", default="")
	ap.add_argument("--sortie", default=SORTIE)
	a = ap.parse_args()
	source = a.dump or max(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	docs = json.load(open(source, encoding="utf-8"))["docs"]
	print(f"Dump : {os.path.relpath(source, RACINE)}")
	import gen_armure_naturelle as gen_arm
	rangs, erreurs = gen_arm.rangs_du_dump(docs)
	for e in erreurs:
		print(f"⚠️ rang illisible : {e}")
	especes = sorted((d for d in docs if isinstance(d, dict) and d.get("type") == "espece"),
					 key=lambda d: d["_id"])
	sortie = delta(especes, rangs) + affinites_a_importer(docs)
	ids = [d["_id"] for d in sortie]
	if len(ids) != len(set(ids)):
		sys.exit("Collision d'_id dans la sortie.")
	chemin = os.path.join(RACINE, a.sortie)
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")
	compte: dict = {}
	for d in sortie:
		if CHAMP in d:
			cle = f"{d[CHAMP][0]}-{d[CHAMP][1]}"
			compte[cle] = compte.get(cle, 0) + 1
	print(f"{len(especes)} espèces, {len(sortie)} docs → {a.sortie}")
	print("Fourchettes : " + ", ".join(f"{k} × {v}" for k, v in sorted(compte.items())))


if __name__ == "__main__":
	main()
