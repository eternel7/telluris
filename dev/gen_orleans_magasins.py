#!/usr/bin/env python
# dev/gen_orleans_magasins.py
# Peuplement d'Orléans (11/11/2026) : 45 boutiques + 4 grandes maisons, enseignes AUTHORÉES
# (lore : docs/lore/cites/20261111_histoire_d_orleans.md — Martroi, halage, Loire, Châtelet…),
# et les spécialités de cave d'Orléans (vinaigre, moutarde). UN SEUL fichier (CLAUDE.md §18) :
#
#   python dev/gen_orleans_magasins.py   → jsons/orleans_magasins_a_importer.json
#
# puis les images (portrait + façade de chaque boutique, façade des auberges) :
#   python dev/gen_images_magasins.py preparer --cite lieu:orleans --lot jsons/orleans_magasins_a_importer.json
#
# ⚠️ Cases : région de la VILLE par `dev/region_ville.js` = le code de « 📍 Compléter les
# positions » (`_regionCible` de admin_lieux.html) — l'intra-muros, pas la campagne, plus grande.
# Étalées loin des portes existantes (`gen_spec_rhemi.etaler`).
# ⚠️ Tenanciers (feedback de l'auteur) : portrait GÉNÉRIQUE `marchand_<race>_<m|f>_<métier>NN`
# existant, nom tiré du répertoire du recrutement selon race et sexe. Les Lignées ne sont tirées
# que parmi les portraits génériques du métier : on prend la Lignée la MOINS présente jusque-là
# dans le lot, pour approcher des chances égales.
# ⚠️ Validation et forme des docs : `gen_magasins.construire` (refus sur `_id` pris, case ≠ 1…).
# Tirages seedés : relancer sur le même dump redonne le même fichier.

import json
import os
import random
import subprocess
import sys
import tempfile

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "dev"))

import gen_magasins  # noqa: E402
import gen_spec_rhemi as spec_outils  # noqa: E402

CITE = "lieu:orleans"
GRAINE = 20261111
SORTIE = os.path.join("jsons", "orleans_magasins_a_importer.json")
DOSSIER_PNJ = os.path.join(RACINE, "templates", "resources", "pnj")
DOSSIER_TOWNS = os.path.join(RACINE, "templates", "resources", "towns")
NODE = os.environ.get("NODE") or (r"C:\Program Files\nodejs\node.exe"
								  if os.path.exists(r"C:\Program Files\nodejs\node.exe") else "node")

# (catégorie, [enseignes]) — validé par l'auteur le 11/11/2026.
BOUTIQUES = [
	("negociant", ["Le Comptoir de Genabum", "Le Connaissement du Châtelet", "La Pesée Juste du Martroi",
				   "La Maison de Négoce des Gabarres"]),
	("cave", ["Le Vinaigrier du Châtelet", "La Barrique des Quais", "Le Pressoir de la Porte de Bourgogne"]),
	("salaison", ["Le Grenier à Sel des Quais", "La Saumure de la Loire"]),
	("corderie", ["Le Câble des Gabarres", "La Haussière du Halage"]),
	("atelier_d_artisan", ["La Douelle des Turcies", "Le Chantier du Fil de l'Eau"]),
	("boucherie", ["Le Billot du Martroi", "La Hampe de la Porte Bannier"]),
	("boulangerie", ["La Miche de Sainte-Croix", "L'Épi de la Porte Bannier"]),
	("cuisine", ["Le Cotignac du Martroi", "La Marmite des Bateliers"]),
	("jardinier", ["Le Clos aux Coings", "Le Verger des Turcies"]),
	("fumoir", ["Le Haloir à Poissons des Quais"]),
	("etable", ["Les Chevaux du Halage"]),
	("tannerie", ["Le Corroi de la Loire"]),
	("apothicairerie", ["L'Herbier de Sainte-Croix"]),
	("armurerie", ["L'Enclume des Tourelles"]),
	("atelier_de_cirier", ["Le Cierge du Huit-Mai"]),
	("atelier_de_l_empenneur", ["La Penne de la Forêt"]),
	("fletcher", ["L'Arc de La Hire"]),
	("bijouterie", ["La Sertissure du Châtelet"]),
	("bourrellerie", ["Le Collier de Halage"]),
	("boyauderie", ["La Baudruche des Quais"]),
	("brosserie", ["L'Époussette de Genabum"]),
	("laboratoire_d_alchimie", ["Le Mortier des Deux Crues"]),
	("lutherie", ["Le Rondeau du Martroi"]),
	("maroquinerie", ["La Gibecière du Passeur"]),
	("necromancie", ["Le Linceul des Tourelles"]),
	("plumasserie", ["Le Duvet des Grèves"]),
	("savonnerie", ["Le Battoir de la Loire"]),
	("scriptorium", ["Le Vélin d'Aurelianum"]),
	("tabletterie", ["La Plaquette du Vieux Pont"]),
	# Grandes maisons
	("grande_corderie", ["La Grande Corderie des Gabarriers"]),
	("maison_des_conserves", ["Le Grenier des Expéditions"]),
	("grande_manufacture_textile", ["La Halle aux Draps de Bourgogne"]),
	("grandes_halles_alimentaires", ["Les Halles du Martroi"]),
]
# Auberges : sans tenancier (aucun `pnj:marchand_auberge`) ; façade provisoire existante.
AUBERGES = [
	("Au Passeur de Loire", "auberge_europe01.png"),
	("La Gabarre Amarrée", "auberge_europe03.png"),
	("L'Auberge du Huit-Mai", "auberge_europe04.png"),
	("À l'Étendard de Dunois", "auberge_europe07.jpg"),
]

