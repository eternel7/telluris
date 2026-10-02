"""Propose la grille de terrain (`cells`) et les murs (`nav`) d'un lieu à partir de son
image de carte.

POURQUOI UN OUTIL : la grille d'une cité, c'est 4 128 cases (88×48) à poser au pinceau.
Deux lieux seulement l'ont reçue — `lieu:auxerre` et `lieu:lutecia` — et `lieu:france`
comme `lieu:rhemi` sont restés des matrices de `1` uniformes, c'est-à-dire des cartes où
rien n'arrête personne. Ce script pose une PREMIÈRE PASSE que l'auteur retouche ensuite
dans l'éditeur de carte ; il ne remplace pas son œil.

POURQUOI CE SCRIPT N'ÉCRIT PAS EN BASE : comme les 26 autres `gen_*.py`, il produit des
fichiers. `admin_import_bulk` fait un PUT COMPLET, jamais un merge (CLAUDE.md §11) — on
relit donc le doc depuis le DUMP, source unique, et on n'y injecte que `cells`, `nav` et
`dimensions`. `nav` part de celui du doc : aucun mur peint à la main n'est retiré.

⚠️ Pillow n'est utilisé QUE dans ce fichier, `calibrer_grille_image.py`, `utils/image_bords.py` et l'endpoint
`grille_proposee` ; toute la classification vit dans `utils/grille_image.py`, qui n'a aucune
dépendance et se teste là où Pillow n'est pas installé (cf. CLAUDE.md § Running tests).

Usage :
  python dev/gen_grille_image.py lieu:auxerre 86 48
  python dev/gen_grille_image.py towns/paris_capital.png 88 48
  python dev/gen_grille_image.py lieu:auxerre 86 48 jsons/telluris-dump-….json
Options : --profil=ville|foret|catacombes|pays (défaut : `pays` pour un lieu de catégorie
            pays, sinon lu sur les tags du lieu)
          --sans-passages (ni enceinte, ni coins, ni passages)
          --sans-rues (pas de tracé des rues intra-muros)
          --sans-nav (aucun mur nav proposé ; l'enceinte est fermée par le terrain)
          --sans-enceinte · --connexite (efface les poches praticables enclavées)
          --sans-apercu
          --nav-vide (repart d'un nav VIDE au lieu de celui du doc : pour mesurer le profil
            contre les murs peints à la main sans les recopier — rien à importer)

Sorties (dans jsons/) :
  <slug>_grille_a_importer.json   le doc lieu complet, prêt pour la carte d'import
  <slug>_grille.json              {dimensions, cells, nav} brut
  <slug>_grille_apercu.png        l'image avec la grille proposée en surimpression, les
                                  murs nav (rouge), les passages (vert vif), le rempart (orange),
                                  les rues ouvertes (bleu clair) ; profil pays : la côte
                                  (orange)
"""

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import grille_image, image_bords  # noqa: E402

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
	3: (200, 140, 75, 89),     # falaise — ocre translucide
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


def echantillonner_fins(chemin: str, cols: int, rows: int, k: int = grille_image.SOUS_CASES):
	"""Couleurs à `k×k` sous-cases par case (`cols·k × rows·k`, `Image.BOX`) : ce que lit le
	tracé des rues, plus fines qu'une case."""
	from PIL import Image
	with Image.open(chemin) as img:
		img.load()
		return _pixels(img.convert("RGB").resize((cols * k, rows * k), Image.BOX))


def _pixels(img) -> list:
	"""Les pixels d'une image, à plat, ligne par ligne.

	⚠️ `getdata()` est déprécié depuis Pillow 12 mais `get_flattened_data()` n'existe pas
	avant : le conteneur installe la dernière version au démarrage (`docker-compose.yml`) et
	rien ne l'épingle, donc les deux âges de Pillow doivent passer."""
	if hasattr(img, "get_flattened_data"):
		return list(img.get_flattened_data())
	return list(img.getdata())


