#!/usr/bin/env python
# dev/gen_enquete_escolives.py
# Les morts d'Escolives — l'enquête du rang D, premier vampire de l'aventurier
# (docs/lore/personnages/20261013_enquete_d_escolives.md, arbitrage de l'Auteur du 13/10).
#
#   Gautier de Valcroix (bureau du maître de guilde d'Auxerre) confie une quête d'APPORT
#   unique : rapporter les ossements du Strigoï (`item:strigoi`, carcasse que tout Strigoï
#   abattu laisse au butin) → Escolives, village sur la carte de France au sud d'Auxerre
#   → Gaspard le fossoyeur ouvre la crypte de la nécropole (service `acces`, salle de donjon
#   comme la nef de Jumièges) → 3 Strigoï → retour au bureau, remise des ossements.
#
# 100 % DONNÉE, aucune ligne de moteur :
#   · la quête est une `collect` ordinaire (`services.apport` de Gautier, donneur ET receveur) ;
#   · la crypte s'ouvre tant que cette collecte est À FAIRE et que la salle n'est pas gagnée ;
#   · TROIS Strigoï (Auteur, 13/10) : le moteur tire chaque monstre au hasard parmi les
#     espèces de la salle — avec un relevé dans la liste, il pourrait n'y avoir aucun Strigoï,
#     donc aucun ossement à rapporter. Les « relevés » SONT des Strigoï (il déforme les morts
#     avant de les relever par le sang).
#   · le DOUTE (Auteur) : la guérisseuse et la veuve ne sont jamais convaincues ; que Jehan
#     soit l'un des relevés n'est JAMAIS dit.
#
# ⚠️ UN SEUL FICHIER À IMPORTER : jsons/enquete_escolives_a_importer.json, qui porte AUSSI les
# docs du bestiaire des vampires (`gen_vampires.docs_vampires` : Abhartach, penanggalan,
# draugr et ce qui n'est pas encore en base), docs neufs ET Gautier retouché, chacun COMPLET (l'import est un PUT, CLAUDE.md §11). Gautier est RELU du
# dernier dump et seuls son service `apport`, ses choix d'entrée et ses nœuds `escolives_*`
# changent : régénération idempotente. ⚠️ `gen_mission_bucherons.py` et `gen_acces_donjon.py`
# réécrivent Gautier depuis des dumps FIGÉS plus anciens : les relancer et importer leur
# sortie effacerait cette quête.
#
# Usage : python dev/gen_enquete_escolives.py [jsons/telluris-dump-….json]

import copy
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gen_vampires import docs_vampires  # noqa: E402

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSONS = os.path.join(RACINE, "jsons")
SORTIE = os.path.join(JSONS, "enquete_escolives_a_importer.json")

QUETE = "quete:les_morts_d_escolives"
GAUTIER = "pnj:gautier_de_valcroix"
VILLAGE = "lieu:escolives"
CRYPTE = "lieu:crypte_de_la_necropole_d_escolives"
DONJON = "donjon:crypte_d_escolives"
LIEN = "link:escolives_to_france"
OSSEMENTS = "item:strigoi"
STRIGOI = "espece:strigoi"
FOSSOYEUR = "pnj:fossoyeur_gaspard_fouquet"
GUERISSEUSE = "pnj:guerisseuse_ysolde_vernier"
VEUVE = "pnj:veuve_perrine_vaudin"
PORTRAITS = {
	FOSSOYEUR: "fossoyeur_Gaspard_Fouquet_nain_m.jpg",
	GUERISSEUSE: "guerisseuse_Ysolde_Vernier_elfe_f.jpg",
	VEUVE: "veuve_Perrine_Vaudin_hobbit_f.jpg",
}
# Carte de France : Auxerre occupe (50,18)-(50,19) ; Escolives est à deux lieues au sud,
# sur l'Yonne — une case libre plus bas.
POS_FRANCE = [50, 21]

# La crypte s'ouvre tant que les ossements restent À RAPPORTER (ni avant la quête, ni une
# fois la preuve en poche) — les barrières n'ont pas de filtre `id` : la collecte se
# reconnaît à sa cible.
QUETE_A_FAIRE = {"quete_active": {"types": ["collect"], "cible": OSSEMENTS, "objectif_atteint": False}}

