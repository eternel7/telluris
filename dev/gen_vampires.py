#!/usr/bin/env python
# dev/gen_vampires.py
# Les cinq lignées de vampires (docs/lore/monde/20261012_les_vampires_de_telluris.md) dans le
# bestiaire :
#   - `espece:strigoi` (NOUVEAU) reprend les caractéristiques et les tags de l'ancien
#     `espece:nosferatu` bestial — c'était déjà le portrait des Strigoï ;
#   - `espece:nosferatu` devient un MAGE (Int, Vol hautes ; Cha nul : il ne passe pas pour un
#     Anthrope). Son image (crâne quasi nu, oreilles pointues) est gardée en attendant mieux ;
#   - `sort:soif_du_nosferatu` invoque désormais `espece:strigoi` (« Soif du strigoï ») : la bête
#     garde les caractéristiques de l'ancien nosferatu, le budget de l'invocation ne bouge pas
#     (`dev/gen_sorts_invocation.py`). L'`_id` du sort reste, des personnages le connaissent ;
#   - `espece:vampire` / `espece:comte_vampire` : description seule (lignée de Dracula) ;
#   - `espece:lamie`, `espece:dragon_de_sang`, `espece:dragon_de_sang_dechu` (NOUVEAUX), sans
#     image (`image: ""`, prompts au § 8 de la séance) ;
#   - un `item:<espece>` d'ossements par espèce neuve, `item:nosferatu` au poids recalculé —
#     même forme que ceux du dump (poids = F moyenne / 5).
#
# ⚠️ Les tables EXHAUSTIVES de `gen_genres_especes.py`, `gen_jetons_especes.py` et
# `gen_equipement_humanoides.py` citent déjà les espèces neuves, et `gen_sorts_invocation.py`
# l'invocation du strigoï : ces quatre scripts échouent tant que l'import n'est pas fait et
# qu'un dump FRAIS ne l'a pas relu. Les kits d'équipement sont LUS dans la table de
# `gen_equipement_humanoides.py` (source unique) et vérifiés par la même `erreurs_kit`.
#
# ⚠️ POURQUOI UN SCRIPT : `admin_import_bulk` fait un PUT COMPLET. Les docs existants sont
# RELUS du dump le plus récent et seuls les champs listés changent ; un doc neuf dont l'`_id`
# est déjà en base n'est jamais réécrit (il apparaît « déjà en base »). Idempotent.
#
# Usage : python dev/gen_vampires.py
# Sortie (à coller dans /admin → Import en masse) :
#   jsons/vampires_a_importer.json

import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gen_equipement_humanoides import TABLE as KITS, _dump_le_plus_recent, charger, erreurs_kit  # noqa: E402

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = "jsons/vampires_a_importer.json"


def _attrs(V, F, R, Ag, Vol, Int, Cha, Ch) -> dict:
	return {k: {"min": a, "max": b} for k, (a, b) in
			zip(("V", "F", "R", "Ag", "Vol", "Int", "Cha", "Ch"), (V, F, R, Ag, Vol, Int, Cha, Ch))}


# ── Docs existants : champs remplacés ──────────────────────────────────────────

MODIFS = {
	"espece:nosferatu": {
		"description": "Vampire chauve et livide aux doigts trop longs, que nul ne prendrait pour un "
					   "Anthrope ; héritier de la sorcellerie de Babylone, il manie une magie que peu "
					   "de vivants atteignent.",
		"base_attributes": _attrs((5, 7), (25, 40), (30, 50), (30, 50), (60, 85), (60, 90), (0, 0), (25, 45)),
		"tags": ["undead", "non_mort", "magique", "nocturne"],
	},
	"espece:vampire": {
		"description": "Vampire aristocrate de la lignée de Dracula : d'apparence toute anthrope, "
					   "séducteur, aussi habile à l'épée qu'en magie, il craint le soleil.",
	},
	"espece:comte_vampire": {
		"description": "Aîné de la lignée de Dracula, noble et ancien ; son influence et sa puissance "
					   "dépassent largement celles de ses cadets.",
	},
	"sort:soif_du_nosferatu": {
		"nom": "Soif du strigoï",
		"description": "Une silhouette voûtée se déplie dans l'ombre, les os de travers et les crocs "
					   "déjà découverts. Le strigoï frappe vite et sans bruit, comme la bête qu'on a "
					   "faite de lui.",
	},
}

# ── Espèces neuves ─────────────────────────────────────────────────────────────
# `None` en base_attributes/tags = repris de l'ancien `espece:nosferatu` (relu AVANT sa
# réécriture : une relance après import relit le strigoï lui-même, déjà en base).

