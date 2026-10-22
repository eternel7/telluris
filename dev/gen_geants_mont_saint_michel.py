#!/usr/bin/env python
# dev/gen_geants_mont_saint_michel.py
# Les géants de la baie du Mont-Saint-Michel, sur la carte de France.
#
# UNE zone numérotée jusque-là inutilisée (`zone:zone_danger_3`, aucun lieu ne la portait au
# dump du 22/10), un seul placement : une ellipse inclinée qui part du MONT — l'îlot dessiné en
# (23,14), sur la rangée de côte murée par `nav` — et file vers l'arrière-pays au sud-est,
# toute en terre. On y croise les géants ordinaires (`espece:geant_ou_titan`) et le Géant du
# Mont-Saint-Michel.
#
# LE GÉANT DU MONT EST TOUJOURS UN SEIGNEUR, quel que soit le profil tiré. `roll_monster_stats`
# vaut, par caractéristique, clamp(min + écart du profil, min, max) : poser sur l'espèce
# [min, max] = la fourchette d'un géant ordinaire au profil Seigneur suffit — le profil ne peut
# plus le faire sortir de cette fourchette. Elle est RELUE dans le dump (`geant_ou_titan` +
# `profil:seigneur`), jamais recopiée : rééquilibrer l'un ou l'autre se reporte au prochain
# passage. Le niveau du profil ne joue plus que sur l'XP rendue (niveau × 4).
#
# ⚠️ UNE zone ⇒ UN tirage de grade pour tout le pool (`zones.resolve_profil_weights`) : les
# grades posés ici sont ceux des géants ordinaires, plafonnés à Champion pour rester sous le
# maître du Mont. Le placement ne touche pas la zone très dangereuse, dont les Héros/Seigneurs
# s'additionneraient aux géants (verrouillé par tests/test_gen_geants_mont_saint_michel.py).
#
# Comme `gen_grades_france.py` : on RELIT les docs depuis le dump et on n'y touche que
# `zone_influences` / `rencontres` (ajouts) de `lieu:france` et `base_attributes` du géant du
# Mont — PUT complet à l'import (CLAUDE.md §11). Idempotent.
#
# Usage : python dev/gen_geants_mont_saint_michel.py [jsons/telluris-dump-….json]
#         (sans argument : le dump le plus récent)
# Sortie : jsons/geants_mont_saint_michel_a_importer.json
#          (2 docs : lieu:france, espece:geant_du_mont_saint_michel)

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
SEIGNEUR = "profil:seigneur"
ZONE = "zone:zone_danger_3"

# Du Mont (23,14) jusqu'à (31,18) : 23 cases, aucune en mer.
PLACEMENT = {
	"x": 27, "y": 16, "w": 10, "h": 3, "rot": 30, "forme": "ellipse", "zone": ZONE,
	"profil_weights": {
		"profil:combattant": 2,  # niveau 2
		"profil:veteran": 3,     # niveau 3
		"profil:champion": 1,    # niveau 4
	},
}


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


def _sans_rev(doc: dict) -> dict:
	doc = copy.deepcopy(doc)
	doc.pop("_rev", None)
	return doc


def _meme_placement(a: dict, b: dict) -> bool:
	return all(a.get(k) == b.get(k) for k in ("x", "y", "w", "h", "rot", "forme", "zone"))


def fourchette_seigneur(geant: dict, seigneur: dict) -> dict:
	"""[min, max] de chaque caractéristique d'un géant ordinaire au profil Seigneur, avec la
	règle de `combat.roll_monster_stats` : clamp(min + écart, min, max)."""
	out = {}
	mods = seigneur.get("attributs_modifier") or {}
	for cle, borne in (geant.get("base_attributes") or {}).items():
		bmin, bmax = borne.get("min", 1), borne.get("max", 5)
		mod = mods.get(cle) or {}
		out[cle] = {
			"min": max(bmin, min(bmax, bmin + mod.get("min", 0))),
			"max": max(bmin, min(bmax, bmin + mod.get("max", 0))),
		}
	return out


def appliquer_france(lieu: dict) -> dict:
	"""Copie de `lieu` avec le placement et les deux rencontres. Pur, idempotent."""
	lieu = _sans_rev(lieu)
	placements = lieu.setdefault("zone_influences", [])
	if not any(_meme_placement(p, PLACEMENT) for p in placements):
		p = copy.deepcopy(PLACEMENT)
		p["bbox"] = compute_bbox(p)
		placements.append(p)

	rencontres = lieu.setdefault("rencontres", [])
	for espece in (GEANT, GEANT_DU_MONT):
		entree = next((r for r in rencontres if r.get("espece") == espece), None)
		if entree is None:
			rencontres.append({"espece": espece, "zones": [ZONE]})
		elif ZONE not in entree.setdefault("zones", []):
			entree["zones"].append(ZONE)
	return lieu


def appliquer_geant_du_mont(base: dict) -> dict:
	doc = _sans_rev(base[GEANT_DU_MONT])
	doc["base_attributes"] = fourchette_seigneur(base[GEANT], base[SEIGNEUR])
	return doc


def valider(base: dict) -> None:
	manquants = [i for i in [LIEU_ID, GEANT, GEANT_DU_MONT, SEIGNEUR, ZONE, *PLACEMENT["profil_weights"]]
				 if i not in base]
	if manquants:
		sys.exit("ERREUR : absents du dump : " + ", ".join(manquants))


def generer(base: dict) -> list:
	valider(base)
	return [appliquer_france(base[LIEU_ID]), appliquer_geant_du_mont(base)]


def main(argv):
	chemin = dernier_dump(argv)
	docs = generer(charger(chemin))
	with open(os.path.join(RACINE, SORTIE), "w", encoding="utf-8", newline="\n") as f:
		f.write(json.dumps(docs, ensure_ascii=False, indent=2) + "\n")
	print(f"Source : {os.path.basename(chemin)}")
	print(f"{SORTIE} : {', '.join(d['_id'] for d in docs)}")
	for cle, b in docs[1]["base_attributes"].items():
		print(f"  {cle:>3} {b['min']:>3} – {b['max']}")


if __name__ == "__main__":
	main(sys.argv)
