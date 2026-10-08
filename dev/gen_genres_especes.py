#!/usr/bin/env python
# dev/gen_genres_especes.py
# Pose l'ACCORD GRAMMATICAL des espèces du bestiaire, lu par `utils/accord_espece.py` :
#   - `genre` : "m" | "f" (posé sur TOUTES les espèces) ;
#   - `pluriel` : true pour un nom de groupe (« Fauves », « Rapaces ») ;
#   - `nom_propre` : true pour un être unique (« Apep ») — pas d'article ;
#   - `h_aspire` : true pour un « h » aspiré (« la Harpie ») — les autres « h » s'élident.
# L'élision se déduit de la première lettre du nom : pas de champ.
#
# Sans cela, tout titre généré qui cite une espèce est fautif (« traquer le Vipère »,
# « la tête du Harpie »). Un doc sans `genre` reste lu au masculin (aucune migration).
#
# ⚠️ LA TABLE EST EXHAUSTIVE (même parti que `gen_jetons_especes.py`) : le script ÉCHOUE si une
# espèce du dump manque à la table ou si la table cite une espèce absente — une espèce ajoutée
# depuis ne reçoit jamais un genre par défaut sans qu'on l'ait décidé.
#
# ⚠️ POURQUOI UN SCRIPT : `admin_import_bulk` fait un PUT COMPLET, jamais un merge. On RELIT
# chaque espèce depuis le dump le plus récent et on n'y injecte que ces champs (placés juste
# après `nom`) : régénérer est idempotent, et une retouche faite en base survit — à condition
# de relancer sur un dump FRAIS. N'écrit que les espèces dont l'accord change.
#
# Usage : python dev/gen_genres_especes.py
# Sortie (à coller dans /admin → Import en masse) :
#   jsons/genres_especes_a_importer.json

import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = "jsons/genres_especes_a_importer.json"

CHAMPS = ("genre", "pluriel", "nom_propre", "h_aspire")

FEMININS = {
	"aicha_kandicha", "ammit", "araignee", "araignee_geante", "banshee", "bete_de_l_apocalypse",
	"bete_du_gevaudan", "chauve_souris", "chauve_souris_geante", "chimere", "cockatrice",
	"corneille_noire", "dryade", "fee", "gargouille", "gorgone", "goule", "harpie", "horreur",
	"hydre", "lhamia", "liche", "licorne", "manticore", "momie", "monture_angelique",
	"monture_demoniaque", "monture_squelette", "naiade", "nereide", "oceanide", "oreade",
	"reine_lhamia", "sirene", "succube", "tarasque", "vouivre", "wyvern",
}

MASCULINS = {
	"aigle_geant", "ane", "ange_de_la_connaissance", "ange_de_la_justice", "apep",
	"archange_de_l_ordre", "archange_du_savoir", "avatar", "basilic", "besien", "boukhnoun",
	"bunyip", "centaure", "cerbere", "cerf", "cheval", "cheval_de_trait", "cheval_normand",
	"chevalier_du_sang", "comte_vampire", "coursier_elfique", "coursier_persan", "crocodile",
	"cupidon", "cyclope", "demon_guerrier", "demon_majeur_de_la_destinee",
	"demon_majeur_de_la_destruction", "demon_mineur", "demon_servant", "doppleganger", "dragnard",
	"dragon", "dragon_empereur", "dragon_zombie", "ecureuil", "familier", "fantome",
	"fils_de_sobek", "geant_ou_titan", "genie", "ghul_des_sables", "gnome", "gobelin",
	"gobelin_chamanique", "gobelin_des_marais", "golem_de_chair", "golem_de_fer",
	"golem_de_pierre", "grand_dragon", "grand_faucon", "grand_phenix", "grand_sanglier",
	"griffon", "hippogriffe", "homme_arbre", "ifrit", "incube", "jann", "kraken", "leprechaun",
	"leviathan", "lievre", "loup", "loup_garou", "loup_geant", "malandhir", "mammouth", "marid",
	"minotaure", "mulet", "nosferatu", "ondin", "orc", "ours", "ours_polaire", "pegase",
	"petit_dragon", "petits_animaux_divers", "phenix", "polar_kraken", "poney", "prince_demon",
	"rat_geant", "rejeton_demoniaque", "renard", "revenant", "roi_des_tombes", "roi_liche",
	"sanglier", "sanglier_apprivoise", "satyre", "seigneur_du_sang", "seraphin", "serpent",
	"serpent_geant", "serpopard", "silat", "spectre", "sphinx", "squelette", "taureau", "triton",
	"troglodyte", "troll", "vampire", "zombie",
	# Noms de groupe : masculins, mais au pluriel (voir PLURIELS).
	"elementaux", "fauves", "oiseaux_de_proies", "poissons_mammiferes_marins", "rapaces",
	"vers_des_sables",
}

