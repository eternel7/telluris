#!/usr/bin/env python
# dev/gen_portrait_aelis_jumieges.py
# Portrait d'Aélis devant les ruines de Jumièges (image de l'Auteur) : remplace le portrait
# générique dans l'épreuve du rang C — l'entrée PNJ du lieu ET le doc `pnj:*` de Jumièges.
#
# DELTA seul (CLAUDE.md §18) : les deux docs RELUS au dernier dump, seul `portrait` change
# (l'import est un PUT complet, §11). La constante vit dans dev/gen_quete_rang_c_jumieges.py,
# qui l'émet aussi : une régénération de l'épreuve ne défait pas ce portrait. Idempotent.
#
# Usage : python dev/gen_portrait_aelis_jumieges.py [jsons/telluris-dump-….json]

import copy
import importlib.util
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "portrait_aelis_jumieges_a_importer.json")


def _epreuve():
	chemin = os.path.join(RACINE, "dev", "gen_quete_rang_c_jumieges.py")
	spec = importlib.util.spec_from_file_location("gen_quete_rang_c_jumieges", chemin)
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod


Q = _epreuve()


def docs(par_id: dict) -> list:
	lieu = copy.deepcopy(par_id[Q.ABBAYE])
	pnj_doc = copy.deepcopy(par_id[Q.AELIS_JUMIEGES])
	for d in (lieu, pnj_doc):
		d.pop("_rev", None)
	entrees = [e for e in lieu.get("pnj") or [] if e.get("character") == Q.AELIS_JUMIEGES]
	if not entrees:
		sys.exit(f"ERREUR : {Q.ABBAYE} ne porte pas l'entrée de {Q.AELIS_JUMIEGES}")
	for e in entrees:
		e["portrait"] = Q.PORTRAIT_AELIS_JUMIEGES
	pnj_doc["portrait"] = Q.PORTRAIT_AELIS_JUMIEGES
	return [lieu, pnj_doc]


def main(argv):
	image = os.path.join(RACINE, "templates", "resources", "pnj", Q.PORTRAIT_AELIS_JUMIEGES)
	if not os.path.isfile(image):
		sys.exit(f"ERREUR : image absente — {os.path.relpath(image, RACINE)}")
	dump = Q.charger(Q.dernier_dump(argv))
	sortie = docs({d["_id"]: d for d in dump["docs"]})
	Q.ecrire(SORTIE, sortie)
	print(f"{len(sortie)} docs → {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
	main(sys.argv)
