#!/usr/bin/env python
# dev/gen_monstres_hekla.py
# Bestiaire de l'arc de l'Hekla (demande du 28/11/2026) — docs/hekla_neuf_cercles.md § Monstres à créer :
#   - neuf gardiens, êtres uniques (les Furies en TROIS espèces : Auteur, 28/11 — le moteur attache les
#     capacités à l'espèce, pas à l'exemplaire ; chaque sœur porte son rôle dans son KIT, le profil tiré
#     au hasard ne fait que régler ses caractéristiques) ;
#   - six espèces de combats secondaires (Malebranche, ange déchu, et les trois bêtes du chant I : la Lonza,
#     le Lion, la Louve maigre ; les chiennes noires de la forêt).
# Aucune n'est placée en zone : on ne les croise que dans les salles de l'Enfer et dans la cavité du
# Malebranche (dev/gen_quetes_de_l_hekla.py). Tags `demon`/`infernal` pour les geôliers ; aucun `humanoide`
# (il exigerait un kit d'équipement : ils se battent de leurs armes propres, décrites).
#
# MÊME MOTEUR que dev/gen_monstres_legendes.py (globales remplacées par `installer()`), lignes ajoutées aux
# tables exhaustives (`gen_jetons_especes`, `gen_genres_especes`, `gen_capacites_monstres`). Ce module
# n'écrit RIEN : `gen_quetes_de_l_hekla.py` reprend ses docs dans LE fichier à importer (CLAUDE.md §18).
# Images : dev/gen_images_hekla.py (déjà détourées, `<slug>_transparent.webp`).

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_monstres_legendes as moteur  # noqa: E402
from gen_vampires import _attrs  # noqa: E402

GEOLIER = ["monstre", "demon", "infernal"]
UNIQUE = ["legendaire", "unique", "boss"]