# Spécialités de cave d'Orléans (calquées sur Lutèce et Reims, prix et poids compris).
SPECIALITES = [
	{"_id": "item:Vinaigre_d_Orleans", "type": "item", "nom": "Vinaigre d'Orléans",
	 "description": ("Vinaigre des vinaigriers du Châtelet, mûri sans hâte en fûts de chêne au bord de la "
					 "Loire. On en charge les navires qui partent vers les mers de Mu : le penanggalan le craint."),
	 "icon": "🫙", "rarete": "commun", "categorie": "composant", "sous_categorie": "condiment",
	 "slots": [], "tags": [], "poids": 0.8, "valeur": [{"cu": 12}, {"cu": 30}]},
	{"_id": "recette:specialite_vinaigre_d_orleans", "type": "recette", "lieu_categorie": "cave",
	 "lieu_portee": CITE, "objet_final": "Vinaigre_d_Orleans", "quantite_produite": 3,
	 "matieres_premieres": [{"item": "item:Vin_de_pays", "quantite": 2}]},
	{"_id": "item:Moutarde_d_Orleans", "type": "item", "nom": "Moutarde d'Orléans",
	 "description": "Graines broyées au vinaigre d'Orléans, à la meule de pierre. Douce d'abord, puis elle mord.",
	 "icon": "🟡", "rarete": "commun", "categorie": "composant", "sous_categorie": "condiment",
	 "slots": [], "tags": [], "poids": 0.4, "valeur": [{"cu": 18}, {"cu": 45}]},
	{"_id": "recette:specialite_moutarde_d_orleans", "type": "recette", "lieu_categorie": "cave",
	 "lieu_portee": CITE, "objet_final": "Moutarde_d_Orleans", "quantite_produite": 3,
	 "matieres_premieres": [{"item": "item:Graines_de_moutarde", "quantite": 3},
							{"item": "item:Vinaigre_d_Orleans", "quantite": 1},
							{"item": "item:Sel", "quantite": 1}]},
]


def region_ville(cite_doc, ancres):
	"""Cases de la région de la ville (même code que 📍, via Node)."""
	entree = {"cells": cite_doc["cells"], "nav": cite_doc.get("nav") or {},
			  "dims": cite_doc["dimensions"], "ancres": ancres, "zone": None}
	with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
		json.dump(entree, f)
		chemin = f.name
	try:
		sortie = subprocess.run([NODE, os.path.join(RACINE, "dev", "region_ville.js"), chemin],
								capture_output=True, text=True, encoding="utf-8", check=True).stdout
	finally:
		os.unlink(chemin)
	return json.loads(sortie)


def portes_de(docs, par_id, cite):
	"""Positions des connexions de la cité vers un AUTRE lieu (hors pays) : les ancres."""
	out = []
	for c in docs:
		if not isinstance(c, dict) or c.get("type") != "connection":
			continue
		nodes = c.get("nodes") or []
		ici = [n for n in nodes if n.get("lieu") == cite]
		la = next((n for n in nodes if n.get("lieu") != cite), None)
		if len(ici) != 1 or not la:
			continue
		if (par_id.get(la.get("lieu")) or {}).get("categorie") == "pays":
			continue
		out.append(tuple(ici[0]["pos"]))
	return out


