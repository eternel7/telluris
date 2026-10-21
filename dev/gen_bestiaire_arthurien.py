#!/usr/bin/env python
# dev/gen_bestiaire_arthurien.py
# Bestiaire arthurien (docs/lore/cites/20261021_camelot_winchester.md, arbitrages de l'Auteur
# du 21/10) :
#   - êtres uniques, boss : `espece:twrch_trwyth` (rang B), `espece:cath_palug` (E – D),
#     `espece:bete_glatissante` (C, que Pellinore traque), `espece:geant_du_mont_saint_michel` (D) ;
#   - les deux dragons du donjon de Dinas Emrys (A) : `espece:dragon_rouge`, `espece:dragon_blanc`.
# Rangs : progression adoptée (§ 2, point 16) ; les stats sont calibrées sur les espèces de rang
# voisin du dump (cu_sidhe / failinis, lycaon, geant_ou_titan, grand_dragon / dragon_empereur).
# Images à générer : templates/resources/monsters/<slug>_transparent.png.
#
# Loot : une CARCASSE par espèce ; au-delà du seuil de découpe, ses portions et morceaux sont
# produits DANS LE MÊME FICHIER par `gen_carcasses_parties.generer` (CLAUDE.md §18).
#
# ⚠️ Les tables EXHAUSTIVES de `gen_genres_especes.py` et `gen_jetons_especes.py` citent déjà
# les espèces neuves : elles échouent tant que l'import n'est pas fait et qu'un dump FRAIS ne
# l'a pas relu. Le jeton est LU dans leur table (source unique), l'accord aussi.
#
# ⚠️ POURQUOI UN SCRIPT : `admin_import_bulk` fait un PUT COMPLET. Un doc neuf dont l'`_id` est
# déjà en base n'est jamais réécrit (« déjà en base ») : le fichier ne porte que le DELTA.
#
# Usage : python dev/gen_bestiaire_arthurien.py [jsons/telluris-dump-….json]
# Sortie : jsons/bestiaire_arthurien_a_importer.json

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_carcasses_parties as carcasses  # noqa: E402
from gen_dragons_serpents import _espece  # noqa: E402
from gen_equipement_humanoides import _dump_le_plus_recent, charger  # noqa: E402
from gen_jetons_especes import TABLE as JETONS  # noqa: E402
from gen_loups_garous import _carcasse  # noqa: E402
from gen_vampires import _attrs  # noqa: E402

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "bestiaire_arthurien_a_importer.json")

