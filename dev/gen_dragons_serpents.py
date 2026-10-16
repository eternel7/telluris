#!/usr/bin/env python
# dev/gen_dragons_serpents.py
# Dragons et serpents des mythes (docs/lore/monde/20261016_dragons_et_serpents.md, arbitrage de
# l'Auteur du 16/10) dans le bestiaire :
#   - espèces : `espece:balaur` (dragon-serpent des Carpates, celui des terres de Vlad),
#     `espece:dragon_hydre`, `espece:mushhushshu` (le dragon de Marduk), `espece:xiuhcoatl`
#     (serpent de feu des Mexicas) ;
#   - êtres uniques, boss : `espece:zmey_gorynych`, `espece:ladon`, `espece:yamata_no_orochi`,
#     `espece:illuyanka` ;
#   - `espece:apep` (déjà en jeu) : description seule, `_id` et caractéristiques inchangés.
# Tiamat et Quetzalcoatl restent HORS bestiaire (puissance primordiale, dieu).
# Faiblesses : DESCRIPTION SEULE, aucune mécanique, et pas forcément propres à un seul être.
# Images à générer (prompts dans la séance) : templates/resources/monsters/<slug>_transparent.png.
#
# Loot : une CARCASSE par espèce ; au-delà du seuil de découpe, ses portions et morceaux sont
# produits DANS LE MÊME FICHIER par `gen_carcasses_parties.generer` (CLAUDE.md §18) — profils
# existants (`quadrupede` / `aile`), comme l'hydre et le grootslang.
#
# ⚠️ Les tables EXHAUSTIVES de `gen_genres_especes.py` et `gen_jetons_especes.py` citent déjà
# les espèces neuves : elles échouent tant que l'import n'est pas fait et qu'un dump FRAIS ne
# l'a pas relu. Le jeton est LU dans leur table (source unique), l'accord aussi.
#
# ⚠️ POURQUOI UN SCRIPT : `admin_import_bulk` fait un PUT COMPLET. Apep est RELU du dump le plus
# récent et seule sa description change ; un doc neuf dont l'`_id` est déjà en base n'est
# jamais réécrit (« déjà en base »). Le fichier ne porte que le DELTA (CLAUDE.md §18).
#
# Usage : python dev/gen_dragons_serpents.py [jsons/telluris-dump-….json]
# Sortie : jsons/dragons_serpents_a_importer.json

import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_carcasses_parties as carcasses  # noqa: E402
from gen_equipement_humanoides import _dump_le_plus_recent, charger  # noqa: E402
from gen_genres_especes import accord_de  # noqa: E402
from gen_jetons_especes import TABLE as JETONS  # noqa: E402
from gen_loups_garous import _carcasse  # noqa: E402
from gen_vampires import _attrs, _sans_rev  # noqa: E402

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "dragons_serpents_a_importer.json")

# ── Doc existant : champs remplacés ────────────────────────────────────────────

MODIFS = {
	"espece:apep": {
		"description": "Serpent du chaos lové sous le monde. Chaque nuit, dit-on en Égypte, il "
					   "assaille la barque du soleil dans la Douat, et chaque nuit on le repousse "
					   "sans jamais le tuer ; les orages et les éclipses seraient ses assauts. Sa "
					   "seule présence éteint les torches et fend la pierre. Les prêtres écrivent son "
					   "nom pour le brûler et piétinent sa figure de cire ; nul ne sait si cela "
					   "l'affaiblit ou le rend furieux.",
	},
}

# ── Espèces neuves ─────────────────────────────────────────────────────────────
# `carcasse` = (poids min, poids max, rareté). Accord et jeton : tables des générateurs dédiés.

