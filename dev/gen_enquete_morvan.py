#!/usr/bin/env python
# dev/gen_enquete_morvan.py
# La bête de Dun-les-Places — l'enquête du rang E, premier lycanthrope de l'aventurier
# (docs/lore/personnages/20261014_enquete_du_morvan.md, arbitrage de l'Auteur du 14/10).
#
#   Borin Barbe-de-Jais (comptoir du Bastion de l'Yonne) confie, au RANG E seulement
#   (condition de dialogue `rang_min`), une quête d'APPORT unique : rapporter la tête du
#   loup-garou (`item:loup_garou_tete`, portion de la carcasse `item:loup_garou`, qu'on
#   débite à la lame) → Dun-les-Places, hameau du Morvan sur la carte de France → la vieille
#   Jacotte, meneuse de loups, mène à `lieu:clairiere_du_charbonnier` (service `acces`, salle
#   de donjon) → un loup-garou → retour au comptoir, remise de la tête.
#
# 100 % DONNÉE (hors la condition `rang_min`, ajoutée au moteur de dialogue pour cette quête) :
#   · la quête est une `collect` ordinaire (`services.apport` de Borin, donneur ET receveur) ;
#   · la clairière s'ouvre tant que la tête reste À RAPPORTER — SANS `combat_gagne` faux,
#     à la différence d'Escolives : la tête se découpe sur une carcasse tombée au sol, un pas
#     de trop et elle est perdue ; la porte doit alors se rouvrir, sans quoi la quête serait
#     bloquée pour toujours ;
#   · UN loup-garou, salle à espèce UNIQUE (un second type pourrait évincer la bête et
#     rendre la preuve introuvable, cf. Escolives) ;
#   · le DOUTE (Auteur) : le charbonnier disparaît une fois la clairière gagnée
#     (`combat_gagne` sur sa présence), la meneuse jure que ce n'était qu'un loup, puis
#     regrette qu'on ne l'ait pas appelé par son nom — le nom n'est JAMAIS dit.
#
# ⚠️ UN SEUL FICHIER À IMPORTER : jsons/enquete_morvan_a_importer.json — Borin RELU du dernier
# dump (seuls son service `apport`, ses choix d'accueil et ses nœuds `morvan_*` changent :
# régénération idempotente) + les docs neufs, chacun COMPLET (l'import est un PUT, CLAUDE.md
# §11). ⚠️ Tout script qui réécrirait Borin depuis un dump FIGÉ plus ancien effacerait la quête.
#
# Usage : python dev/gen_enquete_morvan.py [jsons/telluris-dump-….json]

import copy
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSONS = os.path.join(RACINE, "jsons")
SORTIE = os.path.join(JSONS, "enquete_morvan_a_importer.json")

QUETE = "quete:la_bete_de_dun_les_places"
BORIN = "pnj:borin_barbe_de_jais"
CITE = "lieu:auxerre"
RANG = "E"
VILLAGE = "lieu:dun_les_places"
CLAIRIERE = "lieu:clairiere_du_charbonnier"
DONJON = "donjon:clairiere_du_charbonnier"
LIEN = "link:dun_les_places_to_france"
TETE = "item:loup_garou_tete"
LOUP_GAROU = "espece:loup_garou"
BERGERE = "pnj:bergere_margot_gueneau"
CHARBONNIER = "pnj:charbonnier_pierre_chaumereuil"
MENEUSE = "pnj:meneuse_de_loups_jacotte"
PORTRAITS = {
	BERGERE: "bergere_Margot_Gueneau_hobbit_f.jpg",
	CHARBONNIER: "charbonnier_Pierre_Chaumereuil_ogre_m.jpg",
	MENEUSE: "meneuse_de_loups_Jacotte_elfe_f.jpg",
}
# Carte de France : Auxerre occupe (50,18)-(50,19), Escolives (50,21). Dun-les-Places est à
# une douzaine de lieues au sud-est, dans le Morvan (≈ 0,2° de latitude par case).
POS_FRANCE = [52, 22]

RANG_E = {"rang_min": {"cite": CITE, "rang": RANG}}
# La clairière s'ouvre tant que la tête reste À RAPPORTER (cf. en-tête : pas de
# `combat_gagne`). Les barrières n'ont pas de filtre `id` : la collecte se reconnaît à sa cible.
QUETE_A_FAIRE = {"quete_active": {"types": ["collect"], "cible": TETE, "objectif_atteint": False}}

