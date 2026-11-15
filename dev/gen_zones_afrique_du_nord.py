#!/usr/bin/env python
"""Zones d'influence de l'Afrique du Nord adaptées aux biomes de la région (Auteur, 15/11).

Écrit UN fichier `jsons/zones_afrique_du_nord_a_importer.json` (CLAUDE.md §18) : `lieu:afrique_du_nord`
RELU du dump, seul `zone_influences` change (PUT complet, §11).

Déjà fait par `dev/gen_zones_biomes.py` (repeinte du 16/11), gardé tel quel : contreforts → contreforts
arides, le fleuve → fleuve tropical, la bande du bord sud → steppe épineuse. Ce générateur part de cet
état, retire d'abord les doublons d'une même zone (piste A de `dev/gen_simplification_zones.py` — ce
fichier REMPLACE donc la part Afrique du Nord de `simplification_zones_a_importer.json`), puis pose les
biomes lus sur l'image de la carte (`templates/resources/maps/afrique_du_nord.png`, 88 × 48) là où
aucune zone ne couvrait la terre :

- forêt de chênes-lièges : la frange boisée de la côte nord (Kabylie–Kroumirie) et la forêt du Rif ;
- maquis : la côte nord du Maroc entre les deux ;
- cédraie d'altitude : les conifères dessinés au pied de l'Atlas ;
- désert de sel : les chotts bleus au sud-est de l'Atlas (le contrefort voisin cède sa rangée du bas) ;
- palmeraie : le Djérid–Ziban (bosquet dessiné) et les deux oasis à palmiers du Sahara ;
- oliveraie : le Sahel tunisien et la plaine atlantique du Maroc ;
- steppe aride : la basse vallée du Drâa et les côtes de Tripolitaine et de Cyrénaïque ;
- désert côtier brumeux : la côte atlantique du Sahara ;
- fleuve tropical : le Niger (et son bras sud) et le Sénégal, tracés sur la carte ;
- lac alcalin : le lac Tchad ;
- steppe épineuse : la savane verte du bord sud ; l'erg posé dans cette savane (et la bande de steppe
  qu'il chevauchait) lui laisse la place.

Zones d'eau (fleuve, lac, palmeraie : oasis) : leur superposition est normale. Les autres placements
neufs sont des rectangles posés sur des cases non couvertes, sauf bords d'ellipses désertiques.
Idempotent : rejoué sur un dump déjà importé, aucun placement neuf n'est ajouté (marqueur : présence
d'un placement de chacune des zones neuves) ⇒ aucun fichier.

    python dev/gen_zones_afrique_du_nord.py [--dump jsons/telluris-dump-….json] [--sortie …]
"""

import argparse
import importlib.util
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)


def _simplification():
	chemin = os.path.join(RACINE, "dev", "gen_simplification_zones.py")
	spec = importlib.util.spec_from_file_location("gen_simplification_zones", chemin)
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod


SIMP = _simplification()
SORTIE = os.path.join(RACINE, "jsons", "zones_afrique_du_nord_a_importer.json")
LIEU = "lieu:afrique_du_nord"

# (zone, x0, y0, x1, y1) en cases INCLUSES — lu sur l'image de la carte.
NEUFS = [
	("zone:foret_chenes_lieges", 28, 6, 43, 7),    # frange boisée de la côte nord
	("zone:foret_chenes_lieges", 16, 8, 19, 11),   # forêt du Rif
	("zone:maquis", 20, 8, 27, 9),                 # côte nord du Maroc
	("zone:cedraie_altitude", 23, 15, 27, 16),     # conifères au pied de l'Atlas
	("zone:desert_sel", 36, 10, 41, 11),           # chotts
	("zone:palmeraie", 36, 12, 39, 15),            # Djérid–Ziban
	("zone:palmeraie", 20, 29, 24, 31),            # oasis à palmiers (ouest)
	("zone:palmeraie", 28, 34, 31, 36),            # oasis à palmiers (centre)
	("zone:oliveraie", 42, 8, 43, 11),             # Sahel tunisien
	("zone:oliveraie", 14, 12, 15, 15),            # plaine atlantique du Maroc
	("zone:steppe_aride", 8, 21, 11, 24),          # basse vallée du Drâa, au sud de l'Atlas
	("zone:steppe_aride", 45, 13, 49, 14),         # côte de Tripolitaine
	("zone:steppe_aride", 57, 14, 64, 15),         # côte de Cyrénaïque
	("zone:desert_brumeux", 5, 25, 6, 30),         # côte atlantique du Sahara (nord)
	("zone:desert_brumeux", 3, 31, 4, 43),         # côte atlantique du Sahara (sud)
	# Sénégal, d'ouest en est.
	("zone:fleuve_tropical", 3, 40, 7, 41),
	("zone:fleuve_tropical", 8, 41, 10, 42),
	("zone:fleuve_tropical", 11, 43, 12, 45),
	("zone:fleuve_tropical", 13, 46, 14, 47),
	# Niger, de la boucle au sud-ouest, puis son bras sud.
	("zone:fleuve_tropical", 23, 39, 28, 40),
	("zone:fleuve_tropical", 21, 41, 22, 42),
	("zone:fleuve_tropical", 19, 43, 20, 44),
	("zone:fleuve_tropical", 17, 45, 18, 47),
	("zone:fleuve_tropical", 29, 41, 30, 43),
	("zone:fleuve_tropical", 31, 44, 32, 47),
	("zone:lac_alcalin", 47, 44, 50, 47),          # lac Tchad
	("zone:steppe_epineuse", 17, 44, 38, 47),      # savane verte du bord sud
	("zone:steppe_epineuse", 34, 42, 38, 43),
	("zone:steppe_epineuse", 39, 45, 45, 47),
]

