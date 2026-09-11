"""Propose la grille de terrain (`cells`) d'un lieu à partir de son image de carte.

POURQUOI UN OUTIL : la grille d'une cité, c'est 4 128 cases (88×48) à poser au pinceau.
Deux lieux seulement l'ont reçue — `lieu:auxerre` et `lieu:lutecia` — et `lieu:france`
comme `lieu:rhemi` sont restés des matrices de `1` uniformes, c'est-à-dire des cartes où
rien n'arrête personne. Ce script pose une PREMIÈRE PASSE que l'auteur retouche ensuite
dans l'éditeur de carte ; il ne remplace pas son œil.

POURQUOI CE SCRIPT N'ÉCRIT PAS EN BASE : comme les 26 autres `gen_*.py`, il produit des
fichiers. `admin_import_bulk` fait un PUT COMPLET, jamais un merge (CLAUDE.md §11) — on
relit donc le doc depuis le DUMP, source unique, et on n'y injecte que `cells` et
`dimensions`. Une retouche faite à la main en base survit à une régénération, et la carte
d'import de `/admin` reste le seul chemin vers CouchDB.

⚠️ Pillow n'est utilisé QUE dans ce fichier et dans l'endpoint `grille_proposee` ; toute la
classification vit dans `utils/grille_image.py`, qui n'a aucune dépendance et se teste là
où Pillow n'est pas installé (cf. CLAUDE.md § Running tests).

Usage :
  python dev/gen_grille_image.py lieu:auxerre 86 48
  python dev/gen_grille_image.py towns/paris_capital.png 88 48
  python dev/gen_grille_image.py lieu:auxerre 86 48 jsons/telluris-dump-….json
Options : --connexite (efface les poches praticables enclavées) · --sans-apercu

Sorties (dans jsons/) :
  <slug>_grille_a_importer.json   le doc lieu complet, prêt pour la carte d'import
  <slug>_grille.json              {dimensions, cells} brut
  <slug>_grille_apercu.png        l'image avec la grille proposée en surimpression
"""

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import grille_image  # noqa: E402

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_JSONS = os.path.join(RACINE, "jsons")
RESSOURCES = os.path.join(RACINE, "templates", "resources")

# ⚠️ Même cascade, même ordre que le client (`admin_map_editor.html:1591`) : un doc ne porte
# qu'un NOM de fichier, jamais son dossier. Diverger d'ici ferait proposer une grille sur une
# image que l'éditeur n'affiche pas.
DOSSIERS_IMAGE = ("towns", "battle_maps", "maps")

# Voile de l'aperçu, aligné sur `VALUE_COLORS` de l'éditeur (`admin_map_editor.html:1233`) :
# l'auteur doit retrouver les couleurs qu'il a sous les yeux quand il peint.
VOILE = {
	0: (30, 30, 40, 153),      # inaccessible — bleu nuit opaque
	1: None,                   # libre — rien de peint, comme dans l'éditeur
	5: (200, 75, 75, 89),      # terrain très difficile — rouge translucide
}


def charger_dump(chemin=None):
	"""Le dump demandé, sinon le plus récent de `jsons/` (tri lexical = tri chronologique)."""
	if chemin:
		with open(chemin, encoding="utf-8") as f:
			return json.load(f)["docs"]
	dumps = sorted(glob.glob(os.path.join(DOSSIER_JSONS, "telluris-dump-*.json")))
	if not dumps:
		return []
	with open(dumps[-1], encoding="utf-8") as f:
		return json.load(f)["docs"]


def trouver_image(nom: str):
	"""Chemin absolu d'une image de lieu, cherchée dans la cascade des trois dossiers."""
	if os.path.isabs(nom) and os.path.exists(nom):
		return nom
	direct = os.path.join(RESSOURCES, nom)
	if os.path.exists(direct):
		return direct
	for dossier in DOSSIERS_IMAGE:
		candidat = os.path.join(RESSOURCES, dossier, nom)
		if os.path.exists(candidat):
			return candidat
	return None


