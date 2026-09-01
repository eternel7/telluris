#!/usr/bin/env python
# dev/gen_armes_tranchantes.py
# Pose le tag `tranchant` sur les armes qui ont un VRAI FIL — celles avec lesquelles on peut
# débiter une carcasse (`utils/carcasse.a_arme_tranchante`).
#
# ⚠️ POURQUOI UNE LISTE À LA MAIN ET PAS UNE HEURISTIQUE. Les 105 armes du jeu ne portent que
# quatre tags (`cac`, `jet`, `hast`, `tir`) et leur `sous_categorie` est VIDE dans 91 cas sur
# 105 : il n'existe aucun champ dont « a un fil » se déduirait. Un filtre sur le nom se
# tromperait dans les deux sens — le « Bec de corbin » et le « Trident barbelé » sont des
# armes d'HAST qui percent, la « Masse d'armes bénie » et le « Casse-tête polynésien »
# écrasent, tandis que la « Hunga munga » et le « Kpinga » sont bel et bien des lames de jet.
# La liste est donc explicite, et le script SORT EN ERREUR sur un id absent du dump : mieux
# vaut un échec bruyant qu'un tag posé nulle part.
#
# LE CRITÈRE : une lame ou un tranchant d'acier assez long pour ouvrir une bête — épées,
# couteaux et dagues, haches, lames de jet, et les armes d'hast à FER TRANCHANT (faucharde,
# guisarme, hallebarde, naginata, ji, pata à hampe). Sont exclus, volontairement :
#   · tout ce qui ÉCRASE (masses, fléaux, marteaux, bâtons, cestes, casse-têtes) ;
#   · tout ce qui PERCE sans trancher (lances, piques, javelots, plumbatae, poinçons, ainsi
#     que le bec de corbin et le trident) ;
#   · tout ce qui se lance sans fil utile (bolas, boomerang, shuriken, kestros, sarbacane) ;
#   · les arcs et arbalètes — la corde ne coupe rien ;
#   · les instruments de musique, rangés en `categorie: arme` par le bestiaire d'items.
#
# ⚠️ La rapière EST incluse alors qu'elle estoque : c'est une lame d'acier de 100 cm, un
# boucher s'en tirerait. La distinction perce/tranche a été poussée jusqu'aux armes d'hast,
# pas jusqu'aux épées — aucune épée du jeu n'est un pur estoc.
#
# ⚠️ POURQUOI UN SCRIPT ET PAS UN JSON ÉCRIT À LA MAIN : `admin_import_bulk` fait un PUT
# COMPLET, jamais un merge — éditer un champ oblige à reproduire tout le doc. On RELIT donc
# les armes depuis le dump et on n'y ajoute que le tag : régénérer est idempotent, et les
# `outil_coupe_bois` déjà posés sur les deux haches survivent.
#
# Usage : python dev/gen_armes_tranchantes.py
# Sortie (à coller dans /admin -> Import en masse) :
#   jsons/armes_tranchantes_a_importer.json

import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from models import character_stats   # noqa: E402

# SOURCE UNIQUE : le dump complet de la base. ⚠️ Figé explicitement (et non « le glob le plus
# récent ») pour que régénérer donne toujours le même résultat ; à mettre à jour à la main
# après un nouveau dump.
SRC_DUMP = "jsons/telluris-dump-20260831-122931.json"

TAG = character_stats.CARCASSE_TRANCHANT_TAG

SORTIE = "jsons/armes_tranchantes_a_importer.json"

# Slugs (sans le préfixe `item:`), groupés pour être relus.
TRANCHANTES: dict[str, list] = {
	"couteaux et dagues": [
		"Couteau_de_chasse", "Couteau_de_jet_africain", "Dague", "Dague_de_jet",
		"Dague_de_parade", "Dague_de_scene", "dague_rituelle", "Kunai", "Lame_courte",
	],
	"epees": [
		"Da_dao", "Epee_argent", "Epee_courte", "Epee_courte_rune", "Epee_longue",
		"Epee_longue_ordre", "Epee_une_main_benie", "Gladius", "Jian", "Katana",
		"Rapiere", "Schiavona", "Talwar",
	],
	"haches": [
		"Francisque", "Hache_apparat_amerindienne", "Hache_de_bucheron", "Hache_de_guerre",
		"Hachette_scandinave", "Nzappa_zap", "Sagaris", "Tomahawk",
	],
	"lames de jet": [
		"Chakram", "Hunga_munga", "Kpinga", "Mambele",
	],
	"hast a fer tranchant": [
		"Faucharde", "Guisarme", "Hallebarde", "Ji", "Naginata", "Pata_a_hampe",
	],
}

# ⚠️ ARMES NON IDENTIFIÉES, volontairement LAISSÉES DE CÔTÉ : ni le dump ni le nom ne disent
# si elles tranchent (aucune `description` en base). Les taguer au jugé mettrait un fil sur
# une masse ; les inscrire ici les rend visibles plutôt que silencieusement oubliées.
# Il suffit de déplacer une ligne dans TRANCHANTES pour trancher (sans jeu de mots).
INCERTAINES: list[str] = ["Omukuba", "Sestiere", "Sheitan", "Woludo"]


def charger(chemin: str) -> list:
	"""Docs d'un export admin ou d'un dump : tableau nu, ou {"docs": [...]}."""
	with open(os.path.join(RACINE, chemin), encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


def main() -> None:
	par_id = {d["_id"]: d for d in charger(SRC_DUMP)
			  if isinstance(d, dict) and d.get("_id")}

	voulus = [(groupe, "item:" + slug)
			  for groupe, slugs in TRANCHANTES.items() for slug in slugs]

	absents = [iid for (_g, iid) in voulus if iid not in par_id]
	if absents:
		sys.exit("ERREUR : armes introuvables dans le dump :\n   " + "\n   ".join(absents))
	# Une arme est `categorie: "arme"` — poser un fil sur une armure signalerait une faute de
	# frappe dans la liste, pas une intention.
	pas_armes = [iid for (_g, iid) in voulus if par_id[iid].get("categorie") != "arme"]
	if pas_armes:
		sys.exit("ERREUR : ces docs ne sont pas des armes :\n   " + "\n   ".join(pas_armes))

	sortie, deja = [], 0
	for (groupe, iid) in voulus:
		doc = par_id[iid]
		tags = list(doc.get("tags") or [])
		if TAG in tags:
			deja += 1
		else:
			tags.append(TAG)
		doc["tags"] = tags
		sortie.append(doc)

	chemin = os.path.join(RACINE, SORTIE)
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")

	print(f"ecrit {SORTIE}")
	print(f"   {len(sortie)} arme(s) taguees `{TAG}` "
		  f"({deja} deja a jour - reimport sans effet)")
	for groupe, slugs in TRANCHANTES.items():
		print(f"   {groupe:24} {len(slugs):>2}   {', '.join(slugs)}")
	print(f"   NON taguees (a trancher a la main) : {', '.join(INCERTAINES)}")


if __name__ == "__main__":
	main()
