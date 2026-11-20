#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Donne un DÉBOUCHÉ aux gelées des slimes (Slime, Mère-gelée — ajoutés le 17/11).

Leur butin (`item:slime`, `item:mere_gelee`) porte `sous_categorie: "gelee"`, qu'aucune
recette ne consomme : hors négociant, aucun marchand ne le rachète (`lieu_buys`).
Même schéma que `dev/gen_loot_immateriel.py` :
  1. la matière générique `item:gelee` — ⚠️ obligatoire, sinon `matiere_item_id` valorise
     la clé à vide ; elle devient une feuille livrée (comme `item:residu_spectral`) ;
  2. des recettes qui consomment la clé `gelee`, vers des objets DÉJÀ produits par une
     autre recette du même métier (aucune feuille du monde ne bouge).

Contrôles (refus d'écrire en cas d'échec) : `_id` neufs, feuilles inchangées hors `gelee`,
prix des produits inchangés, et après le lot chaque butin d'espèce (`source_espece`) a au
moins un acheteur hors négociant — les manques préexistants hors gelée sont seulement listés.
Sortie : `jsons/debouches_gelee_a_importer.json` (delta seul ; base à jour ⇒ aucun fichier).
"""
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "dev"))
import gen_recettes_orphelins as base  # noqa: E402  (dernier_dump, brancher_moteur)

SORTIE = os.path.join(RACINE, "jsons", "debouches_gelee_a_importer.json")
CLE = "gelee"

MATIERE = {
	"_id": "item:gelee",
	"type": "item",
	"nom": "Gelée de slime",
	"icon": "🫧",
	"description": "Gelée translucide et collante, recueillie sur les slimes des donjons.",
	"rarete": "commun",
	"categorie": "composant",
	"sous_categorie": CLE,
	"slots": [],
	"tags": [],
	"poids": 1,
	"valeur": 3,
}

# (lieu_categorie, objet_final, quantité de gelée, quantité produite)
RECETTES = [
	("laboratoire_d_alchimie", "Glu_de_nuit", 2, 1),
	("laboratoire_d_alchimie", "reactif_magique", 2, 1),
	("apothicairerie", "onguent", 2, 1),
	("savonnerie", "savon", 2, 2),
]


def recette_doc(cat, final, q, qp):
	return {
		"_id": "recette:%s_%s_%s" % (CLE, final.lower(), cat),
		"type": "recette",
		"lieu_categorie": cat,
		"objet_final": final,
		"quantite_produite": qp,
		"matieres_premieres": [{"sous_categorie": CLE, "quantite": q}],
	}


def main():
	chemin = base.dernier_dump()
	docs = json.load(open(chemin, encoding="utf-8"))["docs"]
	print("Dump :", os.path.basename(chemin))
	par_id = {d["_id"]: d for d in docs}
	lot = [MATIERE] + [recette_doc(*r) for r in RECETTES]

	# Delta seul : un doc identique en base (hors _rev) est retiré du lot.
	def sans_rev(d):
		return {k: v for k, v in d.items() if k != "_rev"}
	delta = [d for d in lot if sans_rev(par_id.get(d["_id"], {})) != d]
	for d in delta:
		if d["_id"] in par_id:
			sys.exit("REFUS : %s existe déjà avec un autre contenu" % d["_id"])
	if not delta:
		print("Base à jour : aucun fichier écrit.")
		return

	marche = base.brancher_moteur(docs)
	cats = sorted({r[0] for r in RECETTES})
	finals = sorted({r[1] for r in RECETTES})
	for f in finals:
		if not any(d.get("type") == "recette" and d.get("objet_final") == f
				   and d.get("lieu_categorie") == c and not d.get("sur_commande")
				   for d in docs for c in cats):
			sys.exit("REFUS : %s n'est produit par aucune recette existante" % f)

	def etat():
		feuilles = {c: set(marche.appro_leaves_categorie(c)) for c in cats}
		prix = {f: marche.prix_range_cuivre(par_id["item:" + f], "item:" + f) for f in finals}
		return feuilles, prix

	f_avant, p_avant = etat()
	docs.extend(delta)
	marche.reset_prix_cache()
	f_apres, p_apres = etat()

	for c in cats:
		diff = f_apres[c] ^ f_avant[c]
		if diff - {CLE, MATIERE["_id"]}:
			sys.exit("REFUS : feuilles de %s modifiées : %s" % (c, sorted(diff)))
	for f in finals:
		if p_avant[f] != p_apres[f]:
			sys.exit("REFUS : prix de %s modifié %s → %s" % (f, p_avant[f], p_apres[f]))

	lieux = [d for d in docs if str(d.get("_id", "")).startswith("lieu:")
			 and d.get("categorie") not in (None, "ville", "pays")
			 and not marche.est_negociant(d)]
	manques = []
	for it in (d for d in docs if d.get("source_espece")):
		acheteurs = sorted({l.get("categorie") for l in lieux if marche.lieu_buys(l, it)})
		if not acheteurs:
			manques.append(it)
		elif it.get("sous_categorie") == CLE:
			print("  %s → %s" % (it["_id"], ", ".join(acheteurs)))
	if any(m.get("sous_categorie") == CLE for m in manques):
		sys.exit("REFUS : gelée encore sans acheteur")
	for m in manques:
		print("  (hors périmètre) sans acheteur hors négociant : %s (sous_categorie %r)"
			  % (m["_id"], m.get("sous_categorie")))

	with open(SORTIE, "w", encoding="utf-8") as fh:
		json.dump(delta, fh, ensure_ascii=False, indent=2)
		fh.write("\n")
	print("%d docs → %s" % (len(delta), os.path.relpath(SORTIE, RACINE)))


if __name__ == "__main__":
	main()