# Les villageois ne parlent de l'enquête que quête EN COURS (Auteur, 15/10) : AVANT, un simple
# bonjour ; APRÈS, ce que la quête a changé. La conjonction des deux `attendu: false` dit
# « jamais confiée » (une quête abandonnée y retombe) — `pnj.CONDITIONS_QUETE`.
AVANT = {"quete_active": {"id": QUETE, "attendu": False}, "quete_reussie": {"id": QUETE, "attendu": False}}
EN_COURS = {"quete_active": {"id": QUETE}}
APRES = {"quete_reussie": {"id": QUETE}}

# ── Grille de la crypte (image 768×1376, quadrillage de 15 × 27 cases) ─────────────────────
# '#' = 0 (roc, murs, niches) · '.' = 1 (dalles, terre, ossements épars) · 'x' = 3
# (sarcophages : on ne marche pas dessus, un volant les survole).
GRILLE_CRYPTE = [
	"###############",  # 0
	"###############",
	"######...######",  #    ossuaire (salle ronde au nord)
	"#####.....#####",
	"#####.....#####",
	"#####.....#####",  # 5
	"######...######",
	"######...######",  #    arche vers la salle des sarcophages
	"##...........##",
	"##...........##",
	"##........xx.##",  # 10
	"##.xxx.......##",
	"##.xxx....xx.##",
	"##........xx.##",
	"##.xxx.......##",  #    tombes ouvertes à l'ouest
	"##.xxx....xx.##",  # 15
	"##...........##",
	"##........xx.##",
	"##.xxx....xx.##",
	"##...........##",
	"######...######",  # 20 escalier d'entrée, au sud
	"######...######",
	"######...######",
	"######...######",
	"######...######",
	"######...######",  # 25
	"######...######",
]
CODES = {"#": 0, ".": 1, "x": 3}


def cells_crypte() -> list:
	return [[CODES[c] for c in ligne] for ligne in GRILLE_CRYPTE]


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


# ── Gautier : la quête, le rappel, la remise ──────────────────────────────────────────────

CHOIX_GAUTIER = [
	{"id": "escolives_offre", "label": "« On parle de morts, dans les villages du sud. »",
	 "condition": {"apport_offert": True}, "next": "escolives_propose"},
	{"id": "escolives_rappel", "label": "« Escolives… rappelez-moi. »",
	 "condition": {"apport_en_cours": True, "apport_possible": False}, "next": "escolives_rappel"},
	{"id": "escolives_remettre", "label": "« Voici ce qu'il y avait dans la crypte. »",
	 "condition": {"apport_possible": True}, "action": {"service": "apport", "op": "remettre"}},
	{"id": "escolives_souvenir", "label": "« Des nouvelles d'Escolives ? »",
	 "condition": {"quete_reussie": {"id": QUETE}}, "next": "escolives_souvenir"},
]

