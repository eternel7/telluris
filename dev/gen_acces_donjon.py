#!/usr/bin/env python
# dev/gen_acces_donjon.py
# Génère les fichiers d'import de la chaîne d'accès au donjon-mine de Saint-Austrelin :
#
#   rang D à Auxerre → Borin ouvre le bureau du maître de guilde
#   → Gautier de Valcroix mandate une commission d'éradication (quête `chasse`)
#   → George Dourdan laisse entrer dans le temple-portail (checkpoint de PRINCIPE)
#   → Armand de Vaucremont ouvre la mine (checkpoint SPÉCIFIQUE) = COMBAT
#
# ⚠️ POURQUOI UN SCRIPT ET PAS UN JSON ÉCRIT À LA MAIN : `admin_import_bulk` fait un PUT
# COMPLET, jamais un merge. Éditer un champ d'un doc existant oblige donc à reproduire TOUS
# ses autres champs — et parmi les docs à éditer il y a `lieu:la_mine_aux_cristaux`, une
# battle map de 60×40 cases (`cells` + table `nav`). Le retranscrire à la main serait le seul
# vrai risque de corruption de ce chantier : on le RELIT depuis son export et on n'y injecte
# que le bloc `acces`. Même traitement pour Borin (arbre de dialogue de ~250 lignes) et pour
# les deux lieux gardés.
#
# Usage : python dev/gen_acces_donjon.py
# Sorties (à coller dans /admin → Import en masse) :
#   jsons/acces_donjon_saint_austrelin_a_importer.json   (8 docs : gardes, portes, PNJ, donjon)
#   jsons/acces_donjon_mine_a_importer.json              (1 doc : la battle map + son acces)
#   jsons/acces_donjon_bureau_connexion_correctif.json   (1 doc : la porte comptoir ↔ bureau)
# Le troisième est un CORRECTIF ciblé (précédent : `jsons/carte_aventurier_correctif.json`) :
# les 8 autres docs étant déjà en base, il permet de n'importer que la porte manquante sans
# réécrire quoi que ce soit d'autre.

import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SOURCE UNIQUE : le dump complet de la base. Les docs qu'on ÉDITE en sont relus tels quels,
# et on n'y injecte que le champ ajouté — donc régénérer est idempotent, et une retouche faite
# à la main en base (un texte de Gautier, une case de la mine) survit à la régénération.
# ⚠️ Figé explicitement (et non « le glob le plus récent ») pour que régénérer donne toujours
# le même résultat ; à mettre à jour à la main après un nouveau dump.
SRC_DUMP = "jsons/telluris-dump-20260726-123742.json"

BUREAU_ID = "lieu:bureau_du_maitre_de_guilde_d_auxerre"
TEMPLE_INT_ID = "lieu:temple_portail_de_saint_austrelin_interieur"
MINE_ID = "lieu:la_mine_aux_cristaux"
CITE_ID = "lieu:auxerre"
DONJON_ID = "donjon:mine_de_saint_austrelin"

TEMPLE_EXT_ID = "lieu:temple_portail_de_saint_austrelin"
COMPTOIR_ID = "lieu:le_bastion_de_l_yonne_comptoir"

BORIN_ID = "pnj:borin_barbe_de_jais"
GEORGE_ID = "pnj:templier_nain_m_01"
ARMAND_ID = "pnj:templier_armand_de_vaucremont_01"
GAUTIER_ID = "pnj:gautier_de_valcroix"