NOUVELLES = {
	# Carpates (Auteur, 13/10) : le monstre qui ravagea les terres de Vlad était un balaur.
	"balaur": {
		"nom": "Balaur",
		"description": "Dragon-serpent des Carpates aux ailes de cuir, qui porte trois, sept ou douze "
					   "têtes selon les récits. On dit que sa bave durcit en pierres précieuses, et "
					   "qu'un balaur sorti d'un donjon qui débordait ravagea jadis les terres d'un "
					   "prince de ces montagnes. Une tête tranchée repousse si le cou n'est pas "
					   "brûlé ; certains assurent qu'il faut les abattre toutes d'un même élan.",
		"base_attributes": _attrs((14, 16), (65, 95), (65, 95), (30, 50), (55, 80), (30, 50), (0, 0), (35, 60)),
		"tags": ["monstre", "draconique", "vol", "regeneration", "legendaire", "predateur"],
		"carcasse": ([400, 1200], "rare"),
	},
	"dragon_hydre": {
		"nom": "Dragon-hydre",
		"description": "Dragon sans ailes au corps massif, dont cinq à sept cous jaillissent des "
					   "épaules ; chaque gueule crache le feu. Une tête tranchée en fait repousser "
					   "deux, sauf si le moignon est brûlé aussitôt. On raconte qu'une de ses têtes "
					   "ne meurt jamais et qu'il faut l'enterrer sous un rocher.",
		"base_attributes": _attrs((6, 8), (65, 100), (70, 105), (20, 35), (55, 80), (20, 35), (0, 0), (40, 65)),
		"tags": ["monstre", "draconique", "souffle", "regeneration", "legendaire", "predateur"],
		"carcasse": ([2500, 7000], "rare"),
	},
	# Babylone : le dragon de Marduk, sur la porte d'Ishtar.
	"mushhushshu": {
		"nom": "Mušḫuššu",
		"description": "Le « serpent furieux » des déserts de Mésopotamie : tête de serpent cornue, "
					   "pattes avant de lion, pattes arrière d'aigle, queue armée d'un dard de "
					   "scorpion. Il fut l'un des onze monstres de Tiamat avant que Marduk ne le "
					   "dompte ; Babylone l'a peint sur la porte d'Ishtar. Les prêtres de l'Esagil "
					   "disent qu'il recule devant la bêche de Marduk.",
		"base_attributes": _attrs((7, 9), (45, 70), (45, 65), (35, 55), (40, 60), (15, 30), (0, 0), (25, 45)),
		"tags": ["monstre", "reptile", "venin", "predateur"],
		"carcasse": ([150, 350], "peu_commun"),
	},
	# Mexicas : le serpent de feu, arme de Huitzilopochtli.
	"xiuhcoatl": {
		"nom": "Xiuhcóatl",
		"description": "Serpent de feu des terres sèches des Mexicas, aux écailles couleur de "
					   "turquoise et au museau retroussé : il brûle ce qu'il traverse. On dit que "
					   "Huitzilopochtli en fit son arme sur la colline de Coatepec. La saison sèche "
					   "l'appelle ; la pluie, dit-on, le rend aux braises.",
		"base_attributes": _attrs((7, 9), (40, 60), (35, 55), (40, 60), (40, 60), (15, 30), (0, 0), (25, 45)),
		"tags": ["monstre", "reptile", "souffle", "magique", "predateur"],
		"carcasse": ([40, 90], "peu_commun"),
	},
	# Êtres uniques, boss (Auteur, 16/10).
	"zmey_gorynych": {
		"nom": "Zmeï Gorynytch",
		"description": "Dragon à trois têtes des terres de Kiev, aux griffes de fer, qui crache le feu "
					   "et enlève qui lui plaît. Il garde le pont Kalinov sur la Smorodina, la "
					   "rivière de feu ; on dit que ce pont mène au pays des morts, et nul n'en est "
					   "revenu pour le confirmer. Ses têtes repoussent ; la terre, dit-on, refuse "
					   "de boire son sang tant qu'on ne l'en supplie pas.",
		"base_attributes": _attrs((14, 16), (80, 115), (75, 110), (35, 55), (70, 100), (45, 65), (0, 0), (50, 80)),
		"tags": ["monstre", "draconique", "vol", "souffle", "regeneration", "legendaire", "boss"],
		"carcasse": ([800, 2500], "rare"),
	},
	"ladon": {
		"nom": "Ladon",
		"description": "Serpent aux cent têtes et aux cent voix, enroulé autour de l'arbre aux pommes "
					   "d'or du jardin des Hespérides, au-delà des Colonnes, que les marins disent "
					   "apercevoir au couchant. Il ne dort jamais. Les uns le disent né de Cétô, les "
					   "autres d'Échidna. Des flèches trempées dans le venin d'une hydre l'auraient "
					   "déjà blessé ; une ruse l'aurait déjà détourné.",
		"base_attributes": _attrs((4, 6), (80, 120), (80, 115), (15, 30), (80, 110), (50, 70), (0, 0), (50, 80)),
		"tags": ["monstre", "reptile", "gardien", "legendaire", "boss", "insensible_furtivite"],
		"carcasse": ([3000, 9000], "rare"),
	},
	"yamata_no_orochi": {
		"nom": "Yamata no Orochi",
		"description": "Serpent d'Izumo à huit têtes et huit queues, long de huit vallées et de huit "
					   "collines : des cyprès poussent sur son dos, ses yeux sont rouges comme des "
					   "cerises d'hiver, son ventre suinte le sang. Chaque année il exigeait une "
					   "jeune fille. Le saké huit fois brassé endort ses têtes une à une ; on dit "
					   "qu'une lame dort dans l'une de ses queues.",
		"base_attributes": _attrs((5, 7), (100, 145), (95, 140), (15, 30), (70, 100), (30, 50), (0, 0), (55, 85)),
		"tags": ["monstre", "reptile", "legendaire", "boss", "predateur"],
		"carcasse": ([8000, 20000], "rare"),
	},
	"illuyanka": {
		"nom": "Illuyanka",
		"description": "Serpent-dragon des hauts plateaux d'Anatolie, terré dans un trou de la "
					   "montagne : on raconte qu'il vainquit un jour le dieu de l'orage et lui prit "
					   "son cœur et ses yeux. Sa gloutonnerie le perd : gavé de festin, il ne repasse "
					   "plus par son trou, et un simple anthrope put le ligoter.",
		"base_attributes": _attrs((4, 6), (80, 120), (80, 120), (15, 25), (60, 90), (35, 55), (0, 0), (45, 75)),
		"tags": ["monstre", "reptile", "souterrain", "legendaire", "boss"],
		"carcasse": ([3000, 8000], "rare"),
	},
}