# Les villageois ne parlent de l'enquête que quête EN COURS (Auteur, 15/10) : AVANT, un simple
# bonjour ; APRÈS, ce que la quête a changé. La conjonction des deux `attendu: false` dit
# « jamais confiée » (une quête abandonnée y retombe) — `pnj.CONDITIONS_QUETE`.
AVANT = {"quete_active": {"id": QUETE, "attendu": False}, "quete_reussie": {"id": QUETE, "attendu": False}}
EN_COURS = {"quete_active": {"id": QUETE}}
APRES = {"quete_reussie": {"id": QUETE}}
CLAIRIERE_GAGNEE = {"combat_gagne": {"lieu": CLAIRIERE}}
CLAIRIERE_INTACTE = {"combat_gagne": {"lieu": CLAIRIERE, "attendu": False}}

# ── Grille de la clairière (image 1376×746, quadrillage de 40 × 20 cases) ──────────────────
# L'image livrée (1376×768) a été rognée de 10 px en haut et 12 px en bas : son quadrillage
# dessiné (34,4 × 37,3 px) commence à y = 10 et finit à y = 756 ; rognée, elle tombe juste.
# '#' = 0 (forêt, ciel, cabane) · '.' = 1 (terre, sentier) · 'x' = 3 (meules, bûches, souches,
# branchages : on ne marche pas dessus, un volant les survole).
GRILLE_CLAIRIERE = [
	"########################################",  # 0
	"########################################",
	"########################################",
	"##################.......#..#####.######",  # 3 cabane au nord-est, meule nord-est
	"###############...xxx..xx..######.######",
	"#########.........xxx..xx.#######..#####",  # 5
	"#########xx....xx.xxx..xx.#######..#####",
	"########..x...xxxx...........###.#######",  # 7 meule nord-ouest
	"#######xx.....xxxx............##.#######",
	"#######....x..xxxx..............########",
	"#######..x....xx..............xx########",  # 10
	"########.....xxxx............xxx########",  # 11 meule sud
	"#########....xxxx...............########",
	"#########....xxxx........x.xxx..########",  # 13 billot (hache), piles de bûches
	"##########x.............x..xxxx.########",
	"##########xx....x.............xx########",  # 15
	"#################.....##################",  # 16 sentier d'entrée, au sud
	"#################.....##################",
	"#################.....##################",
	"#################.....##################",
]
CODES = {"#": 0, ".": 1, "x": 3}


def cells_clairiere() -> list:
	return [[CODES[c] for c in ligne] for ligne in GRILLE_CLAIRIERE]


def charger(chemin):
	with open(chemin, encoding="utf-8") as f:
		return json.load(f)


def ecrire(chemin, docs):
	with open(chemin, "w", encoding="utf-8", newline="\n") as f:
		f.write(json.dumps(docs, ensure_ascii=False, indent=2) + "\n")


def dernier_dump(argv):
	if len(argv) > 1:
		return argv[1]
	dumps = sorted(glob.glob(os.path.join(JSONS, "telluris-dump-*.json")))
	if not dumps:
		sys.exit("Aucun dump jsons/telluris-dump-*.json")
	return dumps[-1]


def sans_rev(doc):
	doc = copy.deepcopy(doc)
	doc.pop("_rev", None)
	return doc


def poser_choix(noeud: dict, choix: list):
	"""Insère les choix juste AVANT le dernier choix du nœud (la sortie). Idempotent : un
	choix déjà là (même id) est remplacé en place."""
	liste = noeud.setdefault("choix", [])
	for c in choix:
		idx = next((i for i, x in enumerate(liste) if x.get("id") == c["id"]), None)
		if idx is not None:
			liste[idx] = c
		else:
			liste.insert(max(0, len(liste) - 1), c)


# ── Borin : la quête, le rappel, la remise ────────────────────────────────────────────────

CHOIX_BORIN = [
	{"id": "morvan_offre", "label": "« Il paraît qu'une bête court le Morvan ? »",
	 "condition": {"apport_offert": True, **RANG_E}, "next": "morvan_propose"},
	{"id": "morvan_rappel", "label": "« Dun-les-Places… rappelle-moi. »",
	 "condition": {"apport_en_cours": True, "apport_possible": False}, "next": "morvan_rappel"},
	{"id": "morvan_remettre", "label": "« Voilà la tête de ta bête. »",
	 "condition": {"apport_possible": True}, "action": {"service": "apport", "op": "remettre"}},
	{"id": "morvan_souvenir", "label": "« Des nouvelles du Morvan ? »",
	 "condition": {"quete_reussie": {"id": QUETE}}, "next": "morvan_souvenir"},
]

