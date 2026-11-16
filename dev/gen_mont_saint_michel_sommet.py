#!/usr/bin/env python
# dev/gen_mont_saint_michel_sommet.py
# Le sommet du Mont-Saint-Michel : une carte DÉDIÉE où le géant du Mont attend qui gravit.
#
# Sur la carte de France, l'îlot du Mont est dessiné en (23,14) (cf. gen_geants_mont_saint_michel).
# Une connexion y propose « Gravir le mont » → `lieu:sommet_du_mont_saint_michel`, carte
# explorable 30 × 17 cases. Le lieu porte un bloc `combat_arrivee` (utils/combat_arrivee.py) :
# arriver par la connexion ouvre aussitôt un combat contre le Géant du Mont-Saint-Michel et ses
# comparses (`espece:geant_ou_titan`, 1 + 1 par tranche de 2 compagnons, Auteur 16/11) — sauf si
# le géant a été abattu, par n'importe quel joueur, depuis moins de 5 minutes : le sommet est
# alors vide (délai GLOBAL, doc d'état `reapparition:sommet_du_mont_saint_michel`, créé à la
# première mort, jamais importé).
#
# Grades des comparses = ceux de la zone des géants de la baie (Combattant → Champion), RELUS
# dans `gen_geants_mont_saint_michel.PLACEMENT`, jamais recopiés. Le géant du Mont reste un
# Seigneur quel que soit le profil tiré (fourchette posée sur l'espèce) : le grade ne joue que
# sur son XP.
#
# IMAGE : `templates/resources/battle_maps/mont_saint_michel_sommet.jpg` (1376 × 768, 30 × 17
# cases comme les donjons d'Orléans). `--image-provisoire` dessine une image de travail tirée
# de la grille même (sans elle, /play rendrait un 404 au premier joueur arrivé là-haut) ; à
# remplacer par l'image générée avec le prompt ci-dessous, puis recaler la grille dans
# l'éditeur. ⚠️ L'option n'écrase jamais une image existante.
#
# Prompt (docs/prompts_images.md § 0.1 et § 0.5 quater) :
#   Réalise l'image du sommet du Mont-Saint-Michel, vu du dessus, au milieu des grèves d'une
#   baie immense. Un plateau de granit gris battu des vents, couvert d'herbe rase et de
#   lichens, occupe presque toute l'image ; ses bords tombent en falaises abruptes sur le sable
#   mouillé et les filets d'eau de la marée basse, qui entourent le rocher de tous côtés. Au
#   nord-ouest, les murs effondrés d'une petite chapelle de pierre sans toit, une brèche à
#   l'est et une porte au sud. À l'est du centre, un grand foyer de pierres noircies, une
#   broche de fer posée en travers, des braises encore rouges ; tout autour, des os rongés, des
#   crânes de bœufs et d'anthropes, des armes brisées, une tunique déchirée. Quelques gros
#   blocs de granit épars. Au sud, au milieu du bord, un escalier taillé dans la roche monte de
#   la grève jusqu'au plateau. Aucun personnage, aucun animal. Illustration de fantasy
#   médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture
#   numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles.
#   Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune
#   signature, aucun filigrane. La vue est aérienne. C'est une battlemap.
#
# Usage : python dev/gen_mont_saint_michel_sommet.py [jsons/telluris-dump-….json] [--image-provisoire]
#         (sans dump : le plus récent)
# Sortie (UN seul fichier, CLAUDE.md §18) : jsons/mont_saint_michel_sommet_a_importer.json
#   lieu:sommet_du_mont_saint_michel et link:sommet_du_mont_saint_michel_to_france — deux docs
#   NEUFS (refus si l'un des `_id` existe déjà au dump : l'import est un PUT complet).

import glob
import json
import os
import random
import sys
from collections import deque

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.join(RACINE, "dev"))

import gen_geants_mont_saint_michel as geants  # noqa: E402
from utils import combat_arrivee  # noqa: E402

SORTIE = "jsons/mont_saint_michel_sommet_a_importer.json"
LIEU_ID = "lieu:sommet_du_mont_saint_michel"
LINK_ID = "link:sommet_du_mont_saint_michel_to_france"
FRANCE = "lieu:france"
MONT_FRANCE = (23, 14)          # l'îlot dessiné sur la carte de France
IMAGE = "mont_saint_michel_sommet.jpg"
IMAGE_TAILLE = (1376, 768)
COLS, ROWS = 30, 17
ARRIVEE = (15, 15)              # haut de l'escalier taillé, au sud
REAPPARITION_MIN = 5

VIDE, SOL, FALAISE = 0, 1, 3

