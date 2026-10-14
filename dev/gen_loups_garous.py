#!/usr/bin/env python
# dev/gen_loups_garous.py
# Les familles de la bête et les chiens d'Irlande (docs/lore/monde/20261014_les_loups_garous_de_telluris.md,
# cinq arbitrages de l'Auteur du 14/10) dans le bestiaire :
#   - Irlande : `espece:faoladh` (loup-garou gardien), `espece:cu_sidhe` (chien des tertres),
#     `espece:dobhar_chu` (chien des eaux), `espece:failinis` (être unique, boss) ;
#   - Amériques : `espece:nahual` (sorcier au double de jaguar), `espece:uturuncu` (chaman
#     perdu dans le jaguar) ;
#   - Nord et Grèce : `espece:ulfhedinn` (chasseur en peau de loup, HUMANOÏDE armé),
#     `espece:lycaon` (roi-loup d'Arcadie, être unique, boss) ;
#   - `espece:loup_garou` (déjà en jeu) devient le loup-garou de FRANCE : description seule,
#     `_id` et caractéristiques inchangés (Auteur).
# Lune et faiblesses de chaque famille : DESCRIPTION SEULE, aucune mécanique (comme les vampires).
# Images détourées dans templates/resources/monsters/ ; le nahual n'en a pas encore (prompt au § 12).
# Loot : une CARCASSE par bête (forme de `item:loup`, poids [min, max] ≤ 100 kg : pas de
# découpe), des OSSEMENTS pour l'ulfheðinn humanoïde (forme de `gen_vampires._ossements`).
#
# ⚠️ Les tables EXHAUSTIVES de `gen_genres_especes.py`, `gen_jetons_especes.py` et
# `gen_equipement_humanoides.py` citent déjà les espèces neuves : elles échouent tant que
# l'import n'est pas fait et qu'un dump FRAIS ne l'a pas relu. Le kit de l'ulfheðinn est LU
# dans la table de `gen_equipement_humanoides.py` (source unique) et vérifié par `erreurs_kit`.
#
# ⚠️ POURQUOI UN SCRIPT : `admin_import_bulk` fait un PUT COMPLET. Le loup-garou est RELU du
# dump le plus récent et seule sa description change ; un doc neuf dont l'`_id` est déjà en
# base n'est jamais réécrit (« déjà en base »). Le fichier ne porte que le DELTA (CLAUDE.md §18).
#
# Usage : python dev/gen_loups_garous.py [jsons/telluris-dump-….json]
# Sortie : jsons/loups_garous_a_importer.json

import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gen_equipement_humanoides import TABLE as KITS, _dump_le_plus_recent, charger, erreurs_kit  # noqa: E402
from gen_vampires import _attrs, _ossements, _sans_rev  # noqa: E402

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "loups_garous_a_importer.json")

# ── Doc existant : champs remplacés ────────────────────────────────────────────

MODIFS = {
	# Loup-garou de France (Auteur, 14/10) : « anthrope », pas « humain » — toute Lignée.
	"espece:loup_garou": {
		"description": "Anthrope maudit que la pleine lune change en bête, comme on en conte dans les "
					   "campagnes de France ; force et rage décuplées. Appelé par son nom, ou blessé "
					   "jusqu'au sang, il redevient anthrope.",
	},
}

# ── Espèces neuves ─────────────────────────────────────────────────────────────
# `carcasse` = (poids min, poids max, rareté) d'une bête ; absent = ossements (humanoïde).

