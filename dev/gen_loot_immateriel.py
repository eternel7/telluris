#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Donne un DÉBOUCHÉ aux 32 butins d'espèces qui n'ont aucune recette.

Contexte : chaque espèce du bestiaire laisse un item `item:<sub_id>` (`source_espece`).
105 d'entre eux portent `sous_categorie: "carcasse"` et sont donc dépecés à la boucherie ;
les 32 autres — esprits (« Résidu spectral »), morts-vivants (« Ossements ») et
constructs/élémentaires (« Débris ») — ont une **`sous_categorie` VIDE** : aucune recette
ne les consomme, donc aucun marchand ne les rachète (`lieu_buys` = sous-catégorie ∈
recettes du lieu) et ils restent du poids mort dans le sac.

Ce générateur produit `jsons/loot_immateriel_a_importer.json` :
  1. les 32 docs item **COMPLETS** (⚠️ `admin_import_bulk` fait un PUT complet, jamais un
     merge) avec leur `sous_categorie` renseignée, déduite des `tags` de l'espèce ;
  2. les 3 docs de matière génériques `item:<sous_categorie>` — ⚠️ obligatoires, sinon
     `marche.matiere_item_id` valorise la clé à **1 cu en silence** et le prix faux se
     propage à tout ce qui en dérive par la marge de transformation ;
  3. les recettes qui les consomment, dont les `objet_final` sont **tous** des items déjà
     en base ET déjà produits par une autre recette — ⚠️ produire une matière « feuille »
     (fer, acier, argent, plomb, peaux…) la sortirait de l'auto-approvisionnement et
     couperait l'appro du métier concerné.

