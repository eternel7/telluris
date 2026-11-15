#!/usr/bin/env python
# dev/gen_tag_distance.py
# Tag `distance` des espèces QUI TIRENT (Auteur, 15/11) : une espèce dont la liste `items` porte
# une arme de TIR (item `categorie: arme` tagué `tir` : arcs, arbalètes, sarbacane) reçoit le
# tag `distance`, qui ouvre les profils restreints `distance` (tireur, archer… : `zones.profil_compatible`)
# et donc le rôle « distance » de la composition des rencontres (`composition_rencontre.role`).
# Les armes de JET (`jet` : javelots, haches de lancer, bolas…) ne comptent pas.
#
# N'AJOUTE que le tag (jamais de retrait). ⚠️ PUT COMPLET à l'import (CLAUDE.md §11) : chaque
# espèce est RELUE du dump le plus récent, seul `tags` change ; le fichier ne porte que le DELTA,
# régénération idempotente.
#
# Usage : python dev/gen_tag_distance.py [--dump jsons/telluris-dump-….json] [--sortie …]
# Sortie : jsons/tag_distance_a_importer.json
# ⚠️ Après l'import, redémarrer le serveur : le potentiel (XP, coût en budget) est mémoïsé par process.

import argparse
import glob
import json
import os

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = "jsons/tag_distance_a_importer.json"
TAG = "distance"
TAG_ARME_TIR = "tir"


def arme_de_tir(item: dict | None) -> bool:
	return bool(item) and item.get("categorie") == "arme" and TAG_ARME_TIR in (item.get("tags") or [])


def tire(espece: dict, items: dict) -> bool:
	"""L'espèce porte-t-elle au moins une arme de tir dans `items` ? (`items` : _id → doc)."""
	return any(arme_de_tir(items.get(i)) for i in espece.get("items") or [])


def delta(especes: list, items: dict) -> list:
	"""Espèces qui tirent sans encore porter le tag, copiées avec le tag AJOUTÉ en fin de liste."""
	out = []
	for e in especes:
		tags = list(e.get("tags") or [])
		if TAG not in tags and tire(e, items):
			out.append({**e, "tags": tags + [TAG]})
	return out


def main():
	ap = argparse.ArgumentParser()
	ap.add_argument("--dump", default=None)
	ap.add_argument("--sortie", default=SORTIE)
	a = ap.parse_args()
	dump = a.dump or max(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	docs = json.load(open(dump, encoding="utf-8"))["docs"]
	items = {d["_id"]: d for d in docs if d["_id"].startswith("item:")}
	especes = sorted((d for d in docs if d["_id"].startswith("espece:")), key=lambda d: d["_id"])
	sortie = delta(especes, items)
	with open(os.path.join(RACINE, a.sortie), "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"{a.sortie} : {len(sortie)} espèce(s) — " + ", ".join(d["_id"][7:] for d in sortie))


if __name__ == "__main__":
	main()