NOEUDS_GAUTIER = {
	"escolives_propose": {
		"texte": "Gautier ne répond pas tout de suite. Il cherche sur sa carte, au sud de la cité, un point minuscule au bord de l'Yonne, et y plante une épingle grise. « Escolives. Deux lieues d'ici, des vignes, un lavoir, une nécropole plus vieille qu'Auxerre. Sept morts en trois semaines. Le premier, un vigneron. Puis sa voisine, puis deux enfants, puis les autres. » Il croise les bras. « Le fossoyeur a rouvert les tombes. Il jure que les corps n'avaient pas pourri, qu'ils avaient du sang frais aux lèvres, et tout le village dit Strigoï. La guérisseuse, elle, dit fièvre, et puits souillé. »",
		"choix": [
			{"id": "details", "label": "« Et vous, qu'en dites-vous ? »", "next": "escolives_details"},
			{"id": "accepter", "label": "« J'irai voir. »", "action": {"service": "apport", "op": "accepter"}},
			{"id": "plus_tard", "label": "« Pas aujourd'hui. »", "next": "accueil"},
		],
	},
	"escolives_details": {
		"texte": "« Moi ? Je dis que je ne paie pas les rumeurs. » Il tapote l'épingle grise. « Si quelque chose sort de cette nécropole la nuit, il dort quelque part le jour : dans la crypte, sous les sarcophages. Le fossoyeur s'appelle Gaspard ; il a la clef et il a peur, ce qui le rend bavard. Descendez. S'il y a une bête, rapportez-m'en {objet}. S'il n'y a rien… » Il hausse une épaule. « Alors la guérisseuse avait raison, et ce n'est plus un travail pour la Guilde. »",
		"choix": [
			{"id": "accepter", "label": "« J'irai voir. »", "action": {"service": "apport", "op": "accepter"}},
			{"id": "plus_tard", "label": "« Pas aujourd'hui. »", "next": "accueil"},
		],
	},
	"escolives_accepte": {
		"texte": "Gautier note votre nom en marge, à côté de l'épingle grise. « La porte du sud, puis l'Yonne jusqu'aux vignes ; vous ne pouvez pas la manquer. » Il ajoute, sans lever les yeux : « Ne vous battez pas avec les villageois. Ils ont peur, et des gens qui ont peur déterrent leurs morts pour les brûler. Ce n'est pas votre affaire. La crypte, si. »",
		"choix": [{"id": "ok", "label": "« Messire. »", "next": "fin"}],
	},
	"escolives_rappel": {
		"texte": "« Escolives, au sud, sur l'Yonne. Gaspard le fossoyeur vous ouvrira la crypte. Ce que j'attends, c'est {objet} — pas un récit de veillée. »",
		"choix": [{"id": "ok", "label": "« J'y vais. »", "next": "fin"}],
	},
	"escolives_partiel": {
		"texte": "Gautier compte ce que vous posez sur la table. « Il en manque. Encore {reste}. »",
		"choix": [{"id": "ok", "label": "« J'y retourne. »", "next": "fin"}],
	},
	"escolives_remis": {
		"texte": "Gautier déplie le linge sur sa table et ne dit rien pendant un long moment. Des os d'Anthrope, mais tordus, ressoudés de travers, un crâne enfoncé qui a pourtant continué de mordre. Il les retourne du bout de sa plume. « Strigoï. » Il remplace l'épingle grise par une noire, pousse vers vous {prime} pièces de cuivre et porte {xp} points à votre nom. Puis, plus bas : « Que ce soit la chose qui tuait Escolives, ou une chose de plus, je ne le saurai pas. Le registre dira Strigoï. Vous, vous saurez ce que vous avez vu en bas. »",
		"choix": [{"id": "ok", "label": "« Messire. »", "next": "fin"}],
	},
	"escolives_souvenir": {
		"texte": "« Plus de morts depuis votre passage, à ce qu'on me dit. » Il regarde l'épingle noire. « La guérisseuse m'a écrit que la fièvre était tombée avec les premières gelées. Elle ne le dit pas pour vous contredire. Elle le dit parce que c'est vrai aussi. »",
		"choix": [{"id": "ok", "label": "Revenir.", "next": "accueil"}],
	},
}


def gautier(doc: dict) -> dict:
	doc = sans_rev(doc)
	doc.setdefault("services", {})["apport"] = {
		"offre": {
			"id": QUETE,
			"titre": "Les morts d'Escolives",
			"description": "Sept morts en trois semaines à Escolives, au sud d'Auxerre, sur l'Yonne. Le fossoyeur a rouvert les tombes et parle de Strigoï ; la guérisseuse parle de fièvre. Descendez dans la crypte de la nécropole et rapportez à Gautier de Valcroix la preuve de ce qui s'y terre.",
			"item": OSSEMENTS,
			"quantite": 1,
			"unique": True,
			"recompenses": {"xp": 120, "cuivre": 30000},
		},
		"noeuds": {"accepte": "escolives_accepte", "partiel": "escolives_partiel", "remis": "escolives_remis"},
	}
	noeuds = doc["dialogue"]["noeuds"]
	for nid in ("accueil", "commission_repos"):
		if nid in noeuds:
			poser_choix(noeuds[nid], CHOIX_GAUTIER)
	noeuds.update(copy.deepcopy(NOEUDS_GAUTIER))
	return doc