NOUVELLES = {
	"strigoi": {
		"nom": "Strigoï", "genre": "m",
		"description": "Vampire difforme aux os mal ressoudés et au crâne enfoncé : son maître a brisé "
					   "son cadavre avant de le relever par le sang. Il ne ruse pas, il fond sur sa proie.",
		"base_attributes": None, "tags": None,
	},
	"lamie": {
		"nom": "Lamie", "genre": "f",
		"description": "Vampire d'une beauté souveraine, fille de la reine Lamia ; elle séduit avant de "
					   "boire, et le soleil la laisse inerte comme une statue.",
		"base_attributes": _attrs((5, 7), (30, 50), (30, 50), (45, 70), (45, 70), (45, 70), (60, 90), (0, 0)),
		"tags": ["undead", "non_mort", "magique", "seduction", "humanoide"],
	},
	"dragon_de_sang": {
		"nom": "Dragon de sang", "genre": "m",
		"description": "Paladin de l'Ordre du Dragon relevé par le sang ; tant qu'il garde la foi, le "
					   "soleil ne peut rien contre lui, et il protège encore les routes.",
		"base_attributes": _attrs((6, 8), (45, 70), (45, 70), (35, 55), (60, 85), (35, 55), (35, 55), (20, 35)),
		"tags": ["undead", "non_mort", "guerrier", "magique", "humanoide"],
	},
	"dragon_de_sang_dechu": {
		"nom": "Dragon de sang déchu", "genre": "m",
		"description": "Dragon de sang qui a perdu la foi ; le soleil le gêne, et de son serment il ne "
					   "lui reste que la soif.",
		"base_attributes": _attrs((6, 8), (50, 75), (45, 70), (35, 55), (45, 65), (30, 45), (20, 35), (25, 40)),
		"tags": ["undead", "non_mort", "guerrier", "nocturne", "humanoide"],
	},
}

# Invocation retargetée : même sort, la bête porte désormais son vrai nom.
INVOCATION = ("sort:soif_du_nosferatu", "espece:strigoi")


def _poids_ossements(base_attributes: dict) -> float:
	f = base_attributes.get("F") or {}
	return round((f.get("min", 10) + f.get("max", 10)) / 2 / 5, 1)


def _ossements(espece_id: str, nom: str, base_attributes: dict) -> dict:
	"""Même forme que les `item:<espece>` d'ossements du dump (`item:vampire`, `item:goule`…)."""
	return {
		"_id": "item:" + espece_id.split(":", 1)[1],
		"type": "item",
		"nom": f"Ossements de {nom}",
		"sous_categorie": "ossements",
		"icon": "🦴",
		"rarete": "peu_commun",
		"categorie": "composant",
		"slots": [],
		"poids": _poids_ossements(base_attributes),
		"description": f"Ossements et reliquats récupérés sur {nom} après sa destruction.",
		"source_espece": espece_id,
		"loot_defaut": True,
	}


def _sans_rev(doc: dict) -> dict:
	return {k: v for k, v in copy.deepcopy(doc).items() if k != "_rev"}


def main() -> None:
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	source = _dump_le_plus_recent()
	base = {d["_id"]: d for d in charger(source) if isinstance(d, dict) and d.get("_id")}
	items = {i: d for i, d in base.items() if i.startswith("item:")}
	erreurs, docs, deja = [], [], []

	for i in MODIFS:
		if i not in base:
			erreurs.append(f"{i} absent du dump")
	if erreurs:
		sys.exit("ERREUR :\n   " + "\n   ".join(erreurs))

	# Le strigoï hérite de la bête — lue sur lui-même s'il est déjà en base, sinon sur l'ancien
	# nosferatu, tant qu'il n'a pas encore été réécrit en mage.
	bete = base.get("espece:strigoi") or base["espece:nosferatu"]
	if "magique" in (bete.get("tags") or []):
		sys.exit("ERREUR : espece:nosferatu est déjà un mage et espece:strigoi est absent — "
				 "impossible de retrouver les caractéristiques de la bête.")

	especes_neuves = {}
	for slug, spec in NOUVELLES.items():
		eid = "espece:" + slug
		doc = {
			"_id": eid, "type": "espece", "nom": spec["nom"], "genre": spec["genre"], "image": "",
			"description": spec["description"],
			"base_attributes": spec["base_attributes"] or copy.deepcopy(bete["base_attributes"]),
			"tags": spec["tags"] or list(bete.get("tags") or []),
		}
		kit = KITS.get(slug)
		if kit:
			doc["items"] = ["item:" + i for i in kit]
		doc["proprietes"] = {}
		if kit:
			e = erreurs_kit(slug, doc, kit, items)
			if e:
				erreurs.append(f"{eid} : " + " ; ".join(e))
		especes_neuves[eid] = doc
	if erreurs:
		sys.exit("ERREUR :\n   " + "\n   ".join(erreurs))

	for eid, doc in especes_neuves.items():
		if eid in base:
			deja.append(eid)
		else:
			docs.append(doc)
		oid = "item:" + eid.split(":", 1)[1]
		if oid in base:
			deja.append(oid)
		else:
			docs.append(_ossements(eid, doc["nom"], doc["base_attributes"]))

	for i, champs in MODIFS.items():
		doc = _sans_rev(base[i])
		if all(doc.get(k) == v for k, v in champs.items()) and not (
				i == INVOCATION[0] and (doc.get("invocation") or {}).get("espece") != INVOCATION[1]):
			deja.append(i)
			continue
		doc.update(copy.deepcopy(champs))
		if i == INVOCATION[0]:
			doc["invocation"] = {**(doc.get("invocation") or {}), "espece": INVOCATION[1]}
		docs.append(doc)

	# Ossements du nosferatu : poids recalculé sur sa nouvelle Force.
	oss = base.get("item:nosferatu")
	if oss:
		poids = _poids_ossements(MODIFS["espece:nosferatu"]["base_attributes"])
		if oss.get("poids") == poids:
			deja.append("item:nosferatu")
		else:
			doc = _sans_rev(oss)
			doc["poids"] = poids
			docs.append(doc)

	chemin = os.path.join(RACINE, SORTIE)
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"relu {os.path.relpath(source, RACINE)}")
	for d in docs:
		print(f"   écrit {d['_id']}")
	for i in deja:
		print(f"   déjà en base {i}")
	print(f"écrit {SORTIE} : {len(docs)} doc(s)")


if __name__ == "__main__":
	main()
