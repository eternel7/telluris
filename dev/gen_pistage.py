#!/usr/bin/env python
# dev/gen_pistage.py
# Passive « Lecture des traces » du forestier, niveau 0 : clé d'effet `pistage`, agrégée par
# `competences.bonus_passifs`, lue par `utils/traces.pisteur`. Elle REMPLACE l'ancien test
# sur la vocation (`voc == "forestier"`) : la lecture des traces tient désormais à une
# compétence apprise, donc survit à un changement de vocation (les compétences s'empilent).
#
# Niveau 0 = hors de la règle « 2 passives + 5 actives par niveau 1 → 10 » de
# dev/gen_competences_1_10.py : rien à déclarer HORS_COMPTE.
#
# ⚠️ `admin_import_bulk` fait un PUT COMPLET : seul le doc absent du dump le plus récent, ou
# qui en diffère, est écrit — régénération idempotente. Le doc passe les gardes de
# dev/check_competences_doc.py ; rien n'est écrit sinon.
#
# Usage : python dev/gen_pistage.py
# Sortie (/admin → Import en masse) : jsons/competence_pistage_a_importer.json

import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.join(RACINE, "dev"))

import check_competences_doc as check  # noqa: E402

SORTIE = "jsons/competence_pistage_a_importer.json"

# Joueur au NEUTRE (règle de l'Auteur, 16/10).
LECTURE_DES_TRACES = {
	"_id": "competence:lecture_des_traces", "type": "competence", "nom": "Lecture des traces",
	"icon": "🐾",
	"description": "Une empreinte, une branche brisée, une touffe de poils accrochée aux ronces : "
				   "la bête est nommée, et sa force jaugée, avant même d'être vue.",
	"vocation": "forestier", "niveau": 0, "mode": "passive", "effets": {"pistage": 1},
}


def docs_pistage() -> list:
	"""Les docs de la passive de pistage, tels qu'importés (sans `_rev`)."""
	return [dict(LECTURE_DES_TRACES, effets=dict(LECTURE_DES_TRACES["effets"]))]


def _dump_le_plus_recent() -> str:
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		raise SystemExit("ERREUR : aucun jsons/telluris-dump-*.json — exporter la base d'abord.")
	return dumps[-1]


def delta(base: dict) -> list:
	"""Docs neufs ou modifiés par rapport à `base` ({_id: doc}), gardes passées."""
	vocations = {d.get("vocation") for d in base.values() if d.get("type") == "competence"}
	noms = {d.get("nom"): i for i, d in base.items() if d.get("type") == "competence"}
	erreurs, sortie = [], []
	for doc in docs_pistage():
		if doc["vocation"] not in vocations:
			erreurs.append(f"{doc['_id']} : vocation `{doc['vocation']}` inconnue du dump")
		if noms.get(doc["nom"], doc["_id"]) != doc["_id"]:
			erreurs.append(f"{doc['_id']} : nom « {doc['nom']} » déjà porté par {noms[doc['nom']]}")
		erreurs += check.verifier_competence(doc, doc["_id"], niveaux=None)
		existant = {k: v for k, v in (base.get(doc["_id"]) or {}).items() if k != "_rev"}
		if existant != doc:
			sortie.append(doc)
	if erreurs:
		raise SystemExit("ERREUR :\n  " + "\n  ".join(erreurs))
	return sortie


def main() -> None:
	dump = _dump_le_plus_recent()
	with open(dump, encoding="utf-8") as f:
		base = {d["_id"]: d for d in json.load(f)["docs"]}
	sortie = delta(base)
	with open(os.path.join(RACINE, SORTIE), "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"{len(sortie)} compétence(s) → {SORTIE} (dump {os.path.basename(dump)})")


if __name__ == "__main__":
	main()
