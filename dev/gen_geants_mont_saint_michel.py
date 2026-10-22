#!/usr/bin/env python
# dev/gen_geants_mont_saint_michel.py
# Les géants de la baie du Mont-Saint-Michel, sur la carte de France.
#
# DEUX placements, deux zones numérotées jusque-là inutilisées (aucun lieu ne les portait au
# dump du 22/10) :
#   · `zone:zone_danger_1` sur le MONT lui-même — l'îlot dessiné en (23,14), au bord de la côte
#     murée par `nav` — où vit le Géant du Mont-Saint-Michel, en grade Héros/Seigneur ;
#   · `zone:zone_danger_3` sur l'ARRIÈRE-PAYS, au sud-est de la baie, côté terre : les géants
#     ordinaires (`espece:geant_ou_titan`), en grade Novice/Combattant.
#
# ⚠️ POURQUOI DEUX ZONES ET NON UNE : le grade se tire par PLACEMENT, jamais par espèce
# (`zones.resolve_profil_weights` somme les tables des placements actifs, puis
# `instantiate_monsters` l'applique à toutes les espèces du pool). Une seule zone donnerait
# aux géants ordinaires le même grade que le géant du Mont. Les deux ellipses ne se touchent
# donc pas (verrouillé par tests/test_gen_geants_mont_saint_michel.py), ni la zone très
# dangereuse voisine, dont les Héros/Seigneurs s'additionneraient aux géants.
#
# ⚠️ POURQUOI `zone_danger_1` POUR LE MONT : l'effectif d'un combat aléatoire vaut
# round(intensité × 3) (`routers/combat.start_combat`) ; à 0,4 il n'y a qu'UN monstre — le géant
# est seul sur son rocher, comme dans la légende. À 0,8 (`zone_danger_3`) on en tirerait deux.
#
# ⚠️ GRADES : à profil égal le Géant du Mont est PLUS FAIBLE que le géant ordinaire
# (Seigneur 105 ≈ géant Vétéran 103, `potentiel.potentiel_espece`). Les géants de l'arrière-pays
# s'arrêtent donc à Combattant (≈ 66) pour rester nettement sous le maître du Mont (101-105).
#
# Comme `gen_grades_france.py` : on RELIT `lieu:france` depuis le dump et on n'y touche que
# `zone_influences` (ajout) et `rencontres` (ajout) — PUT complet à l'import (CLAUDE.md §11).
# Idempotent : un placement ou une rencontre déjà présents ne sont pas redoublés.
#
# Usage : python dev/gen_geants_mont_saint_michel.py [jsons/telluris-dump-….json]
#         (sans argument : le dump le plus récent)
# Sortie : jsons/geants_mont_saint_michel_a_importer.json   (1 doc : lieu:france)

import copy
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from utils.zones import compute_bbox  # noqa: E402

LIEU_ID = "lieu:france"
SORTIE = "jsons/geants_mont_saint_michel_a_importer.json"

GEANT = "espece:geant_ou_titan"
GEANT_DU_MONT = "espece:geant_du_mont_saint_michel"
ZONE_MONT = "zone:zone_danger_1"
ZONE_ARRIERE_PAYS = "zone:zone_danger_3"

# Le Mont : (23,14) à (25,14), la dernière rangée de terre avant la baie, plus (24,15) et
# (24,13) — cette dernière en mer, derrière le mur de côte, donc jamais foulée.
PLACEMENT_MONT = {
	"x": 24, "y": 14, "w": 3, "h": 2, "rot": 0, "forme": "ellipse", "zone": ZONE_MONT,
	"profil_weights": {
		"profil:heros": 2,     # niveau 5
		"profil:seigneur": 3,  # niveau 6
	},
}

# L'arrière-pays de la baie : x 24 → 32, y 15 → 19, tout en terre.
PLACEMENT_ARRIERE_PAYS = {
	"x": 28, "y": 17, "w": 8, "h": 4, "rot": 0, "forme": "ellipse", "zone": ZONE_ARRIERE_PAYS,
	"profil_weights": {
		"profil:novice": 1,      # niveau 1
		"profil:combattant": 3,  # niveau 2
	},
}

PLACEMENTS = [PLACEMENT_MONT, PLACEMENT_ARRIERE_PAYS]
RENCONTRES = {GEANT: ZONE_ARRIERE_PAYS, GEANT_DU_MONT: ZONE_MONT}


def dernier_dump(argv):
	if len(argv) > 1:
		return argv[1]
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		sys.exit("Aucun dump jsons/telluris-dump-*.json")
	return dumps[-1]


def charger(chemin: str) -> dict:
	with open(chemin, encoding="utf-8") as f:
		data = json.load(f)
	docs = data["docs"] if isinstance(data, dict) and "docs" in data else data
	return {d["_id"]: d for d in docs if isinstance(d, dict) and d.get("_id")}


def _meme_placement(a: dict, b: dict) -> bool:
	return all(a.get(k) == b.get(k) for k in ("x", "y", "w", "h", "rot", "forme", "zone"))


def appliquer(lieu: dict) -> dict:
	"""Copie de `lieu` avec les deux placements et les deux rencontres. Pur, idempotent."""
	lieu = copy.deepcopy(lieu)
	lieu.pop("_rev", None)

	placements = lieu.setdefault("zone_influences", [])
	for spec in PLACEMENTS:
		if not any(_meme_placement(p, spec) for p in placements):
			p = copy.deepcopy(spec)
			p["bbox"] = compute_bbox(p)
			placements.append(p)

	rencontres = lieu.setdefault("rencontres", [])
	for espece, zone in RENCONTRES.items():
		entree = next((r for r in rencontres if r.get("espece") == espece), None)
		if entree is None:
			rencontres.append({"espece": espece, "zones": [zone]})
		elif zone not in entree.setdefault("zones", []):
			entree["zones"].append(zone)
	return lieu


def valider(base: dict) -> None:
	manquants = [i for i in [LIEU_ID, GEANT, GEANT_DU_MONT, ZONE_MONT, ZONE_ARRIERE_PAYS]
				 + [pid for s in PLACEMENTS for pid in s["profil_weights"]] if i not in base]
	if manquants:
		sys.exit("ERREUR : absents du dump : " + ", ".join(manquants))


def main(argv):
	chemin = dernier_dump(argv)
	base = charger(chemin)
	valider(base)
	lieu = appliquer(base[LIEU_ID])
	with open(os.path.join(RACINE, SORTIE), "w", encoding="utf-8", newline="\n") as f:
		f.write(json.dumps([lieu], ensure_ascii=False, indent=2) + "\n")
	print(f"Source : {os.path.basename(chemin)}")
	print(f"{SORTIE} : {LIEU_ID}, {len(lieu['zone_influences'])} placements, "
		  f"{len(lieu['rencontres'])} rencontres")


if __name__ == "__main__":
	main(sys.argv)
