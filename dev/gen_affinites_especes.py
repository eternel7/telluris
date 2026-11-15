#!/usr/bin/env python
# dev/gen_affinites_especes.py
# Doc `rules:affinites_especes` (Auteur, 15/11) : COMPOSITION des rencontres groupées
# (`utils/composition_rencontre.py`, lu par `combat.instantiate_groupes`).
#   • bandes        : listes d'espèces NOMMÉES qui s'associent en second groupe (prioritaires :
#                     une espèce membre d'une bande ne cherche pas de famille de tags) ;
#   • familles_tags : repli par tags pour les espèces d'aucune bande ;
#   • maitre_betes, chasse, charognards : les trois autres associations ;
#   • formes, hierarchie, diversite_pleine : forme du groupe et chance du second.
#
# ⚠️ PUT COMPLET à l'import (CLAUDE.md §11) : le doc est RÉÉCRIT en entier. S'il existe déjà
# dans le dump, le script le signale — les retouches faites depuis /admin/table seraient perdues.
# Contrôle au lancement : chaque espèce d'une bande existe dans le dump le plus récent.
#
# Usage : python dev/gen_affinites_especes.py [--dump jsons/telluris-dump-….json] [--sortie …]
# Sortie : jsons/affinites_especes_a_importer.json

import argparse
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RACINE not in sys.path:
	sys.path.insert(0, RACINE)
from utils import composition_rencontre as composition  # noqa: E402

SORTIE = "jsons/affinites_especes_a_importer.json"

BANDES = [
	("horde_peau_verte", "Horde peau-verte",
	 ["orc", "gobelin", "gobelin_chamanique", "troll", "loup_geant", "loup"]),
	("tribu_des_marais", "Tribu des marais",
	 ["gobelin_des_marais", "gobelin_chamanique", "rat_geant", "crocodile", "bunyip"]),
	("profondeurs", "Profondeurs",
	 ["troglodyte", "gnome", "rat_geant", "araignee_geante", "chauve_souris_geante", "nuee_de_scarabees"]),
	("cortege_des_fees", "Cortège des fées",
	 ["fee", "leprechaun", "cu_sidhe", "cwn_annwn", "gwyn_ap_nudd", "dryade"]),
	("cour_du_vampire", "Cour du vampire",
	 ["comte_vampire", "vampire", "nosferatu", "strigoi", "dearg_due", "chauve_souris_geante", "loup"]),
	("tertre_du_roi_des_tombes", "Tertre du roi des tombes",
	 ["roi_des_tombes", "draugr", "squelette", "zombie", "revenant", "corneille_noire", "monture_squelette"]),
	("cercle_du_necromancien", "Cercle du nécromancien",
	 ["liche", "roi_liche", "squelette", "zombie", "goule", "spectre", "fantome"]),
	("ordre_du_sang", "Ordre du sang",
	 ["seigneur_du_sang", "chevalier_du_sang", "dragon_de_sang", "abhartach"]),
	("legion_infernale", "Légion infernale",
	 ["prince_demon", "demon_majeur_de_la_destinee", "demon_majeur_de_la_destruction", "demon_guerrier",
	  "demon_mineur", "demon_servant", "besien", "rejeton_demoniaque", "cerbere", "monture_demoniaque"]),
	("cour_des_tentations", "Cour des tentations",
	 ["succube", "incube", "lamie", "dearg_due", "vouivre", "aicha_kandicha"]),
	("ost_celeste", "Ost céleste",
	 ["seraphin", "archange_de_l_ordre", "archange_du_savoir", "ange_de_la_connaissance",
	  "ange_de_la_justice", "cupidon", "monture_angelique", "pegase"]),
	("cortege_des_eaux", "Cortège des eaux",
	 ["naiade", "nereide", "oceanide", "ondin", "triton", "sirene", "marid"]),
	("savane", "Savane",
	 ["fauves", "hyenes", "antilopes", "autruches", "elephants", "buffles"]),
	("sables_du_desert", "Sables du désert",
	 ["ghul_des_sables", "nasnas", "scorpion_geant", "serpopard", "vers_des_sables", "jann", "silat",
	  "nuee_de_scarabees"]),
	("grand_nord", "Grand Nord",
	 ["ours_polaire", "rennes", "boeufs_musques", "phoques_et_morses", "loup", "draugr", "ulfhedinn"]),
	("gardiens_du_nil", "Gardiens du Nil",
	 ["fils_de_sobek", "crocodile", "ammit", "sphinx", "momie", "nuee_de_scarabees"]),
]

