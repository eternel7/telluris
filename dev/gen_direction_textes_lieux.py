#!/usr/bin/env python
# dev/gen_direction_textes_lieux.py
# La recherche PAR TYPE du service `direction` couvre tous les lieux de la ville
# (`transport.lieux_par_type` : temples, auberges, guilde, portes…), plus seulement les
# magasins. Deux répliques le disent désormais :
#   · la question d'ouverture (`direction_demande`) : « … un genre d'endroit : un temple, une
#     auberge, une boutique ? » au lieu de « un genre de boutique » ;
#   · le refus par type (`type_inconnu`) : « aucun endroit de ce genre en ville » au lieu de
#     « pas de magasin de ce type ».
#
# Textes de référence : `gen_direction_marchands.NOEUDS_DIALOGUE_DIRECTION` (source unique).
# Ne touche QUE le texte de ces deux nœuds chez chaque PNJ qui porte le service `direction` :
# tout le reste du doc est relu du dump le plus récent (PUT complet, CLAUDE.md §11). Les DEUX
# textes dans un seul fichier : deux fichiers séparés s'écraseraient l'un l'autre à l'import.
# Delta seul (§18) → jsons/direction_textes_lieux_a_importer.json. Rejouable : un second
# passage ne change rien.
#
# Usage : python dev/gen_direction_textes_lieux.py

import copy
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_direction_marchands as direction  # noqa: E402

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "direction_textes_lieux_a_importer.json")

# Nœud de la question d'ouverture : celui où mène le choix d'accueil « Vous sauriez m'indiquer
# un lieu ? » (il n'est pas un nœud de service, `services.direction.noeuds` ne le nomme pas).
NOEUD_DEMANDE = direction.CHOIX_ACCUEIL_DIRECTION[0]["next"]
NOEUD_REFUS = direction.NOEUDS_DIRECTION["type_inconnu"]
TEXTES = {nid: direction.NOEUDS_DIALOGUE_DIRECTION[nid]["texte"]
		  for nid in (NOEUD_DEMANDE, NOEUD_REFUS)}


def dernier_dump():
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		sys.exit("ERREUR : aucun dump jsons/telluris-dump-*.json")
	with open(dumps[-1], encoding="utf-8") as f:
		return json.load(f)["docs"], os.path.basename(dumps[-1])


def a_direction(doc):
	"""Le PNJ porte-t-il le service `direction` ?"""
	return bool((((doc or {}).get("services") or {}).get("direction") or {}).get("noeuds"))


def noeuds_vises(doc):
	"""{nœud: texte} à poser sur `doc` : la question d'ouverture et le refus par type, lus
	sur SON service (`type_inconnu`) et son nœud de demande, s'ils existent."""
	noeuds = ((doc.get("dialogue") or {}).get("noeuds") or {})
	refus = (doc["services"]["direction"]["noeuds"]).get("type_inconnu")
	vises = {}
	if NOEUD_DEMANDE in noeuds:
		vises[NOEUD_DEMANDE] = TEXTES[NOEUD_DEMANDE]
	if refus in noeuds:
		vises[refus] = TEXTES[NOEUD_REFUS]
	return vises


def appliquer(doc):
	"""Copie de `doc`, les deux textes remplacés. Idempotent."""
	doc = copy.deepcopy(doc)
	if a_direction(doc):
		for nid, texte in noeuds_vises(doc).items():
			doc["dialogue"]["noeuds"][nid]["texte"] = texte
	return doc


def modifies(docs):
	"""Docs qui changent par rapport à `docs` (sans `_rev`)."""
	sortie = []
	for doc in sorted(docs, key=lambda d: d.get("_id", "")):
		if not a_direction(doc):
			continue
		apres = appliquer(doc)
		if apres != doc:
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
