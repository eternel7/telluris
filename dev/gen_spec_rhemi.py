#!/usr/bin/env python
# dev/gen_spec_rhemi.py
# Peuplement d'une cité (Rhemi, puis Chartres) : écrit la SPEC d'un lot de magasins (2 par
# métier de base + ses auberges), à passer ensuite à `dev/gen_magasins.py`, qui valide et
# produit l'import. Réglages par cité : `VILLES`.
#
#   python dev/gen_spec_rhemi.py [--cite lieu:chartres]  → jsons/<cité>_magasins_spec.json
#   python dev/gen_magasins.py --dump <dump> --spec jsons/<cité>_magasins_spec.json
#
# ⚠️ CITÉ SANS PORTES (Chartres au 09/10) : l'enceinte est un polygone RELEVÉ SUR LA CARTE
# (`VILLES[cite]["enceinte"]`, en cases de 16 px), et « joignable à pied » = la plus grande
# composante de terrain 1 en 8-voisins (le pavé de marche a 8 directions) dans ce polygone.
#
# ⚠️ « À L'INTÉRIEUR DES PORTES » : l'enceinte de Rhemi n'est PAS murée dans la grille (`nav`
# quasi vide, un remplissage des cases 1 depuis une porte intérieure sort de la ville). Le dedans
# est donc GÉOMÉTRIQUE : le polygone des portes `*_interieur` telles qu'elles sont posées en base,
# une case de marge au bord, et seules les cases de terrain 1 qu'on rejoint à pied depuis une
# porte intérieure sans sortir du polygone.
#
# ⚠️ Métiers de base = catégories ayant un tenancier `pnj:marchand_*` HORS des grandes maisons
# (`LIEU_CATEGORIES_FUSION`) : relus du dump et de `models/character_stats.py`, jamais recopiés.
#
# ⚠️ Tenanciers : portrait GÉNÉRIQUE `marchand_<race>_<m|f>_<métier>NN` de
# `templates/resources/pnj/` (les portraits nominatifs appartiennent à des PNJ précis), nom tiré
# du répertoire du recrutement selon la race et le sexe du portrait. `utils/recrutement` tire la
# base à l'import : ses constantes sont lues par `ast`, sans importer le module.
#
# Tirages seedés : relancer sur le même dump redonne la même spec.

import ast
import glob
import json
import math
import os
import random
import re
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RACINE not in sys.path:
	sys.path.insert(0, RACINE)

from utils import enseignes  # noqa: E402  (module pur, n'importe que `random`)

CITE = "lieu:rhemi"
DOSSIER_PNJ = os.path.join(RACINE, "templates", "resources", "pnj")
DOSSIER_TOWNS = os.path.join(RACINE, "templates", "resources", "towns")
GRAINE = 20261008

PAR_METIER = 2
AUBERGES = [
	("Auberge du Sacre", "auberge_europe02.png"),
	("Au Bon Vigneron", "auberge_europe05.png"),
	("La Crayère", "auberge_europe06.jpg"),
]

# Par cité : auberges (label, image), graine, et l'enceinte quand la cité n'a pas de portes.
VILLES = {
	"lieu:rhemi": {"auberges": AUBERGES, "graine": GRAINE, "enceinte": None},
	"lieu:chartres": {
		"auberges": [
			("Aux Deux Flèches", "auberge_europe01.png"),       # les deux flèches de la cathédrale
			("Le Relais de l'Eure", "auberge_europe03.png"),
			("Au Grenier de Beauce", "auberge_europe04.png"),   # la Beauce, grenier à blé de Chartres
			("La Halte des Pèlerins", "auberge_europe07.jpg"),
		],
		"graine": 20261009,
		# Remparts de chartres_city.png (1408×768, cases de 16 px), relevés tour par tour le 09/10 :
		# porte ouest, nord-ouest, front nord sous la cathédrale, angle nord-est, front est,
		# pointe sud-est, front sud au-dessus de l'Eure, sud-ouest, ouest.
		"enceinte": [(26.5, 20.6), (34.7, 14.4), (52.5, 12.2), (60, 13), (66, 18.7), (66, 26),
					 (58.7, 28.7), (52, 31.5), (46, 35), (39, 37.5), (28.7, 34), (24.7, 28.7)],
	},
}


