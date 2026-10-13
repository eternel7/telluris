"""Frontières entre pays CALÉES (la carte la plus détaillée fait foi) et Calais reposée sur la
carte de France — UN seul fichier d'import (CLAUDE.md §18).

Lance et fusionne, chacun n'émettant que ce qui diffère du dump :
  · `gen_voisins_france` — plaine recalée sur la France (bord nord ET bord droit), Italie recalée sur la France
    puis sur la Pannonie, Pannonie recalée sur la Roumanie (Bulgarie roumaine), passages ;
  · `gen_ports_manche` — Calais sous `lieu:france`, ses sorties, anciens liens supprimés ;
  · `gen_villes_pays` — Afrique du Nord recalée sur l'Égypte, passages.
Recalage : `dev/frontieres_calees.py` ; calage des cartes : `dev/calage_cartes.py` ;
validation visuelle : `dev/superposer_cartes.py --import <ce fichier>`.

Usage :
  python dev/gen_frontieres_calees.py [--dump jsons/telluris-dump-….json]

Sortie : jsons/frontieres_calees_a_importer.json
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_grille_image as ggi  # noqa: E402
from dev import gen_ports_manche, gen_villes_pays, gen_voisins_france  # noqa: E402

SORTIE = os.path.join(ggi.DOSSIER_JSONS, "frontieres_calees_a_importer.json")


def main() -> int:
	args = [a for a in sys.argv[1:] if a != "--sans-apercu"] + ["--sans-apercu"]
	emis, vus = [], set()
	with tempfile.TemporaryDirectory() as tmp:
		for module in (gen_voisins_france, gen_ports_manche, gen_villes_pays):
			module.SORTIE = os.path.join(tmp, module.__name__.rsplit(".", 1)[1] + ".json")
			sys.argv = [module.__file__] + args
			code = module.main()
			if code:
				print(f"✗ {module.__name__} : code {code}, rien n'est écrit.")
				return code
			if os.path.exists(module.SORTIE):
				with open(module.SORTIE, encoding="utf-8") as f:
					for doc in json.load(f):
						if doc["_id"] in vus:
							print(f"✗ {doc['_id']} : produit par les deux générateurs.")
							return 1
						vus.add(doc["_id"])
						emis.append(doc)
	if not emis:
		print("Rien à importer : le dump contient déjà tout.")
		return 0
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(emis, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"\n✎ {os.path.relpath(SORTIE, ggi.RACINE)} — {len(emis)} doc(s) à importer")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
