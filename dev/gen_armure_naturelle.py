#!/usr/bin/env python
# dev/gen_armure_naturelle.py
# ARMURE NATURELLE des espèces de rang élevé (Auteur, 15/11) : champ `armure_naturelle` (entier)
# du doc `espece:*`, ajouté par le moteur à `R // FACTEUR_DEGATS_ARMURE`
# (`utils.combat.armure_naturelle_espece`), cumulé aux pièces d'un humanoïde armé.
#
# Barème — le RANG de l'espèce (`potentiel.rang_espece`, celui de /admin/table) :
#   F, E, D : 0 · C : +1 · B : +2 · A : +3 · S : +4 · S+ : +5
# puis, à partir du rang C seulement, la NATURE : +1 pour une bête cuirassée (`TAGS_CUIRASSE`),
# −1 pour une créature sans corps solide (`TAGS_SANS_CORPS`) ; jamais sous 0.
#
# ⚠️ Le rang est mesuré SANS le champ (retiré avant le calcul) : l'armure relève la menace, donc
# le rang mesuré avec elle pourrait monter d'un cran à chaque relance. Régénération idempotente.
#
# ⚠️ PUT COMPLET à l'import (CLAUDE.md §11) : chaque espèce est RELUE du dump le plus récent et
# seul `armure_naturelle` y est posé, changé ou retiré. Le fichier ne porte que le DELTA.
#
# Usage : python dev/gen_armure_naturelle.py [--dump jsons/telluris-dump-….json] [--sortie …]
# Sortie : jsons/armure_naturelle_a_importer.json
# ⚠️ Après l'import, redémarrer le serveur : le potentiel (XP, prix des dépouilles) est mémoïsé
# par process.

import argparse
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RACINE not in sys.path:
	sys.path.insert(0, RACINE)
SORTIE = "jsons/armure_naturelle_a_importer.json"
CHAMP = "armure_naturelle"

BAREME = {"C": 1, "B": 2, "A": 3, "S": 4, "S+": 5}
TAGS_CUIRASSE = ("draconique", "reptile", "construct", "geant", "elementaire")
TAGS_SANS_CORPS = ("incorporel", "esprit")


def bonus_armure(rang: str, tags) -> int:
	"""PA naturels à poser pour une espèce de ce rang et de ces tags (0 = aucun champ)."""
	base = BAREME.get(rang, 0)
	if not base:
		return 0
	tags = set(tags or [])
	nature = (1 if tags & set(TAGS_CUIRASSE) else 0) - (1 if tags & set(TAGS_SANS_CORPS) else 0)
	return max(0, base + nature)


def avec_armure(doc: dict, armure: int) -> dict:
	"""Copie du doc avec le champ posé (ou retiré si 0) — aucune autre clé ne bouge."""
	out = {k: v for k, v in doc.items() if k != CHAMP}
	if armure > 0:
		out[CHAMP] = armure
	return out


def delta(especes: list, rangs: dict) -> list:
	"""Docs à importer : les espèces dont le champ diffère de la règle. `rangs` = _id → rang ;
	une espèce sans rang lisible est laissée telle quelle."""
	out = []
	for doc in especes:
		rang = rangs.get(doc["_id"])
		if rang is None:
			continue
		voulu = bonus_armure(rang, doc.get("tags"))
		actuel = doc.get(CHAMP)
		if (voulu == 0 and CHAMP not in doc) or actuel == voulu:
			continue
		out.append(avec_armure(doc, voulu))
	return out


def _dump_le_plus_recent() -> str:
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		raise SystemExit("ERREUR : aucun jsons/telluris-dump-*.json — exporter la base d'abord.")
	return dumps[-1]


def charger(chemin: str) -> list:
	with open(chemin, encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


def rangs_du_dump(docs: list) -> tuple[dict, list]:
	"""`(_id → rang, erreurs)` mesurés par le moteur sur les docs du dump, espèces SANS champ."""
	par_id = {d["_id"]: d for d in docs if isinstance(d, dict) and d.get("_id")}
	for i, d in list(par_id.items()):
		if d.get("type") == "espece" and CHAMP in d:
			par_id[i] = {k: v for k, v in d.items() if k != CHAMP}

	def get_doc(i, *a, **k):
		return par_id.get(i)

	import db.config as cfg
	cfg.get_doc = get_doc
	cfg.find_docs = lambda *a, **k: []
	from models import character_stats
	character_stats.load_world_variables()
	from utils import potentiel
	# Tout module qui a importé `get_doc` par son nom garde l'original : on le remplace partout.
	for module in list(sys.modules.values()):
		if getattr(module, "__name__", "").startswith(("utils.", "routers.")) and hasattr(module, "get_doc"):
			module.get_doc = get_doc
	rangs, erreurs = {}, []
	for i, d in par_id.items():
		if d.get("type") != "espece":
			continue
		try:
			rangs[i] = potentiel.rang_espece(i, get_doc)["rang"]
		except Exception as e:  # une espèce qui ne se construit pas : signalée, laissée telle quelle
			erreurs.append(f"{i} : {e}")
	return rangs, erreurs


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("--dump", default="")
	parser.add_argument("--sortie", default=SORTIE)
	args = parser.parse_args()
	source = args.dump or _dump_le_plus_recent()
	docs = charger(source)
	print(f"Dump : {os.path.relpath(source, RACINE)}")
	rangs, erreurs = rangs_du_dump(docs)
	especes = sorted((d for d in docs if isinstance(d, dict) and d.get("type") == "espece"),
					 key=lambda d: d["_id"])
	sortie = delta(especes, rangs)

	chemin = os.path.join(RACINE, args.sortie)
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")
	compte: dict = {}
	for d in sortie:
		compte[d.get(CHAMP, 0)] = compte.get(d.get(CHAMP, 0), 0) + 1
	print(f"{len(especes)} espèces, {len(sortie)} à importer → {args.sortie}")
	for pa in sorted(compte):
		print(f"   +{pa} PA : {compte[pa]}" if pa else f"   retrait : {compte[pa]}")
	for d in sortie:
		print(f"   {d['_id']:<45} {rangs[d['_id']]:<3} +{d.get(CHAMP, 0)}")
	if erreurs:
		print("⚠ Espèces sans rang lisible (laissées telles quelles) :")
		for e in erreurs:
			print("   " + e)


if __name__ == "__main__":
	main()
