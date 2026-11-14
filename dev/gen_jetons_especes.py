#!/usr/bin/env python
# dev/gen_jetons_especes.py
# Donne un GABARIT de jeton de combat aux espèces du bestiaire : taille (LxP) et forme.
#
# Le champ `jeton: {"taille": "LxP", "forme": ...}` (lu par `utils/jetons.py`) fait occuper
# plusieurs cases à un acteur de combat : portées, cases bloquées, zones d'effet et dessin
# en tiennent compte. `L` = largeur en travers de la marche, `P` = profondeur dans le sens de
# la marche (un cheval est 1x2, une envergure d'archange 2x1, un dragon 3x2). La forme
# (ellipse / rectangle / triangle) n'habille que le dessin. Sans champ : 1x1 rond, comme avant.
#
# Principe de la table : triangle = ailés (envergure), rectangle = colosses bipèdes et
# constructs, ellipse = corps organiques. Gabarits admis : 1x1, 2x1, 1x2, 2x2, 3x2, 4x3, 5x4, 2x5.
# Paliers des plus grands : 3x2 pour les dragons et grands monstres ordinaires, 4x3 pour les
# boss légendaires, 5x4 pour le SEUL Dragon Empereur (le plus gros du bestiaire).
#
# ⚠️ LA TABLE EST EXHAUSTIVE : chaque espèce du dump y figure, `None` = 1x1 (aucun champ). Le
# script ÉCHOUE si une espèce du dump manque à la table ou si la table cite une espèce absente —
# une espèce ajoutée depuis ne reçoit jamais un gabarit par défaut sans qu'on l'ait décidé.
#
# ⚠️ POURQUOI UN SCRIPT ET PAS UN JSON ÉCRIT À LA MAIN : `admin_import_bulk` fait un PUT
# COMPLET, jamais un merge. On RELIT donc chaque espèce depuis le dump le plus récent et on n'y
# injecte que `jeton` (placé juste après `nom`) : régénérer est idempotent, et une retouche faite
# en base (stats, tags, animation) survit — à condition de relancer sur un dump FRAIS.
#
# N'écrit que les espèces dont le champ est à poser, à changer ou à retirer : une espèce déjà
# à jour dans le dump n'est pas réimportée.
#
# Usage : python dev/gen_jetons_especes.py [--seulement slug,slug…] [--sortie jsons/x.json]
#   --seulement : restreint le fichier aux espèces citées — quand une passe précédente n'est pas
#                 encore dans le dump, sans quoi elle ressortirait (un fichier = une demande).
# Sortie (à coller dans /admin → Import en masse) :
#   jsons/jetons_especes_a_importer.json

import argparse
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = "jsons/jetons_especes_a_importer.json"

TAILLES = ("1x1", "2x1", "1x2", "2x2", "3x2", "4x3", "5x4", "2x5")
FORMES = ("ellipse", "rectangle", "triangle")

