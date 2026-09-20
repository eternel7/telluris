#!/usr/bin/env python
# dev/gen_fabrication_matieres.py
# Ce qu'une MATIÈRE apporte à une pièce fabriquée sur mesure — bloc `fabrication` sur les
# docs `item:*` de matière première.
#
# Sans ce bloc, une matière reste utilisable dans une commande (elle coûte son prix et pèse
# son poids) mais n'apporte AUCUNE propriété : `fabrication.proprietes_matiere` rend un bloc
# vide. C'est le comportement d'avant pour les 1 324 items en base — aucune migration.
#
# ⚠️ AUCUNE RECETTE N'EST TOUCHÉE, et c'est délibéré. Ajouter un intrant à une recette ouvre
# un point de vente pour lui (`appro_leaves_categorie` → `approvisionner`) et risque la
# FAUSSE FEUILLE (une matière qu'une recette produit ailleurs n'est plus jamais livrée, ce
# qui gèle en silence toutes les recettes qui la citent — cf. compétence telluris-economie).
# Ce script ne fait qu'ENRICHIR des docs item existants.
#
# ⚠️ Les matières retenues sont toutes CONSOMMÉES par au moins un métier : c'est la condition
# pour qu'un artisan les accepte (`commande.matiere_acceptee` → `marche.besoins_lieu`). Une
# matière que personne ne travaille ne serait proposée nulle part.
#
# IDEMPOTENT : relit le dump, réémet le doc COMPLET tel qu'il est en base avec le seul bloc
# `fabrication` ajouté (l'import fait un PUT complet, cf. CLAUDE.md §11). Un doc absent de la
# base est signalé et sauté ; un doc qui porte déjà le même bloc n'est pas réémis.
#
# Usage : python dev/gen_fabrication_matieres.py [--dump chemin/vers/telluris-dump-*.json]
#         (sans --dump : le dump le plus récent de jsons/)
# Sortie : jsons/fabrication_matieres_a_importer.json (📥 Importer depuis /admin/dev-tools)

import argparse
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
DOSSIER_JSONS = os.path.join(RACINE, "jsons")
SORTIE = os.path.join(DOSSIER_JSONS, "fabrication_matieres_a_importer.json")

from utils import fabrication  # noqa: E402

# ── La table ────────────────────────────────────────────────────────────────────
# `nom`  : fragment ajouté au nom de la pièce (« Épée longue en acier au cristal de feu »).
# `modificateurs` : composés par `fabrication.appliquer_modificateurs` — additif sur les
#   `bonus_*`, fusion clé à clé sur `bonus`, multiplicatif sur `poids`/`valeur`, palier le
#   plus haut sur `rarete`. Tout champ hors de `CLES_MODIFIABLES` serait ignoré.
#
# ⚠️ Volontairement SOBRE. Ces valeurs s'ajoutent à celles de l'objet de base et se cumulent
# entre matières (× quantité) : les armes réelles de la base tiennent dans +2/+3 de dégâts et
# 17-30 de PA, une matière qui donnerait +10 déclasserait tout le contenu authoré d'un coup.
# Le levier de rareté, lui, est le PRIX (`valeur`), qui se propage au coût de la commande.
MATIERES = {
	"item:fer": {
		"nom": "en fer",
		"modificateurs": {"bonus_degats": 1, "poids": {"facteur": 1.05}},
	},
	"item:acier": {
		"nom": "en acier",
		"modificateurs": {"bonus_degats": 2, "bonus_pa": 2,
						  "poids": {"facteur": 1.05}, "valeur": {"facteur": 1.3}},
	},
	"item:bronze": {
		"nom": "en bronze",
		"modificateurs": {"bonus_degats": 1, "poids": {"facteur": 1.1},
						  "valeur": {"facteur": 0.9}},
	},
	"item:plomb": {
		# Lourde et sourde : elle frappe fort et se porte mal. Le poids EST le contrepoids.
		"nom": "plombé",
		"modificateurs": {"bonus_degats": 2, "poids": {"facteur": 1.4},
						  "valeur": {"facteur": 0.8}},
	},
	"item:argent": {
		# L'argent est le métal des canaux : `item:Epee_argent` porte déjà bonus_pm 4 et
		# bonus Int 2 — la matière prolonge cette ligne au lieu d'en ouvrir une autre.
		"nom": "aux ferrures d'argent",
		"modificateurs": {"bonus_pm": 3, "bonus": {"Int": 1},
						  "valeur": {"facteur": 1.8}, "rarete": "peu_commun"},
	},
	"item:cuir": {
		"nom": "à garniture de cuir",
		"modificateurs": {"bonus_pa": 1, "poids": {"facteur": 0.95}},
	},
	"item:tendons": {
		"nom": "à ligature de tendons",
		"modificateurs": {"bonus_degats": 1, "poids": {"facteur": 0.95}},
	},
	"item:os": {
		"nom": "à poignée d'os",
		"modificateurs": {"bonus_degats": 1, "poids": {"facteur": 0.9}},
	},
	"item:crocs": {
		"nom": "à garde de crocs",
		"modificateurs": {"bonus_degats": 2, "valeur": {"facteur": 1.2}},
	},
	"item:gemmes": {
		"nom": "serti d'une gemme",
		"modificateurs": {"bonus_pm": 4, "bonus": {"Vol": 1},
						  "valeur": {"facteur": 2.0}, "rarete": "rare"},
	},
	"item:metaux_precieux": {
		"nom": "à incrustations précieuses",
		"modificateurs": {"bonus": {"Cha": 2}, "valeur": {"facteur": 2.5},
						  "rarete": "rare"},
	},
	"item:perles": {
		"nom": "perlé",
		"modificateurs": {"bonus": {"Cha": 1}, "valeur": {"facteur": 1.6}},
	},
}