# Placements existants retouchés, reconnus par (zone, x, y, w, h) — jamais par index.
# erg posé dans la savane, bande de steppe qu'il chevauchait : remplacés par la savane ci-dessus.
RETIRES = [
	("zone:erg", 36, 44, 4, 4),
	("zone:steppe_epineuse", 36, 47, 5, 2),
]
# Contrefort au-dessus des chotts : ne garde que ses rangées 8-9 (cède la 10 au désert de sel).
REDUITS = [
	(("zone:contreforts_arides", 38, 9, 6, 2), (35, 8, 41, 9)),
]


def _cle(p: dict) -> tuple:
	return (p["zone"], p["x"], p["y"], p["w"], p["h"])


def rect(zone: str, x0: int, y0: int, x1: int, y1: int) -> dict:
	return SIMP.rectangle_cases(zone, x0, y0, x1 - x0 + 1, y1 - y0 + 1)


def adapter(placements: list, larg: int, haut: int) -> tuple[list, list]:
	"""(placements, journal). Rien de neuf si toutes les zones neuves sont déjà posées."""
	presentes = {p["zone"] for p in placements}
	if all(z in presentes for z, *_ in NEUFS):
		return placements, []
	journal = []
	out = []
	reduits = dict(REDUITS)
	for p in placements:
		k = _cle(p)
		if k in RETIRES:
			journal.append(f"retiré {k}")
			continue
		if k in reduits:
			x0, y0, x1, y1 = reduits[k]
			neuf = rect(p["zone"], x0, y0, x1, y1)
			neuf.update({c: v for c, v in p.items() if c not in neuf and c != "bbox"})
			journal.append(f"réduit {k} → cases x{x0}-{x1} y{y0}-{y1}")
			out.append(neuf)
			continue
		out.append(p)
	manquants = [k for k in RETIRES + list(reduits) if k not in {_cle(p) for p in placements}]
	assert not manquants, f"placements attendus absents du dump : {manquants}"
	for z, x0, y0, x1, y1 in NEUFS:
		assert 0 <= x0 <= x1 < larg and 0 <= y0 <= y1 < haut, (z, x0, y0, x1, y1)
		out.append(rect(z, x0, y0, x1, y1))
	return out, journal


def main(argv=None) -> int:
	ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	ap.add_argument("--dump", default=None)
	ap.add_argument("--sortie", default=SORTIE)
	args = ap.parse_args(argv)
	dump = args.dump or SIMP.dernier_dump()
	with open(dump, encoding="utf-8") as f:
		docs = {d["_id"]: d for d in json.load(f)["docs"]}
	print(f"Dump : {os.path.basename(dump)}")
	lieu = docs[LIEU]
	larg, haut = lieu["dimensions"]["x"], lieu["dimensions"]["y"]
	origine = lieu["zone_influences"]
	zi, retires = SIMP.retirer_doublons(origine, larg, haut)
	print(f"Doublons d'une même zone retirés : {len(retires)}")
	zi, journal = adapter(zi, larg, haut)
	for ligne in journal:
		print(f"  {ligne}")
	if zi == origine:
		print("Rien à émettre.")
		return 0
	# Contrôles : aucune case ne perd toute zone ; les zones de chaque case avant/après.
	za, zb = SIMP.zones_par_case(origine, larg, haut), SIMP.zones_par_case(zi, larg, haut)
	trous = [c for c in za if c not in zb]
	assert not trous, f"{len(trous)} case(s) sans zone après adaptation : {trous[:10]}"
	n0, s0 = SIMP.stats(origine, larg, haut)
	n1, s1 = SIMP.stats(zi, larg, haut)
	gagnees = sum(1 for c in zb if c not in za)
	print(f"{LIEU} : {n0} → {n1} placements ; cases couvertes {len(za)} → {len(zb)} (+{gagnees}) ; "
		  f"cases ≥ 2 zones : {s0} → {s1}")
	eau = {"zone:fleuve_tropical", "zone:delta", "zone:lac_alcalin", "zone:palmeraie"}
	compte: dict = {}
	for p in zi:
		if p["zone"] in eau:
			continue
		for c in SIMP.cases_de(p, larg, haut):
			compte[c] = compte.get(c, 0) + 1
	print(f"  dont hors eau : {sum(1 for n in compte.values() if n >= 2)}")
	doc = {k: v for k, v in lieu.items() if k != "_rev"}
	doc["zone_influences"] = zi
	with open(args.sortie, "w", encoding="utf-8") as f:
		f.write(json.dumps([doc], ensure_ascii=False, indent=2) + "\n")
	print(f"→ {os.path.relpath(args.sortie, RACINE)} (1 doc)")
	return 0


if __name__ == "__main__":
	sys.exit(main())