NOUVELLES = {
	# Irlande — gardiens (Auteur) : le faoladh n'attaque que s'il croit menacés ceux qu'il garde.
	"faoladh": {
		"nom": "Faoladh", "genre": "m", "image": "faoladh_transparent.png",
		"description": "Loup-garou d'Irlande, héritier du don de Laignech Fáelad : il garde les enfants, "
					   "les blessés et les égarés, et ne frappe que s'il les croit menacés. Pendant "
					   "qu'il court, son corps anthrope dort là où il l'a laissé ; déplacé, l'esprit ne "
					   "le retrouve plus.",
		"base_attributes": _attrs((5, 7), (40, 65), (40, 60), (45, 70), (45, 65), (30, 45), (0, 0), (25, 45)),
		"tags": ["monstre", "metamorphe", "gardien", "nocturne"],
		"carcasse": ([40, 80], "peu_commun"),
	},
	"cu_sidhe": {
		"nom": "Cú Sídhe", "genre": "m", "image": "cu_sidhe_transparent.png",
		"description": "Chien des tertres, grand comme un jeune taureau, au pelage vert sombre : il "
					   "chasse en silence et n'aboie que trois fois — au troisième aboiement, qui "
					   "l'entend meurt de peur. Il ne franchit pas l'eau courante.",
		"base_attributes": _attrs((6, 8), (40, 60), (35, 55), (50, 75), (40, 60), (25, 40), (0, 0), (20, 40)),
		"tags": ["monstre", "feerique", "terreur", "predateur"],
		"carcasse": ([60, 100], "peu_commun"),
	},
	"dobhar_chu": {
		"nom": "Dobhar-chú", "genre": "m", "image": "dobhar_chu_transparent.png",
		"description": "Chien des eaux, mi-chien mi-loutre, qui guette les lacs du nord-ouest de "
					   "l'Irlande et tue qui s'y baigne. Quand on l'abat, son compagnon sort de l'eau "
					   "pour le venger.",
		"base_attributes": _attrs((5, 7), (35, 55), (35, 55), (45, 65), (25, 40), (15, 25), (0, 0), (15, 30)),
		"tags": ["monstre", "aquatique", "predateur"],
		"carcasse": ([30, 60], "commun"),
	},
	# Être unique (Auteur) : « Failinis », pas « le Failinis ».
	"failinis": {
		"nom": "Failinis", "genre": "m", "nom_propre": True, "image": "failinis_transparent.png",
		"description": "Le chien invincible du roi d'Ioruaidh, que Lugh voulut pour lui : nulle bête ne "
					   "lui échappe, et toute bête qui le voit tombe. Nul ne sait s'il est chien, loup "
					   "ou autre chose venu d'un tertre.",
		"base_attributes": _attrs((7, 9), (60, 85), (55, 80), (70, 95), (55, 80), (30, 45), (0, 0), (50, 75)),
		"tags": ["monstre", "feerique", "predateur", "legendaire", "boss"],
		"carcasse": ([50, 90], "rare"),
	},
	# Amériques (Auteur) : nahual à volonté, uturuncu par un rite — et perdu s'il tarde.
	"nahual": {
		"nom": "Nahual", "genre": "m",
		"description": "Sorcier des terres de Teotihuacan qui revêt à volonté la forme de son double, "
					   "un jaguar. On dit que Tepeyollotl, le Cœur de la montagne, donna le premier "
					   "double ; d'autres le nient. Ce qui blesse le jaguar blesse le sorcier, et le sel "
					   "jeté sur sa peau abandonnée lui interdit de la reprendre.",
		"base_attributes": _attrs((6, 8), (35, 55), (35, 50), (55, 80), (55, 80), (50, 75), (0, 0), (30, 50)),
		"tags": ["monstre", "metamorphe", "magique", "nocturne"],
		"carcasse": ([40, 80], "peu_commun"),
	},
	"uturuncu": {
		"nom": "Uturuncu", "genre": "m", "image": "uturuncu_transparent.png",
		"description": "Chaman d'Amazonie devenu jaguar par le rite, qui a trop tardé à revenir : il ne "
					   "redeviendra jamais anthrope. Seuls ses yeux, et les lambeaux d'un collier de "
					   "graines, rappellent ce qu'il était.",
		"base_attributes": _attrs((6, 8), (50, 75), (40, 60), (55, 80), (30, 50), (10, 20), (0, 0), (20, 35)),
		"tags": ["monstre", "metamorphe", "predateur", "foret"],
		"carcasse": ([60, 100], "peu_commun"),
	},
	# Nord (Auteur) : un chasseur que la peau a pris — humanoïde armé, kit de gen_equipement.
	"ulfhedinn": {
		"nom": "Ulfheðinn", "genre": "m", "image": "ulfhedinn_transparent.png",
		"description": "Chasseur de monstres du Nord vêtu d'une peau de loup : la peau l'a pris, la rage "
					   "le rend sourd à la douleur et il ne reconnaît plus personne. Brûlée, la peau "
					   "perd son pouvoir.",
		"base_attributes": _attrs((5, 7), (50, 75), (50, 70), (35, 55), (50, 70), (15, 30), (10, 25), (25, 45)),
		"tags": ["metamorphe", "guerrier", "humanoide"],
	},
	# Être unique, boss (Auteur) : la malédiction des dieux qui ne vaut que pour lui.
	"lycaon": {
		"nom": "Lycaon", "genre": "m", "nom_propre": True, "image": "lycaon_transparent.png",
		"description": "Roi d'Arcadie qui servit de la chair anthrope à un dieu de passage : les dieux "
					   "le changèrent en loup. La chair anthrope le garde loup ; qui s'en abstiendrait "
					   "neuf ans redeviendrait anthrope, et il ne s'en abstient jamais.",
		"base_attributes": _attrs((6, 8), (65, 90), (60, 85), (55, 80), (60, 85), (40, 60), (0, 0), (40, 60)),
		"tags": ["monstre", "metamorphe", "malediction", "legendaire", "boss"],
		"carcasse": ([70, 100], "rare"),
	},
}

