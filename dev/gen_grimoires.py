#!/usr/bin/env python
# dev/gen_grimoires.py
# Un GRIMOIRE UNIQUE et sa RECETTE de scriptorium pour tout sort qui n'en a pas.
#
# Un sort sans grimoire ne s'apprend pas (`sorts.grimoire_pour`), et un grimoire sans recette
# n'arrive jamais en rayon : les scriptoriums tirent leur production parmi leurs recettes.
# ⚠️ COUVERT = par un grimoire UNIQUE (`sorts == [sort_id]`) : un sort que seul un grimoire
# multiple cite reçoit quand même le sien. Règle et docs : `utils/grimoires.py`.
#
# Prix et rareté par niveau (`valeur_grimoire`, `rarete_grimoire`) ; matières reprises de la
# recette de grimoire la plus répandue en base. ⚠️ Chaque recette neuve entre au tirage de
# TOUS les scriptoriums.
#
# IDEMPOTENT : un sort couvert, une recette qui produit déjà son grimoire ne sont pas réémis.
# Un `_id` pris par AUTRE CHOSE arrête tout, sans rien écrire — l'import (PUT complet)
# l'écraserait. Sans rien à créer, aucun fichier n'est écrit.
#
# Usage : python dev/gen_grimoires.py [--dump chemin/vers/telluris-dump-*.json]
#         (sans --dump : le dump le plus récent de jsons/)
# Sortie : jsons/grimoires_a_importer.json (📥 Importer depuis /admin/dev-tools)

import argparse
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
DOSSIER_JSONS = os.path.join(RACINE, "jsons")
SORTIE = os.path.join(DOSSIER_JSONS, "grimoires_a_importer.json")

from utils import grimoires  # noqa: E402


def charger_dump(chemin=None) -> dict:
	if chemin:
		print("source : %s" % chemin)
		return json.load(open(chemin, encoding="utf-8"))
	dumps = sorted(
		f for f in os.listdir(DOSSIER_JSONS)
		if f.startswith("telluris-dump-") and f.endswith(".json")
	)
	if not dumps:
		raise SystemExit("Aucun telluris-dump-*.json dans jsons/ — passez --dump.")
	print("source : jsons/%s" % dumps[-1])
	return json.load(open(os.path.join(DOSSIER_JSONS, dumps[-1]), encoding="utf-8"))


def main() -> None:
	# Console Windows en cp1252 : sans cela, le premier accent fait planter le script.
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass

	parser = argparse.ArgumentParser(description="Grimoires uniques manquants")
	parser.add_argument("--dump", help="dump à relire (défaut : le plus récent de jsons/)")
	args = parser.parse_args()

	dump = charger_dump(args.dump)
	base = {d["_id"]: d for d in dump["docs"] if isinstance(d, dict) and d.get("_id")}
	nb_sorts = sum(1 for d in base.values() if d.get("type") == "sort")
	nb_grimoires = sum(1 for d in base.values() if d.get("type") == "item" and grimoires.est_grimoire(d))
	print("%d sort(s), %d grimoire(s) en base" % (nb_sorts, nb_grimoires))

	sans_recette = grimoires.grimoires_sans_recette(base)
	if sans_recette:
		print("\n== Grimoires qu'aucune recette ne produit (jamais en rayon — signalés, rien n'est créé)")
		for gid in sans_recette:
			sorts = base[gid].get("sorts") or []
			print("   %-44s %s" % (gid, ", ".join(sorts) if sorts else "(n'enseigne aucun sort)"))

	print("\n== Grimoires uniques et recettes manquants")
	docs, lignes, erreurs = grimoires.grimoires_manquants(base)
	for ligne in lignes:
		print("   " + ligne)

	if erreurs:
		print("\n⚠️ %d erreur(s) — RIEN n'est écrit :" % len(erreurs))
		for e in erreurs:
			print("   " + e)
		sys.exit(1)

	if not docs:
		print("   tout est couvert : chaque sort a son grimoire unique. Aucun fichier écrit.")
		return

	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print("\nécrit jsons/%s : %d doc(s) — %d grimoire(s), %d recette(s)" % (
		os.path.basename(SORTIE), len(docs),
		sum(1 for d in docs if d["type"] == "item"),
		sum(1 for d in docs if d["type"] == "recette")))


if __name__ == "__main__":
	main()
