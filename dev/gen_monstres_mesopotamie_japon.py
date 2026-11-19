#!/usr/bin/env python
# dev/gen_monstres_mesopotamie_japon.py
# Bestiaire de Mésopotamie et du Japon (demande du 19/11/2026, deux planches d'images) :
#   - 10 espèces `espece:*` neuves — Mušḫuššu, Kappa et Tengu existent déjà et ne sont pas touchés :
#       Mésopotamie : lamassu, pazuzu, lamashtu, ugallu, homme_scorpion ;
#       Japon       : kitsune (une à trois queues), kyubi (neuf queues, boss), oni, nue, tanuki ;
#   - un butin par défaut par espèce et la découpe des grosses carcasses (comme gen_monstres_legendes) ;
#   - les défauts de rencontre des zones par biome : région `afrique_du_nord` (Levant compris) pour la
#     Mésopotamie, faute de région ou de carte propre ; région DORMANTE `asie` pour le Japon, comme Kappa
#     et Tengu (rien n'y apparaît avant qu'une carte de pays y soit rattachée).
# Choix de l'utilisateur : gardiens (lamassu, ugallu, homme-scorpion) HOSTILES, IA d'embuscade qui
# tient le seuil ; Pazuzu et Lamashtu en espèces GÉNÉRIQUES (pas d'être unique) ; kitsune et tanuki
# en monstres rusés, kitsune décliné par queues ; le Kyūbi, boss, reste au bestiaire seul (même règle
# que les boss de gen_monstres_legendes). Lamashtu ne porte pas le tag `demon` : il est interdit en zone
# (gen_defauts_zones_biomes.TAGS_INTERDITS) et elle doit y être placée.
#
# MÊME MOTEUR que dev/gen_monstres_legendes.py : ses fonctions lisent les globales du module
# (`NOUVELLES`, `ZONES`, `DONJONS`, `REGIONS_NEUVES`), remplacées ici avant l'appel. Les tables
# exhaustives (`gen_jetons_especes`, `gen_genres_especes`, `gen_equipement_humanoides`,
# `gen_capacites_monstres`) citent déjà les espèces neuves : elles échouent tant que l'import n'est pas
# fait et qu'un dump FRAIS ne l'a pas relu.
#
# Usage : python dev/gen_monstres_mesopotamie_japon.py [--dump jsons/telluris-dump-….json] [--prompts]
# Sortie : jsons/monstres_mesopotamie_japon_a_importer.json

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_monstres_legendes as moteur  # noqa: E402
from gen_vampires import _attrs  # noqa: E402

SORTIE = os.path.join(moteur.RACINE, "jsons", "monstres_mesopotamie_japon_a_importer.json")

