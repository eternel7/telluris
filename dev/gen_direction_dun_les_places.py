#!/usr/bin/env python
# dev/gen_direction_dun_les_places.py
# À Auxerre, Milo, Borin et le révérend Malakor indiquent le chemin de Dun-les-Places :
# au sud-est d'Auxerre, à la lisière de la forêt du Morvan, aux sources de l'Yonne
# (France (52,21), Auxerre (50,19) : la route ne fait que la confirmer).
#
# Une réplique de GÉOGRAPHIE, jamais de l'enquête (`quete:la_bete_de_dun_les_places`) : elle se
# dit dans les trois états sans rien trahir. Seul Borin la retire pendant sa quête d'apport
# (`apport_en_cours`) : son « Dun-les-Places… rappelle-moi » la dit déjà, avec Jacotte.
# Borin, Milo et Malakor tutoient ; narration au « vous » ; le joueur vouvoie le révérend.
#
# Part de l'état CORRIGÉ (`gen_correctifs_dialogues.CORRECTIFS` appliqués au dump) : un second
# fichier portant Borin écraserait l'autre au PUT complet de l'import.
# Relit le dump le plus récent, n'écrit que les docs qui CHANGENT (CLAUDE.md §11, §18) →
# jsons/direction_dun_les_places_a_importer.json. Rejouable : un second passage ne change rien.
#
# Usage : python dev/gen_direction_dun_les_places.py

import copy
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_correctifs_dialogues as correctifs  # noqa: E402

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "direction_dun_les_places_a_importer.json")

NOEUD = "dun_les_places"
CHOIX_ID = "dun_les_places"

# pnj → (libellé du joueur, condition du choix, id du choix AVANT lequel l'insérer, nœud)
DIRECTIONS = {
	"pnj:borin_barbe_de_jais": (
		"« Où se trouve Dun-les-Places ? »",
		{"apport_en_cours": False},
		"rien",
		{
			"texte": "Borin tend un doigt épais vers le sud-est, comme si le mur du comptoir n'existait "
					 "pas. « Dun-les-Places ? Un village de charbonniers, dans le Morvan. Tu remontes l'Yonne "
					 "vers ses sources, au sud-est d'ici. Quand la rivière n'est plus qu'un ruisseau qu'on "
					 "enjambe et que la forêt te barre l'horizon, tu y es : le village tient la lisière, "
					 "juste avant les grands bois. Quatre jours de marche, si tes jambes valent les miennes. »",
			"choix": [
				{"id": "merci", "label": "« Merci, Borin. »", "next": "fin"},
				{"id": "retour", "label": "Autre chose…", "next": "accueil"},
			],
		},
	),
	"pnj:milo_cartographe": (
		"« Dun-les-Places, tu sais où c'est ? »",
		None,
		"fin",
		{
			"texte": "Le jeune hobbit repousse l'encrier pour dégager un coin du parchemin. « Dun-les-Places ? "
					 "Attends… là. » Son doigt part d'Auxerre et descend vers le sud-est, le long d'un trait "
					 "bleu qui s'amincit. « Tu remontes l'Yonne, toujours elle, jusqu'à ses sources. Au bout, "
					 "ce n'est plus qu'un filet d'eau qui sort de la forêt, et le village est là, à la lisière "
					 "du Morvan. » Il tapote l'endroit : au-delà, une grande tache verte, sans un seul nom. "
					 "« Après, ma carte s'arrête. Si tu y vas, regarde bien ce qu'il y a derrière les arbres, "
					 "et reviens me le dire. »",
			"choix": [
				{"id": "merci", "label": "« Promis. »", "next": "fin"},
				{"id": "retour", "label": "(Rester près de sa table.)", "next": "accueil"},
			],
		},
	),
	"pnj:reverend_malakor": (
		"Connaissez-vous le chemin de Dun-les-Places ?",
		None,
		"fin",
		{
			"texte": "Le révérend joint ses larges mains. « Dun-les-Places… Au sud-est, mon enfant, aux confins "
					 "du Morvan. Remonte l'Yonne : elle descend de là-bas. Là où elle prend "
					 "sa source, la forêt commence, et le village se tient à sa lisière, entre les champs et les "
					 "grands arbres. Les charbonniers de là-haut passent parfois par ce temple. Ce sont des gens "
					 "rudes, mais leur porte s'ouvre à qui frappe poliment. »",
			"choix": [
				{"id": "retour", "label": "Merci, révérend.", "next": "accueil"},
				{"id": "fin", "label": "J'y vais de ce pas.", "next": "au_revoir"},
			],
		},
	),
}


def dernier_dump():
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		sys.exit("ERREUR : aucun dump jsons/telluris-dump-*.json")
	with open(dumps[-1], encoding="utf-8") as f:
		return {d["_id"]: d for d in json.load(f)["docs"]}, os.path.basename(dumps[-1])


def appliquer(doc):
	"""Mute `doc` (copie) : nœud + choix d'accueil vers Dun-les-Places. Idempotent."""
	label, condition, avant, noeud = DIRECTIONS[doc["_id"]]
	dialogue = doc["dialogue"]
	dialogue["noeuds"][NOEUD] = copy.deepcopy(noeud)
	choix = dialogue["noeuds"][dialogue["noeud_depart"]]["choix"]
	nouveau = {"id": CHOIX_ID, "label": label, "next": NOEUD}
	if condition:
		nouveau["condition"] = copy.deepcopy(condition)
	ids = [c.get("id") for c in choix]
	if CHOIX_ID in ids:
		choix[ids.index(CHOIX_ID)] = nouveau
	else:
		choix.insert(ids.index(avant) if avant in ids else len(choix), nouveau)
	return doc


def etat_vise(doc):
	"""Copie de `doc` : correctifs de dialogue, puis le chemin de Dun-les-Places."""
	doc = copy.deepcopy(doc)
	if doc["_id"] in correctifs.CORRECTIFS:
		correctifs.CORRECTIFS[doc["_id"]](doc)
	return appliquer(doc)


def modifies(docs):
	"""Docs qui changent par rapport à `docs` (sans `_rev`)."""
	sortie = []
	for pid in DIRECTIONS:
		if pid not in docs:
			sys.exit(f"ERREUR : {pid} absent du dump")
		apres = etat_vise(docs[pid])
		if apres != docs[pid]:
			apres.pop("_rev", None)
			sortie.append(apres)
	return sortie


def main():
	docs, nom_dump = dernier_dump()
	sortie = modifies(docs)
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"{len(sortie)} PNJ modifiés (dump {nom_dump}) → {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
	main()