# ── Escolives : le village, ses trois PNJ, la crypte ──────────────────────────────────────

def fossoyeur() -> dict:
	return {
		"_id": FOSSOYEUR,
		"type": "pnj",
		"nom": "Gaspard Fouquet",
		"race": "nain",
		"vocation": "guerrier",
		"portrait": PORTRAITS[FOSSOYEUR],
		"description": "Le fossoyeur d'Escolives, appuyé sur sa pelle au bord des tombes rouvertes.",
		"services": {"acces": {"lieu": CRYPTE, "noeuds": {"ouvre": "crypte_ouverte", "refus": "crypte_close"}}},
		"dialogue": {
			"noeud_depart": "accueil",
			"noeuds": {
				"accueil": {
					"texte": "Au bord de la nécropole, un nain s'appuie sur sa pelle, entre deux tas de terre fraîche. Les sarcophages affleurent l'herbe comme des dos de bêtes endormies. Il vous dévisage sans se presser. « Le bonjour. Vous n'êtes pas d'ici. Gaspard, fossoyeur. »",
					"choix": [
						{"id": "bonjour", "label": "« Bonjour. Vous allez bien ? »", "condition": AVANT, "next": "bonjour"},
						{"id": "tombes", "label": "« Ces tombes rouvertes… »", "condition": EN_COURS, "next": "tombes"},
						# `acces_ouvrable` suppose la collecte en cours (barrière de la crypte).
						{"id": "guilde", "label": "« La Guilde d'Auxerre m'envoie. Ouvrez-moi la crypte. »",
						 "condition": {"acces_ouvrable": True}, "next": "seuil"},
						# `acces_libere` = la menace est tombée (état du MONDE), avant même le rapport.
						{"id": "apres", "label": "« Vous dormez, maintenant ? »",
						 "condition": {"acces_libere": True}, "next": "apres"},
						{"id": "fin", "label": "(Le laisser à ses tombes.)", "next": "fin"},
					],
				},
				"bonjour": {
					"texte": "« Je vais comme va un fossoyeur : je creuse, je couche, je recouvre. » Il essuie son front d'un revers de manche. « Les vignes sont belles, cette année, si vous passez par le coteau. Bonne route à vous. »",
					"choix": [{"id": "fin", "label": "« Bonne journée, Gaspard. »", "next": "fin"}],
				},
				"tombes": {
					"texte": "« C'est moi qui les ai rouvertes, oui. Personne ne voulait, alors je l'ai fait. » Il crache dans ses mains, comme pour reprendre la pelle, et ne la reprend pas. « Gonflés, qu'ils étaient. Pas un qui avait pourri. Les ongles longs, la peau rose, et du sang aux lèvres, du sang frais, comme s'ils venaient de boire. Et deux tombes vides. Vides, je vous dis, la terre grattée de l'intérieur. » Il désigne du menton une dalle, plus loin, à moitié enfouie. « La nuit, j'entends racler, là-dessous. Dans la crypte. »",
					"choix": [
						{"id": "qui", "label": "« À qui étaient les tombes vides ? »", "next": "qui"},
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
					],
				},
				"qui": {
					"texte": "Gaspard regarde longtemps le fond du trou qu'il vient de creuser. « Les deux derniers enterrés. » Il n'en dit pas davantage, et vous comprenez qu'il n'en dira pas davantage. « Il y a des veuves dans ce village. Je ne mets pas de noms sur des tombes vides. »",
					"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}],
				},
				"seuil": {
					"texte": "Gaspard vous mène jusqu'à la dalle à moitié enfouie, l'arrache de ses deux mains et dévoile un escalier qui s'enfonce dans le noir. Une odeur monte : terre mouillée, fer, et quelque chose de sucré qui donne envie de reculer. « Les sarcophages sont au fond, l'ossuaire derrière l'arche. » Il vous tend une torche. « Je reste en haut. Si c'est vous qui remontez, je vous ouvre. »",
					"choix": [
						{"id": "descendre", "label": "Descendre.", "condition": {"acces_ouvrable": True},
						 "action": {"service": "acces", "op": "passer"}},
						{"id": "attendre", "label": "« Pas encore. »", "next": "accueil"},
					],
				},
				"crypte_ouverte": {
					"texte": "Les marches sont glissantes. En bas, la torche n'éclaire que des couvercles repoussés et des os épars. Puis quelque chose bouge entre les sarcophages, à quatre pattes, la tête de travers sur un cou trop long. Un deuxième se déplie derrière lui, puis un troisième, au fond, sous l'arche de l'ossuaire. Ils ont eu des visages. Ils n'en ont plus.",
					"choix": [{"id": "ok", "label": "Tirer votre arme.", "next": "fin"}],
				},
				"crypte_close": {
					"texte": "Gaspard secoue la tête, la main sur sa clef. « Pas maintenant. »",
					"choix": [{"id": "ok", "label": "Reculer.", "next": "fin"}],
				},
				"apres": {
					"texte": "« Je dors, oui. » Il tasse la terre d'une tombe du plat de sa pelle, trois fois, comme on frappe à une porte. « Les morts restent couchés. Pour l'instant. » Il lève les yeux vers vous. « Vous direz à la Guilde que le fossoyeur d'Escolives n'avait pas rêvé. La guérisseuse, elle, ne le dira jamais. »",
					"choix": [{"id": "fin", "label": "(Le laisser à ses tombes.)", "next": "fin"}],
				},
			},
		},
	}