DESCRIPTION = ("Le sommet du mont, au milieu des grèves : un plateau de granit battu des vents, "
			   "les murs effondrés d'une chapelle et un grand foyer cerné d'os rongés. "
			   "Les pêcheurs de la baie n'y montent pas.")


def grille() -> list:
	"""Terrain du sommet : plateau elliptique (1) ourlé de falaises (3), mer et grèves autour
	(0) ; escalier au sud ; murs de la chapelle (0) au nord-ouest, porte au sud et brèche à
	l'est ; foyer et blocs de granit (0)."""
	cx, cy, rx, ry = 14.5, 8.0, 13.6, 7.4
	cells = []
	for y in range(ROWS):
		ligne = []
		for x in range(COLS):
			d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
			ligne.append(SOL if d <= 1.0 else (FALAISE if d <= 1.25 else VIDE))
		cells.append(ligne)
	for y in range(13, ROWS):                       # escalier depuis la grève
		for x in (14, 15):
			cells[y][x] = SOL
	for x, y in obstacles():
		cells[y][x] = VIDE
	return cells


FOYER = ((18, 7), (19, 7))
BLOCS = ((22, 4), (24, 11), (9, 11), (26, 8))


def murs_chapelle() -> list:
	"""Pourtour de la chapelle (4,3)-(10,7), porte au sud (7,7) et brèche à l'est (10,5)."""
	x0, y0, x1, y1 = 4, 3, 10, 7
	tour = {(x, y) for x in range(x0, x1 + 1) for y in (y0, y1)}
	tour |= {(x, y) for y in range(y0, y1 + 1) for x in (x0, x1)}
	return sorted(tour - {(7, y1), (x1, 5)})


def obstacles() -> list:
	return murs_chapelle() + list(FOYER) + list(BLOCS)


def joignables(cells, depart) -> set:
	"""Cases à 1 joignables depuis `depart` en 8 directions (sans `nav` : aucun mur fin)."""
	vus, file = {depart}, deque([depart])
	while file:
		x, y = file.popleft()
		for dx in (-1, 0, 1):
			for dy in (-1, 0, 1):
				n = (x + dx, y + dy)
				if (0 <= n[0] < COLS and 0 <= n[1] < ROWS and n not in vus
						and cells[n[1]][n[0]] == SOL):
					vus.add(n)
					file.append(n)
	return vus


def lieu_doc(cells) -> dict:
	return {
		"_id": LIEU_ID,
		"type": "lieu",
		"label": "Sommet du Mont-Saint-Michel",
		"description": DESCRIPTION,
		"image": IMAGE,
		"categorie": "chemin",
		"lieu_parent": FRANCE,
		"dimensions": {"x": COLS, "y": ROWS},
		"cells": cells,
		"nav": {},
		"tags": ["mont", "rocher", "ruines", "bord_de_mer"],
		combat_arrivee.CHAMP: {
			"espece": geants.GEANT_DU_MONT,
			"accompagnants": [geants.GEANT],
			"nb_accompagnants": 1,
			"reapparition_min": REAPPARITION_MIN,
			"profil_weights": dict(geants.PLACEMENT["profil_weights"]),
		},
	}


def link_doc() -> dict:
	# Le libellé d'un nœud est celui du bouton qui MÈNE à ce nœud (`get_lieu_links`).
	return {
		"_id": LINK_ID,
		"type": "connection",
		"nodes": [
			{"lieu": FRANCE, "pos": list(MONT_FRANCE), "label": "Redescendre vers la baie"},
			{"lieu": LIEU_ID, "pos": list(ARRIVEE), "label": "Gravir le mont"},
		],
		"metadata": {"type": "chemin", "status": "ouvert"},
	}


def verifier(docs: dict, cells) -> None:
	for _id in (LIEU_ID, LINK_ID):
		if _id in docs:
			sys.exit(f"{_id} existe déjà au dump : PUT complet, refus d'écraser.")
	for _id in (geants.GEANT_DU_MONT, geants.GEANT, *geants.PLACEMENT["profil_weights"]):
		if _id not in docs:
			sys.exit(f"{_id} absent du dump.")
	france = docs.get(FRANCE) or {}
	x, y = MONT_FRANCE
	if (france.get("cells") or [[]] * (y + 1))[y][x] != SOL:
		sys.exit(f"{FRANCE} ({x},{y}) n'est pas une case praticable.")
	ax, ay = ARRIVEE
	if cells[ay][ax] != SOL:
		sys.exit("La case d'arrivée n'est pas praticable.")
	tout_sol = {(x, y) for y in range(ROWS) for x in range(COLS) if cells[y][x] == SOL}
	if joignables(cells, ARRIVEE) != tout_sol:
		sys.exit("Le plateau n'est pas d'un seul tenant depuis l'arrivée.")
	if combat_arrivee.spec(lieu_doc(cells)) is None:
		sys.exit("Bloc combat_arrivee illisible.")