def sortie_de(cite):
	return os.path.join("jsons", f"{cite.split(':', 1)[-1]}_magasins_spec.json")

# Jeton de métier écrit dans un nom de portrait → catégorie de lieu.
ALIAS_METIER = {
	"archerie": "fletcher",
	"tanerie": "tannerie",
	"cuisinie": "cuisine",
	"empeneur": "atelier_de_l_empenneur",
	"empenneur": "atelier_de_l_empenneur",
	"atelier_de_l_empeneur": "atelier_de_l_empenneur",
	"cirier": "atelier_de_cirier",
	"atelier_cirier": "atelier_de_cirier",
	"herboriste": "jardinier",
	"jardinerie": "jardinier",
	"tisserie": "tissage",
	"negoce": "negociant",
}
ALIAS_RACE = {"humaine": "humain"}
PORTRAIT_GENERIQUE = re.compile(r"^marchand_(elfe|hobbit|humaine?|nain|ogre)_([mf])_(.+?)(\d*)\.(png|jpe?g)$")

# Image de lieu d'un métier qui n'a pas de fichier `<categorie>_europeNN` à son nom.
PREFIXE_IMAGE = {
	"fletcher": "archerie_europe",
	"laboratoire_d_alchimie": "cabinet_alchimie_europe",
	"negociant": "negoce_europe",
}


# ── Lecture ─────────────────────────────────────────────────────────────────────

def _dump_le_plus_recent() -> str:
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		raise SystemExit("ERREUR : aucun jsons/telluris-dump-*.json — exporter la base d'abord.")
	return dumps[-1]


def charger(chemin: str) -> list:
	with open(chemin, encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


def constantes_source(chemin: str, noms: set) -> dict:
	"""Valeurs littérales des affectations de module nommées `noms` (Assign ou AnnAssign)."""
	with open(chemin, encoding="utf-8") as f:
		arbre = ast.parse(f.read())
	out = {}
	for noeud in arbre.body:
		if isinstance(noeud, ast.Assign):
			cibles = [t.id for t in noeud.targets if isinstance(t, ast.Name)]
		elif isinstance(noeud, ast.AnnAssign) and isinstance(noeud.target, ast.Name):
			cibles = [noeud.target.id]
		else:
			continue
		for nom in cibles:
			if nom in noms and noeud.value is not None:
				out[nom] = ast.literal_eval(noeud.value)
	manquants = noms - set(out)
	if manquants:
		raise SystemExit(f"ERREUR : {', '.join(sorted(manquants))} introuvable(s) dans {chemin}.")
	return out


# ── Géométrie : le dedans de l'enceinte ─────────────────────────────────────────

def polygone_des_portes(portes: list) -> list:
	"""Portes triées par angle autour de leur centre → polygone (liste de (x, y))."""
	cx = sum(p[0] for p in portes) / len(portes)
	cy = sum(p[1] for p in portes) / len(portes)
	return sorted(portes, key=lambda p: math.atan2(p[1] - cy, p[0] - cx))


def dans_polygone(x: float, y: float, poly: list) -> bool:
	"""Lancer de rayon (bord exclu par construction : on teste des centres de case)."""
	dedans = False
	n = len(poly)
	for i in range(n):
		x1, y1 = poly[i]
		x2, y2 = poly[(i + 1) % n]
		if (y1 > y) != (y2 > y):
			xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
			if x < xi:
				dedans = not dedans
	return dedans


def distance_au_bord(x: float, y: float, poly: list) -> float:
	meilleure = float("inf")
	n = len(poly)
	for i in range(n):
		(x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
		dx, dy = x2 - x1, y2 - y1
		long2 = dx * dx + dy * dy
		t = 0.0 if long2 == 0 else max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / long2))
		px, py = x1 + t * dx, y1 + t * dy
		meilleure = min(meilleure, math.hypot(x - px, y - py))
	return meilleure


