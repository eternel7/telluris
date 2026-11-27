#!/usr/bin/env python
# dev/gen_monstres_mu.py
# Bestiaire des quêtes de Mu (demande du 26/11/2026) — docs/lore/cites/20261124_de_mu_aux_mondes_divins.md :
#   - Naga : les fils de Kadru venus par les océans, qui forcent les grilles des conduites de la lisière
#     pour atteindre celle qu'ils tiennent pour une mère (« Les eaux troubles de Mu ») ;
#   - murène géante : la bête des failles de la paroi, attirée par les coups contre le sas des
#     jardiniers (« Un service qui ne peut attendre ») ;
#   - Échidna : être unique, la mère des serpents, sous Mu-la-Centrale (« Le serpent sous la cité »).
#     Immortelle : vaincue, elle FUIT. Son butin n'est donc pas une dépouille mais la MUE qu'elle
#     laisse derrière elle (`_mue`).
# Aucune n'est placée en zone : on ne les croise que dans les salles des quêtes (dev/gen_quetes_de_mu.py).
#
# MÊME MOTEUR que dev/gen_monstres_legendes.py (globales remplacées par `installer()`), lignes
# ajoutées aux tables exhaustives (`gen_jetons_especes`, `gen_genres_especes`, `gen_capacites_monstres`).
# Ce module n'écrit RIEN lui-même : `gen_quetes_de_mu.py` reprend ses docs dans LE fichier à
# importer de la demande (CLAUDE.md §18). `--prompts` ajoute les prompts d'image au lot Gemini.
#
# Usage : python dev/gen_monstres_mu.py --prompts

import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_monstres_legendes as moteur  # noqa: E402
from gen_vampires import _attrs  # noqa: E402

# Même forme que gen_monstres_legendes.NOUVELLES ; _attrs = V, F, R, Ag, Vol, Int, Cha, Ch.
NOUVELLES = {
	"naga": {
		"nom": "Naga",
		"description": "Être des grands fonds au buste d'Anthrope et au long corps de serpent, couvert "
					   "d'écailles vert d'eau et coiffé d'un capuchon dressé. Les récits des Retours en "
					   "font les fils de Kadru, la mère des serpents des mers d'Orient, venus par les "
					   "océans. Ils parlent peu, et rarement aux Anthropes. Ceux qui rôdent autour de "
					   "Mu ne cherchent pas ses habitants : ils cherchent un chemin vers le dessous de "
					   "la cité.",
		"base_attributes": _attrs((5, 7), (45, 65), (40, 60), (40, 55), (40, 55), (30, 45), (15, 30), (30, 45)),
		"tags": ["monstre", "reptile", "aquatique", "hybride", "magique"],
		"butin": ("carcasse", [40, 60], "peu_commun"),
		"son": None,
		"visuel": "être hybride au buste d'homme élancé et musclé, peau vert d'eau, et au long corps de "
				  "serpent lové sous lui, écailles vert sombre et nacre, capuchon de cobra déployé derrière "
				  "la tête, yeux dorés à pupille fendue, une lance de corail à la main, bracelets de perles, "
				  "eau ruisselant de ses écailles",
		"fond": "magenta",
	},
	"murene_geante": {
		"nom": "Murène géante",
		"description": "Murène longue comme une barque, à la peau marbrée de brun et d'or, qui vit dans "
					   "les failles de la roche contre la paroi de la bulle. Elle ne sort qu'au bruit : "
					   "un coup contre la pierre, un outil qui tombe. Les jardiniers de la lisière "
					   "savent qu'il faut travailler en silence, et qu'elle a la mémoire longue. Elle ne "
					   "craint pas l'air : comme les murènes des récifs qui chassent le crabe sur les "
					   "rochers découverts, elle quitte l'eau et rampe sur la pierre mouillée pour "
					   "atteindre ce qui l'a dérangée.",
		"base_attributes": _attrs((5, 6), (50, 70), (40, 60), (35, 50), (25, 40), (3, 8), (0, 0), (20, 35)),
		"tags": ["animal", "aquatique", "predateur"],
		"butin": ("carcasse", [60, 90], "peu_commun"),
		"son": None,
		"visuel": "murène colossale au corps serpentin épais, peau lisse marbrée de brun sombre et d'or, "
				  "longue nageoire dorsale ondulante, tête massive à la gueule entrouverte sur deux "
				  "rangées de dents en aiguille, petits yeux ronds et froids, peau ruisselante, elle rampe "
				  "hors de l'eau, le corps à demi enroulé, dressant la tête",
		"fond": "magenta",
	},
	# ── Être unique : la mère des serpents ──
	"echidna": {
		"nom": "Échidna",
		"description": "La mère des serpents. Femme au buste d'une beauté grave et au corps de serpent "
					   "immense, que les Hellènes disaient mère de l'Hydre, du lion de Némée, d'Orthos et "
					   "de Cerbère. Elle vit sous Mu-la-Centrale, près de la porte que la cité a fermée. "
					   "Elle accuse les dieux, tient à ses enfants, et prévient avant de frapper. Elle ne "
					   "meurt pas : vaincue, elle s'enfuit.",
		"base_attributes": _attrs((6, 7), (85, 115), (80, 110), (30, 45), (80, 100), (50, 70), (40, 60), (50, 70)),
		"tags": ["monstre", "reptile", "legendaire", "unique", "boss", "terreur"],
		"butin": ("ossements", [20, 30], "rare"),
		"son": None,
		"visuel": "femme colossale au buste d'une beauté grave et sévère, longue chevelure noire mêlée "
				  "d'algues, diadème de corail et de nacre, regard sombre et digne, prolongée à la taille "
				  "par un immense corps de serpent aux écailles bleu nuit et or lové en anneaux puissants, "
				  "mains ouvertes en avant comme pour avertir",
		"fond": "magenta",
	},
}


