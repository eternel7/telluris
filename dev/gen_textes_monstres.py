#!/usr/bin/env python
# dev/gen_textes_monstres.py
# Textes guerriers orientés vers les monstres (Auteur, 26/11/2026, critique au regard du cahier
# des règles du monde) : « aucune guerre entre Anthropes ; une armée de monstres peut exister ».
# Seules les descriptions qui supposent des armées ou des guerres anthropes sont réécrites ; le
# vocabulaire de combat (« Cri de guerre », « champ de bataille », soldats des garnisons) reste.
#
# Relit le dump le plus récent et n'écrit que les docs qui CHANGENT (CLAUDE.md §11, §18) →
# jsons/textes_monstres_a_importer.json. Rejouable : un remplacement déjà appliqué (nouveau texte
# présent, ancien absent) est sauté ; un texte introuvable est une ERREUR.
#
# Sources corrigées dans la même passe (sinon une régénération rétablirait l'ancien texte) :
# dev/competences_1_10/{barbare,guerrier,mage}.py, dev/gen_armes_armures_add2e.py,
# dev/gen_descriptions_items.py, templates/home_telluris.html.
#
# Usage : python dev/gen_textes_monstres.py

import copy
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "textes_monstres_a_importer.json")

LANCE_AVANT = "plus faite pour l'office que pour la guerre"
LANCE_APRES = "plus faite pour l'office que pour la chasse aux monstres"

# (doc, chemin du champ, ancien fragment, nouveau fragment)
REMPLACEMENTS = [
	("competence:conjurateur", ("description",), "ont déjà détourné des armées", "ont déjà détourné des hordes entières"),
	("competence:inebranlable", ("description",), "pour arrêter l'armée", "pour arrêter la horde"),
	("competence:lame_enchantee", ("description",), "au service de la guerre", "au service du combat"),
	("competence:avatar_de_la_rage", ("description",), "l'esprit de la guerre", "l'esprit de la bataille"),
	("espece:cheval_normand", ("description",), "Race de guerre", "Race de combat"),
	("espece:grand_sanglier", ("description",), "Sanglier de guerre aux défenses acérées, monture brutale prisée pour les charges de front.",
	 "Sanglier de combat aux défenses acérées, monture brutale prisée pour charger les monstres de front."),
	("espece:prince_demon", ("description",), "peut déchaîner des guerres", "peut lancer ses hordes sur un monde"),
	("item:Doloire", ("description",), "détournée pour la guerre", "détournée pour le combat"),
	("item:Lance_rituelle", ("description",), LANCE_AVANT, LANCE_APRES),
	("item:Lance_rituelle_26b48628", ("description",), LANCE_AVANT, LANCE_APRES),
	("item:Lance_rituelle_e6cf4b19", ("description",), LANCE_AVANT, LANCE_APRES),
	("rules:vocations", ("value", "id=mage", "blurb"), "au service de la guerre", "au service du combat"),
	("rules:vocations", ("value", "id=illusionniste", "blurb"), "peuvent détourner des armées", "peuvent détourner des hordes"),
]


def dernier_dump():
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		sys.exit("ERREUR : aucun dump jsons/telluris-dump-*.json")
	with open(dumps[-1], encoding="utf-8") as f:
		return {d["_id"]: d for d in json.load(f)["docs"]}, os.path.basename(dumps[-1])


def _parent(doc, chemin):
	"""(conteneur, clé) du champ visé ; `id=x` choisit l'élément de liste dont `id` vaut x."""
	cur = doc
	for etape in chemin[:-1]:
		if isinstance(cur, list) and etape.startswith("id="):
			cur = next((e for e in cur if isinstance(e, dict) and e.get("id") == etape[3:]), None)
		else:
			cur = cur.get(etape) if isinstance(cur, dict) else None
		if cur is None:
			sys.exit(f"ERREUR : {doc['_id']} n'a pas {'.'.join(chemin)}")
	return cur, chemin[-1]


def remplacer(doc, chemin, avant, apres):
	cont, cle = _parent(doc, chemin)
	texte = cont.get(cle) or ""
	if avant in texte:
		cont[cle] = texte.replace(avant, apres)
	elif apres not in texte:
		sys.exit(f"ERREUR : {doc['_id']} {'.'.join(chemin)} : texte introuvable ({avant!r})")


def corriger(base: dict) -> list:
	"""Docs corrigés qui DIFFÈRENT de `base`, dans un ordre stable."""
	docs = {}
	for did, chemin, avant, apres in REMPLACEMENTS:
		if did not in base:
			sys.exit(f"ERREUR : {did} absent du dump")
		if did not in docs:
			docs[did] = copy.deepcopy(base[did])
			docs[did].pop("_rev", None)
		remplacer(docs[did], chemin, avant, apres)
	return [d for did, d in sorted(docs.items())
			if d != {k: v for k, v in base[did].items() if k != "_rev"}]


def main():
	base, nom = dernier_dump()
	docs = corriger(base)
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"{len(docs)} docs ({nom}) → {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
	main()