def cases_interieures(cells: list, portes: list, marge: float = 1.0) -> list:
	"""Cases (x, y) de terrain 1, dans le polygone des portes, à `marge` cases au moins du bord,
	hors des portes, et rejointes à pied (4-voisins, terrain 1, sans sortir du polygone) depuis
	une porte intérieure. Triées (y, x)."""
	poly = polygone_des_portes(portes)
	h, w = len(cells), len(cells[0]) if cells else 0

	def marchable(x, y):
		return 0 <= x < w and 0 <= y < h and cells[y][x] == 1 and dans_polygone(x, y, poly)

	vues = set()
	file = []
	for (px, py) in portes:
		for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
			c = (px + dx, py + dy)
			if c not in vues and marchable(*c):
				vues.add(c)
				file.append(c)
	while file:
		x, y = file.pop()
		for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
			c = (x + dx, y + dy)
			if c not in vues and marchable(*c):
				vues.add(c)
				file.append(c)
	portes_set = {tuple(p) for p in portes}
	return sorted((c for c in vues
				   if c not in portes_set and distance_au_bord(c[0], c[1], poly) >= marge),
				  key=lambda c: (c[1], c[0]))


def cases_dans_enceinte(cells: list, enceinte: list, marge: float = 1.0) -> list:
	"""Cité SANS portes : cases de terrain 1 dans le polygone `enceinte`, à `marge` du bord, de
	la plus grande composante 8-connexe (le pavé de marche a 8 directions). Triées (y, x)."""
	h, w = len(cells), len(cells[0]) if cells else 0
	dedans = {(x, y) for y in range(h) for x in range(w)
			  if cells[y][x] == 1 and dans_polygone(x, y, enceinte)}
	vues, meilleure = set(), []
	for depart in sorted(dedans, key=lambda c: (c[1], c[0])):
		if depart in vues:
			continue
		vues.add(depart)
		comp, file = [], [depart]
		while file:
			x, y = file.pop()
			comp.append((x, y))
			for dx in (-1, 0, 1):
				for dy in (-1, 0, 1):
					c = (x + dx, y + dy)
					if c in dedans and c not in vues:
						vues.add(c)
						file.append(c)
		if len(comp) > len(meilleure):
			meilleure = comp
	return sorted((c for c in meilleure if distance_au_bord(c[0], c[1], enceinte) >= marge),
				  key=lambda c: (c[1], c[0]))


def etaler(candidats: list, n: int) -> list:
	"""`n` cases distinctes, tirées au point le plus éloigné des cases déjà prises (départ : la
	plus proche du barycentre). Déterministe : ex æquo départagés par l'ordre (y, x)."""
	if n > len(candidats):
		raise ValueError(f"{n} cases demandées, {len(candidats)} disponibles")
	cx = sum(c[0] for c in candidats) / len(candidats)
	cy = sum(c[1] for c in candidats) / len(candidats)
	choisies = [min(candidats, key=lambda c: ((c[0] - cx) ** 2 + (c[1] - cy) ** 2, c[1], c[0]))]
	dmin = {c: (c[0] - choisies[0][0]) ** 2 + (c[1] - choisies[0][1]) ** 2 for c in candidats}
	while len(choisies) < n:
		suivante = max(candidats, key=lambda c: (dmin[c], -c[1], -c[0]))
		choisies.append(suivante)
		for c in candidats:
			d = (c[0] - suivante[0]) ** 2 + (c[1] - suivante[1]) ** 2
			if d < dmin[c]:
				dmin[c] = d
	return choisies


