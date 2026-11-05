#!/usr/bin/env python
# dev/gen_direction_mine_borin.py
# Pendant une commission d'éradication de la mine (`donjon:mine_de_saint_austrelin`, confiée
# par Gautier de Valcroix), Borin indique le chemin du Temple-Portail de Saint-Austrelin, par
# où l'on descend à la mine : à l'EST du Bastion (porte du comptoir (26,22), parvis du temple
# (46,25)-(47,26) sur la grille d'Auxerre — `transport.direction_cardinale` dit « est »).
#
# Choix gardé par la condition `commission_donjon` (utils/pnj.condition_ok) : les ids de
# commission sont générés, `quete_active` ne peut pas les nommer. Hors commission, Borin ne
# propose rien : il n'y a pas de raison d'y descendre.
# Borin tutoie ; narration au « vous ».
#
# Part de l'état VISÉ des générateurs qui touchent déjà Borin (correctifs de dialogue, chemin
# de Dun-les-Places) : un fichier antérieur portant Borin écraserait l'autre au PUT complet.
# Relit le dump le plus récent, n'écrit que les docs qui CHANGENT (CLAUDE.md §11, §18) →
# jsons/direction_mine_borin_a_importer.json. Rejouable : un second passage ne change rien.
#
# Usage : python dev/gen_direction_mine_borin.py

import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_direction_dun_les_places as dun  # noqa: E402

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "direction_mine_borin_a_importer.json")

PNJ = "pnj:borin_barbe_de_jais"
DONJON = "donjon:mine_de_saint_austrelin"
NOEUD = "mine_temple"
CHOIX_ID = "mine_temple"
AVANT = "dun_les_places"

CHOIX = {
	"id": CHOIX_ID,
	"label": "« Par où descend-on à la mine ? »",
	"next": NOEUD,
	"condition": {"commission_donjon": DONJON},
}

NOEUD_DOC = {
	"texte": "Borin jette un œil au sceau de Gautier, puis pointe le pouce vers l'est, par-dessus "
			 "son épaule. « La mine ? On n'y entre pas par un trou dans la colline, {prenom} : on y "
			 "descend par le Temple-Portail de Saint-Austrelin. Sors du Bastion et file à l'est, à "
			 "travers la ville, jusqu'au parvis du temple. Passe le seuil du sanctuaire : un templier "
			 "tient l'escalier du portail, montre-lui ta commission. Plus bas, un autre garde l'arche "
			 "de la mine. Après, c'est toi et ce qui vit dans les galeries. »",
	"choix": [
		{"id": "merci", "label": "« Merci, Borin. »", "next": "fin"},
		{"id": "retour", "label": "Autre chose…", "next": "accueil"},
	],
}


def appliquer(doc):
	"""Mute `doc` : nœud + choix d'accueil vers le temple-portail. Idempotent."""
	dialogue = doc["dialogue"]
	dialogue["noeuds"][NOEUD] = copy.deepcopy(NOEUD_DOC)
	choix = dialogue["noeuds"][dialogue["noeud_depart"]]["choix"]
	ids = [c.get("id") for c in choix]
	if CHOIX_ID in ids:
		choix[ids.index(CHOIX_ID)] = copy.deepcopy(CHOIX)
	else:
		choix.insert(ids.index(AVANT) if AVANT in ids else len(choix), copy.deepcopy(CHOIX))
	return doc


def etat_vise(doc):
	"""Copie de `doc` : correctifs + Dun-les-Places (`gen_direction_dun_les_places`), puis la mine."""
	return appliquer(dun.etat_vise(doc))


def modifies(docs):
	"""Docs qui changent par rapport à `docs` (sans `_rev`)."""
	if PNJ not in docs:
		sys.exit(f"ERREUR : {PNJ} absent du dump")
	if DONJON not in docs:
		sys.exit(f"ERREUR : {DONJON} absent du dump")
	apres = etat_vise(docs[PNJ])
	if apres == docs[PNJ]:
		return []
	apres.pop("_rev", None)
	return [apres]


def main():
	docs, nom_dump = dun.dernier_dump()
	sortie = modifies(docs)
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"{len(sortie)} PNJ modifiés (dump {nom_dump}) → {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
	main()