def guerisseuse() -> dict:
	return {
		"_id": GUERISSEUSE,
		"type": "pnj",
		"nom": "Ysolde Vernier",
		"race": "elfe",
		"vocation": "lettre",
		"portrait": PORTRAITS[GUERISSEUSE],
		"description": "La guérisseuse d'Escolives, entre ses herbes qui sèchent et ses fioles.",
		"dialogue": {
			"noeud_depart": "accueil",
			"noeuds": {
				"accueil": {
					"texte": "Une elfe aux tresses châtaines examine, à la lumière de la fenêtre, une coupe d'eau trouble. Des bouquets d'herbes sèchent au plafond. Elle ne pose pas la coupe pour vous saluer. « Si vous avez de la fièvre, asseyez-vous. Sinon, bonjour, et ne marchez pas sur mes herbes. »",
					"choix": [
						{"id": "bonjour", "label": "« Bonjour. Vous allez bien ? »", "condition": AVANT, "next": "bonjour"},
						{"id": "morts", "label": "« La Guilde m'envoie. De quoi meurt-on, à Escolives ? »",
						 "condition": EN_COURS, "next": "fievre"},
						{"id": "apres", "label": "« La crypte est vide, désormais. »",
						 "condition": APRES, "next": "apres"},
						{"id": "fin", "label": "(La laisser à son travail.)", "next": "fin"},
					],
				},
				"bonjour": {
					"texte": "« Assez bien, merci. La saison est chargée, on ne manque jamais de toux ni d'entorses. » Elle lève un instant les yeux vers vous. « Si vous repassez, j'ai un onguent pour les ampoules : les voyageurs en ont toujours. Bonne route. »",
					"choix": [{"id": "fin", "label": "« Merci. Bonne journée. »", "next": "fin"}],
				},
				"fievre": {
					"texte": "« Vous aussi, vous venez pour les vampires. » Elle ne pose pas la coupe. « On meurt de fièvre. » Elle fait tourner l'eau dans la coupe. « Une fièvre qui assoiffe, qui pâlit, qui vide les gens en quelques nuits. Tous ceux qui sont morts buvaient au puits du bas, celui qu'on a creusé trop près de la nécropole. Regardez cette eau. » Elle vous tend la coupe ; quelque chose y flotte, qui n'est pas de la terre. « Gaspard voit des Strigoï partout depuis qu'il creuse. Moi, je vois un puits souillé et des morts qu'on n'a pas laissés reposer. »",
					"choix": [
						{"id": "corps", "label": "« Et les corps qui n'ont pas pourri ? »", "next": "corps"},
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
					],
				},
				"corps": {
					"texte": "« La terre de la nécropole est froide et grasse. Elle garde les corps. » Elle hausse les épaules. « Le sang aux lèvres, un mort en rend souvent. Les ongles ont l'air de pousser parce que la peau se retire. Je l'ai vu cent fois. » Un temps. « Les tombes vides, je ne les explique pas. Mais je n'ai pas besoin d'un vampire pour ne pas savoir quelque chose. »",
					"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}],
				},
				"apres": {
					"texte": "Ysolde pose enfin sa coupe. « Vous avez tué des choses, en bas. Je ne le nie pas : Gaspard m'a montré le sang sur les marches. » Elle reprend un bouquet d'herbes, le défait brin à brin. « Mais Marthe, la fille du charron, a encore de la fièvre ce matin, et elle n'est jamais descendue dans aucune crypte. Vous avez tué ce qui vivait sous la nécropole. Vous n'avez pas guéri le village. » Elle ne vous regarde plus. « Ce sont peut-être deux choses différentes. C'est peut-être la même. Je ne le saurai qu'en voyant qui tombe malade cet hiver. »",
					"choix": [{"id": "fin", "label": "(La laisser à son travail.)", "next": "fin"}],
				},
			},
		},
	}


