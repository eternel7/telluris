#!/usr/bin/env python
# dev/gen_monstres_madagascar.py
# Bestiaire de Madagascar (demande du 24/11/2026) : six créatures des traditions malgaches.
#   - 5 espèces placées en zone, région `afrique` (Madagascar y est rangée) : kalanoro, fanany,
#     songomby, lalomena, tokantongotra ;
#   - 1 être unique, boss au bestiaire seul : trimobe (l'ogre des contes, « Itrimobe »).
# Choix de l'utilisateur (questionnaire du 24/11) : rencontres en `@A` (toute carte subsaharienne,
# l'île comprise), le Fanany en espèce (le mythe le fait naître du corps d'un noble défunt : il y en
# a plusieurs), Trimobe en boss non placé, kalanoro rare et fuyant (deux zones, comme qilin et baku).
#
# MÊME MOTEUR que dev/gen_monstres_legendes.py (globales remplacées par `installer()`), lignes
# ajoutées aux tables exhaustives (`gen_jetons_especes`, `gen_genres_especes`,
# `gen_capacites_monstres`) : elles échouent tant que l'import n'est pas fait et qu'un dump FRAIS ne
# l'a pas relu. Aucun humanoïde dans le lot : aucune ligne dans `gen_equipement_humanoides`.
#
# Usage : python dev/gen_monstres_madagascar.py [--dump jsons/telluris-dump-….json] [--prompts]
# Sortie : jsons/monstres_madagascar_a_importer.json

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_monstres_legendes as moteur  # noqa: E402
from gen_vampires import _attrs  # noqa: E402

SORTIE = os.path.join(moteur.RACINE, "jsons", "monstres_madagascar_a_importer.json")