# ── Tenanciers ──────────────────────────────────────────────────────────────────

def decoder_portrait(fichier: str):
	"""`marchand_<race>_<m|f>_<métier>NN.ext` → (race, "M"/"F", catégorie), ou None (portrait
	nominatif ou hors motif)."""
	m = PORTRAIT_GENERIQUE.match(fichier)
	if not m:
		return None
	race = ALIAS_RACE.get(m.group(1), m.group(1))
	metier = m.group(3)
	return race, m.group(2).upper(), ALIAS_METIER.get(metier, metier)


def portraits_par_metier(fichiers: list) -> dict:
	"""{catégorie: [(fichier, race, sexe), …]} triés par nom de fichier."""
	out = {}
	for f in sorted(fichiers):
		d = decoder_portrait(f)
		if d:
			out.setdefault(d[2], []).append((f, d[0], d[1]))
	return out


def tirer_nom(race: str, sexe: str, rng: random.Random, repertoire: dict, pris: set) -> str:
	"""Prénom + nom du répertoire du recrutement (règle de prénom mutualisé comprise), jamais
	un nom complet déjà `pris`."""
	prenoms, noms = repertoire["PRENOMS"], repertoire["NOMS"]
	mutualisee = repertoire["PRENOM_RACE_MUTUALISEE"]

	def pool(rid):
		p = prenoms.get(rid) or prenoms["defaut"]
		return p.get(sexe) or p.get("M") or prenoms["defaut"]["M"]

	for _ in range(500):
		if race != mutualisee and rng.random() < repertoire["PRENOM_MUTUALISE_PROBA"]:
			pp = pool(mutualisee)
		else:
			pp = pool(race)
		nom = f"{rng.choice(pp)} {rng.choice(noms.get(race) or noms['defaut'])}"
		if nom not in pris:
			pris.add(nom)
			return nom
	raise SystemExit(f"ERREUR : plus de nom libre pour {race}/{sexe}.")


# ── Assemblage ──────────────────────────────────────────────────────────────────

def images_de(categorie: str, fichiers_towns: list) -> list:
	prefixe = PREFIXE_IMAGE.get(categorie, categorie + "_europe")
	return sorted(f for f in fichiers_towns if f.startswith(prefixe))