# `carcasse` = (poids min, poids max, rareté). Accord et jeton : tables des générateurs dédiés.
NOUVELLES = {
	# Rang D — en France, à portée du joueur dès les premiers rangs.
	"geant_du_mont_saint_michel": {
		"nom": "Géant du Mont-Saint-Michel",
		"description": "Géant venu d'Ibérie qui s'installa sur le mont, au milieu des grèves de la "
					   "baie, et dévorait les gens du pays. Il enleva Hélène, nièce d'un duc "
					   "d'Armorique, qui mourut de terreur entre ses mains. Arthur gravit le mont "
					   "avec Kaï et Bedwyr et l'abattit, dit-on. Pourtant il y a toujours un géant "
					   "sur le mont : le même qui revient, ou un autre qui a pris sa place, les "
					   "pêcheurs de la baie ne se risquent pas à trancher.",
		"base_attributes": _attrs((5, 7), (60, 90), (55, 85), (10, 20), (25, 40), (10, 20), (0, 0), (30, 50)),
		"tags": ["humanoide", "geant", "legendaire", "boss", "predateur"],
		"carcasse": ([500, 900], "rare"),
	},
	# Rang E – D.
	"cath_palug": {
		"nom": "Cath Palug",
		"description": "Chat monstrueux de l'île de Môn. Une truie errante, Henwen, l'aurait mis bas "
					   "au pied d'un rocher ; des porchers jetèrent le chaton à la mer, et les fils "
					   "de Palug le recueillirent sur l'île, où il dévora neuf-vingts guerriers. Les "
					   "Bretons de l'île disent que Kaï l'affronta ; ceux du continent, qu'Arthur "
					   "le tua au bord d'un lac des montagnes. Les deux récits ne peuvent pas être "
					   "vrais, et il chasse encore.",
		"base_attributes": _attrs((7, 9), (40, 60), (35, 55), (55, 80), (35, 55), (20, 35), (0, 0), (35, 55)),
		"tags": ["monstre", "legendaire", "boss", "rapide", "predateur"],
		"carcasse": ([120, 250], "rare"),
	},
	# Rang C — Pellinore, immortel, la traque depuis le temps d'Arthur.
	"bete_glatissante": {
		"nom": "Bête glatissante",
		"description": "Tête de serpent, corps de léopard, croupe de lion, pieds de cerf : de son "
					   "ventre sort le vacarme de trente couples de chiens qui donnent de la voix, "
					   "d'où son nom. Le roi Pellinore la traque depuis le temps d'Arthur et ne l'a "
					   "jamais rattrapée. Certains disent que c'est la quête qui le garde en vie, et "
					   "que la bête le sait.",
		"base_attributes": _attrs((8, 10), (50, 75), (45, 70), (60, 85), (50, 70), (30, 45), (0, 0), (45, 70)),
		"tags": ["monstre", "hybride", "legendaire", "boss", "rapide", "terreur", "insensible_furtivite"],
		"carcasse": ([200, 400], "rare"),
	},
	# Rang B.
	"twrch_trwyth": {
		"nom": "Twrch Trwyth",
		"description": "Sanglier-roi aux soies d'argent : un roi changé en sanglier pour ses fautes, "
					   "disent les Gallois. Entre ses oreilles il porte un peigne, un rasoir et des "
					   "ciseaux. Il traversa la mer d'Irlande à la nage avec ses sept marcassins et "
					   "ravagea le pays de Galles jusqu'à la Cornouailles ; Arthur et ses chevaliers "
					   "le chassèrent d'une côte à l'autre, et il disparut dans la mer. Nul ne l'a "
					   "vu mourir.",
		"base_attributes": _attrs((6, 8), (80, 115), (80, 115), (25, 45), (60, 85), (25, 40), (0, 0), (45, 70)),
		"tags": ["monstre", "malediction", "legendaire", "boss", "predateur"],
		"carcasse": ([700, 1400], "rare"),
	},
	# Rang A — le donjon sous la tour de Vortigern.
	"dragon_rouge": {
		"nom": "Dragon rouge",
		"description": "L'un des deux dragons de Dinas Emrys. Un roi les aurait pris au centre de "
					   "l'île, endormis dans une cuve d'hydromel, et enfermés sous la colline. Quand "
					   "Vortigern voulut y bâtir sa tour, elle s'effondrait chaque nuit : les deux "
					   "dragons se battaient dessous. Un enfant sans père, que certains appellent "
					   "Merlin, l'annonça. Le blanc a l'avantage au début de chaque combat ; le "
					   "rouge, celui que les Gallois peignent sur leurs bannières, l'emporte à la fin.",
		"base_attributes": _attrs((16, 18), (85, 125), (85, 125), (40, 60), (80, 115), (50, 80), (0, 0), (55, 85)),
		"tags": ["monstre", "draconique", "vol", "souffle", "legendaire", "boss"],
		"carcasse": ([1500, 4000], "rare"),
	},
	"dragon_blanc": {
		"nom": "Dragon blanc",
		"description": "Le second dragon de Dinas Emrys, pâle comme la craie. Il ouvre chaque combat "
					   "en furie et repousse le rouge jusqu'au bord du lac souterrain, puis faiblit "
					   "et recule. On dit qu'il ne meurt jamais tout à fait, qu'il revient toujours "
					   "pour une nouvelle lutte, et que la tour au-dessus n'a jamais tenu longtemps.",
		"base_attributes": _attrs((17, 19), (80, 115), (80, 120), (45, 65), (80, 115), (50, 80), (0, 0), (55, 85)),
		"tags": ["monstre", "draconique", "vol", "souffle", "legendaire", "boss"],
		"carcasse": ([1500, 4000], "rare"),
	},
}


def docs_bestiaire_arthurien(base: dict, nouvelles: dict = NOUVELLES) -> tuple[list, list]:
	"""(docs à importer, ids déjà en base) d'après les docs du dump `base` ({_id: doc}).
	`nouvelles` : un autre lot de même forme (cf. `gen_chasse_sauvage.py`)."""
	erreurs = [f"espece:{s} absente de gen_jetons_especes.TABLE" for s in nouvelles if s not in JETONS]
	if erreurs:
		sys.exit("ERREUR :\n   " + "\n   ".join(erreurs))

	docs, deja = [], []
	neufs = []  # espèces + carcasses, tels qu'ils seraient en base (pour la découpe)
	for slug, spec in nouvelles.items():
		doc = _espece(slug, spec)
		carc = _carcasse(doc["_id"], doc["nom"], *spec["carcasse"])
		neufs += [doc, carc]
		for d in (doc, carc):
			if d["_id"] in base:
				deja.append(d["_id"])
			else:
				docs.append(d)

	# Découpe des grosses carcasses : même cœur que gen_carcasses_parties, restreint aux neuves.
	carcasses.controler_profils()
	vue = {**base, **{d["_id"]: d for d in neufs}}
	grosses = [s for s, spec in nouvelles.items() if spec["carcasse"][0][1] > carcasses.seuil()]
	sortie, _resume, _ign, _orph, inchanges = carcasses.generer(list(vue.values()), grosses)
	par_id = {d["_id"]: i for i, d in enumerate(docs)}
	for d in sortie:
		if d["_id"] in par_id:
			docs[par_id[d["_id"]]] = d  # la carcasse neuve, enrichie de `decoupe`
		else:
			docs.append(d)
	deja += [i for i in inchanges if i in base and i not in deja]
	return docs, deja


def main() -> None:
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	source = sys.argv[1] if len(sys.argv) > 1 else _dump_le_plus_recent()
	base = {d["_id"]: d for d in charger(source) if isinstance(d, dict) and d.get("_id")}
	docs, deja = docs_bestiaire_arthurien(base)
	print(f"relu {os.path.relpath(source, RACINE)}")
	for d in docs:
		print(f"   à importer {d['_id']}")
	for i in deja:
		print(f"   déjà en base {i}")
	if not docs:
		print("rien à importer — la base est à jour")
		return
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"{len(docs)} doc(s) → {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
	main()