def veuve() -> dict:
	return {
		"_id": VEUVE,
		"type": "pnj",
		"nom": "Perrine Vaudin",
		"race": "hobbit",
		"vocation": "lettre",
		"portrait": PORTRAITS[VEUVE],
		"description": "Une veuve d'Escolives, sur le seuil de sa maison, devant une porte où l'on a cloué de l'aubépine.",
		"dialogue": {
			"noeud_depart": "accueil",
			"noeuds": {
				"accueil": {
					"texte": "Sur le seuil d'une maison de pierre blonde, une jeune hobbit en deuil se tient les bras croisés sur son châle. Quelqu'un a cloué une branche d'aubépine en fleur sur sa porte. Pas elle, à en juger par la façon dont elle la regarde. Elle vous salue d'un signe de tête.",
					"choix": [
						{"id": "bonjour", "label": "« Bonjour, madame. Vous allez bien ? »", "condition": AVANT, "next": "bonjour"},
						{"id": "aubepine", "label": "« Qui a cloué cette aubépine ? »",
						 "condition": EN_COURS, "next": "aubepine"},
						{"id": "apres", "label": "« C'est fini, en bas. »",
						 "condition": APRES, "next": "apres"},
						{"id": "fin", "label": "(La laisser.)", "next": "fin"},
					],
				},
				"bonjour": {
					"texte": "« On fait aller. Merci de demander. » Elle resserre son châle. « Le lavoir est en bas du chemin, si vous voulez faire boire vos bêtes. Bonne route. »",
					"choix": [{"id": "fin", "label": "« Bonne journée. »", "next": "fin"}],
				},
				"aubepine": {
					"texte": "« Les voisins. Pour que Jehan ne rentre pas. » Sa voix ne tremble pas. « Jehan, c'était mon mari. Le premier à mourir, alors c'est lui qu'ils accusent. Il est rentré des vignes un soir avec la fièvre, il a eu soif trois jours, et le quatrième il ne s'est pas réveillé. » Elle serre son châle. « Maintenant ils veulent le déterrer et le brûler, avec un pieu dans le cœur. Ils ne le feront pas. Pas tant que je serai devant cette porte. »",
					"choix": [
						{"id": "tombe", "label": "« Gaspard a rouvert les tombes… »", "next": "tombe"},
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
					],
				},
				"tombe": {
					"texte": "« Sans me demander. » Elle détourne les yeux vers la nécropole, au bout du chemin. « Je ne suis pas allée voir. Je ne lui ai pas demandé ce qu'il a vu. Si je le lui demande, il me le dira, et je ne pourrai plus jamais ne pas le savoir. »",
					"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}],
				},
				"apres": {
					"texte": "Perrine vous regarde longtemps, sans décroiser les bras. « Ce que vous avez tué, en bas… » Elle s'arrête. Ses lèvres bougent encore un peu, sans un son. Puis : « Non. Ne me répondez pas. » Elle se retourne, arrache l'aubépine de sa porte d'un seul geste et la jette dans le chemin. « Jehan dort où on l'a couché. C'est tout ce que je veux savoir. »",
					"choix": [{"id": "fin", "label": "(La laisser.)", "next": "fin"}],
				},
			},
		},
	}


