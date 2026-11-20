#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Donne un DÉBOUCHÉ (acheteur hors négociant) à TOUTES les dépouilles d'espèce.

Au dump du 20/11, deux cas, un seul fichier :
  1. GELÉES (Slime, Mère-gelée, `sous_categorie: "gelee"`) : aucune recette ne consomme la
     clé. Même schéma que `dev/gen_loot_immateriel.py` : matière générique `item:gelee`
     (sinon `matiere_item_id` la valorise à vide ; elle devient une feuille livrée, comme
     `item:residu_spectral`) + recettes vers des objets DÉJÀ produits par le même métier.
     Refus si les feuilles bougent (hors `gelee`) ou si le prix d'un produit change.
  2. SANS SOUS-CATÉGORIE (Ghûl des Sables, Ifrit, Djinn des Ruines, Marid, Si'lat) : famille
     de `gen_loot_immateriel._famille_de` (tags de l'espèce), `DEROGATIONS` pour les
     inclassables ; doc item COMPLET repris du dump (PUT complet), `sous_categorie` ajoutée.

Contrôle final : lot appliqué, tout item à `source_espece` a au moins un acheteur hors
négociant, sinon rien n'est écrit. Sortie : `jsons/debouches_depouilles_a_importer.json`
(delta seul ; base à jour ⇒ aucun fichier).
"""
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "dev"))
import gen_recettes_orphelins as base       # noqa: E402  (dernier_dump, brancher_moteur)
import gen_loot_immateriel as immateriel    # noqa: E402  (_famille_de)

SORTIE = os.path.join(RACINE, "jsons", "debouches_depouilles_a_importer.json")

# ── 1. Gelées ─────────────────────────────────────────────────────────────────────────
CLE_GELEE = "gelee"
MATIERE_GELEE = {
	"_id": "item:gelee",
	"type": "item",
	"nom": "Gelée de slime",
	"icon": "🫧",
	"description": "Gelée translucide et collante, recueillie sur les slimes des donjons.",
	"rarete": "commun",
	"categorie": "composant",
	"sous_categorie": CLE_GELEE,
	"slots": [],
	"tags": [],
	"poids": 1,
	"valeur": 3,
}
# (lieu_categorie, objet_final, quantité de gelée, quantité produite) — savon ×2 : à ×1 son
# prix montait (max sur les recettes, `cout_production_cuivre`).
RECETTES_GELEE = [
	("laboratoire_d_alchimie", "Glu_de_nuit", 2, 1),
	("laboratoire_d_alchimie", "reactif_magique", 2, 1),
	("apothicairerie", "onguent", 2, 1),
	("savonnerie", "savon", 2, 2),
]

# ── 2. Butins sans sous-catégorie : espèces qu'aucun tag de famille ne classe ─────────
DEROGATIONS = {
	"espece:silat": "residu_spectral",   # djinn errante → résidu de son essence
}


def recette_gelee(cat, final, q, qp):
	return {
		"_id": "recette:%s_%s_%s" % (CLE_GELEE, final.lower(), cat),
		"type": "recette",
		"lieu_categorie": cat,
		"objet_final": final,
		"quantite_produite": qp,
		"matieres_premieres": [{"sous_categorie": CLE_GELEE, "quantite": q}],
	}


def _sans_rev(d):
	return {k: v for k, v in (d or {}).items() if k != "_rev"}


def delta_gelee(par_id):
	lot = [MATIERE_GELEE] + [recette_gelee(*r) for r in RECETTES_GELEE]
	delta = [d for d in lot if _sans_rev(par_id.get(d["_id"])) != d]
	for d in delta:
		if d["_id"] in par_id:
			sys.exit("REFUS : %s existe déjà avec un autre contenu" % d["_id"])
	return delta


def delta_sans_famille(docs, par_id):
	delta, inclassables = [], []
	for it in docs:
		if not it.get("source_espece") or it.get("sous_categorie"):
			continue
		tags = set((par_id.get(it["source_espece"]) or {}).get("tags") or [])
		famille = DEROGATIONS.get(it["source_espece"]) or immateriel._famille_de(tags)
		if not famille:
			inclassables.append(it["_id"])
			continue
		if "item:" + famille not in par_id:
			sys.exit("REFUS : matière générique item:%s absente" % famille)
		doc = _sans_rev(it)
		doc["sous_categorie"] = famille
		delta.append(doc)
		print("  %s → %s" % (it["_id"], famille))
	if inclassables:
		sys.exit("REFUS : sans famille ni dérogation : %s" % ", ".join(inclassables))
	return delta


def main():
	chemin = base.dernier_dump()
	docs = json.load(open(chemin, encoding="utf-8"))["docs"]
	print("Dump :", os.path.basename(chemin))
	par_id = {d["_id"]: d for d in docs}

	d_gelee = delta_gelee(par_id)
	d_famille = delta_sans_famille(docs, par_id)
	delta = d_gelee + d_famille
	if not delta:
		print("Base à jour : aucun fichier écrit.")
		return

	marche = base.brancher_moteur(docs)
	cats = sorted({r[0] for r in RECETTES_GELEE})
	finals = sorted({r[1] for r in RECETTES_GELEE})
	for f in finals:
		if not any(d.get("type") == "recette" and d.get("objet_final") == f
				   and d.get("lieu_categorie") in cats and not d.get("sur_commande")
				   for d in docs):
			sys.exit("REFUS : %s n'est produit par aucune recette existante" % f)

	def etat():
		feuilles = {c: set(marche.appro_leaves_categorie(c)) for c in cats}
		prix = {f: marche.prix_range_cuivre(par_id["item:" + f], "item:" + f) for f in finals}
		return feuilles, prix

	f_avant, p_avant = etat()
	# Lot appliqué EN PLACE (liste partagée avec le moteur branché).
	remplace = {d["_id"]: d for d in delta}
	docs[:] = [remplace.pop(d["_id"], d) for d in docs] + list(remplace.values())
	marche.reset_prix_cache()
	f_apres, p_apres = etat()

	for c in cats:
		diff = f_apres[c] ^ f_avant[c]
		if diff - {CLE_GELEE, MATIERE_GELEE["_id"]}:
			sys.exit("REFUS : feuilles de %s modifiées : %s" % (c, sorted(diff)))
	for f in finals:
		if p_avant[f] != p_apres[f]:
			sys.exit("REFUS : prix de %s modifié %s → %s" % (f, p_avant[f], p_apres[f]))

	lieux = [d for d in docs if str(d.get("_id", "")).startswith("lieu:")
			 and d.get("categorie") not in (None, "ville", "pays")
			 and not marche.est_negociant(d)]
	manques = [it["_id"] for it in docs if it.get("source_espece")
			   and not any(marche.lieu_buys(l, it) for l in lieux)]
	if manques:
		sys.exit("REFUS : encore sans acheteur hors négociant : %s" % ", ".join(manques))
	print("Toutes les dépouilles d'espèce ont un acheteur hors négociant.")

	with open(SORTIE, "w", encoding="utf-8") as fh:
		json.dump(delta, fh, ensure_ascii=False, indent=2)
		fh.write("\n")
	print("%d docs (%d gelée, %d reclassés) → %s"
		  % (len(delta), len(d_gelee), len(d_famille), os.path.relpath(SORTIE, RACINE)))


if __name__ == "__main__":
	main()