NOEUDS_BORIN = {
	"morvan_propose": {
		"texte": "Borin pose sur le comptoir une lettre au papier taché, pliée en quatre. « Ça vient de Dun-les-Places, dans le Morvan. Des hameaux de charbonniers au fond des bois, à quatre jours d'ici. » Il tapote le papier. « Une bête leur mange les moutons depuis la dernière lune. Ils ont doublé les pieux des enclos ; elle a arraché la porte de la bergerie. Et la semaine passée, elle a tué un berger. Un gamin. » Il lève les yeux vers vous. « Ils disent loup-garou. Ils disent toujours loup-garou, là-haut. »",
		"choix": [
			{"id": "details", "label": "« Et toi, tu y crois ? »", "next": "morvan_details"},
			{"id": "accepter", "label": "« J'y vais. »", "action": {"service": "apport", "op": "accepter"}},
			{"id": "plus_tard", "label": "« Pas tout de suite. »", "next": "accueil"},
		],
	},
	"morvan_details": {
		"texte": "« Moi ? » Borin hausse ses larges épaules. « J'ai vu des loups gros comme des veaux, dans les forêts de l'est. J'ai vu des gens courir les bois les nuits de pleine lune, aussi, et revenir au matin les mains griffées. Je ne sais pas ce que c'était. » Il replie la lettre. « La Guilde paie au résultat, comme les primes au loup d'autrefois : tu me rapportes {objet}, et on écrit ce que c'était dans le registre. Là-haut, va voir la vieille Jacotte. On dit qu'elle mène les loups. Si quelqu'un sait où la bête se couche, c'est elle. »",
		"choix": [
			{"id": "accepter", "label": "« J'y vais. »", "action": {"service": "apport", "op": "accepter"}},
			{"id": "plus_tard", "label": "« Pas tout de suite. »", "next": "accueil"},
		],
	},
	"morvan_accepte": {
		"texte": "Borin inscrit votre nom au registre, d'une écriture lourde et appliquée. « Par la porte du sud-est, et puis les bois, toujours les bois. » Il ajoute, sans relever la tête : « Prends une bonne lame. Une bête comme ça, tu ne la ramèneras pas entière sur ton dos. La tête suffit. »",
		"choix": [{"id": "ok", "label": "« Compris. »", "next": "fin"}],
	},
	"morvan_rappel": {
		"texte": "« Dun-les-Places, au sud-est, dans le Morvan. Demande la vieille Jacotte. Et moi, j'attends {objet}, pas une histoire de veillée. »",
		"choix": [{"id": "ok", "label": "« J'y retourne. »", "next": "fin"}],
	},
	"morvan_partiel": {
		"texte": "Borin regarde ce que vous posez sur le comptoir. « Il en manque. Encore {reste}. »",
		"choix": [{"id": "ok", "label": "« J'y retourne. »", "next": "fin"}],
	},
	"morvan_remis": {
		"texte": "Borin défait le linge et recule d'un demi-pas. La tête est celle d'un loup, mais trop large, le front trop haut, et les yeux, à demi clos, n'ont pas tout à fait la couleur d'un œil de bête. Il la recouvre. « Loup-garou », dit-il, et il l'écrit au registre. Il pousse vers vous {prime} pièces de cuivre et porte {xp} points à votre nom. Puis, plus bas : « Ou un très grand loup. C'est ce qu'ils diront, là-haut, la moitié d'entre eux. Moi, j'écris ce que la Guilde a payé. »",
		"choix": [{"id": "ok", "label": "« Ça me va. »", "next": "fin"}],
	},
	"morvan_souvenir": {
		"texte": "« Plus une brebis de perdue, à ce qu'on m'écrit de Dun-les-Places. » Borin lisse une natte de sa barbe. « Et leur charbonnier n'est jamais revenu. Ils ont brûlé sa cabane. Moi, je dis que ça ne prouve rien, ni dans un sens ni dans l'autre. »",
		"choix": [{"id": "ok", "label": "Revenir.", "next": "accueil"}],
	},
}