# slug d'espèce → (taille, forme), ou None pour 1x1 sans champ.
TABLE = {
	"abhartach": None,
	"aicha_kandicha": None,
	"aigle_geant": ("2x2", "triangle"),
	"ammit": ("2x2", "ellipse"),
	"ane": ("1x2", "ellipse"),
	"ange_de_la_connaissance": None,
	"ange_de_la_justice": None,
	"apep": ("4x3", "ellipse"),
	"araignee": None,
	"araignee_geante": ("2x2", "ellipse"),
	"archange_de_l_ordre": ("2x1", "triangle"),
	"archange_du_savoir": None,
	"avatar": ("1x1", "rectangle"),
	"balaur": ("3x2", "triangle"),
	"banshee": None,
	"basilic": ("1x2", "ellipse"),
	"besien": None,
	"bete_de_l_apocalypse": ("4x3", "ellipse"),
	"bete_du_gevaudan": ("1x2", "ellipse"),
	"bete_glatissante": ("1x2", "ellipse"),
	"boukhnoun": None,
	"bunyip": ("1x2", "ellipse"),
	"cath_palug": ("1x2", "ellipse"),
	"centaure": ("1x2", "ellipse"),
	"cerbere": ("2x2", "ellipse"),
	"cerf": ("1x2", "ellipse"),
	"chauve_souris": None,
	"chauve_souris_geante": ("2x1", "triangle"),
	"cheval": ("1x2", "ellipse"),
	"cheval_de_trait": ("1x2", "ellipse"),
	"cheval_normand": ("1x2", "ellipse"),
	"chevalier_du_sang": None,
	"chimere": ("2x2", "ellipse"),
	"cockatrice": None,
	"comte_vampire": None,
	"corneille_noire": None,
	"coursier_elfique": ("1x2", "ellipse"),
	"coursier_persan": ("1x2", "ellipse"),
	"crocodile": ("1x2", "ellipse"),
	"cu_sidhe": ("1x2", "ellipse"),
	"cupidon": None,
	"cwn_annwn": ("1x2", "ellipse"),
	"cyclope": ("2x2", "rectangle"),
	"dearg_due": None,
	"demon_guerrier": None,
	"demon_majeur_de_la_destinee": None,
	"demon_majeur_de_la_destruction": ("2x2", "rectangle"),
	"demon_mineur": None,
	"demon_servant": None,
	"doppleganger": None,
	"dobhar_chu": None,
	"dragnard": ("1x2", "ellipse"),
	"dragon_hydre": ("4x3", "ellipse"),
	"draugr": None,
	"dragon": ("3x2", "triangle"),
	"dragon_blanc": ("4x3", "triangle"),
	"dragon_de_sang": None,
	"dragon_empereur": ("5x4", "triangle"),
	"dragon_rouge": ("4x3", "triangle"),
	"dragon_zombie": ("4x3", "triangle"),
	"dryade": None,
	"ecureuil": None,
	"elementaux": None,
	"failinis": ("1x2", "ellipse"),
	"familier": None,
	"fantome": None,
	"faoladh": None,
	"fauves": ("1x2", "ellipse"),
	"fee": None,
	"fils_de_sobek": ("3x2", "ellipse"),
	"gargouille": None,
	"geant_de_ad": ("2x2", "rectangle"),
	"geant_du_mont_saint_michel": ("2x2", "rectangle"),
	"geant_ou_titan": ("4x3", "rectangle"),
	"genie": None,
	"ghul_des_sables": None,
	"gnome": None,
	"gobelin": None,
	"gobelin_chamanique": None,
	"gobelin_des_marais": None,
	"golem_de_chair": ("2x2", "rectangle"),
	"golem_de_fer": ("2x2", "rectangle"),
	"golem_de_pierre": ("2x2", "rectangle"),
	"gorgone": ("1x2", "ellipse"),
	"goule": None,
	"grand_dragon": ("4x3", "triangle"),
	"grand_faucon": ("2x1", "triangle"),
	"grand_phenix": ("3x2", "triangle"),
	"grand_sanglier": ("1x2", "ellipse"),
	"griffon": ("2x2", "triangle"),
	"grootslang": ("4x3", "ellipse"),
	"harpie": None,
	"gwyn_ap_nudd": None,
	"hippogriffe": ("2x2", "triangle"),
	"homme_arbre": ("2x2", "ellipse"),
	"horreur": None,
	"hydre": ("4x3", "ellipse"),
	"ifrit": ("2x2", "ellipse"),
	"illuyanka": ("4x3", "ellipse"),
	"incube": None,
	"jann": None,
	"kraken": ("4x3", "ellipse"),
	"ladon": ("4x3", "ellipse"),
	"leprechaun": None,
	"leviathan": ("4x3", "ellipse"),
	"lamie": None,
	"lhamia": ("1x2", "ellipse"),
	"liche": None,
	"licorne": ("1x2", "ellipse"),
	"lievre": None,
	"loup": None,
	"loup_garou": None,
	"loup_geant": ("1x2", "ellipse"),
	"lycaon": None,
	"malandhir": ("1x2", "ellipse"),
	"mammouth": ("2x2", "ellipse"),
	"manticore": ("2x2", "ellipse"),
	"marid": ("2x2", "ellipse"),
	"mimique": None,
	"minotaure": ("2x2", "rectangle"),
	"momie": None,
	"monture_angelique": ("1x2", "ellipse"),
	"monture_demoniaque": ("1x2", "ellipse"),
	"monture_squelette": ("1x2", "ellipse"),
	"mulet": ("1x2", "ellipse"),
	"mushhushshu": ("1x2", "ellipse"),
	"nahual": None,
	"naiade": None,
	"nereide": None,
	"nosferatu": None,
	"oceanide": None,
	"oiseaux_de_proies": None,
	"ondin": None,
	"orc": None,
	"oreade": None,
	"ours": ("1x2", "ellipse"),
	"ours_polaire": ("2x2", "ellipse"),
	"pegase": ("1x2", "ellipse"),
	"penanggalan": None,
	"petit_dragon": ("2x2", "triangle"),
	"petits_animaux_divers": None,
	"phenix": ("2x1", "triangle"),
	"poissons_mammiferes_marins": ("1x2", "ellipse"),
	"polar_kraken": ("4x3", "ellipse"),
	"poney": ("1x2", "ellipse"),
	"prince_demon": ("2x2", "rectangle"),
	"rapaces": None,
	"rat_geant": None,
	"reine_lhamia": ("1x2", "ellipse"),
	"rejeton_demoniaque": None,
	"renard": None,
	"revenant": None,
	"roi_des_tombes": None,
	"roi_liche": None,
	"sanglier": None,
	"sanglier_apprivoise": ("1x2", "ellipse"),
	"satyre": None,
	"seigneur_du_sang": None,
	"seraphin": ("4x3", "triangle"),
	"serpent": None,
	"serpent_de_marcel": ("4x3", "ellipse"),
	"serpent_geant": ("1x2", "ellipse"),
	"serpopard": ("1x2", "ellipse"),
	"silat": None,
	"sirene": None,
	"spectre": None,
	"sphinx": ("1x2", "ellipse"),
	"squelette": None,
	"strigoi": None,
	"succube": None,
	"tarasque": ("3x2", "ellipse"),
	"taureau": ("1x2", "ellipse"),
	"triton": None,
	"troglodyte": None,
	"troll": ("2x2", "rectangle"),
	"twrch_trwyth": ("2x2", "ellipse"),
	"ulfhedinn": None,
	"uturuncu": None,
	"vampire": None,
	"vers_des_sables": ("2x5", "rectangle"),
	"vouivre": ("1x2", "ellipse"),
	"wyvern": ("3x2", "triangle"),
	"xiuhcoatl": ("1x2", "ellipse"),
	"yamata_no_orochi": ("4x3", "ellipse"),
	"zmey_gorynych": ("4x3", "triangle"),
	"zombie": None,
	"nasnas": None,
	"nuee_de_scarabees": ("2x2", "ellipse"),
	"qudar": None,
	"scorpion_geant": ("2x2", "ellipse"),
}