def image_provisoire(cells, chemin: str) -> None:
	"""Image de TRAVAIL tirée de la grille (à remplacer par l'image du prompt)."""
	from PIL import Image, ImageDraw, ImageFilter
	rnd = random.Random(1408)
	w, h = IMAGE_TAILLE
	cw, ch = w / COLS, h / ROWS
	img = Image.new("RGB", (w, h), (168, 150, 112))
	dr = ImageDraw.Draw(img)
	# grève et filets d'eau
	for _ in range(900):
		x, y = rnd.uniform(0, w), rnd.uniform(0, h)
		dr.ellipse([x, y, x + rnd.uniform(20, 90), y + rnd.uniform(4, 14)],
				   fill=(rnd.randint(70, 95), rnd.randint(110, 130), rnd.randint(130, 150)))
	for y in range(ROWS):
		for x in range(COLS):
			v = cells[y][x]
			box = [x * cw, y * ch, (x + 1) * cw, (y + 1) * ch]
			if v == FALAISE:
				g = rnd.randint(95, 120)
				dr.rectangle(box, fill=(g, g - 4, g - 12))
			elif v == SOL:
				dr.rectangle(box, fill=(rnd.randint(110, 125), rnd.randint(118, 132), rnd.randint(82, 95)))
	img = img.filter(ImageFilter.GaussianBlur(6))
	dr = ImageDraw.Draw(img)
	for _ in range(500):                            # lichens et cailloux
		x, y = rnd.randrange(COLS), rnd.randrange(ROWS)
		if cells[y][x] == SOL:
			px, py = (x + rnd.random()) * cw, (y + rnd.random()) * ch
			r = rnd.uniform(2, 6)
			c = rnd.choice([(150, 148, 135), (92, 98, 70), (175, 170, 120)])
			dr.ellipse([px - r, py - r, px + r, py + r], fill=c)
	for x, y in obstacles():                        # murs, blocs, foyer
		box = [x * cw + 2, y * ch + 2, (x + 1) * cw - 2, (y + 1) * ch - 2]
		if (x, y) in FOYER:
			dr.rectangle(box, fill=(55, 45, 38))
			dr.ellipse([box[0] + 8, box[1] + 8, box[2] - 8, box[3] - 8], fill=(214, 96, 34))
		else:
			dr.rectangle(box, fill=(128, 126, 118), outline=(70, 68, 62), width=3)
	dr.line([18 * cw, 7.5 * ch, 20 * cw, 7.5 * ch], fill=(40, 40, 44), width=5)  # broche
	for _ in range(40):                             # os autour du foyer
		px, py = rnd.uniform(16, 22) * cw, rnd.uniform(5.5, 9.5) * ch
		dr.line([px, py, px + rnd.uniform(-14, 14), py + rnd.uniform(-8, 8)],
				fill=(225, 218, 196), width=3)
	for i in range(4):                              # marches
		y = (13 + i) * ch + ch / 2
		dr.line([14 * cw + 4, y, 16 * cw - 4, y], fill=(80, 76, 70), width=3)
	for x in range(COLS + 1):                       # quadrillage discret
		dr.line([x * cw, 0, x * cw, h], fill=(60, 60, 60), width=1)
	for y in range(ROWS + 1):
		dr.line([0, y * ch, w, y * ch], fill=(60, 60, 60), width=1)
	img.save(chemin, quality=90)


def main(argv):
	args = [a for a in argv[1:] if not a.startswith("--")]
	dump = args[0] if args else sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))[-1]
	docs = geants.charger(dump)
	cells = grille()
	verifier(docs, cells)
	sortie = [lieu_doc(cells), link_doc()]
	with open(os.path.join(RACINE, SORTIE), "w", encoding="utf-8", newline="\n") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=1)
	print(f"{SORTIE} : {len(sortie)} docs (dump {os.path.basename(dump)})")
	if "--image-provisoire" in argv:
		chemin = os.path.join(RACINE, "templates", "resources", "battle_maps", IMAGE)
		if os.path.exists(chemin):
			print(f"{IMAGE} existe déjà : non écrasée.")
		else:
			image_provisoire(cells, chemin)
			print(f"image provisoire : {chemin}")


if __name__ == "__main__":
	main(sys.argv)