def borin(doc: dict) -> dict:
	doc = sans_rev(doc)
	doc.setdefault("services", {})["apport"] = {
		"offre": {
			"id": QUETE,
			"titre": "La bête de Dun-les-Places",
			"description": "Une bête décime les troupeaux de Dun-les-Places, au fond des forêts du Morvan, et a tué un jeune berger. Les villageois parlent de loup-garou. Trouvez où elle se couche — la vieille Jacotte, la meneuse de loups, le sait peut-être — et rapportez sa tête à Borin Barbe-de-Jais, au comptoir du Bastion de l'Yonne.",
			"item": TETE,
			"quantite": 1,
			"unique": True,
			"recompenses": {"xp": 70, "cuivre": 800},  # barème E/D (gen_recalage_primes.py)
		},
		"noeuds": {"accepte": "morvan_accepte", "partiel": "morvan_partiel", "remis": "morvan_remis"},
	}
	noeuds = doc["dialogue"]["noeuds"]
	poser_choix(noeuds["accueil"], CHOIX_BORIN)
	noeuds.update(copy.deepcopy(NOEUDS_BORIN))
	return doc


# ── Dun-les-Places : le hameau, ses trois PNJ, la clairière ───────────────────────────────

def meneuse() -> dict:
	return {
		"_id": MENEUSE,
		"type": "pnj",
		"nom": "Jacotte",
		"race": "elfe",
		"vocation": "chaman",
		"portrait": PORTRAITS[MENEUSE],
		"description": "La vieille Jacotte, meneuse de loups, sa musette serrée contre elle au bord du bois.",
		"services": {"acces": {"lieu": CLAIRIERE, "noeuds": {"ouvre": "clairiere_ouverte", "refus": "clairiere_close"}}},
		"dialogue": {
			"noeud_depart": "accueil",
			"noeuds": {
				"accueil": {
					"texte": "À la lisière, là où le hameau s'arrête et où les grands chênes commencent, une vieille elfe aux cheveux blancs dénoués est assise sur une souche, une musette sur les genoux. Entre les arbres, derrière elle, deux paires d'yeux luisent sans bouger. Elle ne les regarde pas. « Bonjour, voyageur. N'aie pas peur de ceux-là : ils sont avec moi. »",
					"choix": [
						{"id": "bonjour", "label": "« Bonjour. Vous allez bien ? »", "condition": AVANT, "next": "bonjour"},
						{"id": "loups", "label": "« Ces loups vous suivent ? »", "condition": EN_COURS, "next": "loups"},
						# `acces_ouvrable` suppose la collecte en cours (barrière de la clairière).
						{"id": "guilde", "label": "« La Guilde m'envoie. Où la bête se couche-t-elle ? »",
						 "condition": {"acces_ouvrable": True}, "next": "seuil"},
						# `acces_libere` = la clairière est gagnée (état du MONDE), avant même le rapport.
						{"id": "apres", "label": "« La bête est morte. »",
						 "condition": {"acces_libere": True}, "next": "apres"},
						{"id": "fin", "label": "(La laisser à sa musette.)", "next": "fin"},
					],
				},
				"bonjour": {
					"texte": "« Aussi bien qu'une vieille peut aller. » Elle souffle une note légère dans sa musette ; derrière elle, les yeux clignent et disparaissent entre les troncs. « Les bois sont beaux, en cette saison. Reste sur le chemin, et bonne route. »",
					"choix": [{"id": "fin", "label": "« Bonne journée. »", "next": "fin"}],
				},
				"loups": {
					"texte": "« Tu cherches la bête. Ils te l'ont tous dit avant de te dire bonjour. » Elle tapote sa musette. « Ceux-là me suivent quand je joue. » Elle souffle dans la musette, une seule note, aigre et longue ; les yeux, derrière elle, se ferment et se rouvrent. « Les loups de ces bois, je les connais tous, et chacun par son nom. Celle qui mange les moutons de Margot, ce n'est pas un des miens. Elle ne répond pas quand je joue. » Elle repose l'instrument. « Ce qui ne répond pas à la musette, d'habitude, répond à autre chose. »",
					"choix": [
						{"id": "quoi", "label": "« À quoi ? »", "next": "nom"},
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
					],
				},
				"nom": {
					"texte": "« À son nom. Son vrai nom, celui qu'on lui a donné avant qu'il coure le garou. » Jacotte vous regarde enfin, et vous comprenez qu'elle ne vous le dira pas. « Ceux qui courent le garou font sept villages avant l'aube, les nuits de pleine lune. Appelle-les par leur nom, ou fais-leur couler trois gouttes de sang, et ils te reviennent. Mais il faut savoir à qui l'on parle. » Elle hausse les épaules. « Et ici, tout le monde croit le savoir. »",
					"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}],
				},
				"seuil": {
					"texte": "Jacotte se lève, lentement, et vous fait signe de la suivre. Elle marche longtemps sous les arbres sans lumière, sans jamais trébucher. Les deux loups vont devant, sans bruit. Enfin, une odeur de fumée froide, une lueur rouge entre les troncs : la clairière du charbonnier, ses meules qui fument sous la lune. Elle s'arrête au bord. « C'est là qu'elle revient. Moi, je n'entre pas. »",
					"choix": [
						{"id": "entrer", "label": "Entrer dans la clairière.", "condition": {"acces_ouvrable": True},
						 "action": {"service": "acces", "op": "passer"}},
						{"id": "attendre", "label": "« Pas encore. »", "next": "accueil"},
					],
				},
				"clairiere_ouverte": {
					"texte": "Vous faites trois pas sur la terre noire. Les meules fument doucement. Personne devant la cabane. Puis, de l'autre côté de la clairière, quelque chose se lève d'entre les bûches : un loup, mais trop grand, debout sur des pattes de derrière qui ne sont pas faites pour ça, et qui retombe à quatre pattes en grondant. Il vous a vu avant que vous le voyiez.",
					"choix": [{"id": "ok", "label": "Tirer votre arme.", "next": "fin"}],
				},
				"clairiere_close": {
					"texte": "Jacotte ne se lève pas. « La clairière est vide, maintenant. Il n'y a plus rien à y chercher. »",
					"choix": [{"id": "ok", "label": "Reculer.", "next": "fin"}],
				},
				"apres": {
					"texte": "« Morte, oui. Je l'ai entendue. » Jacotte souffle une note dans sa musette ; derrière elle, les deux loups se couchent. « Ce n'était qu'un loup, tu sais. Un loup plus grand que les autres, venu d'ailleurs, qui ne connaissait pas ma musette. » Elle se tait un long moment.",
					"choix": [
						{"id": "nom", "label": "« Et s'il ne l'était pas ? »", "next": "le_nom"},
						{"id": "fin", "label": "(La laisser à sa musette.)", "next": "fin"},
					],
				},
				"le_nom": {
					"texte": "Jacotte regarde ses mains. « Alors il aurait fallu l'appeler par son nom. Il serait peut-être revenu. » Vous lui demandez quel nom. Elle se lève sans répondre et rentre dans le bois, ses deux loups sur les talons.",
					"choix": [{"id": "fin", "label": "(La laisser partir.)", "next": "fin"}],
				},
			},
		},
	}


