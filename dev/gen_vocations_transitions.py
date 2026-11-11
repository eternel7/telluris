#!/usr/bin/env python
# dev/gen_vocations_transitions.py
# `rules:vocations_transitions` = {id: [ids]} : vers quelles vocations NOUVELLES on peut passer
# depuis chacune (utils/vocations.py ; le retour vers une vocation déjà connue est libre).
# Repris À LA LETTRE des lignes « Transitions → … » de la page d'accueil (templates/
# home_telluris.html, Auteur), qui le relit désormais au lieu de les écrire en dur.
# ⚠️ Rien à voir avec `rules:vocations_proximity`, réservé au choix des PORTRAITS.
#
# Contrôles : chaque id (source et cible) existe dans `rules:vocations` du dump, aucune
# boucle sur soi, toutes les vocations ont une entrée. Doc écrit seulement s'il diffère de
# celui du dump (PUT complet de `admin_import_bulk`).
#
# Usage : python dev/gen_vocations_transitions.py
# Sortie (/admin → Import en masse) : jsons/vocations_transitions_a_importer.json

import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from utils.vocations import TRANSITIONS_DOC_ID  # noqa: E402

SORTIE = "jsons/vocations_transitions_a_importer.json"

# Ordre des cibles = celui de la page d'accueil (« Mage de batailles » = `mage`).
TRANSITIONS = {
	"guerrier":      ["paladin", "repurgateur", "templier"],
	"barbare":       ["druide", "forestier", "moine"],
	"forestier":     ["barbare", "elementaliste", "voleur"],
	"duelliste":     ["assassin", "illusionniste", "menestrel"],
	"moine":         ["barbare", "druide", "chaman"],
	"elementaliste": ["druide", "forestier", "lettre", "mage"],
	"mage":          ["duelliste", "necromancien", "templier", "demoniste"],
	"illusionniste": ["assassin", "duelliste", "lettre"],
	"lettre":        ["menestrel", "moine", "pretre"],
	"druide":        ["chaman", "elementaliste", "forestier"],
	"chaman":        ["druide", "moine", "elementaliste"],
	"pretre":        ["elementaliste", "paladin", "demoniste"],
	"paladin":       ["guerrier", "pretre", "templier"],
	"templier":      ["guerrier", "mage", "repurgateur"],
	"repurgateur":   ["guerrier", "necromancien", "paladin", "demoniste"],
	"necromancien":  ["moine", "pretre", "repurgateur", "demoniste"],
	"assassin":      ["duelliste", "necromancien", "voleur", "demoniste"],
	"voleur":        ["assassin", "illusionniste", "menestrel"],
	"menestrel":     ["illusionniste", "lettre", "voleur"],
	"demoniste":     ["necromancien", "repurgateur", "illusionniste"],
}


def doc_transitions() -> dict:
	return {"_id": TRANSITIONS_DOC_ID, "type": "rules",
			"value": {k: list(v) for k, v in TRANSITIONS.items()}}


def erreurs(vocations_ids: set) -> list:
	out = []
	for src, cibles in TRANSITIONS.items():
		if src not in vocations_ids:
			out.append(f"source `{src}` absente de rules:vocations")
		for c in cibles:
			if c not in vocations_ids:
				out.append(f"{src} → `{c}` absente de rules:vocations")
			if c == src:
				out.append(f"{src} → lui-même")
		if len(set(cibles)) != len(cibles):
			out.append(f"{src} : cible en double")
	for v in sorted(vocations_ids - set(TRANSITIONS)):
		out.append(f"vocation `{v}` sans entrée de transitions")
	return out


def delta(base: dict) -> list:
	ids = {str(v.get("id")) for v in (base.get("rules:vocations") or {}).get("value") or []}
	probs = erreurs(ids)
	if probs:
		raise SystemExit("ERREUR :\n  " + "\n  ".join(probs))
	doc = doc_transitions()
	existant = {k: v for k, v in (base.get(doc["_id"]) or {}).items() if k != "_rev"}
	return [] if existant == doc else [doc]


def main() -> None:
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		raise SystemExit("ERREUR : aucun jsons/telluris-dump-*.json — exporter la base d'abord.")
	with open(dumps[-1], encoding="utf-8") as f:
		base = {d["_id"]: d for d in json.load(f)["docs"]}
	sortie = delta(base)
	with open(os.path.join(RACINE, SORTIE), "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"{len(sortie)} doc(s) -> {SORTIE} (dump {os.path.basename(dumps[-1])})")


if __name__ == "__main__":
	main()