def charger_dump(chemin=None) -> dict:
	if chemin:
		print("source : %s" % chemin)
		return json.load(open(chemin, encoding="utf-8"))
	dumps = sorted(
		f for f in os.listdir(DOSSIER_JSONS)
		if f.startswith("telluris-dump-") and f.endswith(".json")
	)
	if not dumps:
		raise SystemExit("Aucun telluris-dump-*.json dans jsons/ — passez --dump.")
	print("source : jsons/%s" % dumps[-1])
	return json.load(open(os.path.join(DOSSIER_JSONS, dumps[-1]), encoding="utf-8"))


def _cles_consommees(base: dict) -> set:
	"""Toutes les clés matières qu'une recette consomme, quelque part. Relu du dump plutôt
	qu'appelé sur `utils.marche` : ce script ne doit pas dépendre d'une base joignable."""
	cles = set()
	for doc in base.values():
		if doc.get("type") != "recette":
			continue
		for m in (doc.get("matieres_premieres") or []):
			cle = m.get("item") or m.get("sous_categorie")
			if cle:
				cles.add(cle)
		if doc.get("matiere_premiere_sous_categorie"):
			cles.add(doc["matiere_premiere_sous_categorie"])
	return cles


def main() -> None:
	# Console Windows en cp1252 : sans cela, le premier accent fait planter le script.
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass

	parser = argparse.ArgumentParser(description="Propriétés de fabrication des matières")
	parser.add_argument("--dump", help="dump à relire (défaut : le plus récent de jsons/)")
	args = parser.parse_args()

	dump = charger_dump(args.dump)
	base = {d["_id"]: d for d in dump["docs"] if isinstance(d, dict) and d.get("_id")}
	consommees = _cles_consommees(base)

	docs, absents, inchanges, jamais_travaillees = [], [], [], []
	for item_id, bloc in sorted(MATIERES.items()):
		doc = base.get(item_id)
		if doc is None:
			absents.append(item_id)
			continue
		# Une matière que personne ne travaille ne serait proposée par aucun artisan
		# (`besoins_lieu`) : le bloc serait posé pour rien. On le signale.
		sous_cat = doc.get("sous_categorie") or doc.get("categorie")
		if item_id not in consommees and sous_cat not in consommees:
			jamais_travaillees.append(item_id)
		if doc.get("fabrication") == bloc:
			inchanges.append(item_id)
			continue
		# ⚠️ PUT COMPLET à l'import : on réémet le doc tel qu'il est en base, `_rev` retiré
		# (il est réattaché depuis la base), avec le seul champ ajouté.
		neuf = {k: v for k, v in doc.items() if k != "_rev"}
		neuf["fabrication"] = bloc
		docs.append(neuf)

	# Contrôle de forme : un modificateur hors liste blanche serait ignoré EN SILENCE par
	# `proprietes_matiere`. Mieux vaut l'apprendre ici que de chercher pourquoi une matière
	# n'apporte rien en jeu.
	erreurs = []
	for item_id, bloc in sorted(MATIERES.items()):
		for cle in (bloc.get("modificateurs") or {}):
			if cle not in fabrication.CLES_MODIFIABLES:
				erreurs.append("%s : `%s` n'est pas un modificateur reconnu" % (item_id, cle))

	print("\n== Matières")
	for item_id, bloc in sorted(MATIERES.items()):
		etat = ("ABSENTE de la base" if item_id in absents
				else "déjà à jour" if item_id in inchanges else "à écrire")
		note = "  ⚠️ travaillée par aucun métier" if item_id in jamais_travaillees else ""
		nom = (base.get(item_id) or {}).get("nom") or "—"
		print("   %-26s %-22s %-14s %s%s" % (item_id, nom, etat, bloc["nom"], note))

	if erreurs:
		print("\n⚠️ %d erreur(s) — RIEN n'est écrit :" % len(erreurs))
		for e in erreurs:
			print("   " + e)
		sys.exit(1)

	if absents:
		print("\n⚠️ %d matière(s) absente(s) de la base, sautée(s) : %s"
			  % (len(absents), ", ".join(absents)))

	if not docs:
		print("\n   toutes les matières portent déjà leur bloc. Aucun fichier écrit.")
		return

	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print("\nécrit jsons/%s : %d doc(s) item enrichi(s)"
		  % (os.path.basename(SORTIE), len(docs)))


if __name__ == "__main__":
	main()
