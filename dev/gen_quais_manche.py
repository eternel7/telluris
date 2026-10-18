"""Quais de Calais et de Douvres : plusieurs accès sur le pourtour du port.

Chaque quai (`lieu:calais_quais`, `lieu:douvres_quais`, où se tient le capitaine de la
traversée) n'avait qu'UNE connexion depuis la cité (`link:quai01_to_*`) : on longeait les
bassins sans le trouver. On en pose une par tronçon de quai dessiné — même forme que
`quai01` (pas de label : le bouton reprend celui du lieu), `_id` `link:quaiNN_to_<cité>`.

Refus avant toute écriture : case ≠ 1, case que les rues ne relient pas à `quai01`,
case déjà prise par une autre connexion de la cité, `_id` en collision.

Usage :
  python dev/gen_quais_manche.py [--dump jsons/telluris-dump-….json]

Sortie : jsons/quais_manche_a_importer.json (ÉMIS = ce qui diffère du dump : un rejeu sur un
dump à jour n'écrit rien). ⚠️ Import = PUT COMPLET (CLAUDE.md §11).
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_grille_image as ggi  # noqa: E402
from dev.gen_calais_remparts import atteint  # noqa: E402
from dev.gen_voisins_france import a_emettre  # noqa: E402

SORTIE = os.path.join(ggi.DOSSIER_JSONS, "quais_manche_a_importer.json")

# Cases de quai lues sur l'image de la cité (grille 88×48), une par tronçon de quai ;
# `quai01` (connexion existante) reste la première.
QUAIS = (
	{"cite": "lieu:calais", "quai": "lieu:calais_quais", "existant": (36, 19),
	 "cases": ((30, 17),     # quai nord-ouest du bassin
			   (37, 17),     # angle nord-est
			   (36, 21),     # quai est, sous l'existant
			   (33, 25),     # quai sud
			   (30, 25))},   # angle sud-ouest
	{"cite": "lieu:douvres", "quai": "lieu:douvres_quais", "existant": (60, 24),
	 "cases": ((50, 27),     # quai ouest
			   (56, 22),     # quai nord, côté ouest
			   (66, 22),     # quai nord, côté est
			   (70, 26),     # jetée est
			   (56, 33))},   # quai sud
)
META = {"type": "quai", "status": "ouvert"}


def slug_cite(cite_id):
	return cite_id.split(":", 1)[1]


def construire(docs):
	"""(sortants, refus) — les connexions `quai02…` de chaque cité."""
	par_id = {d.get("_id"): d for d in docs}
	sortants, refus = [], []
	for q in QUAIS:
		cite = par_id.get(q["cite"])
		if not cite or q["quai"] not in par_id:
			refus.append(f"{q['cite']} / {q['quai']} : absent du dump")
			continue
		cells, nav = cite["cells"], cite.get("nav") or {}
		joint = atteint(cells, nav, q["existant"])
		prises = {tuple(n["pos"]): d["_id"] for d in docs if d.get("type") == "connection"
				  for n in d.get("nodes", []) if n.get("lieu") == q["cite"]}
		for i, (x, y) in enumerate(q["cases"], start=2):
			_id = f"link:quai{i:02d}_to_{slug_cite(q['cite'])}"
			if cells[y][x] != 1:
				refus.append(f"{_id} : case {[x, y]} = {cells[y][x]}, pas 1")
			elif (x, y) not in joint:
				refus.append(f"{_id} : case {[x, y]} non reliée par les rues à {list(q['existant'])}")
			if (x, y) in prises and prises[(x, y)] != _id:
				refus.append(f"{_id} : case {[x, y]} déjà prise par {prises[(x, y)]}")
			ancien = par_id.get(_id)
			if ancien and not any(n.get("lieu") == q["quai"] for n in ancien.get("nodes", [])):
				refus.append(f"{_id} : _id déjà pris par une autre connexion")
			sortants.append({"_id": _id, "type": "connection",
							 "nodes": [{"lieu": q["cite"], "pos": [x, y]},
									   {"lieu": q["quai"], "pos": [0, 0]}],
							 "metadata": dict(META)})
	return sortants, refus


def main() -> int:
	args = sys.argv[1:]
	chemin_dump = None
	if "--dump" in args:
		i = args.index("--dump")
		if i + 1 >= len(args):
			print("✗ --dump attend un chemin.")
			return 2
		chemin_dump = args[i + 1]
	docs = ggi.charger_dump(chemin_dump)
	if not docs:
		print("✗ aucun dump : passer --dump ou exporter un telluris-dump-*.json dans jsons/.")
		return 1
	sortants, refus = construire(docs)
	emis, refus_emis = a_emettre(docs, sortants)
	for r in refus + refus_emis:
		print(f"✗ {r}")
	if refus or refus_emis:
		print("✗ lot refusé : rien n'est écrit.")
		return 1
	if not emis:
		print("Rien à importer : le dump contient déjà tout.")
		return 0
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(emis, f, ensure_ascii=False, indent=2)
		f.write("\n")
	for d in emis:
		print(f"  {d['_id']} : {d['nodes'][0]['pos']}")
	print(f"✎ {os.path.relpath(SORTIE, ggi.RACINE)} — {len(emis)} doc(s) à importer")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