def _mue(doc: dict) -> dict:
	"""Échidna ne meurt pas : son butin est la MUE qu'elle laisse en fuyant, pas des ossements."""
	doc = copy.deepcopy(doc)
	doc.update({
		"nom": "Mue d'Échidna",
		"icon": "🐍",
		"sous_categorie": "mue",
		"description": "Ce qu'Échidna laisse derrière elle en fuyant : une mue entière, longue comme une "
					   "nef, encore tiède, aux écailles bleu nuit et or. Elle, nul ne l'a retrouvée.",
	})
	return doc


def installer(setattr_fn=setattr) -> None:
	"""Branche ce lot sur le moteur de gen_monstres_legendes (globales lues par ses fonctions)."""
	setattr_fn(moteur, "NOUVELLES", NOUVELLES)
	setattr_fn(moteur, "ZONES", {})
	setattr_fn(moteur, "DONJONS", {})
	setattr_fn(moteur, "REGIONS_NEUVES", {})


def docs_monstres(base: dict, rangs_fn=None) -> list:
	"""Docs neufs ou à jour (espèces, butins, compétences de monstre manquantes), d'après le dump
	`base` ({_id: doc}). `rules:regions` (inchangé ici) n'est jamais réémis."""
	# Branchement DÉFAIT après usage : gen_quetes_de_mu est importé par des tests, et les globales du
	# moteur ne doivent pas rester celles de ce lot pour les autres (test_gen_monstres_legendes).
	globales = ("NOUVELLES", "ZONES", "DONJONS", "REGIONS_NEUVES")
	avant = {g: getattr(moteur, g) for g in globales}
	installer()
	try:
		docs, _deja = moteur.docs_monstres(base, rangs_fn)
	finally:
		for g, v in avant.items():
			setattr(moteur, g, v)
	out = []
	for d in docs:
		if d.get("_id") == "rules:regions":
			continue
		out.append(_mue(d) if d.get("_id") == "item:echidna" else d)
	return out


if __name__ == "__main__":
	installer()
	if "--prompts" in sys.argv:
		print(f"{moteur.ecrire_prompts()} prompt(s) ajouté(s) à {os.path.relpath(moteur.PROMPTS, moteur.RACINE)}")
	else:
		for slug in NOUVELLES:
			print(moteur.prompt_de(slug), end="\n\n")
