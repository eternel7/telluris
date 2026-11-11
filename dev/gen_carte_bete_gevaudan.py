#!/usr/bin/env python
# dev/gen_carte_bete_gevaudan.py
# Épreuve du rang A de Lutecia « la Bête » : Maëlys SITUE la Bête du Gévaudan et remet une
# carte (demande de l'Auteur, 11/11). DELTA de `gen_missions_rang_b_a_lutecia.py`, qui reste
# la source des textes et de l'offre : on relit Maëlys du DERNIER dump et l'on n'y remplace que
#   - l'entrée `quete:rang_a_bete_du_gevaudan` de `services.apport.offres` (description +
#     `localisation` → bouton 🗺️ de l'onglet 📜, `apport.localisation_spec`) ;
#   - les nœuds `a_bete_*` (dont le neuf `a_bete_carte`, « Où la chercher ? »).
# Le reste du doc (correctifs postérieurs, autres épreuves) est conservé tel quel.
#
# ⚠️ Une quête DÉJÀ acceptée garde son snapshot (sans `localisation`) : la carte n'apparaît
# qu'aux acceptations suivantes. Aucune migration (CLAUDE.md §4).
#
# UN SEUL FICHIER À IMPORTER (CLAUDE.md §18) : jsons/carte_bete_gevaudan_a_importer.json.
# Régénération idempotente.
#
# Usage : python dev/gen_carte_bete_gevaudan.py [jsons/telluris-dump-….json]

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_missions_rang_b_a_lutecia as GEN  # noqa: E402

SORTIE = os.path.join(GEN.JSONS, "carte_bete_gevaudan_a_importer.json")
PREFIXE = "a_bete_"


def entree_bete():
	return next(e for e in GEN.entrees_maelys()["apport"] if e["offre"]["id"] == GEN.A_BETE)


def noeuds_bete():
	return {k: v for k, v in GEN.noeuds_maelys().items() if k.startswith(PREFIXE)}


def maelys(doc):
	doc = GEN.sans_rev(doc)
	offres = ((doc.get("services") or {}).get("apport") or {}).get("offres")
	if not isinstance(offres, list):
		sys.exit("ERREUR : pnj:maelys n'a pas de `services.apport.offres` au dump")
	idx = next((i for i, e in enumerate(offres) if (e.get("offre") or {}).get("id") == GEN.A_BETE), None)
	if idx is None:
		sys.exit(f"ERREUR : {GEN.A_BETE} absente des offres d'apport de Maëlys")
	offres[idx] = entree_bete()
	doc["dialogue"]["noeuds"].update(noeuds_bete())
	return doc


def generer(par_id):
	for requis in (GEN.MAELYS, GEN.FRANCE, GEN.TETE_BETE, GEN.LOUP, GEN.LOCALISATION_BETE["rencontre"]["espece"]):
		if requis not in par_id:
			sys.exit(f"ERREUR : {requis} absent du dump")
	return [maelys(par_id[GEN.MAELYS])]


def main(argv):
	dump = GEN.charger(GEN.dernier_dump(argv))
	docs = generer({d["_id"]: d for d in dump["docs"]})
	GEN.ecrire(SORTIE, docs)
	print(f"{len(docs)} doc → {os.path.relpath(SORTIE, GEN.RACINE)}")


if __name__ == "__main__":
	main(sys.argv)
