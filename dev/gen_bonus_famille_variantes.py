#!/usr/bin/env python
# dev/gen_bonus_famille_variantes.py
# Variantes sur mesure DÉJÀ en base : retire les bonus hors de la famille de la pièce.
#
# Depuis `fabrication.borner_hors_famille`, une armure ne reçoit plus de dégâts d'une matière,
# une arme plus de points d'armure, un bijou ni l'un ni l'autre, un consommable aucun bonus ;
# un bonus que l'objet de base porte déjà reste, plafonné à base × FABRICATION_PLAFOND_HORS_FAMILLE.
# Les variantes créées avant gardaient leurs bonus figés (`assurer_variante` ne retouche jamais
# un doc existant) : ce script leur applique la MÊME fonction, sur leurs valeurs actuelles —
# les matières ne sont pas relues, seul le hors-famille bouge.
#
# Les exemplaires portés ne sont que des RÉFÉRENCES vers le doc `item:*` : corriger le doc
# corrige tous les exemplaires, au prochain recalcul de l'équipement (`/play`, équiper…).
#
# Relit le dump le plus récent, n'écrit que les docs qui CHANGENT (CLAUDE.md §11, §18) →
# jsons/bonus_famille_variantes_a_importer.json. Base à jour ⇒ aucun fichier.
#
# Usage : python dev/gen_bonus_famille_variantes.py

import copy
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from utils import fabrication  # noqa: E402

SORTIE = os.path.join(RACINE, "jsons", "bonus_famille_variantes_a_importer.json")


def dernier_dump():
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		sys.exit("ERREUR : aucun dump jsons/telluris-dump-*.json")
	with open(dumps[-1], encoding="utf-8") as f:
		return {d["_id"]: d for d in json.load(f)["docs"]}, os.path.basename(dumps[-1])


def corrections(docs):
	"""`[(doc corrigé, {clé: (avant, après)})]` pour chaque variante qui change."""
	sortie = []
	for iid, doc in sorted(docs.items()):
		fab = doc.get("fabrication") if iid.startswith("item:") else None
		base_id = fab.get("base_item") if isinstance(fab, dict) else None
		if not base_id:
			continue
		base = docs.get(base_id)
		if base is None:
			print(f"  ⚠ {iid} : objet de base {base_id} absent du dump — ignorée")
			continue
		corrige = copy.deepcopy(doc)
		corrige.pop("_rev", None)
		fabrication.borner_hors_famille(base, corrige)
		ecarts = {k: (doc.get(k), corrige.get(k)) for k in fabrication.CLES_FILTREES_FAMILLE
				  if doc.get(k) != corrige.get(k)}
		if ecarts:
			sortie.append((corrige, ecarts))
	return sortie


def main():
	docs, nom = dernier_dump()
	sortie = corrections(docs)
	print(f"Dump : {nom}")
	if not sortie:
		print("Base à jour : aucun fichier écrit.")
		return
	for doc, ecarts in sortie:
		detail = ", ".join(f"{k} {a} → {b if b is not None else '∅'}" for k, (a, b) in ecarts.items())
		print(f"  {doc['_id']} : {detail}")
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump([d for d, _ in sortie], f, ensure_ascii=False, indent=2)
	print(f"{len(sortie)} doc(s) → {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
	main()