def ecrire_apercu(chemin_image: str, cells, cible: str, nav=None, rapport=None):
	"""L'image d'origine, la grille proposée en voile par-dessus, et le quadrillage.

	Avec `nav` : chaque direction interdite est un trait rouge du centre de la case vers
	la voisine (l'éditeur dessine le même mur au même endroit). Avec `rapport` : les cases
	creusées par un passage cerclées de vert vif, le pourtour de l'enceinte d'orange."""
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
	rapport = rapport or {}
	for x, y in rapport.get("rempart") or []:
		dessin.rectangle([x * pas_x + 1, y * pas_y + 1, (x + 1) * pas_x - 2, (y + 1) * pas_y - 2],
			outline=(255, 150, 30, 230), width=2)
	for x, y in rapport.get("cote") or []:
		dessin.rectangle([x * pas_x + 1, y * pas_y + 1, (x + 1) * pas_x - 2, (y + 1) * pas_y - 2],
			outline=(255, 150, 30, 160), width=1)
	for x, y in rapport.get("rues") or []:
		dessin.rectangle([x * pas_x + 1, y * pas_y + 1, (x + 1) * pas_x - 2, (y + 1) * pas_y - 2],
			outline=(110, 190, 255, 230), width=2)
	for passage in rapport.get("passages") or []:
		for x, y in passage["cases"]:
			dessin.rectangle([x * pas_x + 1, y * pas_y + 1, (x + 1) * pas_x - 2, (y + 1) * pas_y - 2],
				outline=(170, 255, 60, 255), width=3)
	for cle, masque in (nav or {}).items():
		try:
			x, y = (int(v) for v in str(cle).split(","))
		except ValueError:
			continue
		cx, cy = (x + 0.5) * pas_x, (y + 0.5) * pas_y
		for bit, dx, dy, _op in grille_image.VALID_MOVES:
			if int(masque or 0) & bit:
				dessin.line([(cx, cy), (cx + dx * pas_x * 0.45, cy + dy * pas_y * 0.45)],
					fill=(230, 40, 40, 220), width=2)
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


def proposer_pour_image(chemin: str, cols: int, rows: int, doc_lieu=None, options=frozenset(),
		profil: str = "") -> dict:
	"""La grille proposée pour une image : `{cells, nav, rapport, profil, taille, peinte,
	meme_taille}`. Partagée avec `gen_villes_images.py`, qui applique ainsi EXACTEMENT la même
	passe que ce CLI (mêmes options `--sans-*`, même `--connexite`)."""
	profil = profil or grille_image.profil_de(doc_lieu)
	# ⚠️ Le `nav` du doc n'est repris que si la grille garde sa taille : sinon ses clés
	# désigneraient d'autres cases.
	peinte = (doc_lieu or {}).get("cells")
	meme_taille = bool(peinte) and len(peinte) == rows and all(len(l) == cols for l in peinte)
	nav_doc = ((doc_lieu or {}).get("nav") or {}) if meme_taille else {}
	if "--nav-vide" in options:
		nav_doc = {}

	couleurs, contours, taille = echantillonner(chemin, cols, rows)
	rues = "--sans-rues" not in options
	# Rues d'une cité, lues sur `sous_cases` du profil ; une carte de pays n'en lit pas.
	k = grille_image.sous_cases_de(profil)
	fins = (echantillonner_fins(chemin, cols, rows, k)
		if rues and grille_image.regles_de(profil).get("rues") else None)
	# Carte de pays : profils de bord (même lecture que l'endpoint), cadre décoratif à 0.
	regles = grille_image.regles_de(profil)
	bords = None
	if regles.get("cadre_enlumine"):
		from PIL import Image
		with Image.open(chemin) as img:
			img.load()
			bords = image_bords.profils_bords(img, cols, rows, int(regles.get("cadre_max_cases", 0)))
	proposition = grille_image.proposer(couleurs, contours, cols, rows, nav=nav_doc,
		profil=profil, passages="--sans-passages" not in options,
		enceinte=False if "--sans-enceinte" in options else None,
		fins=fins, k=k, rues=rues, murs_nav="--sans-nav" not in options, bords=bords)
	cells = proposition["cells"]
	if "--connexite" in options:
		cells = grille_image.garder_composante_principale(cells)
	return {"cells": cells, "nav": proposition["nav"], "rapport": proposition["rapport"],
		"profil": proposition["profil"], "taille": taille, "peinte": peinte,
		"meme_taille": meme_taille, "nav_peint": (doc_lieu or {}).get("nav") or {}}