def docs_neufs() -> list:
	return [
		{
			"_id": VILLAGE,
			"type": "lieu",
			"label": "Escolives",
			"image": "escolives.jpg",
			"categorie": "chemin",
			"lieu_parent": "lieu:france",
			"pnj": [
				{"character": FOSSOYEUR, "nom": "Gaspard", "portrait": PORTRAITS[FOSSOYEUR], "probabilite": 1,
				 "description": "Gaspard, le fossoyeur, appuyé sur sa pelle au bord de la nécropole."},
				{"character": GUERISSEUSE, "nom": "Ysolde", "portrait": PORTRAITS[GUERISSEUSE], "probabilite": 1,
				 "description": "Ysolde, la guérisseuse, dans sa maison aux herbes."},
				{"character": VEUVE, "nom": "Perrine", "portrait": PORTRAITS[VEUVE], "probabilite": 1,
				 "description": "Perrine, la veuve, sur le seuil de sa maison."},
			],
		},
		{
			"_id": LIEN,
			"type": "connection",
			"nodes": [
				{"lieu": "lieu:france", "pos": list(POS_FRANCE), "label": "Escolives"},
				{"lieu": VILLAGE, "pos": [0, 0], "label": "Reprendre la route"},
			],
			"metadata": {"type": "chemin", "status": "ouvert"},
		},
		fossoyeur(),
		guerisseuse(),
		veuve(),
		{
			"_id": CRYPTE,
			"type": "lieu",
			"label": "La crypte de la nécropole d'Escolives",
			"image": "crypte_de_la_necropole_d_escolives.jpg",
			"categorie": "battle_map",
			"dimensions": {"x": len(GRILLE_CRYPTE[0]), "y": len(GRILLE_CRYPTE)},
			"cells": cells_crypte(),
			"nav": {},
			"tags": ["sous-terrain", "crypte", "necropole", "humide", "couvert", "donjon"],
			"acces": {
				"gardien": FOSSOYEUR,
				"refus": "La crypte est silencieuse. Plus rien ne racle sous les dalles.",
				"cycle": 1,
				"conditions": [QUETE_A_FAIRE, {"combat_gagne": {"lieu": CRYPTE, "attendu": False}}],
			},
		},
		{
			"_id": DONJON,
			"type": "donjon",
			"nom": "La crypte d'Escolives",
			"description": "Sous la nécropole d'Escolives, une crypte de sarcophages et un ossuaire. Trois Strigoï s'y terrent le jour.",
			"portail": VILLAGE,
			# Strigoï plus fort qu'un loup géant à grade égal (F 45-70 contre 40-65) : un cran
			# sous les bûcherons (loups géants, grades 2-3), entrée au rang D. Non simulé.
			"niveau_min": 1,
			"niveau_max": 2,
			"battle_maps": [{
				"lieu": CRYPTE,
				"especes": [STRIGOI],
				"nb_monstres": 3,
				"niveau_min": 1,
				"niveau_max": 2,
			}],
		},
	]


def main(argv):
	dump = charger(dernier_dump(argv))
	par_id = {d["_id"]: d for d in dump["docs"]}
	for requis in (GAUTIER, STRIGOI, OSSEMENTS, "lieu:france"):
		if requis not in par_id:
			sys.exit(f"ERREUR : {requis} absent du dump")
	neufs = docs_neufs()
	collisions = [d["_id"] for d in neufs if d["_id"] in par_id]
	if collisions:
		print("⚠️ ids déjà présents au dump (écrasés par l'import) :", ", ".join(collisions))
	vampires, _deja = docs_vampires(par_id)
	docs = vampires + [gautier(par_id[GAUTIER])] + neufs
	ecrire(SORTIE, docs)
	print(f"{len(docs)} docs → {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
	main(sys.argv)