def bergere() -> dict:
	return {
		"_id": BERGERE,
		"type": "pnj",
		"nom": "Margot Gueneau",
		"race": "hobbit",
		"vocation": "forestier",
		"portrait": PORTRAITS[BERGERE],
		"description": "Margot Gueneau, bergère, devant l'enclos aux pieux doublés.",
		"dialogue": {
			"noeud_depart": "accueil",
			"noeuds": {
				"accueil": {
					"texte": "Devant un enclos aux pieux doublés, une jeune hobbit compte ses moutons, une houlette à la main, un brassard noir au bras. Elle recommence trois fois et trouve trois fois le même compte, puis lève les yeux. « Bonjour. Attention à la barrière, elle ne tient plus que par habitude. »",
					"choix": [
						{"id": "bonjour", "label": "« Bonjour. Vous allez bien ? »", "condition": AVANT, "next": "bonjour"},
						{"id": "frere", "label": "« La Guilde d'Auxerre m'envoie. »", "condition": EN_COURS, "next": "frere"},
						{"id": "bete", "label": "« Vous avez vu la bête ? »", "condition": EN_COURS, "next": "bete"},
						{"id": "apres", "label": "« La bête ne reviendra pas. »", "condition": APRES, "next": "apres"},
						{"id": "fin", "label": "(La laisser à ses moutons.)", "next": "fin"},
					],
				},
				"bonjour": {
					"texte": "« On fait avec. Les bêtes mangent, l'herbe repousse. » Elle reprend son compte du bout de la houlette. « Bonne route, et refermez bien derrière vous. »",
					"choix": [{"id": "fin", "label": "« Bonne journée. »", "next": "fin"}],
				},
				"frere": {
					"texte": "« Alors vous êtes en retard d'un berger. » Sa voix se durcit. « Mon frère. Colin. Il gardait le troupeau d'en haut, il avait seize ans. » Elle serre la houlette. « On l'a trouvé au matin, contre la porte de la bergerie. La porte était arrachée, et les gonds tordus, comme si on avait tiré dessus avec des mains. Un loup n'a pas de mains. »",
					"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}],
				},
				"bete": {
					"texte": "« Une fois. De loin, sous la lune. » Elle parle vite, comme quelqu'un qui l'a déjà raconté vingt fois. « Un loup trop grand. Il marchait mal, comme un homme qui aurait voulu marcher à quatre pattes. Il est parti vers les bois de l'est. » Elle crache par terre. « Vers la clairière du Gros-Pierre. Et le Gros-Pierre, depuis, il porte un bandage au bras. Demandez-lui donc d'où il vient. »",
					"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}],
				},
				"apres": {
					"texte": "Margot compte ses moutons, une fois, et le compte est bon. « Plus une bête de perdue depuis que vous êtes passé. » Elle regarde vers l'est, vers les bois. « Le Gros-Pierre est parti, aussi. Sa cabane est vide, ses meules se sont éteintes. » Elle serre la houlette. « S'il est parti, c'est bien qu'il était coupable. Non ? » Elle n'attend pas votre réponse. « C'est ce que tout le monde dit. Alors c'est ce que je dirai à Colin. »",
					"choix": [{"id": "fin", "label": "(La laisser à ses moutons.)", "next": "fin"}],
				},
			},
		},
	}