def echantillonner(chemin: str, cols: int, rows: int):
	"""(couleurs, contours) : une couleur moyenne et une densité de traits par case.

	⚠️ `Image.BOX` et pas `BILINEAR` : BOX est une moyenne d'AIRE, donc chaque pixel du
	résultat est exactement la couleur moyenne de sa case. Un rééchantillonnage interpolant
	mélangerait les cases voisines et étalerait les rives de la rivière sur la berge.

	⚠️ La densité de contours se mesure à PLEINE RÉSOLUTION puis se réduit : réduire d'abord
	effacerait précisément ce qu'on cherche à compter — les traits des toits.
	"""
	from PIL import Image, ImageFilter
	with Image.open(chemin) as img:
		img.load()
		taille = img.size
		couleurs = _pixels(img.convert("RGB").resize((cols, rows), Image.BOX))
		contours = _pixels(img.convert("L").filter(ImageFilter.FIND_EDGES)
			.resize((cols, rows), Image.BOX))
	return couleurs, contours, taille


def _pixels(img) -> list:
	"""Les pixels d'une image, à plat, ligne par ligne.

	⚠️ `getdata()` est déprécié depuis Pillow 12 mais `get_flattened_data()` n'existe pas
	avant : le conteneur installe la dernière version au démarrage (`docker-compose.yml`) et
	rien ne l'épingle, donc les deux âges de Pillow doivent passer."""
	if hasattr(img, "get_flattened_data"):
		return list(img.get_flattened_data())
	return list(img.getdata())


def ecrire_apercu(chemin_image: str, cells, cible: str):
	"""L'image d'origine, la grille proposée en voile par-dessus, et le quadrillage."""
	from PIL import Image, ImageDraw
	rows, cols = len(cells), len(cells[0])
	with Image.open(chemin_image) as img:
		fond = img.convert("RGBA")
	largeur, hauteur = fond.size
	calque = Image.new("RGBA", fond.size, (0, 0, 0, 0))
	dessin = ImageDraw.Draw(calque)
	pas_x, pas_y = largeur / cols, hauteur / rows
	for y, ligne in enumerate(cells):
		for x, valeur in enumerate(ligne):
			couleur = VOILE.get(valeur)
			if couleur:
				dessin.rectangle(
					[x * pas_x, y * pas_y, (x + 1) * pas_x - 1, (y + 1) * pas_y - 1],
					fill=couleur)
	for x in range(cols + 1):
		dessin.line([(x * pas_x, 0), (x * pas_x, hauteur)], fill=(255, 255, 255, 36))
	for y in range(rows + 1):
		dessin.line([(0, y * pas_y), (largeur, y * pas_y)], fill=(255, 255, 255, 36))
	Image.alpha_composite(fond, calque).save(cible)


def imprimer_concordance(rapport: dict):
	"""⚠️ Le taux global vient EN DERNIER et jamais seul : sur une carte à 65 % de cases
	libres, répondre « libre » partout l'afficherait à 65 % sans rien savoir faire."""
	print("  Concordance avec la grille peinte à la main :")
	etiquettes = {0: "inaccessible", 1: "libre       ", 5: "eau         "}
	for valeur, m in sorted(rapport["par_valeur"].items()):
		print(f"    {valeur} {etiquettes.get(valeur, '            ')}"
			f" rappel {m['rappel'] * 100:5.1f} %   précision {m['precision'] * 100:5.1f} %"
			f"   (peintes {m['attendu']:5}, proposées {m['obtenu']:5})")
	print(f"    → global {rapport['global'] * 100:.1f} %"
		f" ({rapport['justes']}/{rapport['total']} cases)")