# Même forme que gen_monstres_legendes.NOUVELLES (butin, son, visuel, fond).
NOUVELLES = {
	# ── Mésopotamie ──
	"lamassu": {
		"nom": "Lamassu",
		"description": "Gardien au corps de taureau, aux ailes d'aigle et à la tête d'homme barbu coiffée "
					   "d'une tiare à cornes. Les rois d'Assur et de Babylone en sculptaient aux portes de "
					   "leurs palais, et l'on dit que certains se sont éveillés dans la pierre. Il n'a rien "
					   "de malfaisant : il garde un seuil, et quiconque le force sans y être convié le "
					   "trouve en travers de sa route. Nul ne sait plus qui les a postés devant les ruines "
					   "qu'ils gardent encore.",
		"base_attributes": _attrs((7, 7), (55, 75), (60, 80), (25, 40), (50, 70), (45, 60), (30, 50), (10, 25)),
		"tags": ["monstre", "hybride", "gardien", "vol", "magique"],
		"butin": ("carcasse", [600, 900], "rare"),
		"son": "bete",
		"visuel": "taureau ailé colossal à tête d'homme barbu, barbe et cheveux tressés en boucles "
				  "régulières, tiare cylindrique ornée de cornes, grandes ailes d'aigle aux plumes dorées et "
				  "bleu lapis repliées le long du corps, pelage doré, sabots massifs ; posture de garde, "
				  "regard calme et sévère",
		"fond": "magenta",
	},
	"pazuzu": {
		"nom": "Pazuzu",
		"description": "Esprit des vents brûlants du désert, à face de lion grimaçante, aux quatre ailes, "
					   "aux serres d'aigle et à la queue de scorpion. Il apporte les sauterelles et la "
					   "fièvre avec le vent d'ouest. Pourtant les mères de Babylone pendent son effigie au "
					   "berceau, car Lamashtu le craint : on ne sait s'il protège ou s'il chasse seulement "
					   "sur le même terrain.",
		"base_attributes": _attrs((8, 8), (40, 55), (35, 50), (45, 60), (45, 65), (30, 45), (0, 0), (20, 35)),
		"tags": ["esprit", "hybride", "vol", "magique", "terreur"],
		"butin": ("carcasse", [120, 200], "peu_commun"),
		"son": "bete",
		"visuel": "créature décharnée à tête de lion grimaçante et crinière hérissée, deux paires d'ailes "
				  "d'aigle brun sombre déployées, corps humain musculeux et sec à la peau tannée, serres "
				  "d'aigle aux pieds et aux mains, longue queue de scorpion recourbée, pagne rouge à "
				  "franges ; il plane dans un tourbillon de sable",
		"fond": "bleu vif",
	},
	"lamashtu": {
		"nom": "Lamashtu",
		"description": "Démone à tête de lionne, aux oreilles d'âne et aux serres d'oiseau, qui tient un "
					   "serpent dans chaque main. Elle rôde autour des maisons et des palmeraies, apportant "
					   "fièvres et cauchemars aux mères et aux nouveau-nés. Les récits la disent fille "
					   "d'Anu, chassée du ciel pour sa cruauté ; d'autres jurent qu'elles sont plusieurs, "
					   "et que l'effigie de Pazuzu seule les tient à distance.",
		"base_attributes": _attrs((7, 7), (40, 55), (40, 55), (40, 55), (50, 70), (35, 50), (10, 25), (15, 30)),
		"tags": ["monstre", "hybride", "vol", "nocturne", "maladie", "terreur"],
		"butin": ("carcasse", [60, 90], "rare"),
		"son": "bete",
		"visuel": "créature féminine ailée à tête de lionne rugissante, longues oreilles d'âne dressées, "
				  "longue chevelure noire, corps décharné à la peau fauve, serres d'oiseau aux pieds, un "
				  "serpent vert vivant dressé dans chaque main, pagne rouge déchiré, bijoux d'or ternis",
		"fond": "bleu vif",
	},
	"ugallu": {
		"nom": "Ugallu",
		"description": "Gardien à tête de lion sur un corps d'homme, aux pieds d'oiseau, la dague levée et "
					   "la masse au poing. Les sceaux et les bas-reliefs le montrent aux portes des "
					   "sanctuaires, chassant les esprits mauvais. Ceux qui gardent encore les temples "
					   "abandonnés n'en distinguent plus les visiteurs, et frappent quiconque passe le seuil.",
		"base_attributes": _attrs((6, 6), (50, 70), (45, 65), (40, 55), (45, 60), (25, 40), (5, 20), (15, 30)),
		"tags": ["monstre", "hybride", "gardien", "guerrier", "humanoide"],
		"butin": ("carcasse", [110, 160], "peu_commun"),
		"son": "bete",
		"visuel": "guerrier à tête de lion rugissant et crinière fournie, corps humain très musclé à la "
				  "peau fauve, pieds terminés en serres d'oiseau, pagne à motifs bleu et rouge, bracelets "
				  "d'or, une dague levée dans une main, l'autre main griffue tendue ; posture de garde",
		"fond": "bleu vif",
	},
	"homme_scorpion": {
		"nom": "Homme-scorpion",
		"description": "Torse d'homme barbu sur un corps de scorpion géant, l'arc ou la lance à la main. Le "
					   "récit de Gilgamesh les place aux portes du Soleil, au pied des monts jumeaux de "
					   "Mashu, et dit qu'il suffit de les voir pour mourir. Ils ne laissent passer personne "
					   "sans l'avoir interrogé ; les réponses qu'ils attendent ne sont rapportées nulle part.",
		"base_attributes": _attrs((6, 6), (50, 70), (50, 70), (35, 50), (45, 60), (30, 45), (10, 25), (15, 30)),
		"tags": ["monstre", "hybride", "gardien", "venin", "desert", "humanoide"],
		"butin": ("carcasse", [250, 400], "peu_commun"),
		"son": "insecte",
		"visuel": "torse d'homme barbu musclé, barbe noire tressée, coiffe cylindrique, soudé à la place "
				  "de la tête d'un scorpion géant brun sombre à la carapace luisante, huit pattes, pinces, "
				  "longue queue recourbée terminée par un dard ; il tient une longue lance",
		"fond": "bleu vif",
	},
	# ── Japon ──
	"kitsune": {
		"nom": "Kitsune",
		"description": "Renard au pelage pâle qui a vécu assez longtemps pour gagner une queue de plus, "
					   "puis une autre, et avec elles l'art des illusions. Il prend volontiers forme humaine "
					   "pour tromper un voyageur, allume des feux follets dans les rizières et disparaît "
					   "quand on croit le tenir. Certains servent Inari, dit-on ; d'autres ne servent qu'eux-mêmes.",
		"base_attributes": _attrs((6, 6), (15, 25), (15, 25), (45, 60), (40, 55), (40, 55), (30, 45), (25, 40)),
		"tags": ["esprit", "metamorphe", "magique", "rapide"],
		"butin": ("carcasse", [6, 10], "peu_commun"),
		"son": "loup",
		"visuel": "renard blanc crème à l'allure élégante, trois longues queues touffues aux pointes "
				  "dorées déployées en éventail, yeux dorés rusés, petite flamme bleutée flottant près "
				  "de son museau ; attitude aux aguets",
		"fond": "bleu vif",
	},
	"kyubi": {
		"nom": "Kyūbi",
		"description": "Renard à neuf queues, le plus ancien des kitsune : mille ans de ruse, disent les "
					   "conteurs, et une magie qui fait douter de ses propres yeux. On raconte qu'un "
					   "Kyūbi vécut à la cour sous les traits d'une dame d'une beauté sans égale, avant "
					   "qu'un devin ne le démasque ; qu'il se changea en pierre qui tue ceux qui la "
					   "touchent ; que la pierre s'est brisée. Personne ne s'accorde sur la suite.",
		"base_attributes": _attrs((7, 7), (35, 50), (40, 55), (60, 80), (70, 95), (70, 95), (50, 70), (30, 50)),
		"tags": ["esprit", "metamorphe", "magique", "rapide", "legendaire", "boss"],
		"butin": ("carcasse", [20, 35], "rare"),
		"son": "loup",
		"visuel": "grand renard blanc nacré, neuf longues queues touffues aux pointes dorées déployées "
				  "en une immense couronne derrière lui, yeux d'or perçants, feux follets bleus flottant "
				  "autour de lui ; port majestueux et inquiétant",
		"fond": "magenta",
	},
	"oni": {
		"nom": "Oni",
		"description": "Colosse cornu à la peau rouge, aux crocs saillants et à la crinière hirsute, vêtu "
					   "d'une peau de tigre et armé d'une massue de fer cloutée. Les oni hantent les "
					   "montagnes, les grottes et les îles qu'on évite ; ils pillent, enlèvent et dévorent. "
					   "Les uns les disent nés de la colère des morts, les autres d'un portail de l'autre "
					   "monde ; les haricots grillés qu'on leur jette à la fin de l'hiver, eux, n'ont jamais "
					   "rien prouvé.",
		"base_attributes": _attrs((6, 6), (60, 80), (55, 75), (25, 40), (35, 50), (15, 30), (0, 10), (15, 30)),
		"tags": ["monstre", "humanoide", "guerrier", "predateur"],
		"butin": ("carcasse", [200, 300], "peu_commun"),
		"son": "ogre",
		"visuel": "colosse humanoïde à la peau rouge vif, deux cornes recourbées sur le front, crocs "
				  "saillants, crinière et barbe noires hirsutes, muscles énormes, pagne en peau de tigre, "
				  "une lourde massue de fer hérissée de clous à la main ; posture agressive, jambes fléchies",
		"fond": "bleu vif",
	},
	"nue": {
		"nom": "Nue",
		"description": "Chimère des nuits japonaises : tête de singe, corps de tanuki, pattes de tigre et "
					   "queue de serpent, enveloppée d'une nuée noire. Son cri lugubre, pareil à celui d'un "
					   "oiseau de nuit, apporte maladie et malheur à qui l'entend. Le récit dit qu'un archer "
					   "en abattit un au-dessus d'un palais ; on se demande encore s'il était seul.",
		"base_attributes": _attrs((6, 6), (40, 55), (40, 55), (40, 55), (35, 50), (20, 35), (0, 0), (20, 35)),
		"tags": ["monstre", "hybride", "nocturne", "maladie", "terreur"],
		"butin": ("carcasse", [150, 250], "rare"),
		"son": "bete",
		"visuel": "créature hybride à tête de singe au visage rouge et grimaçant, corps trapu au pelage "
				  "brun de tanuki, pattes avant et arrière rayées de tigre aux griffes puissantes, queue "
				  "formée d'un serpent vert vivant gueule ouverte, volutes de nuée noire autour d'elle",
		"fond": "bleu vif",
	},
	"tanuki": {
		"nom": "Tanuki",
		"description": "Chien viverrin replet et farceur, célèbre pour ses métamorphoses : une théière, un "
					   "moine, une jolie passante, une pièce d'or qui redevient feuille au matin. Il préfère "
					   "duper que mordre et détale dès qu'on le démasque. Les aubergistes posent sa statue "
					   "devant la porte ; nul ne sait si c'est pour l'attirer ou pour l'éloigner.",
		"base_attributes": _attrs((5, 5), (10, 20), (15, 25), (30, 45), (30, 45), (30, 45), (25, 40), (35, 50)),
		"tags": ["animal", "metamorphe", "magique", "petite_taille"],
		"butin": ("carcasse", [5, 9], "commun"),
		"visuel": "chien viverrin rond et replet au pelage brun et crème, masque sombre autour des yeux, "
				  "large chapeau de paille conique sur la tête, ventre rebondi, queue touffue annelée, air "
				  "malicieux, une feuille posée sur le front ; il se tient debout sur ses pattes arrière",
		"fond": "bleu vif",
	},
}