# Repli des espèces d'AUCUNE bande : deux espèces s'associent si elles valent un même groupe.
FAMILLES_TAGS = [
	("draconique", "Dragons et reptiles", ["draconique", "reptile"]),
	("morts", "Morts-vivants", ["undead", "non_mort", "mort_vivant"]),
	("infernal", "Infernaux", ["demon", "infernal"]),
	("celeste", "Célestes", ["ange", "celeste"]),
	("feerique", "Petit peuple", ["feerique"]),
	("esprits", "Esprits", ["esprit"]),
	("elementaire", "Élémentaires", ["elementaire"]),
	("construct", "Créatures façonnées", ["construct"]),
	("metamorphe", "Métamorphes et maudits", ["metamorphe", "malediction"]),
	("aquatique", "Bêtes des eaux", ["aquatique"]),
]

# Les créatures d'une autre nature ne mènent pas de bêtes dressées et n'en servent pas.
_SURNATURELS = ["ange", "celeste", "demon", "infernal", "undead", "non_mort", "esprit",
				"elementaire", "construct", "feerique"]

MAITRE_BETES = {
	"maitres_tags": ["humanoide"],
	"maitres_exclure": _SURNATURELS + ["metamorphe"],
	"betes_tags": ["monture", "ia_meute"],
	"betes_exclure": _SURNATURELS + ["humanoide", "bete_de_somme", "magique", "pure"],
	"necromanciens_tags": ["nécromancie", "magie_necromancie"],
	"morts_tags": ["undead", "non_mort", "mort_vivant"],
}

CHASSE = {
	"predateurs_tags": ["predateur"],
	"proies_tags": ["proie"],
	"proies_exclure": ["predateur", "humanoide", "bete_de_somme"],
	"fuite_pct": 70,
}

CHAROGNARDS = {
	"suivis_tags": ["predateur"],
	"tags": ["nocturne", "petite_taille", "vermine"],
	"exclure": ["proie", "humanoide", "magique", "undead", "non_mort", "feerique", "ange", "celeste", "demon"],
	"max": 2,
}


def construire() -> dict:
	return {
		"_id": composition.DOC_ID,
		"type": "rules",
		"description": "Composition des rencontres groupées : bandes, familles, associations, formes.",
		"bandes": [{"id": i, "nom": n, "especes": [f"espece:{e}" for e in es]} for i, n, es in BANDES],
		"familles_tags": [{"id": i, "nom": n, "tags": t} for i, n, t in FAMILLES_TAGS],
		"maitre_betes": MAITRE_BETES,
		"chasse": CHASSE,
		"charognards": CHAROGNARDS,
		"formes": dict(composition.DEFAUTS["formes"]),
		"hierarchie": dict(composition.DEFAUTS["hierarchie"]),
		"diversite_pleine": composition.DEFAUTS["diversite_pleine"],
	}


def controler(doc: dict, ids: set) -> list:
	"""Espèces de bande absentes du dump (liste vide = tout est là)."""
	return sorted({e for b in doc["bandes"] for e in b["especes"] if e not in ids})


def main():
	ap = argparse.ArgumentParser()
	ap.add_argument("--dump", default=None)
	ap.add_argument("--sortie", default=SORTIE)
	a = ap.parse_args()
	dump = a.dump or max(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	docs = json.load(open(dump, encoding="utf-8"))["docs"]
	ids = {d["_id"] for d in docs}
	doc = construire()
	manquantes = controler(doc, ids)
	if manquantes:
		sys.exit(f"Espèces inconnues du dump : {', '.join(manquantes)}")
	if doc["_id"] in ids:
		print(f"⚠️ {doc['_id']} existe déjà dans {os.path.basename(dump)} : l'import l'écrasera.")
	sortie = os.path.join(RACINE, a.sortie)
	with open(sortie, "w", encoding="utf-8") as f:
		json.dump([doc], f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"{sortie} : 1 doc, {len(doc['bandes'])} bandes, {len(doc['familles_tags'])} familles.")


if __name__ == "__main__":
	main()