ACCORD = ("nom_propre", "pluriel", "h_aspire")


def _espece(slug: str, spec: dict) -> dict:
	accord = accord_de(slug)
	doc = {"_id": "espece:" + slug, "type": "espece", "nom": spec["nom"], "genre": accord["genre"],
		   **{k: True for k in ACCORD if accord.get(k)}}
	jeton = JETONS[slug]
	if jeton:
		doc["jeton"] = {"taille": jeton[0], "forme": jeton[1]}
	doc.update({
		"image": slug + "_transparent.png",
		"description": spec["description"],
		"base_attributes": copy.deepcopy(spec["base_attributes"]),
		"tags": list(spec["tags"]),
		"proprietes": {},
	})
	return doc


def docs_dragons_serpents(base: dict) -> tuple[list, list]:
	"""(docs à importer, ids déjà en base) d'après les docs du dump `base` ({_id: doc})."""
	erreurs = [f"{i} absent du dump" for i in MODIFS if i not in base]
	erreurs += [f"espece:{s} absente de gen_jetons_especes.TABLE" for s in NOUVELLES if s not in JETONS]
	if erreurs:
		sys.exit("ERREUR :\n   " + "\n   ".join(erreurs))

	docs, deja = [], []
	neufs = []  # espèces + carcasses, tels qu'ils seraient en base (pour la découpe)
	for slug, spec in NOUVELLES.items():
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
	grosses = [s for s, spec in NOUVELLES.items() if spec["carcasse"][0][1] > carcasses.seuil()]
	sortie, _resume, _ign, _orph, inchanges = carcasses.generer(list(vue.values()), grosses)
	par_id = {d["_id"]: i for i, d in enumerate(docs)}
	for d in sortie:
		if d["_id"] in par_id:
			docs[par_id[d["_id"]]] = d  # la carcasse neuve, enrichie de `decoupe`
		else:
			docs.append(d)
	deja += [i for i in inchanges if i in base and i not in deja]

	for i, champs in MODIFS.items():
		doc = _sans_rev(base[i])
		if all(doc.get(k) == v for k, v in champs.items()):
			deja.append(i)
			continue
		doc.update(copy.deepcopy(champs))
		docs.append(doc)

	return docs, deja


def main() -> None:
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	source = sys.argv[1] if len(sys.argv) > 1 else _dump_le_plus_recent()
	base = {d["_id"]: d for d in charger(source) if isinstance(d, dict) and d.get("_id")}
	docs, deja = docs_dragons_serpents(base)
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
