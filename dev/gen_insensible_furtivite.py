#!/usr/bin/env python
# dev/gen_insensible_furtivite.py
# Pose le tag `insensible_furtivite` sur les espèces qui perçoivent les furtifs.
#
# Lu par `utils/combat.py` (TAG_INSENSIBLE_FURTIVITE) : le monstre a REPÉRÉ le joueur dès
# son snapshot et ne l'oublie jamais (ni `_activer_furtivite`, ni l'entrée furtive d'un
# donjon à étages) — pas d'embuscade, pas de coup furtif contre lui.
#
# ⚠️ `admin_import_bulk` fait un PUT COMPLET : on RELIT chaque espèce depuis le dump le plus
# récent et on n'y ajoute que le tag — régénération idempotente, une espèce qui le porte déjà
# n'est pas réimportée.
#
# Usage : python dev/gen_insensible_furtivite.py
# Sortie (à coller dans /admin → Import en masse) :
#   jsons/insensible_furtivite_a_importer.json

import glob
import json
import os

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = "jsons/insensible_furtivite_a_importer.json"
TAG = "insensible_furtivite"   # = utils.combat.TAG_INSENSIBLE_FURTIVITE

ESPECES = (
	# Esprits et morts-vivants
	"fantome", "spectre", "banshee", "revenant", "jann",
	# Sens surnaturels
	"chauve_souris", "chauve_souris_geante", "ange_de_la_connaissance", "seraphin", "avatar",
	"liche", "roi_liche",
	# Gardiens
	"cerbere", "ammit",
	# Boss
	"archange_de_l_ordre", "archange_du_savoir", "demon_majeur_de_la_destinee", "prince_demon",
	# Superprédateurs
	"bete_du_gevaudan", "bete_de_l_apocalypse", "grootslang", "boukhnoun", "fauves",
)


def _dump_le_plus_recent() -> str:
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		raise SystemExit("ERREUR : aucun jsons/telluris-dump-*.json — exporter la base d'abord.")
	return dumps[-1]


def main() -> None:
	dump = _dump_le_plus_recent()
	with open(dump, encoding="utf-8") as f:
		docs = {d["_id"]: d for d in json.load(f)["docs"]}
	sortie = []
	for slug in ESPECES:
		doc = docs.get(f"espece:{slug}")
		if doc is None:
			raise SystemExit(f"ERREUR : espece:{slug} absente de {os.path.basename(dump)}.")
		tags = list(doc.get("tags") or [])
		if TAG in tags:
			continue
		doc = {k: v for k, v in doc.items() if k != "_rev"}
		doc["tags"] = tags + [TAG]
		sortie.append(doc)
	with open(os.path.join(RACINE, SORTIE), "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
	print(f"{len(sortie)} espèce(s) → {SORTIE} (dump {os.path.basename(dump)})")


if __name__ == "__main__":
	main()