Idempotent : relit le dernier export d'items (source unique), n'injecte que le champ
manquant, et les `_id` de recettes sont stables → réimporter ne peut rien annuler.
"""
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "loot_immateriel_a_importer.json")

# ── Familles : (sous_categorie, prédicat sur les tags d'espèce, doc générique) ─────────
# L'ordre compte : `esprit` est testé AVANT `undead` (une banshee est les deux, son butin
# est un résidu éthéré et non des ossements).
FAMILLES = [
	("residu_spectral", {"esprit", "incorporel"}, {
		"nom": "Résidu spectral", "icon": "👻", "rarete": "peu_commun", "poids": 0.2,
		"description": "Voile éthéré condensé, encore tiède d'une présence disparue.",
	}),
	("ossements", {"undead", "non_mort"}, {
		"nom": "Ossements", "icon": "🦴", "rarete": "peu_commun", "poids": 0.5,
		"description": "Ossements dépareillés arrachés à une carcasse qui marchait encore.",
	}),
	("debris_anime", {"construct", "elementaire"}, {
		"nom": "Débris animés", "icon": "🪨", "rarete": "peu_commun", "poids": 0.8,
		"description": "Fragments inertes d'un corps que rien de vivant n'habitait.",
	}),
]

# ── Recettes : (sous_categorie, lieu_categorie, objet_final, q_matiere, q_produite) ────
RECETTES = [
	# Ossements — la famille la plus abondante (18 espèces), donc le plus de débouchés.
	("ossements", "necromancie", "relique", 2, 1),
	("ossements", "necromancie", "focus_magique", 3, 1),
	("ossements", "taxidermie", "trophee", 3, 1),
	("ossements", "tabletterie", "manche", 1, 1),
	("ossements", "tabletterie", "de", 1, 4),
	("ossements", "atelier_d_artisan", "poudre_d_os", 1, 2),
	("ossements", "atelier_d_artisan", "bijou", 1, 2),
	("ossements", "bijouterie", "talisman", 2, 1),
	# Résidu spectral — matière à sortilège, et pigment d'encre au scriptorium.
	("residu_spectral", "laboratoire_d_alchimie", "reactif_magique", 1, 1),
	("residu_spectral", "laboratoire_d_alchimie", "catalyseur_magique", 2, 1),
	("residu_spectral", "necromancie", "composant_rituel", 1, 2),
	("residu_spectral", "scriptorium", "pigment", 1, 2),
	# Débris animés — le métal d'un golem se reforge, la pierre se pile.
	("debris_anime", "armurerie", "acier_plisse", 3, 1),
	("debris_anime", "laboratoire_d_alchimie", "poudre_alchimique", 2, 1),
	("debris_anime", "laboratoire_d_alchimie", "catalyseur_magique", 2, 1),
	("debris_anime", "necromancie", "focus_magique", 2, 1),
]


def _dernier(motif: str) -> str | None:
	fichiers = sorted(glob.glob(os.path.join(RACINE, "jsons", motif)))
	return fichiers[-1] if fichiers else None


def _charger_docs() -> tuple[list, dict]:
	"""(items, especes) — les items viennent de l'export ciblé le plus frais s'il existe,
	les espèces du dernier dump complet (l'export `item-*.json` ne contient qu'un type)."""
	items, especes = [], {}
	chemin_items = _dernier("item-*.json")
	chemin_dump = _dernier("telluris-dump-*.json")
	for chemin in (chemin_dump, chemin_items):
		if not chemin:
			continue
		with open(chemin, encoding="utf-8") as fh:
			docs = json.load(fh).get("docs") or []
		print("Source : %s (%d docs)" % (os.path.basename(chemin), len(docs)))
		trouves = [d for d in docs if d.get("type") == "item"]
		if trouves:
			items = trouves       # le dernier lu gagne : l'export ciblé prime sur le dump
		especes.update({d["_id"]: d for d in docs if d.get("type") == "espece"})
	return items, especes


def _famille_de(tags: set, nom: str = "") -> str | None:
	"""Famille d'un butin, d'abord par les `tags` de l'espèce (autorité), sinon par le
	libellé du butin — repli utile si le doc espèce a disparu du bestiaire."""
	for sous_cat, marqueurs, _generique in FAMILLES:
		if tags & marqueurs:
			return sous_cat
	for sous_cat, _marqueurs, generique in FAMILLES:
		if (nom or "").lower().startswith(generique["nom"].split()[0].lower()):
			return sous_cat
	return None


def main() -> int:
	items, especes = _charger_docs()
	if not items:
		print("Aucun doc item trouvé dans jsons/ — rien à faire.", file=sys.stderr)
		return 1

	sortie, sans_famille = [], []
	compte = {sous_cat: 0 for sous_cat, _m, _g in FAMILLES}

	for item in items:
		if not item.get("source_espece") or item.get("sous_categorie"):
			continue
		tags = set((especes.get(item["source_espece"]) or {}).get("tags") or [])
		sous_cat = _famille_de(tags, item.get("nom", ""))
		if not sous_cat:
			sans_famille.append((item["_id"], sorted(tags)))
			continue
		doc = {k: v for k, v in item.items() if k != "_rev"}
		doc["sous_categorie"] = sous_cat
		sortie.append(doc)
		compte[sous_cat] += 1

	# Matières génériques : le doc que `matiere_item_id` valorise pour la clé sous-catégorie.
	for sous_cat, _marqueurs, generique in FAMILLES:
		sortie.append({
			"_id": "item:" + sous_cat,
			"type": "item",
			"nom": generique["nom"],
			"sous_categorie": sous_cat,
			"icon": generique["icon"],
			"rarete": generique["rarete"],
			"categorie": "composant",
			"slots": [],
			"poids": generique["poids"],
			"description": generique["description"],
		})

	for sous_cat, lieu_cat, final, qm, qp in RECETTES:
		sortie.append({
			"_id": "recette:%s_%s_%s" % (sous_cat, final, lieu_cat),
			"type": "recette",
			"lieu_categorie": lieu_cat,
			"objet_final": final,
			"quantite_produite": qp,
			"matieres_premieres": [{"sous_categorie": sous_cat, "quantite": qm}],
		})

	with open(SORTIE, "w", encoding="utf-8") as fh:
		json.dump(sortie, fh, ensure_ascii=False, indent=2)

	print("→ %s" % os.path.relpath(SORTIE, RACINE))
	for sous_cat, _m, _g in FAMILLES:
		print("   %-16s %2d butins reclassés" % (sous_cat, compte[sous_cat]))
	print("   %d matières génériques + %d recettes" % (len(FAMILLES), len(RECETTES)))
	print("   %d docs au total" % len(sortie))
	if sans_famille:
		print("\n⚠️ butins sans famille (tags inattendus), à traiter à la main :")
		for item_id, tags in sans_famille:
			print("   %s  tags=%s" % (item_id, tags))
	return 0


if __name__ == "__main__":
	sys.exit(main())