def charbonnier() -> dict:
	return {
		"_id": CHARBONNIER,
		"type": "pnj",
		"nom": "Pierre Chaumereuil",
		"race": "ogre",
		"vocation": "guerrier",
		"portrait": PORTRAITS[CHARBONNIER],
		"description": "Pierre Chaumereuil, le Gros-Pierre, charbonnier, noir de suie, un bandage au bras.",
		"dialogue": {
			"noeud_depart": "accueil",
			"noeuds": {
				"accueil": {
					"texte": "Un ogre noir de suie décharge des sacs de charbon devant la palissade, sans un regard pour les villageois qui s'écartent sur son passage. Son avant-bras gauche est serré dans un bandage frais. Il vous voit venir et hoche la tête. « Bonjour. Écartez-vous de la charrette, les sacs glissent. »",
					# Pas de branche APRÈS : il a disparu une fois la clairière gagnée (présence du lieu).
					"choix": [
						{"id": "bonjour", "label": "« Bonjour. Vous allez bien ? »", "condition": AVANT, "next": "bonjour"},
						{"id": "accuse", "label": "« On vous accuse, au village. »", "condition": EN_COURS, "next": "accuse"},
						{"id": "bras", "label": "« Ce bandage ? »", "condition": EN_COURS, "next": "bras"},
						{"id": "nuits", "label": "« Où êtes-vous, les nuits de pleine lune ? »", "condition": EN_COURS, "next": "nuits"},
						{"id": "fin", "label": "(Le laisser à son charbon.)", "next": "fin"},
					],
				},
				"bonjour": {
					"texte": "« Je vais. » Il hisse un sac sur la pile. « Le charbon ne se vend pas tout seul, et l'hiver vient toujours plus tôt qu'on croit. Bonne route. »",
					"choix": [{"id": "fin", "label": "« Bon courage. »", "next": "fin"}],
				},
				"accuse": {
					"texte": "Il soupire. « Encore un qui vient voir le loup-garou. Ils accusent toujours celui qui vit dans les bois. » Il jette un sac sur la pile. « Mon père vivait dans les bois, et on l'accusait aussi. Il est mort dans son lit. » Il vous regarde de haut, de très haut. « Si vous voulez la bête, elle passe par ma clairière. Je l'entends gratter aux meules. C'est pour ça que je ne dors plus. »",
					"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}],
				},
				"bras": {
					"texte": "Il cache le bras derrière son dos, comme un enfant. « Une meule qui s'est effondrée. Le feu couvait dessous, la terre a cédé, j'ai mis le bras dedans pour sauver le bois. » Il hausse les épaules. « Allez demander à la vieille Jacotte, si vous ne me croyez pas. Elle sait tout, elle. Elle ne dit rien, mais elle sait tout. »",
					"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}],
				},
				"nuits": {
					"texte": "« Les nuits de pleine lune ? » Il s'arrête, un sac sur l'épaule. « Je ne dors pas. Personne ne dort, ici. » Il repart vers sa charrette. « Une meule, ça se veille sept jours et sept nuits. Moi, je veille mes meules. Les autres veillent leurs moutons. Et tout le monde regarde la lisière. »",
					"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}],
				},
			},
		},
	}