# _attrs = V, F, R, Ag, Vol, Int, Cha, Ch. Repères : Naga (rang B) 45-65 de F ; Échidna (rang S) 85-115.
NOUVELLES = {
	# ── Gardiens ──
	"charon": {
		"nom": "Charon",
		"description": "Le nocher des morts. Les Hellènes le disaient fils de la Nuit, et le payaient d'une "
					   "obole posée dans la bouche du défunt. Ici, il tient la barque de l'Achéron, au premier "
					   "cercle de l'Enfer sous l'Hekla, et refuse le passage aux vivants : « Ce n'est pas ta "
					   "barque. » Il se bat debout dans sa barque, la rame pour arme. Vaincu, il ne meurt pas : "
					   "il se rassoit, et il rame.",
		"base_attributes": _attrs((5, 6), (55, 75), (55, 75), (25, 40), (55, 75), (30, 45), (0, 0), (35, 50)),
		"tags": GEOLIER + UNIQUE + ["magique"],
		"butin": ("ossements", [10, 15], "rare"),
		"son": None,
		"fond": "magenta",
	},
	"minos": {
		"nom": "Minos",
		"description": "Le juge des arrivants. Les Hellènes en faisaient un roi de Crète devenu juge des morts. "
					   "Le récit du poète florentin en fit un démon qui enroule sa queue autant de fois que le "
					   "numéro du cercle assigné. Au deuxième cercle, il juge tout ce qui entre, et tient le "
					   "registre des entrées. Il refuse qu'un vivant aille plus bas sans sentence.",
		"base_attributes": _attrs((5, 6), (60, 80), (60, 80), (25, 40), (65, 85), (45, 60), (25, 40), (35, 50)),
		"tags": GEOLIER + UNIQUE + ["magique", "terreur"],
		"butin": ("carcasse", [180, 240], "rare"),
		"son": None,
		"fond": "magenta",
	},
	"ciacco": {
		"nom": "Ciacco",
		"description": "Un détenu du troisième cercle, que les geôliers laissent régner sur sa fange. Le poète "
					   "florentin rencontra un Ciacco, « le pourceau », qui lui annonça les malheurs de "
					   "Florence. Celui-ci est énorme et bouffi, couvert de boue et de pluie froide, et il rit. "
					   "C'est le seul détenu que l'on combat : il a fait sienne la salle du festin, et il ne la "
					   "rendra pas.",
		"base_attributes": _attrs((4, 5), (60, 80), (70, 95), (15, 25), (45, 60), (30, 45), (20, 35), (40, 55)),
		"tags": ["monstre", "infernal"] + UNIQUE,
		"butin": ("ossements", [20, 30], "rare"),  # forme humaine : pas de découpe « patte, queue »
		"son": None,
		"fond": "magenta",
	},
	"plutus": {
		"nom": "Plutus",
		"description": "Le gardien des biens confisqués, au quatrième cercle. Les Hellènes parlaient de Ploutos, "
					   "la richesse, que Zeus aveugla pour qu'il distribue ses biens sans voir à qui ; le poète "
					   "florentin le confondit avec le maître des Enfers et en fit un démon-loup bouffi. Il "
					   "hurle une langue que personne ne comprend : « Papè Satàn, papè Satàn aleppe. »",
		"base_attributes": _attrs((5, 6), (70, 95), (65, 85), (25, 40), (45, 60), (15, 25), (0, 0), (35, 50)),
		"tags": GEOLIER + UNIQUE + ["predateur", "terreur"],
		"butin": ("carcasse", [200, 260], "rare"),
		"son": None,
		"fond": "magenta",
	},
	"phlegyas": {
		"nom": "Phlégyas",
		"description": "Le passeur des eaux noires du Styx, au cinquième cercle. Les Hellènes disaient qu'il "
					   "fut roi des Lapithes, et que sa colère contre Apollon lui fit incendier le temple de "
					   "Delphes ; il en fut précipité au Tartare. Il arrive sur sa barque au signal d'un feu "
					   "allumé sur une tour, et sa colère est sa faute.",
		"base_attributes": _attrs((5, 6), (75, 100), (70, 90), (25, 40), (50, 65), (25, 40), (15, 25), (40, 55)),
		"tags": GEOLIER + UNIQUE + ["magique"],
		"butin": ("ossements", [20, 30], "rare"),  # idem
		"son": None,
		"fond": "magenta",
	},
	"furie_alecto": {
		"nom": "Alecto",
		"description": "L'une des trois Furies, « l'implacable » : la colère qui ne cesse pas. Les Hellènes "
					   "les nommaient Érinyes, nées du sang d'Ouranos, et elles poursuivaient les crimes de "
					   "sang. Au sommet d'une tour de Dité, Alecto garde ses distances, une torche de fer à la "
					   "main, et crache sur les vivants un feu qui ne s'éteint pas.",
		"base_attributes": _attrs((6, 7), (55, 75), (50, 70), (45, 65), (65, 85), (40, 55), (20, 35), (40, 55)),
		"tags": GEOLIER + UNIQUE + ["vol", "distance"],
		"butin": ("carcasse", [60, 80], "rare"),
		"son": None,
		"fond": "vert vif",
	},
	"furie_megere": {
		"nom": "Mégère",
		"description": "L'une des trois Furies, « celle qui hait » : la jalousie et la rancune. Les Hellènes "
					   "les disaient sœurs ailées à la chevelure de serpents. Mégère pointe un doigt griffu et "
					   "maudit ; sa rancune s'attache à qui l'a regardée, et ne le lâche plus.",
		"base_attributes": _attrs((6, 7), (45, 60), (45, 65), (35, 50), (75, 95), (55, 75), (25, 40), (40, 55)),
		"tags": GEOLIER + UNIQUE + ["vol", "magique"],
		"butin": ("carcasse", [60, 80], "rare"),
		"son": None,
		"fond": "vert vif",
	},
	"furie_tisiphone": {
		"nom": "Tisiphone",
		"description": "L'une des trois Furies, « celle qui venge le meurtre ». Chez le poète latin, elle "
					   "gardait la porte du Tartare, un fouet à la main. À Dité, elle se tient devant ses "
					   "sœurs : son fouet de serpents tressés saisit qui approche, et leurs crocs mordent.",
		"base_attributes": _attrs((6, 7), (70, 90), (65, 85), (40, 55), (55, 70), (30, 45), (15, 25), (40, 55)),
		"tags": GEOLIER + UNIQUE + ["vol"],
		"butin": ("carcasse", [60, 80], "rare"),
		"son": None,
		"fond": "vert vif",
	},
	"geryon": {
		"nom": "Géryon",
		"description": "Le monstre de la fraude, qui monte du gouffre entre le septième cercle et le huitième. "
					   "Les Hellènes parlaient d'un géant à trois corps, maître de troupeaux de bœufs rouges, "
					   "qu'Héraclès abattit. Le poète florentin lui donna un visage d'homme juste, des pattes "
					   "velues, un corps de serpent peint de nœuds et de cercles, et une queue de scorpion. Son "
					   "visage inspire confiance. Sa queue, non.",
		"base_attributes": _attrs((5, 7), (80, 105), (75, 100), (30, 45), (60, 80), (35, 50), (30, 45), (40, 55)),
		"tags": GEOLIER + UNIQUE + ["hybride", "venin"],
		"butin": ("carcasse", [600, 800], "rare"),
		"son": None,
		"fond": "magenta",
	},
	"malacoda": {
		"nom": "Malacoda",
		"description": "« Mauvaise queue », le chef des Malebranche, qui harponnent les détenus plongés dans la "
					   "poix bouillante du huitième cercle. Le poète florentin raconte qu'il indiqua aux "
					   "voyageurs un pont intact qui n'existait plus. Il ment avec une politesse parfaite.",
		"base_attributes": _attrs((6, 7), (70, 90), (65, 85), (45, 60), (65, 85), (50, 65), (35, 50), (40, 55)),
		"tags": GEOLIER + UNIQUE + ["vol", "magique"],
		"butin": ("carcasse", [80, 110], "rare"),
		"son": None,
		"fond": "magenta",
	},
	"antee": {
		"nom": "Antée",
		"description": "Le seul géant que les chaînes ne retiennent pas, au bord du puits du neuvième cercle. "
					   "Les Hellènes le disaient fils de Poséidon et de Gaïa, invincible tant qu'il touchait la "
					   "terre ; Héraclès le vainquit en le soulevant. Chez le poète florentin, il dépose les "
					   "voyageurs au fond. Ici, il s'oppose aux vivants. Vaincu, il les laisse descendre.",
		"base_attributes": _attrs((5, 8), (90, 120), (85, 115), (10, 25), (40, 55), (15, 30), (0, 0), (40, 60)),
		"tags": GEOLIER + UNIQUE + ["geant"],
		"butin": ("ossements", [60, 80], "rare"),
		"son": None,
		"fond": "magenta",
	},
	# ── Combats secondaires ──
	"malebranche": {
		"nom": "Malebranche",
		"description": "Les « Griffes mauvaises », démons ailés et noirs, armés de crocs et de harpons, qui "
					   "gardent la fosse de poix du huitième cercle. Le poète florentin en nomma dix, avec un "
					   "humour grinçant. Ce ne sont pas des bêtes : ils observent, tendent des pièges, frappent "
					   "de loin, et fuient quand ils perdent l'avantage.",
		"base_attributes": _attrs((6, 7), (45, 60), (40, 55), (45, 60), (45, 60), (35, 50), (15, 30), (30, 45)),
		"tags": GEOLIER + ["vol", "distance"],
		"butin": ("carcasse", [40, 55], "peu_commun"),
		"son": None,
		"fond": "magenta",
	},
	"ange_dechu": {
		"nom": "Ange déchu",
		"description": "Un être d'un autre monde, beau et dur, aux ailes noircies comme par le feu, qui garde "
					   "les portes de fer rouge de Dité contre les vivants. Le poète florentin en vit « plus de "
					   "mille, tombés du ciel », sur les remparts. Ils servent ce qu'ils servent, et n'en "
					   "parlent pas.",
		"base_attributes": _attrs((6, 8), (50, 70), (50, 70), (35, 50), (55, 75), (35, 50), (30, 45), (40, 55)),
		"tags": GEOLIER + ["vol", "magique"],
		"butin": ("carcasse", [70, 90], "peu_commun"),
		"son": None,
		"fond": "magenta",
	},
	"lonza": {
		"nom": "Lonza",
		"description": "La première des trois bêtes qui barrèrent la route du poète florentin dans la forêt "
					   "obscure : un félin léger au pelage tacheté, entre l'once et le lynx, figure de la "
					   "convoitise. Elle rôde sur les corniches du deuxième cercle, et attire avant de frapper.",
		"base_attributes": _attrs((6, 8), (40, 55), (35, 50), (55, 75), (35, 50), (15, 25), (20, 35), (25, 40)),
		"tags": ["monstre", "infernal", "predateur"],
		"butin": ("carcasse", [50, 70], "peu_commun"),
		"son": None,
		"fond": "magenta",
	},
	"lion_des_enfers": {
		"nom": "Lion des Enfers",
		"description": "La deuxième des trois bêtes du poète florentin : un lion « la tête haute et la faim "
					   "enragée », dont l'air même semblait trembler, figure de l'orgueil. Il se tient à l'orée "
					   "du désert de feu du septième cercle.",
		"base_attributes": _attrs((6, 7), (65, 85), (60, 80), (40, 55), (50, 65), (15, 25), (0, 0), (30, 45)),
		"tags": ["monstre", "infernal", "predateur", "terreur"],
		"butin": ("carcasse", [200, 260], "peu_commun"),
		"son": None,
		"fond": "magenta",
	},
	"louve_maigre": {
		"nom": "Louve maigre",
		"description": "La troisième des trois bêtes du poète florentin : une louve « chargée de toutes les "
					   "envies dans sa maigreur », figure de l'avarice. Elle rôde dans l'entrepôt des biens "
					   "confisqués du quatrième cercle, et rien de ce qu'elle dévore ne la nourrit.",
		"base_attributes": _attrs((5, 7), (50, 70), (45, 60), (45, 60), (40, 55), (15, 25), (0, 0), (25, 40)),
		"tags": ["monstre", "infernal", "predateur"],
		"butin": ("carcasse", [30, 45], "peu_commun"),
		"son": None,
		"fond": "magenta",
	},
	"chienne_noire": {
		"nom": "Chienne noire",
		"description": "Les chiennes noires, affamées et rapides, que le poète florentin vit chasser dans la "
					   "forêt des suicidés. Elles chassent en meute dans les fourrés du septième cercle, et "
					   "déchirent ce qu'elles attrapent.",
		"base_attributes": _attrs((6, 7), (35, 50), (30, 45), (50, 65), (25, 40), (10, 20), (0, 0), (20, 35)),
		"tags": ["monstre", "infernal", "predateur"],
		"butin": ("carcasse", [30, 40], "commun"),
		"son": None,
		"fond": "vert vif",
	},
}
for _spec in NOUVELLES.values():
	_spec.setdefault("visuel", "")  # prompts déjà faits (dev/gen_images_hekla.py) : jamais réécrits ici


def installer(setattr_fn=setattr) -> None:
	setattr_fn(moteur, "NOUVELLES", NOUVELLES)
	setattr_fn(moteur, "ZONES", {})
	setattr_fn(moteur, "DONJONS", {})
	setattr_fn(moteur, "REGIONS_NEUVES", {})


def docs_monstres(base: dict, rangs_fn=None) -> list:
	"""Docs neufs ou à jour (espèces, butins, compétences de monstre manquantes) d'après le dump `base`.
	Branchement du moteur DÉFAIT après usage (même raison que gen_monstres_mu)."""
	globales = ("NOUVELLES", "ZONES", "DONJONS", "REGIONS_NEUVES")
	avant = {g: getattr(moteur, g) for g in globales}
	installer()
	try:
		docs, _deja = moteur.docs_monstres(base, rangs_fn)
	finally:
		for g, v in avant.items():
			setattr(moteur, g, v)
	return [d for d in docs if d.get("_id") != "rules:regions"]
