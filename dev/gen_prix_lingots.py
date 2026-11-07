#!/usr/bin/env python
# dev/gen_prix_lingots.py
# Prix des lingots précieux : une montée DOUCE vers l'adamantite.
#
# Avant (cuivre) : argent 2 000 → mithril 10 000 (×5) → orichalque 20 000 (×2) → adamantite
# 200 000 (×10). Le dernier palier triplait d'un coup ce que les deux précédents avaient monté.
# L'adamantite reste à 20 or (Auteur, 07/11 : « très élevé mais correct ») ; mithril et
# orichalque montent sur une progression GÉOMÉTRIQUE de raison √5 ≈ ×2,24 qui y aboutit :
# 4 or → 9 or → 20 or. Le saut argent → mithril (×20) est celui du métal commun au métal
# légendaire, assumé.
#
# Seul le champ `valeur` est touché (CLAUDE.md §11) : relit le dump le plus récent, n'écrit que
# les docs qui CHANGENT → jsons/prix_lingots_a_importer.json. Base à jour ⇒ aucun fichier.
# ⚠️ Les variantes sur mesure déjà créées gardent leur `valeur` figée : `dev/gen_prix_variantes.py`
# les réaligne si on le souhaite.
#
# Usage : python dev/gen_prix_lingots.py

import copy
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "prix_lingots_a_importer.json")

PRIX = {
	"item:mithril": [{"or": 4}],
	"item:orichalque": [{"or": 9}],
	"item:adamantite": [{"or": 20}],   # inchangé : borne haute de la progression
}


def dernier_dump():
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		sys.exit("ERREUR : aucun dump jsons/telluris-dump-*.json")
	with open(dumps[-1], encoding="utf-8") as f:
		return {d["_id"]: d for d in json.load(f)["docs"]}, os.path.basename(dumps[-1])


def diff(docs):
	"""Docs du dump dont la `valeur` diffère de la table, corrigés (copies, `_rev` retiré)."""
	sortie = []
	for iid, valeur in PRIX.items():
		if iid not in docs:
			sys.exit(f"ERREUR : {iid} absent du dump")
		if docs[iid].get("valeur") == valeur:
			continue
		doc = copy.deepcopy(docs[iid])
		doc.pop("_rev", None)
		doc["valeur"] = valeur
		sortie.append(doc)
	return sortie


def main():
	docs, nom = dernier_dump()
	sortie = diff(docs)
	print(f"Dump : {nom}")
	if not sortie:
		print("Base à jour : aucun fichier écrit.")
		return
	for d in sortie:
		print(f"  {d['_id']} : {docs[d['_id']].get('valeur')} → {d['valeur']}")
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
	print(f"{len(sortie)} doc(s) → {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
	main()