def choisir_portrait(dispo, compte_races, rng):
	"""Portrait générique du métier dont la Lignée est la moins présente dans le lot (ex æquo : tirage)."""
	races = sorted({r for _, r, _ in dispo}, key=lambda r: (compte_races.get(r, 0), rng.random()))
	race = races[0]
	choix = [p for p in dispo if p[1] == race]
	fichier, race, sexe = rng.choice(choix)
	compte_races[race] = compte_races.get(race, 0) + 1
	return fichier, race, sexe


def construire(docs, fichiers_pnj, fichiers_towns, repertoire):
	par_id = {d.get("_id"): d for d in docs if isinstance(d, dict) and d.get("_id")}
	cite = par_id[CITE]
	pris = [i for i in (d["_id"] for d in SPECIALITES) if i in par_id]
	if pris:
		raise SystemExit("ERREUR : déjà en base : " + ", ".join(pris))
	portes = portes_de(docs, par_id, CITE)
	region = region_ville(cite, [list(p) for p in portes])
	candidats = [tuple(c) for c in region["cases"] if tuple(c) not in set(portes)]
	total = sum(len(l) for _, l in BOUTIQUES) + len(AUBERGES)
	cases = spec_outils.etaler(sorted(candidats, key=lambda c: (c[1], c[0])), total, deja=portes)
	rng = random.Random(GRAINE)
	rng.shuffle(cases)

	portraits = spec_outils.portraits_par_metier(fichiers_pnj)
	noms_pris = {e.get("nom") for d in docs if isinstance(d, dict) and isinstance(d.get("pnj"), list)
				 for e in d["pnj"] if isinstance(e, dict) and e.get("nom")}
	compte_races = {}
	magasins, rapport = [], []
	for cat, labels in BOUTIQUES:
		images = spec_outils.images_de(cat, fichiers_towns)
		dispo = portraits.get(cat)
		if not images or not dispo:
			raise SystemExit(f"ERREUR : {cat} sans image de lieu ou sans portrait générique.")
		for k, label in enumerate(labels):
			fichier, race, sexe = choisir_portrait(dispo, compte_races, rng)
			nom = spec_outils.tirer_nom(race, sexe, rng, repertoire, noms_pris)
			x, y = cases.pop()
			magasins.append({"categorie": cat, "label": label, "image": images[k % len(images)],
							 "pos": [x, y], "nom": nom, "portrait": fichier})
			rapport.append(f"  {cat:28} {label:38} [{x:2},{y:2}]  {nom} ({race} {sexe})")
	for label, image in AUBERGES:
		x, y = cases.pop()
		magasins.append({"categorie": "auberge", "label": label, "image": image, "pos": [x, y]})
		rapport.append(f"  {'auberge':28} {label:38} [{x:2},{y:2}]")
	res = gen_magasins.construire(docs, {"cite": CITE, "magasins": magasins}, set(fichiers_towns))
	if res["erreurs"]:
		raise SystemExit("ERREUR :\n  " + "\n  ".join(res["erreurs"]))
	entete = (f"région de la ville : {region['taille']} cases ({region['raison']}), "
			  f"{len(candidats)} candidates, {len(magasins)} lieux ; Lignées : {compte_races}")
	return res["docs"] + SPECIALITES, [entete] + rapport + ["  ⚠ " + a for a in res["avertissements"]]


def main():
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	source = spec_outils._dump_le_plus_recent()
	repertoire = spec_outils.constantes_source(
		os.path.join(RACINE, "utils", "recrutement.py"),
		{"PRENOMS", "NOMS", "PRENOM_RACE_MUTUALISEE", "PRENOM_MUTUALISE_PROBA"})
	docs, rapport = construire(spec_outils.charger(source), os.listdir(DOSSIER_PNJ),
							   os.listdir(DOSSIER_TOWNS), repertoire)
	with open(os.path.join(RACINE, SORTIE), "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent="\t")
		f.write("\n")
	print(f"relu {os.path.relpath(source, RACINE)}")
	for ligne in rapport:
		print(ligne)
	print(f"{len(docs)} docs → {SORTIE.replace(os.sep, '/')}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