def _dump_le_plus_recent() -> str:
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		raise SystemExit("ERREUR : aucun jsons/telluris-dump-*.json — exporter la base d'abord.")
	return dumps[-1]


def charger(chemin: str) -> list:
	"""Docs d'un export admin ou d'un dump : tableau nu, ou {"docs": [...]}."""
	with open(chemin, encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


def _avec_jeton(doc: dict, jeton: dict | None) -> dict:
	"""Copie du doc avec `jeton` juste après `nom` (ou retiré si None) — la table fait autorité."""
	out = {}
	for cle, valeur in doc.items():
		if cle == "jeton":
			continue
		out[cle] = valeur
		if cle == "nom" and jeton is not None:
			out["jeton"] = jeton
	if jeton is not None and "jeton" not in out:
		out["jeton"] = jeton
	return out


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("--seulement", default="")
	parser.add_argument("--sortie", default=SORTIE)
	args = parser.parse_args()
	seulement = {x.strip() for x in args.seulement.split(",") if x.strip()}
	inconnues = sorted(seulement - set(TABLE))
	if inconnues:
		sys.exit("ERREUR : --seulement cite des espèces absentes de la table : " + ", ".join(inconnues))
	for slug, valeur in TABLE.items():
		if valeur is not None and (valeur[0] not in TAILLES or valeur[1] not in FORMES):
			sys.exit(f"ERREUR : gabarit invalide pour {slug} : {valeur}")

	source = _dump_le_plus_recent()
	especes = {d["_id"]: d for d in charger(source)
			   if isinstance(d, dict) and d.get("type") == "espece" and d.get("_id")}
	slugs_dump = {i.split(":", 1)[1] for i in especes}

	manquantes = sorted(slugs_dump - set(TABLE))
	fantomes = sorted(set(TABLE) - slugs_dump)
	if manquantes or fantomes:
		if manquantes:
			print("Espèces du dump ABSENTES de la table (à classer) :\n   " + ", ".join(manquantes))
		if fantomes:
			print("Espèces de la table ABSENTES du dump :\n   " + ", ".join(fantomes))
		sys.exit(1)

	docs, deja, compte = [], 0, {}
	for slug in sorted(seulement or TABLE):
		doc = especes[f"espece:{slug}"]
		valeur = TABLE[slug]
		jeton = {"taille": valeur[0], "forme": valeur[1]} if valeur else None
		if doc.get("jeton") == jeton or (jeton is None and "jeton" not in doc):
			# Déjà à jour en base : hors du fichier, qui ne porte que le DELTA (CLAUDE.md §18).
			if jeton is not None:
				deja += 1
			continue
		docs.append(_avec_jeton(doc, jeton))
		cle = f"{valeur[0]} {valeur[1]}" if valeur else "retrait"
		compte[cle] = compte.get(cle, 0) + 1

	chemin = os.path.join(RACINE, args.sortie)
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
		f.write("\n")
	unites = sum(1 for v in TABLE.values() if v is None)
	print(f"relu {os.path.relpath(source, RACINE)} ({len(especes)} espèces)")
	print(f"écrit {args.sortie} : {len(docs)} doc(s), {unites} espèce(s) laissée(s) en 1x1")
	for cle in sorted(compte):
		print(f"   {cle} : {compte[cle]}")
	if deja:
		print(f"   {deja} autre(s) déjà à jour en base, laissée(s) hors du fichier")


if __name__ == "__main__":
	main()