def main() -> int:
	args = [a for a in sys.argv[1:] if not a.startswith("--")]
	options = {a for a in sys.argv[1:] if a.startswith("--")}
	if len(args) < 3:
		print(__doc__)
		return 2
	cible, cols, rows = args[0], int(args[1]), int(args[2])
	if cols < 1 or rows < 1:
		print("✗ cols et rows doivent valoir au moins 1.")
		return 2

	docs = charger_dump(args[3] if len(args) > 3 else None)
	doc_lieu = None
	if cible.startswith("lieu:"):
		doc_lieu = next((d for d in docs if d.get("_id") == cible), None)
		if doc_lieu is None:
			print(f"✗ {cible} est absent du dump — vérifier l'id, ou passer un chemin d'image.")
			return 1
		nom_image = doc_lieu.get("image")
		if not nom_image:
			print(f"✗ {cible} ne porte pas de champ `image` : rien à analyser.")
			return 1
	else:
		nom_image = cible

	chemin = trouver_image(nom_image)
	if not chemin:
		print(f"✗ image introuvable : {nom_image} (cherchée dans {', '.join(DOSSIERS_IMAGE)})")
		return 1

	couleurs, contours, taille = echantillonner(chemin, cols, rows)
	cells = grille_image.grille_depuis_echantillons(couleurs, contours, cols, rows)
	cells = grille_image.lisser_majorite(cells)
	if "--connexite" in options:
		cells = grille_image.garder_composante_principale(cells)

	slug = (doc_lieu["_id"].split(":", 1)[1] if doc_lieu
		else os.path.splitext(os.path.basename(nom_image))[0])
	print(f"{os.path.relpath(chemin, RACINE)}  {taille[0]}×{taille[1]} px"
		f"  →  grille {cols}×{rows}  ({taille[0] / cols:.1f}×{taille[1] / rows:.1f} px/case)")
	total = cols * rows
	etiquettes = {0: "inaccessible", 1: "libre", 5: "eau (très difficile)"}
	for valeur, n in sorted(grille_image.comptes(cells).items()):
		print(f"  {valeur} {etiquettes.get(valeur, '?'):22} {n:6}  ({n * 100 / total:5.1f} %)")

	ecrits = []
	brut = os.path.join(DOSSIER_JSONS, f"{slug}_grille.json")
	with open(brut, "w", encoding="utf-8") as f:
		json.dump({"dimensions": {"x": cols, "y": rows}, "cells": cells},
			f, ensure_ascii=False, indent=2)
		f.write("\n")
	ecrits.append(brut)

	if doc_lieu is not None:
		# ⚠️ On repart du doc RELU et on n'y touche que `cells` et `dimensions` : le PUT
		# d'`import-bulk` est complet, toute clé absente disparaîtrait en silence.
		# `nav` est laissé tel quel — l'outil n'en propose jamais (cf. utils/grille_image).
		sortant = dict(doc_lieu)
		sortant["cells"] = cells
		sortant["dimensions"] = {"x": cols, "y": rows}
		a_importer = os.path.join(DOSSIER_JSONS, f"{slug}_grille_a_importer.json")
		with open(a_importer, "w", encoding="utf-8") as f:
			json.dump([sortant], f, ensure_ascii=False, indent=2)
			f.write("\n")
		ecrits.append(a_importer)

		peinte = doc_lieu.get("cells")
		if peinte and len(peinte) == rows and all(len(l) == cols for l in peinte):
			imprimer_concordance(grille_image.concordance(cells, peinte))
		elif peinte:
			print(f"  ⚠ pas de concordance calculée : la grille en base est "
				f"{len(peinte[0])}×{len(peinte)}, la proposition {cols}×{rows}.")
		else:
			print("  (aucune grille en base : rien à quoi comparer)")

	if "--sans-apercu" not in options:
		apercu = os.path.join(DOSSIER_JSONS, f"{slug}_grille_apercu.png")
		ecrire_apercu(chemin, cells, apercu)
		ecrits.append(apercu)

	for f in ecrits:
		print(f"  ✎ {os.path.relpath(f, RACINE)}")
	if doc_lieu is None:
		print("  ⚠ cible sans doc : ni fichier d'import ni concordance "
			"(passer un `lieu:*` pour les obtenir).")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