def imprimer_resume(chemin: str, proposition: dict):
	"""Comptes par valeur, topologie (rues, enceinte, passages) et zones isolées à relier."""
	cells, taille, topo = proposition["cells"], proposition["taille"], proposition["rapport"]
	rows, cols = len(cells), len(cells[0])
	print(f"{os.path.relpath(chemin, RACINE)}  {taille[0]}×{taille[1]} px"
		f"  →  grille {cols}×{rows}  ({taille[0] / cols:.1f}×{taille[1] / rows:.1f} px/case)"
		f"  ·  profil {proposition['profil']}")
	total = cols * rows
	etiquettes = {0: "inaccessible", 1: "libre", 3: "falaise", 5: "eau (très difficile)"}
	for valeur, n in sorted(grille_image.comptes(cells).items()):
		print(f"  {valeur} {etiquettes.get(valeur, '?'):22} {n:6}  ({n * 100 / total:5.1f} %)")
	fermeture = "par nav" if topo["murs_nav"] else "par le terrain"
	if topo.get("cote") is not None:
		print(f"  {len(topo['cote'])} case(s) de côte murée(s) ·"
			f" {topo['nav_ajoutes']} bit(s) nav ajouté(s)")
		if topo.get("cadre_cases"):
			ep = topo.get("cadre") or {}
			print(f"  cadre décoratif à 0 : {topo['cadre_cases']} case(s) — "
				+ " · ".join(f"{c} {ep.get(c, 0)}" for c in grille_image.COTES_CADRE))
		for zone in topo["zones_isolees"]:
			print(f"  ⚠ zone isolée de {zone['taille']} case(s) en {zone['case']} (île)"
				" — à relier à la main si elle doit l'être")
		return
	if topo.get("cadre_cases"):
		ep = topo.get("cadre") or {}
		print(f"  cadre décoratif à 0 : {topo['cadre_cases']} case(s) — "
			+ " · ".join(f"{c} {ep.get(c, 0)}" for c in grille_image.COTES_CADRE)
			+ " (aucun passage n'y est creusé)")
	print(f"  {len(topo['rues'])} case(s) de rue ouverte(s)"
		f" (dont {topo.get('rues_dehors', 0)} hors les murs) · enceinte "
		f"{('fermée ' + fermeture) if topo['enceinte'] else 'aucune'} · {len(topo['passages'])}"
		f" passage(s) creusé(s) · {topo['poches_effacees']} case(s) de poche effacée(s)"
		f" · {topo['nav_ajoutes']} bit(s) nav ajouté(s)")
	for zone in topo["zones_isolees"]:
		print(f"  ⚠ zone isolée de {zone['taille']} case(s) en {zone['case']} — à relier à la main")


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

	profil = next((o.split("=", 1)[1] for o in options if o.startswith("--profil=")), "")
	if profil and profil not in grille_image.PROFILS_GRILLE:
		print(f"✗ profil inconnu : {profil} — {', '.join(grille_image.PROFILS_GRILLE)}")
		return 2
	proposition = proposer_pour_image(chemin, cols, rows, doc_lieu, options, profil)
	cells, nav, topo = proposition["cells"], proposition["nav"], proposition["rapport"]
	peinte, meme_taille = proposition["peinte"], proposition["meme_taille"]

	slug = (doc_lieu["_id"].split(":", 1)[1] if doc_lieu
		else os.path.splitext(os.path.basename(nom_image))[0])
	imprimer_resume(chemin, proposition)

	ecrits = []
	brut = os.path.join(DOSSIER_JSONS, f"{slug}_grille.json")
	with open(brut, "w", encoding="utf-8") as f:
		json.dump({"dimensions": {"x": cols, "y": rows}, "cells": cells, "nav": nav},
			f, ensure_ascii=False, indent=2)
		f.write("\n")
	ecrits.append(brut)

	if doc_lieu is not None and "--nav-vide" not in options:
		# ⚠️ On repart du doc RELU et on n'y touche que `cells`, `nav` et `dimensions` : le PUT
		# d'`import-bulk` est complet, toute clé absente disparaîtrait en silence. `nav` =
		# celui du doc (jamais un bit retiré) plus les murs proposés.
		sortant = dict(doc_lieu)
		sortant["cells"] = cells
		sortant["nav"] = nav
		sortant["dimensions"] = {"x": cols, "y": rows}
		a_importer = os.path.join(DOSSIER_JSONS, f"{slug}_grille_a_importer.json")
		with open(a_importer, "w", encoding="utf-8") as f:
			json.dump([sortant], f, ensure_ascii=False, indent=2)
			f.write("\n")
		ecrits.append(a_importer)

	if doc_lieu is not None:
		if meme_taille and proposition["profil"] == "pays":
			# Cells toutes à 1 des deux côtés : seule la concordance des MURS dit quelque chose.
			m = grille_image.concordance_nav(nav, proposition["nav_peint"])
			print(f"  Murs peints à la main retrouvés (à 1 case près) : {m['retrouvees']}/"
				f"{m['peintes']} cases ({m['rappel'] * 100:.1f} %) · {m['proposees']} case(s)"
				" murée(s) proposée(s)")
		elif meme_taille:
			imprimer_concordance(grille_image.concordance(cells, peinte))
		elif peinte:
			print(f"  ⚠ pas de concordance calculée : la grille en base est "
				f"{len(peinte[0])}×{len(peinte)}, la proposition {cols}×{rows}.")
		else:
			print("  (aucune grille en base : rien à quoi comparer)")

	if "--sans-apercu" not in options:
		apercu = os.path.join(DOSSIER_JSONS, f"{slug}_grille_apercu.png")
		ecrire_apercu(chemin, cells, apercu, nav, topo)
		ecrits.append(apercu)

	for f in ecrits:
		print(f"  ✎ {os.path.relpath(f, RACINE)}")
	if doc_lieu is None:
		print("  ⚠ cible sans doc : ni fichier d'import ni concordance "
			"(passer un `lieu:*` pour les obtenir).")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