def construire_spec(docs: list, fichiers_pnj: list, fichiers_towns: list, fusion: dict,
					repertoire: dict, cite_id: str = CITE, auberges: list = AUBERGES,
					graine: int = GRAINE, enceinte: list = None) -> tuple:
	"""PURE. Rend (spec, rapport). `enceinte` (polygone en cases) remplace les portes."""
	par_id = {d.get("_id"): d for d in docs if isinstance(d, dict) and d.get("_id")}
	cite = par_id.get(cite_id)
	if not cite or not cite.get("cells"):
		raise SystemExit(f"ERREUR : {cite_id} absent du dump ou sans grille.")

	portes = []
	for c in docs:
		if not isinstance(c, dict) or c.get("type") != "connection":
			continue
		nodes = c.get("nodes") or []
		ici = next((n for n in nodes if n.get("lieu") == cite_id), None)
		la = next((n for n in nodes if n.get("lieu") != cite_id), None)
		if ici and la and str(la.get("lieu", "")).endswith("_interieur"):
			portes.append(tuple(ici["pos"]))
	if not enceinte and len(portes) < 3:
		raise SystemExit(f"ERREUR : {len(portes)} porte(s) intérieure(s) — impossible de borner la ville.")

	metiers = sorted(i.split("marchand_", 1)[1] for i in par_id
					 if str(i).startswith("pnj:marchand_") and i.split("marchand_", 1)[1] not in fusion)
	portraits = portraits_par_metier(fichiers_pnj)
	sans_portrait = [m for m in metiers if not portraits.get(m)]
	sans_image = [m for m in metiers if not images_de(m, fichiers_towns)]
	if sans_portrait or sans_image:
		raise SystemExit("ERREUR : " + "; ".join(filter(None, [
			sans_portrait and "aucun portrait générique pour " + ", ".join(sans_portrait),
			sans_image and "aucune image de lieu pour " + ", ".join(sans_image)])))

	candidats = (cases_dans_enceinte(cite["cells"], enceinte) if enceinte
				 else cases_interieures(cite["cells"], portes))
	total = len(metiers) * PAR_METIER + len(auberges)
	cases = etaler(candidats, total)
	rng = random.Random(graine)
	rng.shuffle(cases)

	labels_pris = {d.get("label") for d in docs if isinstance(d, dict) and d.get("type") == "lieu"}
	noms_pris = {e.get("nom") for d in docs if isinstance(d, dict) and isinstance(d.get("pnj"), list)
				 for e in d["pnj"] if isinstance(e, dict) and e.get("nom")}

	magasins, rapport = [], []
	for metier in metiers:
		labels = enseignes.tirer_labels(metier, PAR_METIER, cite_id, exclus=labels_pris,
										rand_fn=rng.shuffle)
		images = images_de(metier, fichiers_towns)
		dispo = portraits[metier]
		for k, label in enumerate(labels):
			labels_pris.add(label)
			fichier, race, sexe = dispo[k % len(dispo)]
			nom = tirer_nom(race, sexe, rng, repertoire, noms_pris)
			x, y = cases.pop()
			magasins.append({"categorie": metier, "label": label, "image": images[k % len(images)],
							 "pos": [x, y], "nom": nom, "portrait": fichier})
			rapport.append(f"  {metier:24} {label:40} [{x:2},{y:2}]  {nom} ({fichier})")
	for label, image in auberges:
		if label in labels_pris:
			raise SystemExit(f"ERREUR : l'auberge « {label} » existe déjà.")
		x, y = cases.pop()
		magasins.append({"categorie": "auberge", "label": label, "image": image, "pos": [x, y]})
		rapport.append(f"  {'auberge':24} {label:40} [{x:2},{y:2}]")
	borne = "enceinte relevée sur la carte" if enceinte else f"{len(portes)} portes intérieures"
	rapport.insert(0, f"{borne}, {len(candidats)} cases candidates, "
					  f"{len(magasins)} lieux ({len(metiers)} métiers × {PAR_METIER} + {len(auberges)} auberges)")
	return {"cite": cite_id, "magasins": magasins}, rapport


def main() -> int:
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	import argparse
	p = argparse.ArgumentParser()
	p.add_argument("--cite", default=CITE, choices=sorted(VILLES))
	cite = p.parse_args().cite
	reglages = VILLES[cite]
	source = _dump_le_plus_recent()
	fusion = constantes_source(os.path.join(RACINE, "models", "character_stats.py"),
							   {"LIEU_CATEGORIES_FUSION"})["LIEU_CATEGORIES_FUSION"]
	repertoire = constantes_source(os.path.join(RACINE, "utils", "recrutement.py"),
								   {"PRENOMS", "NOMS", "PRENOM_RACE_MUTUALISEE", "PRENOM_MUTUALISE_PROBA"})
	spec, rapport = construire_spec(charger(source), os.listdir(DOSSIER_PNJ),
									os.listdir(DOSSIER_TOWNS), fusion, repertoire, cite,
									reglages["auberges"], reglages["graine"], reglages["enceinte"])
	sortie = sortie_de(cite)
	with open(os.path.join(RACINE, sortie), "w", encoding="utf-8") as f:
		json.dump(spec, f, ensure_ascii=False, indent="\t")
		f.write("\n")
	print(f"relu {os.path.relpath(source, RACINE)}")
	for ligne in rapport:
		print(ligne)
	print("→ " + sortie.replace("\\", "/"))
	return 0


if __name__ == "__main__":
	sys.exit(main())