def docs_neufs() -> list:
	return [
		{
			"_id": VILLAGE,
			"type": "lieu",
			"label": "Dun-les-Places",
			"image": "dun_les_places.jpg",
			"categorie": "chemin",
			"lieu_parent": "lieu:france",
			"pnj": [
				{"character": MENEUSE, "nom": "Jacotte", "portrait": PORTRAITS[MENEUSE], "probabilite": 1,
				 "description": "La vieille Jacotte, assise sur une souche à la lisière, sa musette sur les genoux."},
				{"character": BERGERE, "nom": "Margot", "portrait": PORTRAITS[BERGERE], "probabilite": 1,
				 "description": "Margot, la bergère, devant l'enclos aux pieux doublés."},
				# Disparu une fois la clairière gagnée (Auteur) : nul ne sait s'il était la bête.
				{"character": CHARBONNIER, "nom": "Gros-Pierre", "portrait": PORTRAITS[CHARBONNIER], "probabilite": 1,
				 "description": "Le Gros-Pierre, le charbonnier, qui décharge ses sacs devant la palissade.",
				 "conditions": [CLAIRIERE_INTACTE]},
			],
		},
		{
			"_id": LIEN,
			"type": "connection",
			"nodes": [
				{"lieu": "lieu:france", "pos": list(POS_FRANCE), "label": "Dun-les-Places"},
				{"lieu": VILLAGE, "pos": [0, 0], "label": "Reprendre la route"},
			],
			"metadata": {"type": "chemin", "status": "ouvert"},
		},
		meneuse(),
		bergere(),
		charbonnier(),
		{
			"_id": CLAIRIERE,
			"type": "lieu",
			"label": "La clairière du charbonnier",
			"image": "clairiere_du_charbonnier.jpg",
			"categorie": "battle_map",
			"dimensions": {"x": len(GRILLE_CLAIRIERE[0]), "y": len(GRILLE_CLAIRIERE)},
			"cells": cells_clairiere(),
			"nav": {},
			"tags": ["foret", "clairiere", "nuit", "donjon"],
			"acces": {
				"gardien": MENEUSE,
				"refus": "La clairière est vide. Les meules se sont éteintes.",
				"cycle": 1,
				"conditions": [QUETE_A_FAIRE],
			},
		},
		{
			"_id": DONJON,
			"type": "donjon",
			"nom": "La clairière du charbonnier",
			"description": "Au fond des bois de Dun-les-Places, la clairière d'un charbonnier, ses meules et sa cabane. Une bête y revient les nuits de pleine lune.",
			"portail": VILLAGE,
			# Une seule bête, de grade bas : premier lycanthrope, au rang E. Non simulé.
			"niveau_min": 1,
			"niveau_max": 2,
			"battle_maps": [{
				"lieu": CLAIRIERE,
				"especes": [LOUP_GAROU],
				"nb_monstres": 1,
				"niveau_min": 1,
				"niveau_max": 2,
			}],
		},
	]


def main(argv):
	dump = charger(dernier_dump(argv))
	par_id = {d["_id"]: d for d in dump["docs"]}
	for requis in (BORIN, LOUP_GAROU, TETE, "lieu:france", CITE):
		if requis not in par_id:
			sys.exit(f"ERREUR : {requis} absent du dump")
	largeurs = {len(l) for l in GRILLE_CLAIRIERE}
	if len(largeurs) != 1:
		sys.exit(f"ERREUR : grille de la clairière irrégulière {sorted(largeurs)}")
	neufs = docs_neufs()
	collisions = [d["_id"] for d in neufs if d["_id"] in par_id]
	if collisions:
		print("⚠️ ids déjà présents au dump (écrasés par l'import) :", ", ".join(collisions))
	docs = [borin(par_id[BORIN])] + neufs
	ecrire(SORTIE, docs)
	print(f"{len(docs)} docs → {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
	main(sys.argv)
