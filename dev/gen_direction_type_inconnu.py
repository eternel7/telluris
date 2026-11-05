#!/usr/bin/env python
# dev/gen_direction_type_inconnu.py
# La recherche PAR TYPE du service `direction` couvre tous les lieux de la ville
# (`transport.lieux_par_type` : temples, auberges, guilde, portes…), plus seulement les
# magasins : le refus `type_inconnu` ne parle donc plus de « magasin de ce type ».
#
# Texte de référence : `gen_direction_marchands.NOEUDS_DIALOGUE_DIRECTION` (source unique).
# Ne touche QUE le texte du nœud `type_inconnu` de chaque PNJ qui porte le service `direction` :
# tout le reste du doc est relu du dump le plus récent (PUT complet, CLAUDE.md §11).
# Delta seul (§18) → jsons/direction_type_inconnu_a_importer.json. Rejouable : un second
# passage ne change rien.
#
# Usage : python dev/gen_direction_type_inconnu.py

import copy
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_direction_marchands as direction  # noqa: E402

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "direction_type_inconnu_a_importer.json")

TEXTE = direction.NOEUDS_DIALOGUE_DIRECTION[direction.NOEUDS_DIRECTION["type_inconnu"]]["texte"]


def dernier_dump():
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		sys.exit("ERREUR : aucun dump jsons/telluris-dump-*.json")
	with open(dumps[-1], encoding="utf-8") as f:
		return json.load(f)["docs"], os.path.basename(dumps[-1])


def noeud_type_inconnu(doc):
	"""Id du nœud `type_inconnu` du service `direction` de `doc`, ou None."""
	conf = ((doc or {}).get("services") or {}).get("direction") or {}
	return (conf.get("noeuds") or {}).get("type_inconnu")


def appliquer(doc):
	"""Copie de `doc`, texte du refus par type remplacé. Idempotent."""
	doc = copy.deepcopy(doc)
	nid = noeud_type_inconnu(doc)
	noeud = ((doc.get("dialogue") or {}).get("noeuds") or {}).get(nid)
	if noeud is not None:
		noeud["texte"] = TEXTE
	return doc


def modifies(docs):
	"""Docs qui changent par rapport à `docs` (sans `_rev`)."""
	sortie = []
	for doc in sorted(docs, key=lambda d: d.get("_id", "")):
		if not noeud_type_inconnu(doc):
			continue
		apres = appliquer(doc)
		if apres != doc:
			apres.pop("_rev", None)
			sortie.append(apres)
	return sortie


def main():
	docs, nom_dump = dernier_dump()
	sortie = modifies(docs)
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"{len(sortie)} PNJ modifiés (dump {nom_dump}) → {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
	main()