def charger(chemin: str) -> list:
	"""Docs d'un export admin ou d'un dump : tableau nu, ou {"docs": [...]}."""
	with open(os.path.join(RACINE, chemin), encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


_BASE = None


def extraire(doc_id: str) -> dict:
	"""Le doc tel qu'il est EN BASE, jamais retapé. Sortie en erreur s'il manque : mieux vaut
	ne rien générer qu'un fichier d'import qui écraserait un doc par une version inventée."""
	global _BASE
	if _BASE is None:
		_BASE = {d["_id"]: d for d in charger(SRC_DUMP)
				 if isinstance(d, dict) and d.get("_id")}
	if doc_id not in _BASE:
		sys.exit(f"ERREUR : {doc_id} introuvable dans {SRC_DUMP}")
	return _BASE[doc_id]


# ── Blocs d'accès ────────────────────────────────────────────────────────────────

# 1. Le bureau du maître de guilde : porte de PRESTIGE, ouverte par le rang de guilde.
ACCES_BUREAU = {
	"gardien": BORIN_ID,
	"refus": "Borin Barbe-de-Jais barre l'escalier du fond d'un bras tranquille : "
			 "le bureau du maître de la Guilde n'est pas ouvert aux recrues.",
	"cycle": 1,
	"conditions": [{"rang_min": {"cite": CITE_ID, "rang": "D"}}],
}

# 2. Le temple-portail : checkpoint de PRINCIPE — « êtes-vous mandaté par la Guilde ? ».
#    Aucun filtre de `lieu` : George ne vérifie pas la destination, seulement le mandat.
ACCES_TEMPLE = {
	"gardien": GEORGE_ID,
	"refus": "Un templier en armure barre l'escalier du portail : la descente est "
			 "réservée aux compagnies mandatées par la guilde.",
	"cycle": 1,
	"conditions": [{"quete_active": {
		"types": ["chasse"],
		"giver_categorie": "bureau_maitre_guilde",
	}}],
}

# 3. La mine : checkpoint SPÉCIFIQUE — « mandaté pour CETTE mine ? ». Lieu `battle_map`,
#    donc franchir cette porte OUVRE LE COMBAT (aucun laissez-passer n'y est posé).
ACCES_MINE = {
	"gardien": ARMAND_ID,
	"refus": "Armand de Vaucremont barre l'accès à l'arche menant au portail : la "
			 "descente est réservée aux compagnies mandatées par la guilde.",
	"cycle": 1,
	"conditions": [{"quete_active": {
		"lieu": MINE_ID,
		"types": ["chasse"],
		"giver_categorie": "bureau_maitre_guilde",
		# ⚠️ CE FILTRE FERME LA BOUCLE. Sans lui, une commission ACCOMPLIE mais pas encore
		# rapportée reste dans `quetes_actives` et continue d'ouvrir la porte : le joueur
		# rejoue le combat du donjon autant de fois qu'il veut, en encaissant le butin à
		# chaque passage, tant qu'il ne va pas rendre compte. Constaté en jeu.
		"objectif_atteint": False,
	}}],
}


# ── Nouveaux nœuds de dialogue de Borin (il introduit auprès du maître) ───────────

BORIN_CHOIX = [
	{"id": "acces_passer", "label": "« Je voudrais voir le maître de la Guilde. »",
	 "condition": {"acces_ouvrable": True},
	 "action": {"service": "acces", "op": "passer"}},
	{"id": "acces_deja", "label": "« Je remonte au bureau. »",
	 "condition": {"acces_ouvert": True}, "next": "acces_deja"},
	{"id": "acces_pourquoi", "label": "« Qui dirige la Guilde, ici ? »",
	 "condition": {"acces_refuse": True}, "next": "acces_refus"},
]

BORIN_NOEUDS = {
	"acces_ouvre": {
		"texte": "« Rang {rang}, et mon registre en témoigne. » Borin repose sa plume, se "
				 "hisse sur la pointe des pieds et désigne l'escalier du fond. « Monte. "
				 "C'est là-haut : {portail}. Frappe, entre, et surtout — écoute. On ne "
				 "ressort jamais de ce bureau sans avoir appris quelque chose, même quand "
				 "on croyait n'y venir que pour un contrat. »",
		# Hook de déplacement automatique : le gardien vient de nous ouvrir, autant nous y
		# conduire. Sans lui, « Monter l'escalier » ne faisait que FERMER le dialogue et le
		# joueur se retrouvait au comptoir, à chercher le bouton du sous-lieu.
		"choix": [{"id": "ok", "label": "Monter l'escalier.", "next": "fin",
				   "deplacer": BUREAU_ID}],
	},
	"acces_refus": {
		"texte": "Le nain referme son registre d'un coup sec. « Le maître de la Guilde, "
				 "{prenom} ? Son bureau n'est pas une salle d'attente. On y monte quand la "
				 "Guilde sait ce qu'on vaut — rang D, pas moins. Tu en es à {rang}. » Il "
				 "se radoucit et tapote la couverture de cuir. « Fais allonger la ligne à "
				 "côté de ton nom. Je t'y conduirai moi-même. »",
		"choix": [{"id": "ok", "label": "J'y travaille.", "next": "fin"}],
	},
	"acces_deja": {
		"texte": "« Je sais, je sais — tu connais le chemin. » Il agite sa plume vers "
				 "l'escalier du fond sans même relever la tête. « Monte, {prenom}. »",
		"choix": [{"id": "ok", "label": "Monter l'escalier.", "next": "fin",
				   "deplacer": BUREAU_ID}],
	},
}


# ── George Dourdan : même hook de déplacement, pour ne pas avoir deux gardiens qui ──
# n'ouvrent pas la porte de la même façon (l'un vous fait entrer, l'autre vous laisse
# chercher le bouton). Son doc est déjà en base : on ne réécrit QUE le `deplacer` de ses
# nœuds `acces_ouvre`/`acces_deja`, le reste de son dialogue est relu tel quel.

GEORGE_NOEUDS_A_DEPLACER = ("acces_ouvre", "acces_deja")


# ── Armand de Vaucremont — gardien de l'arche du donjon-mine ─────────────────────
# ⚠️ Pas de nœud `deja` : la mine est un lieu `battle_map`, aucun laissez-passer n'y est
# jamais posé (chaque descente est un engagement neuf) → le flag `acces_ouvert` est
# structurellement toujours faux. Écrire ce nœud produirait du texte inatteignable.

ARMAND = {
	"_id": ARMAND_ID,
	"type": "pnj",
	"nom": "Armand de Vaucremont",
	"race": "humain",
	"vocation": "garde",
	"portrait": "templier_armand_de_vaucremont_temple_portail.png",
	"description": "Templier de la garde intérieure du Temple-Portail de Saint-Austrelin. "
				   "Armand de Vaucremont tient le registre des descentes : c'est lui qui "
				   "compte ceux qui entrent dans les galeries, et ceux qui en remontent. "
				   "Il n'a jamais aimé que les deux nombres diffèrent.",
	"services": {
		"acces": {
			"lieu": MINE_ID,
			"noeuds": {"ouvre": "acces_ouvre", "refus": "acces_refus"},
		},
	},
	"dialogue": {
		"noeud_depart": "accueil",
		"noeuds": {
			"accueil": {
				"texte": "Devant l'arche, le portail noir pulse faiblement derrière un "
						 "cordon de templiers en armes. {pnj} lève une main gantée sans "
						 "quitter des yeux le grand registre ouvert devant lui. "
						 "« Les papiers. »",
				"choix": [
					{"id": "passer", "label": "« J'ai une commission de la Guilde. »",
					 "condition": {"acces_ouvrable": True},
					 "action": {"service": "acces", "op": "passer"}},
					{"id": "accompli", "label": "« C'est fait. La chose est morte. »",
					 "condition": {"acces_accompli": True}, "next": "acces_accompli"},
					{"id": "pourquoi", "label": "« Pourquoi cette arche est-elle fermée ? »",
					 "condition": {"acces_refuse": True}, "next": "acces_refus"},
					{"id": "registre", "label": "« Que notez-vous dans ce registre ? »",
					 "next": "registre"},
					# Même question, deux réponses selon l'état du LIEU (pas de la quête) :
					# les flags `acces_menace`/`acces_libere` sont complémentaires, donc le
					# joueur ne voit jamais qu'une seule de ces deux lignes.
					{"id": "mineurs", "label": "« Et ces mineurs qui attendent ? »",
					 "condition": {"acces_menace": True}, "next": "mineurs"},
					{"id": "mineurs_libres", "label": "« Et ces mineurs qui attendent ? »",
					 "condition": {"acces_libere": True}, "next": "mineurs_libres"},
					{"id": "rien", "label": "« Rien. Je regardais. »", "next": "fin"},
				],
			},
			"acces_ouvre": {
				"texte": "Il compare le sceau de la Guilde à celui de son registre, hoche "
						 "la tête une fois, puis trace une croix nette à côté de votre nom. "
						 "« Commission enregistrée. » Un geste sec : le cordon de templiers "
						 "s'ouvre sur l'arche. « En bas, c'est {portail}. Descendez tant que "
						 "le portail est calme — et sachez-le tout de suite : personne "
						 "n'ira vous chercher. »",
				"choix": [{"id": "fin", "label": "Franchir l'arche.", "next": "fin"}],
			},
			"acces_refus": {
				"texte": "« Pas de commission, pas de descente. » Armand repousse le "
						 "registre du plat de la main. « {portail} est fermée sur ordre du "
						 "temple : les galeries ne rouvriront qu'une fois l'éradication "
						 "confirmée par une compagnie mandatée. Et ce n'est pas moi qui "
						 "délivre les mandats, {prenom} — c'est la Guilde d'Aventuriers. »",
				"choix": [{"id": "fin", "label": "S'écarter.", "next": "fin"}],
			},
			# Mission remplie, rapport pas encore rendu : la barrière s'est refermée et le
			# gardien DOIT le dire autrement qu'en récitant son refus (flag `acces_accompli`,
			# qui exclut `acces_refuse`). Il renvoie explicitement vers la Guilde — sans quoi
			# le joueur chercherait la sortie de la boucle sans savoir où aller.
			"acces_accompli": {
				"texte": "Pour la première fois, Armand referme son registre. « Nous avons "
						 "entendu, d'en haut. Puis nous n'avons plus rien entendu du tout — "
						 "et c'est à ce silence qu'on reconnaît le travail fait. » Il "
						 "s'écarte de l'arche, mais d'un geste large qui vous invite à "
						 "remonter, pas à descendre. « Ne redescendez pas, {prenom} : les "
						 "galeries ne sont plus votre affaire, ce sont les mineurs qui "
						 "attendent leur tour. Portez votre rapport à la Guilde — c'est "
						 "lui, maintenant, qui rouvrira le chantier. »",
				"choix": [{"id": "fin", "label": "Remonter faire mon rapport.", "next": "fin"}],
			},
			"registre": {
				"texte": "« Deux colonnes. » Il tourne le registre vers vous sans le "
						 "lâcher. « À gauche, ceux qui descendent. À droite, ceux qui "
						 "remontent. Mon travail consiste à ce que les deux colonnes aient "
						 "la même longueur. » Un silence. « Elles ne l'ont pas eue depuis "
						 "trois semaines. »",
				"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}],
			},
			"mineurs": {
				"texte": "Il jette un regard vers la compagnie de mineurs qui piétine "
						 "au fond de la nef, lampes éteintes. « Ils viennent chaque matin "
						 "demander l'accès, et chaque matin je le refuse. Ce ne sont pas "
						 "des combattants : les envoyer maintenant, ce serait les envoyer "
						 "mourir avec leurs pics. Le chantier attend des aventuriers. »",
				"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}],
			},
			# Variante « la mine est purgée » : le monde a changé, et c'est le détail qui le
			# montre — les lampes sont allumées, la file avance. Rappelle le nœud `registre`
			# (« deux colonnes de la même longueur »), qui était son inquiétude de départ.
			"mineurs_libres": {
				"texte": "Les lampes sont allumées, cette fois. La compagnie s'engage sous "
						 "l'arche en file lente, pics à l'épaule, et {pnj} les compte à "
						 "voix basse en cochant son registre. « Vingt-deux descendus. » Il "
						 "laisse courir son doigt jusqu'à la colonne de droite, encore "
						 "vide, et la tapote une fois. « Vingt-deux qui remonteront ce "
						 "soir. C'est la première fois depuis des semaines que j'écris ce "
						 "chiffre sans me mentir — et c'est votre ouvrage qu'ils piétinent, "
						 "là-dessous. »",
				"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}],
			},
		},
	},
}


# ── Gautier de Valcroix — maître de la Guilde d'Auxerre ──────────────────────────

GAUTIER = {
	"_id": GAUTIER_ID,
	"type": "pnj",
	"nom": "Gautier de Valcroix",
	"race": "humain",
	"vocation": "guerrier",
	"portrait": "humain_m_guerrier01.jpg",
	"description": "L'homme qui dirige la Guilde des Aventuriers d'Auxerre est connu de "
				   "tous sous le nom de Gautier de Valcroix, que l'on surnomme parfois le "
				   "Gardien des Cartes.\n"
				   "Ancien capitaine d'une compagnie d'éclaireurs, il ne s'est jamais "
				   "distingué par sa force, mais par son jugement. Les murs de son bureau "
				   "sont couverts de cartes annotées, de rapports d'expéditions et de "
				   "trophées rapportés par ceux qui ont survécu à leurs premières "
				   "missions. On raconte qu'aucun aventurier ne quitte son bureau sans "
				   "avoir appris quelque chose, même lorsqu'il croit n'être venu que "
				   "chercher un contrat.",
	"services": {
		"commission": {
			"donjon": DONJON_ID,
			"noeuds": {"accepte": "commission_accepte", "rapporte": "commission_rapporte"},
		},
	},
	"dialogue": {
		"noeud_depart": "accueil",
		"noeuds": {
			"accueil": {
				"texte": "Le bureau sent le vélin et la cire. Penché sur une carte hérissée "
						 "d'épingles, {pnj} ne lève pas les yeux tout de suite — il termine "
						 "d'annoter une marge, pose sa plume, et vous regarde enfin. "
						 "« {prenom}. Borin vous a fait monter, donc vous valez le "
						 "déplacement. Asseyez-vous. »",
				"choix": [
					{"id": "commission", "label": "« Vous avez du travail pour moi ? »",
					 "condition": {"commission_offerte": True}, "next": "commission_propose"},
					{"id": "commission_rapport",
					 "label": "« C'est fait. La bête ne tient plus les galeries. »",
					 "condition": {"commission_a_rapporter": True},
					 "action": {"service": "commission", "op": "rapporter"}},
					{"id": "commission_relance", "label": "« Où en étais-je, déjà ? »",
					 "condition": {"commission_en_cours": True}, "next": "commission_relance"},
					{"id": "cartes", "label": "« Toutes ces cartes... »", "next": "cartes"},
					{"id": "trophees", "label": "« Et ces trophées, au mur ? »",
					 "next": "trophees"},
					{"id": "rien", "label": "« Rien. Je voulais voir le bureau. »",
					 "next": "fin"},
				],
			},
			"commission_propose": {
				"texte": "Il fait glisser vers vous un parchemin déjà scellé. « Une "
						 "commission d'éradication. Le temple a fermé un chantier : "
						 "{lieu}. Ce n'est pas la vermine ordinaire qui l'inquiète, c'est "
						 "ce qui la commande — un {espece} d'exception, assez vieux pour "
						 "avoir fait des galeries son territoire. » Il repose son doigt sur "
						 "la carte, exactement sur l'épingle noire. « Abattez-le. Les "
						 "mineurs feront le reste. {xp} points d'expérience et {prime} "
						 "pièces de cuivre à votre retour — et le chantier vous devra sa "
						 "réouverture. »",
				"choix": [
					{"id": "commission_details", "label": "« Qui garde l'entrée ? »",
					 "next": "commission_details"},
					{"id": "commission_accepter", "label": "« Donnez-moi ce parchemin. »",
					 "action": {"service": "commission", "op": "accepter"}},
					{"id": "commission_refuser", "label": "« Pas ce chantier-là. »",
					 "next": "accueil"},
				],
			},
			"commission_details": {
				"texte": "« Les templiers de Saint-Austrelin. » Il hausse un sourcil, "
						 "amusé. « Deux barrages : l'un au sommet des marches, qui vérifie "
						 "que la Guilde répond de vous ; l'autre devant l'arche, qui "
						 "vérifie que c'est bien de CE chantier qu'on vous a chargé. Ils "
						 "sont tatillons, et ils ont raison de l'être : le sceau que je "
						 "vous donne est la seule chose qui ouvre les deux. »",
				"choix": [
					{"id": "commission_accepter", "label": "« Donnez-moi ce parchemin. »",
					 "action": {"service": "commission", "op": "accepter"}},
					{"id": "commission_refuser", "label": "« Laissez-moi y réfléchir. »",
					 "next": "accueil"},
				],
			},
			"commission_accepte": {
				"texte": "Il presse son cachet sur la cire, souffle dessus, et vous tend le "
						 "parchemin. « Vous cherchez un {espece} dans {lieu}. Une seule "
						 "consigne, et elle n'est pas dans le texte : ce qui a tenu des "
						 "galeries entières ne se laisse pas surprendre. » Il reprend sa "
						 "plume et se penche déjà sur une autre carte. « Revenez me le dire "
						 "vous-même. J'aime tenir mes registres à jour. »",
				"choix": [{"id": "ok", "label": "« Ce sera fait. »", "next": "fin"}],
			},
			"commission_relance": {
				"texte": "Il suit du doigt une ligne de son registre. « Vous. Un {espece}, "
						 "dans {lieu}. » Il relève les yeux. « Le chantier est toujours "
						 "fermé, {prenom}, et les mineurs comptent les jours. »",
				"choix": [{"id": "ok", "label": "« J'y retourne. »", "next": "fin"}],
			},
			"commission_rapporte": {
				"texte": "Gautier écoute jusqu'au bout sans vous interrompre une seule "
						 "fois, puis prend une épingle blanche et remplace la noire sur sa "
						 "carte. « {lieu} : rouvert. » Il pousse vers vous {prime} pièces "
						 "de cuivre, et {xp} points portés à votre nom sur le registre. "
						 "« Vous avez rapporté le fait, pas la légende — c'est plus rare "
						 "que vous ne croyez, et c'est ce qui me dira, la prochaine fois, "
						 "à qui confier un chantier plus profond. » Il désigne le mur "
						 "couvert de cartes. « Il en reste. »",
				"choix": [{"id": "ok", "label": "« Merci, messire. »", "next": "fin"}],
			},
			"cartes": {
				"texte": "« Elles ne valent rien. » Il dit cela sans quitter des yeux le "
						 "mur qu'il a passé vingt ans à couvrir. « Une carte est le "
						 "souvenir de ce qu'un homme a vu un jour donné. Les galeries "
						 "s'effondrent, les rivières changent de lit, les monstres "
						 "déménagent. Ce qui vaut quelque chose, c'est l'aventurier qui "
						 "revient corriger la mienne. »",
				"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}],
			},
			"trophees": {
				"texte": "Il jette un œil à la rangée de crânes, de griffes et de mâchoires "
						 "clouées au-dessus de la cheminée. « Aucun n'est de moi. Chacun a "
						 "été rapporté par une recrue qui pensait ne pas revenir. » Un "
						 "silence. « Je garde aussi la liste de celles qui n'ont rien "
						 "rapporté. Elle est plus longue, et je la relis plus souvent. »",
				"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}],
			},
		},
	},
}


# ── Les deux portes de la chaîne ────────────────────────────────────────────────
#
# ⚠️ RÈGLE APPRISE DEUX FOIS : **un bloc `acces` n'est pas une porte.** Il dit à quelles
# conditions on FRANCHIT une porte ; c'est le doc `connection` qui la CREUSE. Sans lui, le
# gardien pose bien son laissez-passer, `get_lieu_links` ne trouve aucun lien à révéler, et
# le lieu reste **structurellement** inatteignable — sans aucun message d'erreur : le joueur
# voit le dialogue réussir (« Monte, c'est là-haut ») puis se retrouve exactement où il
# était. Le symptôme observé (« le clic ramène au comptoir ») est simplement le panneau de
# dialogue qui se ferme. Vérification qui l'aurait attrapé tout de suite : un BFS sur les
# docs `connection` depuis la cité, en ignorant les barrières — un lieu à zéro voisin est
# un cul-de-sac, quoi que dise son bloc `acces`.
#
# Gabarit commun : `link:bastion_comptoir_to_bastion_interieur` — deux sous-lieux d'une même
# cité, aucun des deux n'ayant de grille, donc `pos: [0, 0]` de part et d'autre (comme toutes
# les boutiques). ⚠️ Le **`label` par nœud** n'est pas décoratif : `get_lieu_links` fait
# `node["details"]["label"] = node.get("label") or doc.get("label")` → c'est lui qui nomme le
# BOUTON du sous-lieu. Sans label, le bouton afficherait le nom du lieu (« Bureau de Gautier
# de Valcroix, Maitre de la Guilde d'Aventuriers d'Auxerre »), là où la convention maison est
# de nommer le GESTE (« s'approcher du comptoir », « sortir dans la rue »).
# `metadata` n'est lu par AUCUN code (purement descriptif) : on suit la famille du voisinage.
#
# 1. Comptoir ↔ bureau du maître. Accroché au COMPTOIR et non à la salle commune : c'est là
#    que Borin se tient, et c'est lui qui ouvre — « il désigne l'escalier du fond ». Le
#    libellé du bouton reprend mot pour mot le geste qu'il annonce.
#
# 2. Parvis ↔ nef du temple. Sans ce lien, Armand (qui se tient dans la nef) est
#    inatteignable et la chaîne s'arrête au sommet des marches.
#
# Gabarit : `link:bastion_comptoir_to_bastion_interieur` — deux sous-lieux d'une même cité,
# aucun des deux n'ayant de grille, donc `pos: [0, 0]` de part et d'autre (comme toutes les
# boutiques). ⚠️ Le **`label` par nœud** n'est pas décoratif : `get_lieu_links` fait
# `node["details"]["label"] = node.get("label") or doc.get("label")` → c'est lui qui nomme le
# BOUTON du sous-lieu. Sans label, le bouton afficherait le nom du lieu (« Le portail du
# Temple-Portail de Saint-Austrelin »), là où la convention maison est de nommer le GESTE
# (« s'approcher du comptoir », « sortir dans la rue »).
#
# ⚠️ Le sens de la barrière est porté par le LIEU, pas par ce lien (cf. utils/acces.py) :
# `get_lieu_links` masque la connexion tant que le nœud DESTINATION est verrouillé, donc la
# nef reste invisible depuis le parvis jusqu'à ce que George ouvre — et le parvis, lui, n'a
# pas de bloc `acces`, ce qui garantit qu'on puisse TOUJOURS ressortir (aucun enfermement,
# même si le laissez-passer périme pendant qu'on est à l'intérieur).
# `metadata` n'est lu par aucun code (purement descriptif) : on suit les 3 liens de temple
# existants (`type: "temple"`).

CONNEXION_BUREAU = {
	"_id": "link:bastion_bureau_maitre_to_bastion_comptoir",
	"type": "connection",
	"nodes": [
		{"lieu": COMPTOIR_ID, "pos": [0, 0],
		 "label": "redescendre au comptoir"},
		{"lieu": BUREAU_ID, "pos": [0, 0],
		 "label": "monter l'escalier du fond"},
	],
	"metadata": {"type": "guilde_aventurier", "status": "ouvert"},
}

CONNEXION_TEMPLE = {
	"_id": "link:temple_portail_saint_austrelin_interieur_to_exterieur",
	"type": "connection",
	"nodes": [
		{"lieu": TEMPLE_EXT_ID, "pos": [0, 0],
		 "label": "redescendre sur le parvis"},
		{"lieu": TEMPLE_INT_ID, "pos": [0, 0],
		 "label": "franchir le seuil du sanctuaire"},
	],
	"metadata": {"type": "temple", "status": "ouvert"},
}


# ── Le donjon ───────────────────────────────────────────────────────────────────
# Curaté à la main : c'est tout l'objet du type `donjon:*` (une battle map n'a ni zones
# d'influence ni rencontres où placer des espèces — cf. l'en-tête d'utils/donjon.py).
# Casting cohérent avec une mine : gobelins pillards, rats des galeries, chauves-souris des
# grottes, araignées de tunnel.
#
# ⚠️ ÉQUILIBRAGE — `niveau_max: 3` n'est pas décoratif. C'est la PREMIÈRE commission qu'un
# joueur peut prendre (elle s'ouvre au rang D) et le donjon n'a pas de zones d'influence pour
# borner ses grades : sans plafond, l'élite prend le profil de plus haut niveau de la base
# (niveau 6). Mesuré sur un personnage type à 1D6+2 de dégâts, cela donne 300 à 400 PV
# derrière 5 points d'armure — plusieurs centaines de coups portés, donc un combat qu'on ne
# peut pas gagner. Au plafond 3, l'élite la plus dure du casting (l'araignée géante) demande
# ~55 coups, ce qui reste rude et se joue en groupe.
#
# ⚠️ `espece:golem_de_pierre` est VOLONTAIREMENT absent, malgré son évidence thématique dans
# un filon de cristal : c'est un mur à TOUS les grades (260 PV et 3 d'armure dès le niveau 1,
# ~115 coups) — le plafond de grade n'y change rien, c'est l'espèce. Il a sa place dans un
# donjon plus profond, pas dans une commission d'entrée.

DONJON = {
	"_id": DONJON_ID,
	"type": "donjon",
	"nom": "Le donjon-mine de Saint-Austrelin",
	"description": "Sous le Temple-Portail de Saint-Austrelin, les galeries d'un ancien "
				   "filon de cristal s'enfoncent au-delà de ce que les registres du temple "
				   "savent décrire. Le chantier est fermé : quelque chose y a pris ses "
				   "quartiers.",
	"portail": TEMPLE_INT_ID,
	"niveau_max": 3,
	"battle_maps": [
		{
			"lieu": MINE_ID,
			"especes": [
				"espece:gobelin",
				"espece:gobelin_chamanique",
				"espece:rat_geant",
				"espece:chauve_souris_geante",
				"espece:araignee_geante",
			],
		},
	],
}


def main() -> None:
	# 1. Les quatre docs à ÉDITER : relus depuis la base, jamais retapés.
	bureau = extraire(BUREAU_ID)
	temple_int = extraire(TEMPLE_INT_ID)
	mine = extraire(MINE_ID)
	borin = extraire(BORIN_ID)
	# Garde-fou : les deux portes doivent relier des lieux QUI EXISTENT, sinon
	# `get_lieu_links` planterait sur `doc.pop` (il suppose le doc présent).
	for conn in (CONNEXION_BUREAU, CONNEXION_TEMPLE):
		for node in conn["nodes"]:
			extraire(node["lieu"])

	bureau["acces"] = ACCES_BUREAU
	temple_int["acces"] = ACCES_TEMPLE
	mine["acces"] = ACCES_MINE

	# 2. Borin gagne le service `acces` + les 3 choix et les 3 nœuds qui vont avec.
	borin.setdefault("services", {})["acces"] = {
		"lieu": BUREAU_ID,
		"noeuds": {"ouvre": "acces_ouvre", "refus": "acces_refus", "deja": "acces_deja"},
	}
	noeuds = borin["dialogue"]["noeuds"]
	accueil = noeuds["accueil"]["choix"]
	deja_poses = {c.get("id") for c in accueil}
	# Insérés AVANT le « je ne faisais que passer » final, pour que la sortie reste en bas.
	nouveaux = [c for c in BORIN_CHOIX if c["id"] not in deja_poses]
	i_rien = next((i for i, c in enumerate(accueil) if c.get("id") == "rien"), len(accueil))
	borin["dialogue"]["noeuds"]["accueil"]["choix"] = (
		accueil[:i_rien] + nouveaux + accueil[i_rien:]
	)
	noeuds.update(BORIN_NOEUDS)

	# 2 bis. George gagne le même hook de déplacement (son dialogue est relu depuis la base ;
	#        on ne touche QUE le `deplacer` des choix de ses nœuds d'ouverture).
	george = extraire(GEORGE_ID)
	g_noeuds = (george.get("dialogue") or {}).get("noeuds") or {}
	for nid in GEORGE_NOEUDS_A_DEPLACER:
		for c in (g_noeuds.get(nid) or {}).get("choix") or []:
			if not c.get("action"):          # jamais sur un choix qui déclenche un service
				c["deplacer"] = TEMPLE_INT_ID

	# 3. Trois fichiers. La mine est à part parce qu'elle pèse à elle seule 60×40 cases —
	#    l'isoler rend le diff des autres docs lisible à l'œil. Le correctif de la porte du
	#    bureau l'est parce que tout le reste est DÉJÀ en base : on ne réimporte pas huit docs
	#    pour en ajouter un (précédent `jsons/carte_aventurier_correctif.json`). Il figure
	#    quand même dans le fichier principal, pour qu'une installation à neuf soit complète.
	principal = [bureau, borin, CONNEXION_BUREAU, temple_int, CONNEXION_TEMPLE,
				 george, ARMAND, GAUTIER, DONJON]
	sorties = [
		("jsons/acces_donjon_saint_austrelin_a_importer.json", principal),
		("jsons/acces_donjon_mine_a_importer.json", [mine]),
		("jsons/acces_donjon_bureau_connexion_correctif.json", [CONNEXION_BUREAU]),
	]
	for chemin, docs in sorties:
		with open(os.path.join(RACINE, chemin), "w", encoding="utf-8") as f:
			json.dump(docs, f, ensure_ascii=False, indent=2)
			f.write("\n")
		ids = ", ".join(d["_id"] for d in docs)
		print(f"écrit {chemin}\n   {len(docs)} doc(s) : {ids}")


if __name__ == "__main__":
	main()
