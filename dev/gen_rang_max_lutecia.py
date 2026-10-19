#!/usr/bin/env python3
# dev/gen_rang_max_lutecia.py
# Le Grand Relais des Frontières (Lutecia) délivre TOUTE l'échelle des rangs, jusqu'à S+ : la
# capitale est le lieu de la trame D → S+ (docs/lore/redige/06_personnages_et_trame.md).
#
# Deux retouches, relues sur le DERNIER DUMP (l'import est un PUT complet, CLAUDE.md §11) :
#   · lieu:le_grand_relais_des_frontieres_comptoir — `rang_max: "S+"`. Sans le champ, le comptoir
#     prenait `RANG_GUILDE_MAX_DEFAUT` ("D") et, l'apport du rang C passé, Éléonore renvoyait vers
#     « la guilde d'une autre cité ».
#   · pnj:eleonore_de_vaugirard — nœud `rang_sommet` réécrit : il ne s'affiche plus qu'au SOMMET
#     de l'échelle (flag `rang_max` = rang ≥ plafond du comptoir = S+), donc il dit le sommet.
#
# ⚠️ Le plafond ne crée aucune épreuve : les chasses générées restent bornées par le plancher de
# puissance (`QUETE_RANG_POTENTIEL_MIN`), que le bestiaire de Lutecia ne dépasse pas au-delà de D.
# Les rangs B et plus attendent des épreuves écrites.
#
# Le même texte est recopié dans les fichiers source qui portent Éléonore, pour qu'un ré-import
# ne défasse pas la correction.
#
# Usage : python dev/gen_rang_max_lutecia.py [jsons/telluris-dump-….json]

import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSONS = os.path.join(RACINE, "jsons")
SORTIE = os.path.join(JSONS, "rang_max_lutecia_a_importer.json")
SOURCES_ELEONORE = [
	os.path.join(JSONS, "maelys_maitresse_de_guilde_a_importer.json"),
	os.path.join(JSONS, "correctifs_dialogues_a_importer.json"),
]

COMPTOIR = "lieu:le_grand_relais_des_frontieres_comptoir"
ELEONORE = "pnj:eleonore_de_vaugirard"
RANG_MAX = "S+"

RANG_SOMMET = (
	"« Une épreuve à votre mesure ? » Éléonore referme le registre, lentement, et pose la main à plat "
	"sur la couverture. « Rang {rang}. Adamantite. Il n'y a pas de page après celle-ci, {prenom} : "
	"la Guilde n'a plus rien à vous demander, ici ni ailleurs. » Elle vous regarde longtemps, comme "
	"le jour où vous avez posé la main sur ce comptoir pour la première fois. « Ce qui viendra "
	"maintenant, personne ne vous le confiera. Il faudra aller le chercher vous-même — et revenir me "
	"le raconter. Je l'écrirai. » Un léger sourire. « Ce sera la première fois. »"
)


def dernier_dump():
	dumps = sorted(glob.glob(os.path.join(JSONS, "telluris-dump-*.json")))
	if not dumps:
		sys.exit("Aucun dump dans jsons/")
	return dumps[-1]


def comptoir(doc):
	doc = dict(doc)
	doc.pop("_rev", None)
	doc["rang_max"] = RANG_MAX
	return doc


def eleonore(doc):
	doc = json.loads(json.dumps(doc))
	doc.pop("_rev", None)
	doc["dialogue"]["noeuds"]["rang_sommet"]["texte"] = RANG_SOMMET
	return doc


def synchroniser_source(chemin):
	"""Recopie le nouveau `rang_sommet` dans un fichier source qui porte Éléonore (idempotent)."""
	with open(chemin, encoding="utf-8") as f:
		docs = json.load(f)
	for doc in docs:
		if doc.get("_id") == ELEONORE:
			doc["dialogue"]["noeuds"]["rang_sommet"]["texte"] = RANG_SOMMET
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
		f.write("\n")


def main():
	chemin = sys.argv[1] if len(sys.argv) > 1 else dernier_dump()
	with open(chemin, encoding="utf-8") as f:
		docs = {d["_id"]: d for d in json.load(f)["docs"]}
	sortie = [comptoir(docs[COMPTOIR]), eleonore(docs[ELEONORE])]
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")
	for source in SOURCES_ELEONORE:
		synchroniser_source(source)
	print(f"{len(sortie)} docs → {os.path.relpath(SORTIE, RACINE)} (dump : {os.path.basename(chemin)})")


if __name__ == "__main__":
	main()