# « zone@CODES » (codes de gen_monstres_legendes.REG). Le Kyūbi, boss, n'y figure pas.
ZONES = {
	"lamassu": ["ruines_maudites@AN", "desert@AN", "steppe_aride@AN"],
	"pazuzu": ["desert@AN", "hamada@AN", "erg@AN"],
	"lamashtu": ["palmeraie@AN", "terres_cultivees@AN", "ruines_maudites@AN"],
	"ugallu": ["ruines_maudites@AN", "canyon@AN", "contreforts_arides@AN"],
	"homme_scorpion": ["montagne@AN", "canyon@AN", "desert@AN"],
	"kitsune": ["riziere@AS", "foret_mixte_montagne@AS", "foret_bambou@AS"],
	"oni": ["montagne@AS", "grotte@AS", "ile@AS"],
	"nue": ["foret_persistante@AS", "ruines_maudites@AS", "foret_bambou@AS"],
	"tanuki": ["foret_persistante@AS", "terres_cultivees@AS", "foret_bambou@AS"],
}


def installer(setattr_fn=setattr) -> None:
	"""Branche ce lot sur le moteur de gen_monstres_legendes (globales lues par ses fonctions).
	Les tests passent `monkeypatch.setattr` pour que le branchement soit défait après eux."""
	setattr_fn(moteur, "NOUVELLES", NOUVELLES)
	setattr_fn(moteur, "ZONES", ZONES)
	setattr_fn(moteur, "DONJONS", {})
	setattr_fn(moteur, "REGIONS_NEUVES", {})  # asie existe déjà en base
	setattr_fn(moteur, "SORTIE", SORTIE)


if __name__ == "__main__":
	installer()
	moteur.main()
