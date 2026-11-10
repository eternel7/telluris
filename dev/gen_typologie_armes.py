#!/usr/bin/env python
# dev/gen_typologie_armes.py
# Pose la TYPOLOGIE de précision des armes de corps à corps et de jet :
#   · tag `lourde`  → touche sous (3·F + Ag) // 4
#   · tag `legere`  → touche sous (F + 3·Ag) // 4   (le `cc` d'avant la typologie)
#   · aucun des deux → arme ÉQUILIBRÉE, (2·F + 2·Ag) // 4
# (formules : `models/character_stats.TYPOLOGIE_CC`). Le tir n'est pas concerné (`cd`).
#
# HEURISTIQUE, lue dans la donnée de l'arme (restriction F/Ag, poids moyen, deux mains),
# corrigée par une liste d'EXCEPTIONS explicites (`FORCEES`) :
#   1. restriction Ag > 0 et Ag ≥ F, ou poids ≤ 0,9 kg sans restriction de F → légère ;
#   2. mêlée : poids ≥ 3 kg, restriction F ≥ 20, ou deux mains avec F ≥ 19 → lourde ;
#      jet   : restriction F ≥ 19 ou poids ≥ 2 kg → lourde ;
#   3. sinon équilibrée.
#
# ⚠️ PUT COMPLET à l'import (CLAUDE.md § 11) : on RELIT chaque arme du dump et on n'y touche
# qu'aux deux tags de typologie. Le fichier ne porte que le DELTA (armes dont les tags
# changent) : base à jour ⇒ fichier vide. Relançable à volonté.
#
# Usage : python dev/gen_typologie_armes.py
# Sortie (à coller dans /admin -> Import en masse) : jsons/typologie_armes_a_importer.json

import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from models import character_stats   # noqa: E402

# Figé explicitement pour que régénérer donne toujours le même résultat.
SRC_DUMP = "jsons/telluris-dump-20261108-073417.json"
SORTIE = "jsons/typologie_armes_a_importer.json"

TAG_LOURDE = character_stats.TAG_ARME_LOURDE
TAG_LEGERE = character_stats.TAG_ARME_LEGERE

# Exceptions à l'heuristique, slug (sans `item:`) → "lourde" | "legere" | "equilibree".
FORCEES: dict[str, str] = {
	# Daishō : le katana se manie à une ou deux mains et coupe avec tout le corps ; le
	# wakizashi est la lame d'appoint, au poignet.
	"Katana": "equilibree",
	"Wakizashi": "legere",
	# Sabre à deux mains de 2,5 kg : la règle « deux mains + F ≥ 19 » le manque d'un point.
	"No_dachi": "lourde",
	# Armes d'HAST d'adresse : la restriction d'Ag l'emporte, mais une hampe de 2,4 à 2,6 kg
	# maniée à deux mains n'est pas une lame légère.
	"Naginata": "equilibree",
	"Ji": "equilibree",
	"Pata_a_hampe": "equilibree",
	# Lames de 0,5-0,6 kg qu'une petite restriction de F (15) ferait passer en équilibrées :
	# dague de poing et couteau courbe se manient au poignet.
	"Katar": "legere",
	"Kukri": "legere",
}


def charger(chemin: str) -> list:
	with open(os.path.join(RACINE, chemin), encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


def poids_moyen(doc: dict) -> float:
	p = doc.get("poids") or 0
	if isinstance(p, (list, tuple)):
		return (float(p[0]) + float(p[-1])) / 2 if p else 0.0
	return float(p)


def mode_de(doc: dict) -> str:
	tags = set(doc.get("tags") or [])
	return "tir" if "tir" in tags else "jet" if "jet" in tags else "cac"


def typologie_heuristique(doc: dict) -> str:
	r = doc.get("restriction") or {}
	rf, rag = int(r.get("F", 0) or 0), int(r.get("Ag", 0) or 0)
	poids = poids_moyen(doc)
	if (rag > 0 and rag >= rf) or (poids <= 0.9 and rf == 0):
		return "legere"
	if mode_de(doc) == "jet":
		return "lourde" if rf >= 19 or poids >= 2 else "equilibree"
	if poids >= 3 or rf >= 20 or (doc.get("deux_mains") and rf >= 19):
		return "lourde"
	return "equilibree"


def concernee(doc: dict) -> bool:
	return (doc.get("_id", "").startswith("item:") and doc.get("categorie") == "arme"
			and doc.get("sous_categorie") != "instrument" and mode_de(doc) != "tir")


def main() -> None:
	docs = [d for d in charger(SRC_DUMP) if isinstance(d, dict) and concernee(d)]
	par_slug = {d["_id"][len("item:"):]: d for d in docs}
	absents = [s for s in FORCEES if s not in par_slug]
	if absents:
		sys.exit("ERREUR : exceptions introuvables dans le dump : " + ", ".join(absents))

	sortie, groupes = [], {"lourde": [], "equilibree": [], "legere": []}
	for slug, doc in sorted(par_slug.items(), key=lambda kv: kv[1].get("nom", "")):
		typo = FORCEES.get(slug) or typologie_heuristique(doc)
		groupes[typo].append((mode_de(doc), doc.get("nom", slug), slug in FORCEES))
		tags = [t for t in (doc.get("tags") or []) if t not in (TAG_LOURDE, TAG_LEGERE)]
		if typo == "lourde":
			tags.append(TAG_LOURDE)
		elif typo == "legere":
			tags.append(TAG_LEGERE)
		if tags != list(doc.get("tags") or []):
			sortie.append(dict(doc, tags=tags))

	with open(os.path.join(RACINE, SORTIE), "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")

	print(f"ecrit {SORTIE} : {len(sortie)} arme(s) modifiee(s) sur {len(docs)}")
	for typo, armes in groupes.items():
		for mode in ("cac", "jet"):
			noms = [n + (" *" if f else "") for (m, n, f) in armes if m == mode]
			print(f"\n{typo} / {mode} ({len(noms)}) : {', '.join(noms)}")
	print("\n* = exception forcee (FORCEES)")


if __name__ == "__main__":
	main()
