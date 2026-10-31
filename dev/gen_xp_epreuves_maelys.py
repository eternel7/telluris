"""XP des épreuves de rang de Maëlys : XP d'origine + tiers du niveau d'entrée du rang visé.

Delta seul : `pnj:maelys` relu du dump, où seul `recompenses.xp` de ses offres de rang change
(PUT complet à l'import, CLAUDE.md §11). Idempotent : part de `XP_ORIGINE`, pas de la valeur en base.

Usage : python dev/gen_xp_epreuves_maelys.py [jsons/telluris-dump-….json]
"""
import copy
import glob
import json
import os
import sys

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, RACINE)

from utils import chasse  # noqa: E402

SORTIE = os.path.join(RACINE, "jsons", "xp_epreuves_maelys_a_importer.json")
MAELYS = "pnj:maelys"
XP_ORIGINE = {"C": 150, "B": 250, "A": 400}


def dernier_dump():
	return max(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))


def generer(par_id):
	doc = copy.deepcopy(par_id[MAELYS])
	doc.pop("_rev", None)
	for service in doc["services"].values():
		for entree in service.get("offres") or []:
			recompenses = entree["offre"]["recompenses"]
			rang = recompenses["rang_guilde"]
			recompenses["xp"] = XP_ORIGINE[rang] + chasse.xp_promotion(rang)
	return [doc]


def main(argv):
	chemin = argv[1] if len(argv) > 1 else dernier_dump()
	with open(chemin, encoding="utf-8") as f:
		par_id = {d["_id"]: d for d in json.load(f)["docs"]}
	docs = generer(par_id)
	with open(SORTIE, "w", encoding="utf-8", newline="\n") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"{len(docs)} doc -> {os.path.relpath(SORTIE, RACINE)} (dump : {os.path.basename(chemin)})")
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv))