# Même forme que gen_monstres_legendes.NOUVELLES ; _attrs = V, F, R, Ag, Vol, Int, Cha, Ch.
NOUVELLES = {
	"kalanoro": {
		"nom": "Kalanoro",
		"description": "Petit être des forêts et des grottes, pas plus haut qu'un enfant, velu, à la "
					   "longue chevelure et aux ongles crochus, dont les pieds sont tournés vers "
					   "l'arrière : qui suit ses traces s'éloigne de lui. On dit qu'il enlève les enfants "
					   "égarés pour les rendre des jours plus tard, changés, et que certains guérisseurs "
					   "tiennent de lui leur savoir. Il fuit dès qu'on le voit ; s'il cherche quelque "
					   "chose parmi les Anthropes, aucun récit ne s'accorde sur quoi.",
		"base_attributes": _attrs((7, 7), (15, 25), (20, 30), (55, 70), (50, 65), (40, 55), (20, 35), (50, 70)),
		"tags": ["monstre", "feerique", "furtif", "foret", "magique"],
		"butin": ("carcasse", [15, 25], "rare"),
		"son": "gobelin",
		"visuel": "petit être sauvage de la taille d'un enfant, accroupi, corps maigre et noueux couvert "
				  "d'un pelage brun roux, très longue chevelure et longue barbe hirsutes, longs doigts aux "
				  "ongles crochus, pieds nettement tournés vers l'arrière, yeux brillants et méfiants, "
				  "quelques feuilles et brindilles accrochées au pelage",
		"fond": "magenta",
	},
	"fanany": {
		"nom": "Fanany",
		"description": "Serpent monstrueux à sept têtes cornues, qui hante les marais, les lacs et les "
					   "eaux lentes. Les gens des hautes terres disent qu'il naît du corps d'un noble "
					   "défunt, et que les grands ancêtres reviennent ainsi veiller sur leurs terres ; "
					   "d'autres jurent qu'il ne garde que sa faim. Chaque tête a sa volonté, et toutes "
					   "mordent ensemble.",
		"base_attributes": _attrs((6, 7), (65, 90), (60, 85), (25, 40), (60, 80), (25, 40), (0, 0), (35, 55)),
		"tags": ["monstre", "reptile", "venin", "aquatique", "terreur"],
		"butin": ("carcasse", [700, 1000], "rare"),
		"son": "dragon",
		"visuel": "serpent colossal à sept têtes cornues sur sept longs cous dressés en éventail, "
				  "écailles vert sombre et or, cornes recourbées jaune pâle, gueules rouges ouvertes sur "
				  "des crochets et des langues fourchues, corps massif lové en anneaux luisants, "
				  "eau ruisselant de ses écailles",
		"fond": "magenta",
	},
	"songomby": {
		"nom": "Songomby",
		"description": "Bête grande comme un bœuf, couverte d'un pelage hirsute rayé de fauve, aux cornes "
					   "épaisses, qui court plus vite qu'aucun cheval. Les récits du sud en font un "
					   "mangeur d'hommes qui charge sans prévenir ; ceux du nord, une bête qui ne tue que "
					   "ceux qui la chassent. Personne n'a jamais su lequel des deux il croisait avant "
					   "d'entendre le sol trembler.",
		"base_attributes": _attrs((10, 12), (55, 75), (50, 70), (40, 55), (40, 55), (10, 20), (0, 0), (20, 35)),
		"tags": ["monstre", "bestial", "predateur", "rapide"],
		"butin": ("carcasse", [450, 650], "peu_commun"),
		"son": "bete",
		"visuel": "bête massive de la taille d'un bœuf, pelage long et hirsute brun fauve rayé de noir, "
				  "épaisse crinière, deux grosses cornes recourbées vers l'avant, gueule de fauve ouverte "
				  "sur des crocs, sabots fendus, longue queue touffue ; elle charge en pleine course, "
				  "projetant de la terre",
		"fond": "bleu vif",
	},
	"lalomena": {
		"nom": "Lalomena",
		"description": "Bête des eaux au corps de bœuf lourd, à la peau grise et nue, aux cornes d'un rouge "
					   "vif. Elle passe le jour immergée dans les lacs et les rivières lentes, où seuls "
					   "ses naseaux affleurent, et en sort pour renverser les pirogues ou écraser qui "
					   "trouble son eau. Les conteurs disent qu'elle est rare, et que la voir porte "
					   "bonheur ou malheur, selon celui qui raconte.",
		"base_attributes": _attrs((5, 6), (60, 80), (60, 85), (20, 35), (45, 60), (10, 20), (0, 0), (25, 40)),
		"tags": ["monstre", "aquatique", "bestial"],
		"butin": ("carcasse", [600, 900], "rare"),
		"son": "bete",
		"visuel": "grand animal aquatique au corps massif d'hippopotame et à la tête de taureau, peau "
				  "grise épaisse et nue, deux longues cornes d'un rouge éclatant, petites oreilles, "
				  "naseaux larges, il émerge à mi-corps de l'eau, des cascades d'eau ruisselant de son "
				  "dos et de son mufle, quelques nénuphars accrochés",
		"fond": "magenta",
	},
	"tokantongotra": {
		"nom": "Tokantongotra",
		"description": "Créature blanche et décharnée aux membres trop longs, qui se déplace sur une jambe "
					   "autant que sur quatre et va plus vite qu'on ne court. On ne la voit que la nuit, "
					   "en lisière des forêts et des fourrés, et son cri suffit à vider un village. Son nom "
					   "dit « celle d'un seul pied » ; les récits ne s'accordent ni sur sa forme, ni sur "
					   "ce qu'elle chasse.",
		"base_attributes": _attrs((9, 11), (35, 50), (25, 40), (55, 70), (40, 55), (15, 30), (0, 0), (30, 45)),
		"tags": ["monstre", "nocturne", "rapide", "predateur", "furtif"],
		"butin": ("carcasse", [40, 70], "peu_commun"),
		"son": "loup",
		"visuel": "créature décharnée au pelage blanc sale, membres démesurément longs et anguleux aux "
				  "articulations inversées, une patte arrière bien plus longue que l'autre, mains et "
				  "pieds osseux aux doigts griffus, tête de primate aux yeux rouges, oreilles pointues "
				  "et gueule hurlante pleine de crocs ; posture rampante prête à bondir",
		"fond": "bleu vif",
	},
	# ── Être unique : boss au bestiaire seul ──
	"trimobe": {
		"nom": "Trimobe",
		"description": "L'ogre des contes, géant mangeur d'hommes que les veillées appellent Itrimobe. Il "
					   "vit seul dans les rochers, au-dessus d'une forêt, et les récits lui prêtent une "
					   "longue queue, une faim que rien n'apaise et une ruse plus courte que sa force. Les "
					   "contes veulent que des enfants l'aient trompé et vaincu ; on montre pourtant "
					   "encore les rochers où il dort.",
		"base_attributes": _attrs((6, 7), (100, 135), (95, 130), (20, 35), (70, 95), (15, 30), (0, 10), (40, 65)),
		"tags": ["monstre", "geant", "terreur", "legendaire", "boss"],
		"butin": ("carcasse", [900, 1300], "rare"),
		"son": "geant",
		"visuel": "géant colossal à la peau brun cuivré, musculature énorme, longue chevelure et barbe "
				  "hirsutes en mèches épaisses, collier de grosses perles de bois et de dents, pagne de "
				  "fibres végétales et de feuilles, cordes de raphia nouées autour du torse, une longue "
				  "queue épaisse, mains immenses aux doigts crochus tendues en avant, bouche ouverte sur "
				  "un rugissement ; il se penche en avant, menaçant",
		"fond": "magenta",
	},
}

# « zone@CODES » (codes de gen_monstres_legendes.REG). Le boss n'y figure pas.
ZONES = {
	# Rare et fuyant : deux zones (choix de l'utilisateur, comme qilin et baku).
	"kalanoro": ["foret_equatoriale@A", "grotte@A"],
	"fanany": ["marecage_tropical@A", "lac@A", "foret_galerie@A"],
	"songomby": ["savane@A", "plateau@A", "fourre_epineux@A"],
	"lalomena": ["lac@A", "riviere@A", "fleuve_tropical@A"],
	"tokantongotra": ["foret_equatoriale@A", "foret_tropicale_seche@A", "fourre_epineux@A"],
}


def installer(setattr_fn=setattr) -> None:
	"""Branche ce lot sur le moteur de gen_monstres_legendes (globales lues par ses fonctions).
	Les tests passent `monkeypatch.setattr` pour que le branchement soit défait après eux."""
	setattr_fn(moteur, "NOUVELLES", NOUVELLES)
	setattr_fn(moteur, "ZONES", ZONES)
	setattr_fn(moteur, "DONJONS", {})
	setattr_fn(moteur, "REGIONS_NEUVES", {})  # afrique existe déjà en base
	setattr_fn(moteur, "SORTIE", SORTIE)


if __name__ == "__main__":
	installer()
	moteur.main()