PLURIELS = {
	"elementaux", "fauves", "oiseaux_de_proies", "poissons_mammiferes_marins", "rapaces",
	"vers_des_sables",
}

# Êtres uniques : le titre dit « Apep », pas « l'Apep ».
PROPRES = {"aicha_kandicha", "ammit", "apep", "cupidon"}

# « h » aspiré : « la Harpie » et non « l'Harpie ». Hydre, Horreur, Hippogriffe, Homme Arbre
# s'élident.
H_ASPIRES = {"harpie"}


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


def accord_de(slug: str) -> dict:
	"""Champs d'accord d'une espèce, d'après les tables ci-dessus (clés absentes = faux)."""
	accord = {"genre": "f" if slug in FEMININS else "m"}
	if slug in PLURIELS:
		accord["pluriel"] = True
	if slug in PROPRES:
		accord["nom_propre"] = True
	if slug in H_ASPIRES:
		accord["h_aspire"] = True
	return accord


def _avec_accord(doc: dict, accord: dict) -> dict:
	"""Copie du doc avec les champs d'accord juste après `nom` ; les champs d'accord que la table
	ne pose plus sont retirés — la table fait autorité."""
	out = {}
	for cle, valeur in doc.items():
		if cle in CHAMPS:
			continue
		out[cle] = valeur
		if cle == "nom":
			out.update(accord)
	if "nom" not in doc:
		out.update(accord)
	return out


def main() -> None:
	doublons = FEMININS & MASCULINS
	if doublons:
		sys.exit("ERREUR : espèce(s) à la fois féminine(s) et masculine(s) : " + ", ".join(sorted(doublons)))
	table = FEMININS | MASCULINS
	for nom_table, ensemble in (("PLURIELS", PLURIELS), ("PROPRES", PROPRES), ("H_ASPIRES", H_ASPIRES)):
		inconnues = ensemble - table
		if inconnues:
			sys.exit(f"ERREUR : {nom_table} cite des espèces hors table : " + ", ".join(sorted(inconnues)))

	source = _dump_le_plus_recent()
	especes = {d["_id"]: d for d in charger(source)
			   if isinstance(d, dict) and d.get("type") == "espece" and d.get("_id")}
	slugs_dump = {i.split(":", 1)[1] for i in especes}

	manquantes = sorted(slugs_dump - table)
	fantomes = sorted(table - slugs_dump)
	if manquantes or fantomes:
		if manquantes:
			print("Espèces du dump ABSENTES de la table (à classer) :\n   " + ", ".join(manquantes))
		if fantomes:
			print("Espèces de la table ABSENTES du dump :\n   " + ", ".join(fantomes))
		sys.exit(1)

	docs, deja = [], 0
	for slug in sorted(table):
		doc = especes[f"espece:{slug}"]
		accord = accord_de(slug)
		if all(doc.get(c) == accord.get(c) for c in CHAMPS):
			deja += 1
			continue
		docs.append(_avec_accord(doc, accord))

	chemin = os.path.join(RACINE, SORTIE)
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"relu {os.path.relpath(source, RACINE)} ({len(especes)} espèces)")
	print(f"écrit {SORTIE} : {len(docs)} doc(s) — {len(FEMININS)} féminin(s), "
		  f"{len(table) - len(FEMININS)} masculin(s), {len(PLURIELS)} pluriel(s), "
		  f"{len(PROPRES)} nom(s) propre(s), {len(H_ASPIRES)} h aspiré")
	if deja:
		print(f"   dont {deja} déjà à jour en base (non réécrites)")


if __name__ == "__main__":
	main()
