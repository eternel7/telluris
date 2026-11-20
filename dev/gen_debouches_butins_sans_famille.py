#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Débouché des butins d'espèce SANS sous-catégorie (Ghûl des Sables, Ifrit, Djinn des
Ruines, Marid, Si'lat au dump du 20/11) : aucune recette ne les consomme, seul un négociant
les rachète.

Chaque butin reçoit la famille de `dev/gen_loot_immateriel.py` (`_famille_de`, d'après les
tags de l'espèce : esprit → résidu spectral, mort-vivant → ossements, élémentaire → débris
animés), dont les recettes et la matière générique sont déjà en base. `DEROGATIONS` tranche
les espèces qu'aucun tag ne classe.

Doc item COMPLET repris du dump (PUT complet), seul `sous_categorie` ajouté. Contrôle avant
écriture : après le lot (et celui de `gen_debouches_gelee` s'il n'est pas encore en base),
TOUT butin d'espèce a au moins un acheteur hors négociant, sinon refus.
Sortie : `jsons/debouches_butins_sans_famille_a_importer.json` (delta ; base à jour ⇒ aucun fichier).
"""
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "dev"))
import gen_recettes_orphelins as base       # noqa: E402  (dernier_dump, brancher_moteur)
import gen_loot_immateriel as immateriel    # noqa: E402  (_famille_de)
import gen_debouches_gelee as gelee         # noqa: E402  (lot des gelées, contrôle final)

SORTIE = os.path.join(RACINE, "jsons", "debouches_butins_sans_famille_a_importer.json")

# Espèces qu'aucun tag de famille ne classe : une djinn errante → résidu de son essence.
DEROGATIONS = {
	"espece:silat": "residu_spectral",
}


def main():
	chemin = base.dernier_dump()
	docs = json.load(open(chemin, encoding="utf-8"))["docs"]
	print("Dump :", os.path.basename(chemin))
	par_id = {d["_id"]: d for d in docs}

	delta, sans_famille = [], []
	for it in docs:
		if not it.get("source_espece") or it.get("sous_categorie"):
			continue
		tags = set((par_id.get(it["source_espece"]) or {}).get("tags") or [])
		famille = DEROGATIONS.get(it["source_espece"]) or immateriel._famille_de(tags)
		if not famille:
			sans_famille.append(it["_id"])
			continue
		if "item:" + famille not in par_id:
			sys.exit("REFUS : matière générique item:%s absente" % famille)
		doc = {k: v for k, v in it.items() if k != "_rev"}
		doc["sous_categorie"] = famille
		delta.append(doc)
		print("  %s → %s" % (it["_id"], famille))
	if sans_famille:
		sys.exit("REFUS : sans famille ni dérogation : %s" % ", ".join(sans_famille))
	if not delta:
		print("Base à jour : aucun fichier écrit.")
		return

	# Contrôle : lot appliqué (+ gelées si pas encore importées), tout butin a un acheteur.
	nouveaux = {d["_id"]: d for d in delta}
	docs = [nouveaux.get(d["_id"], d) for d in docs]
	lot_gelee = [gelee.MATIERE] + [gelee.recette_doc(*r) for r in gelee.RECETTES]
	docs += [d for d in lot_gelee if d["_id"] not in par_id]
	marche = base.brancher_moteur(docs)
	lieux = [d for d in docs if str(d.get("_id", "")).startswith("lieu:")
			 and d.get("categorie") not in (None, "ville", "pays")
			 and not marche.est_negociant(d)]
	manques = [it["_id"] for it in docs if it.get("source_espece")
			   and not any(marche.lieu_buys(l, it) for l in lieux)]
	if manques:
		sys.exit("REFUS : encore sans acheteur hors négociant : %s" % ", ".join(manques))
	print("Tous les butins d'espèce ont un acheteur hors négociant.")

	with open(SORTIE, "w", encoding="utf-8") as fh:
		json.dump(delta, fh, ensure_ascii=False, indent=2)
		fh.write("\n")
	print("%d docs → %s" % (len(delta), os.path.relpath(SORTIE, RACINE)))


if __name__ == "__main__":
	main()