ACCORD = ("nom_propre", "pluriel", "h_aspire")


def _carcasse(espece_id: str, nom: str, poids: list, rarete: str) -> dict:
	"""Même forme que les carcasses du dump (`item:loup`)."""
	return {
		"_id": "item:" + espece_id.split(":", 1)[1],
		"type": "item",
		"nom": "Carcasse de " + nom,
		"sous_categorie": "carcasse",
		"icon": "🥩",
		"rarete": rarete,
		"categorie": "composant",
		"slots": [],
		"poids": list(poids),
		"description": f"Dépouille de {nom} récupérée à l'issue du combat.",
		"source_espece": espece_id,
		"loot_defaut": True,
	}


def docs_loups_garous(base: dict) -> tuple[list, list]:
	"""(docs à importer, ids déjà en base) d'après les docs du dump `base` ({_id: doc})."""
	items = {i: d for i, d in base.items() if i.startswith("item:")}
	erreurs, docs, deja = [], [], []

	for i in MODIFS:
		if i not in base:
			erreurs.append(f"{i} absent du dump")

	especes = {}
	for slug, spec in NOUVELLES.items():
		eid = "espece:" + slug
		doc = {
			"_id": eid, "type": "espece", "nom": spec["nom"], "genre": spec["genre"],
			**{k: True for k in ACCORD if spec.get(k)},
			"image": spec.get("image", ""),
			"description": spec["description"],
			"base_attributes": copy.deepcopy(spec["base_attributes"]),
			"tags": list(spec["tags"]),
		}
		kit = KITS.get(slug)
		if "humanoide" in doc["tags"] and not kit:
			erreurs.append(f"{eid} : humanoïde sans kit dans gen_equipement_humanoides.TABLE")
		if kit:
			doc["items"] = ["item:" + i for i in kit]
			e = erreurs_kit(slug, doc, kit, items)
			if e:
				erreurs.append(f"{eid} : " + " ; ".join(e))
		doc["proprietes"] = {}
		especes[eid] = doc
	if erreurs:
		sys.exit("ERREUR :\n   " + "\n   ".join(erreurs))

	for eid, doc in especes.items():
		if eid in base:
			deja.append(eid)
		else:
			docs.append(doc)
		oid = "item:" + eid.split(":", 1)[1]
		if oid in base:
			deja.append(oid)
			continue
		carcasse = NOUVELLES[eid.split(":", 1)[1]].get("carcasse")
		if carcasse:
			docs.append(_carcasse(eid, doc["nom"], *carcasse))
		else:
			docs.append(_ossements(eid, doc["nom"], doc["base_attributes"]))

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
	docs, deja = docs_loups_garous(base)
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
