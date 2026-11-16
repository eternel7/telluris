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
# IMAGE : `templates/resources/battle_maps/mont_saint_michel_sommet.jpg` (1408 × 768, Auteur
# 16/11, vue trois-quarts) ; grille 30 × 17 RELEVÉE À L'ŒIL sur cette image (`PLATEAU`, rangée par
# rangée, moins `obstacles()`) : plateau d'herbe et de granit praticable, chapelle, foyer et
# rochers bloquants, escalier taillé en diagonale (de la grève (13,15) au plateau (16,11)).
# L'arrivée est EN HAUT de l'escalier : le combat se joue sur le plateau, pas dans un goulot de
# deux cases que les grands jetons (géants 4 × 3) ne franchissent pas.
#
# Prompt d'origine (docs/prompts_images.md § 0.1 et § 0.5 quater) :
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
# Usage : python dev/gen_mont_saint_michel_sommet.py [jsons/telluris-dump-….json]
#         (sans dump : le plus récent)
# Sortie (UN seul fichier, CLAUDE.md §18) : jsons/mont_saint_michel_sommet_a_importer.json
#   lieu:sommet_du_mont_saint_michel et link:sommet_du_mont_saint_michel_to_france — deux docs
#   NEUFS (refus si l'un des `_id` existe déjà au dump : l'import est un PUT complet).

import glob
import json
import os
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
IMAGE_TAILLE = (1408, 768)
COLS, ROWS = 30, 17
ARRIVEE = (15, 11)              # haut de l'escalier taillé, au sud
REAPPARITION_MIN = 5

VIDE, SOL = 0, 1

DESCRIPTION = ("Le sommet du mont, au milieu des grèves : un plateau de granit battu des vents, "
			   "les murs effondrés d'une chapelle et un grand foyer cerné d'os rongés. "
			   "Les pêcheurs de la baie n'y montent pas.")


# Cases praticables de chaque rangée, intervalles INCLUS (relevé sur l'image).
PLATEAU = {
	3: [(13, 20)],
	4: [(12, 20), (25, 25)],
	5: [(12, 22), (25, 25)],
	6: [(12, 25)],
	7: [(6, 25)],
	8: [(6, 25)],
	9: [(6, 25)],
	10: [(6, 25)],
	11: [(7, 24)],
	12: [(15, 16)],          # escalier taillé, de haut en bas vers le sud-ouest
	13: [(15, 16)],
	14: [(14, 15)],
	15: [(13, 14)],
}
FOYER = ((19, 6), (20, 6), (21, 6), (19, 7), (20, 7), (21, 7))
ROCHERS = ((19, 4), (15, 7), (8, 9), (9, 9), (19, 10), (20, 10), (19, 11), (20, 11))


def obstacles() -> list:
	"""Cases du plateau rendues infranchissables : foyer à broche, rochers. La chapelle (6-11,
	1-6) est HORS du plateau relevé : ses murs et son intérieur restent à 0."""
	return list(FOYER) + list(ROCHERS)


def grille() -> list:
	"""Terrain du sommet : 1 sur le plateau et l'escalier, 0 ailleurs (falaises, grèves,
	chapelle, foyer, rochers)."""
	cells = [[VIDE] * COLS for _ in range(ROWS)]
	for y, spans in PLATEAU.items():
		for x0, x1 in spans:
			for x in range(x0, x1 + 1):
				cells[y][x] = SOL
	for x, y in obstacles():
		cells[y][x] = VIDE
	return cells


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
	from PIL import Image
	chemin = os.path.join(RACINE, "templates", "resources", "battle_maps", IMAGE)
	if not os.path.exists(chemin):
		sys.exit(f"{IMAGE} absente : /play rendrait un 404 au sommet.")
	with Image.open(chemin) as img:
		if img.size != IMAGE_TAILLE:
			sys.exit(f"{IMAGE} fait {img.size}, la grille est relevée sur {IMAGE_TAILLE}.")


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


if __name__ == "__main__":
	main(sys.argv)
