#!/usr/bin/env python
# dev/gen_piece_derriere_le_mur.py
# « La pièce derrière le mur » — première quête d'Aélis après Jumièges, rang C
# (docs/lore/personnages/20261119_la_piece_derriere_le_mur.md, arbitrages de l'Auteur du 19/11 ;
# système d'énigmes : docs/conception_enigmes.md).
#
#   Départs : Aélis (Archives des Seuils) et Maître Villard (Cour des Arches) OFFRENT l'escorte
#   (même quête, `unique`) ; Maëlys et Éléonore de Vaugirard ORIENTENT vers Villard (réplique).
#   Condition commune : Jumièges réussie.
#   Escorte : Aélis rejoint le groupe à l'acceptation ; dépose au SEUIL DE LA BOÎTE, lieu gardé
#   par l'énigme de sortie — la quête ne se rend pas sans avoir traversé la boîte.
#
#   Chaîne (croisement façon Myst, un seul retour) :
#     Ateliers de Convergence : la réserve (déduction) → le meuble (crans ; plan dans le carnet)
#     → la cave aux cinq arches (graphe ; ordre cousu sur le tissu du meuble) → le Púca
#     (association) → la maison pliée : la Zashiki-warashi (placement) → le plan impossible
#     (réseau ; règle gravée sous la plaque) → l'Homme au sac et trois Nopperabō (salle à
#     composition fixe) → la porte de sortie (placement ; le sceau vu sous le socle au début).
#
# ⚠️ UN SEUL FICHIER À IMPORTER : jsons/piece_derriere_le_mur_a_importer.json. PNJ et lieu déjà
# en base RELUS du dernier dump (seuls les choix, nœuds, services et la présence ajoutés
# changent : régénération idempotente) + docs neufs COMPLETS (l'import est un PUT, CLAUDE.md §11).
#
# Usage : python dev/gen_piece_derriere_le_mur.py [jsons/telluris-dump-….json]

import copy
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from utils import enigmes as enigmes_util  # noqa: E402
from utils import lint_dialogues  # noqa: E402

JSONS = os.path.join(RACINE, "jsons")
SORTIE = os.path.join(JSONS, "piece_derriere_le_mur_a_importer.json")

QUETE = "quete:piece_derriere_le_mur"
JUMIEGES = "quete:escorte_aelis_abbaye_de_jumieges"
LUTECIA = "lieu:lutecia"

COUR = "lieu:la_cour_des_arches"
ARCHIVES = "lieu:les_archives_des_seuils"
ATELIERS = "lieu:les_ateliers_de_convergence"
CAVE = "lieu:cave_aux_cinq_arches"
MAISON = "lieu:maison_pliee"
CHAMBRE = "lieu:chambre_du_sac"
SEUIL = "lieu:seuil_de_la_boite"
DONJON = "donjon:maison_pliee"

VILLARD = "pnj:villard_de_honnecourt"
AELIS_ARCHIVES = "pnj:aelis_de_montfaucon_archives"
MAELYS = "pnj:maelys"
ELEONORE = "pnj:eleonore_de_vaugirard"
AELIS_ATELIERS = "pnj:aelis_de_montfaucon_ateliers"
AELIS_CAVE = "pnj:aelis_de_montfaucon_cave"
AELIS_MAISON = "pnj:aelis_de_montfaucon_maison"
PUCA = "pnj:puca"
ZASHIKI = "pnj:zashiki_warashi"

HOMME_AU_SAC = "espece:homme_au_sac"
NOPPERABO = "espece:nopperabo"

E_RESERVE = "enigme:reserve_de_villard"
E_MEUBLE = "enigme:meuble_aux_trois_tiroirs"
E_ARCHES = "enigme:cave_aux_cinq_arches"
E_PUCA = "enigme:propositions_du_puca"
E_PLAN_MAISON = "enigme:maison_de_la_zashiki_warashi"
E_PLAN_IMPOSSIBLE = "enigme:plan_impossible"
E_SORTIE = "enigme:porte_de_sortie"

PORTRAIT_AELIS = "architecte_Aélis_de_Montfaucon_dans_les_invalides.jpg"  # sans blessure (Auteur, 19/11)
# Aélis dans les Ateliers de Convergence : portrait propre au lieu (Auteur, 19/11).
PORTRAIT_AELIS_ATELIERS = "architecte_Aélis_de_Montfaucon_ateliers.jpg"
# Aélis dans la cave aux cinq arches : portrait propre au lieu (Auteur, 20/11).
PORTRAIT_AELIS_CAVE = "architecte_Aélis_de_Montfaucon_cave.jpg"

# Présences et conditions — les trois états (AVANT · PENDANT · APRÈS, telluris-quetes-pnj).
ESCORTE_ACTIVE = {"quete_active": {"types": ["escorte"], "cible": SEUIL}}
AVANT = {"quete_active": {"id": QUETE, "attendu": False}, "quete_reussie": {"id": QUETE, "attendu": False}}
PENDANT = {"quete_active": {"id": QUETE}}
APRES = {"quete_reussie": {"id": QUETE}}


# ---------------------------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------------------------

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


def choix(id_, label, next_=None, **kw):
	c = {"id": id_, "label": label}
	if next_:
		c["next"] = next_
	c.update(kw)
	return c


def noeud(texte, *les_choix, **kw):
	n = {"texte": texte, "choix": list(les_choix)}
	n.update(kw)
	return n


def ajouter_choix(doc, noeud_id, nouveaux, en_tete=False):
	"""Ajoute des choix à un nœud RELU, en remplaçant ceux de même id (idempotent)."""
	n = doc["dialogue"]["noeuds"][noeud_id]
	ids = {c["id"] for c in nouveaux}
	garde = [c for c in n.get("choix", []) if c.get("id") not in ids]
	n["choix"] = (nouveaux + garde) if en_tete else (garde[:-1] + nouveaux + garde[-1:] if garde else nouveaux)


def lien(id_, a, label_a, b, label_b):
	return {"_id": id_, "type": "connection",
			"nodes": [{"lieu": a, "pos": [0, 0], "label": label_a}, {"lieu": b, "pos": [0, 0], "label": label_b}],
			"metadata": {"type": "institut_des_architectes", "status": "ouvert"}}


def entree_pnj(pnj_id, nom, portrait, description, conditions):
	return {"character": pnj_id, "nom": nom, "portrait": portrait, "probabilite": 1,
			"conditions": conditions, "description": description}


def pnj_doc(id_, nom, race, description, portrait, noeuds, depart="accueil", vocation=None, services=None):
	d = {"_id": id_, "type": "pnj", "nom": nom, "race": race, "portrait": portrait,
		 "description": description, "dialogue": {"noeud_depart": depart, "noeuds": noeuds}}
	if vocation:
		d["vocation"] = vocation
	if services:
		d["services"] = services
	return d


def aelis(quand, texte):
	return {"quand": quand, "qui": {"protege": "Aélis"}, "texte": texte}


def compagnon(vocation, quand, texte):
	return {"quand": quand, "qui": {"vocation": vocation}, "texte": texte}


# ---------------------------------------------------------------------------------------------
# L'offre d'escorte (portée par Aélis ET par Villard : même quête, `unique`)
# ---------------------------------------------------------------------------------------------

def offre_escorte():
	return {
		"id": QUETE,
		"titre": "La pièce derrière le mur",
		"description": "Une petite boîte de métal, gravée de figures, a quitté une armoire fermée "
					   "des Ateliers de Convergence sans en passer la porte. Maître Villard la veut "
					   "de retour, et Aélis de Montfaucon veut comprendre. Accompagnez-la jusqu'à "
					   "la boîte et ramenez-la vivante, de l'autre côté de ce qu'elle a ouvert. "
					   "Elle ne sait pas se battre.",
		"destination": SEUIL,
		"proteges": [{"prenom": "Aélis", "nom": "de Montfaucon", "race": "humain", "sex": "F",
					  "image": PORTRAIT_AELIS,
					  "description": "Architecte de l'Institut, rentrée de Jumièges avec un carnet que "
									 "rien n'explique tout à fait. Un compas, un carnet, un crayon. "
									 "Elle ne sait pas se battre."}],
		"unique": True,
		"proba": 1,
		"rang_min": {"cite": LUTECIA, "rang": "D"},
		# Barème de l'escorte de Jumièges + la Besace offerte par Villard (Auteur, 19/11).
		"recompenses": {"xp": 120, "cuivre": 1500, "items": [{"item": "item:besace_profonde", "poids": 0.5}]},
	}


# ---------------------------------------------------------------------------------------------
# PNJ relus du dump
# ---------------------------------------------------------------------------------------------

def villard(doc):
	doc = sans_rev(doc)
	n = doc["dialogue"]["noeuds"]
	doc.setdefault("services", {})["escorte"] = {"offre": offre_escorte(), "noeuds": {"accepte": "piece_accepte"}}
	ajouter_choix(doc, "etabli", [
		choix("piece_offre", "« Maître, vous avez l'air de quelqu'un qui n'a pas dormi. »", "piece_01",
			  condition=dict(AVANT, escorte_offerte=True, quete_reussie={"id": JUMIEGES})),
		choix("piece_pendant", "« La boîte ? »", "piece_pendant", condition=PENDANT),
		choix("piece_apres", "« Votre boîte est scellée ? »", "piece_souvenir", condition=APRES),
	], en_tete=True)
	n["piece_01"] = noeud(
		"Le nain ne lève pas les yeux de son compas. « Vous êtes de ceux qui ont ramené Aélis vivante de "
		"Jumièges. » Ce n'est pas une question. Il pose l'outil. « J'ai perdu quelque chose qui ne peut pas "
		"se perdre. Une boîte, pas plus grande que ma main. Du métal gravé. Elle était dans une armoire "
		"fermée, aux Ateliers de Convergence. L'armoire est toujours fermée. La boîte n'y est plus. »",
		choix("piece_vol", "« Volée ? »", "piece_02"))
	n["piece_02"] = noeud(
		"« Rien n'a été forcé. Ni la porte, ni la serrure, ni le sceau que j'y avais posé. » Il passe le "
		"pouce sur la tresse de cuivre de sa barbe. « Une boîte ne marche pas. Celle-ci, si. Aélis de "
		"Montfaucon l'étudiait avec moi. Elle viendra. Moi, je reste ici : si quelqu'un doit répondre de "
		"ce qui sortira de cette armoire, c'est l'Institut, pas vous. »",
		choix("piece_ou", "« D'où vient-elle ? »", "piece_03"),
		choix("piece_ok", "« Je vais avec elle. »", action={"service": "escorte", "op": "accepter"}),
		choix("piece_plus_tard", "« Laissez-moi me préparer. »", "fin"))
	n["piece_03"] = noeud(
		"Villard regarde longtemps la toile tendue devant lui. « De là où j'ai fini d'apprendre. » Puis, "
		"plus bas : « Ça ne s'explique pas. Ne me le demandez plus. »",
		choix("piece_ok2", "« Je vais avec Aélis. »", action={"service": "escorte", "op": "accepter"}),
		choix("piece_plus_tard2", "« Laissez-moi me préparer. »", "fin"))
	n["piece_accepte"] = noeud(
		"Aélis arrive sous l'arche au moment où vous vous levez, un carnet neuf sous le bras. Elle salue "
		"Villard d'un signe de tête, et vous d'un demi-sourire. « Il vous a dit qu'elle marche ? Il me l'a "
		"dit aussi. Je ne le crois pas encore. » Villard vous tend une clé de laiton : « Les Ateliers. "
		"Rendez-la-moi avec la boîte. »",
		choix("piece_route", "« Aux Ateliers. »", "fin"))
	n["piece_pendant"] = noeud(
		"« Toujours pas. » Villard ne quitte pas son établi des yeux. « Et Aélis ? Vivante ? Bien. Ramenez-"
		"moi les deux. Dans cet ordre-là. »",
		choix("piece_pendant_fin", "« J'y retourne. »", "fin"))
	n["piece_souvenir"] = noeud(
		"Le petit coffret ferré qui traînait sur l'établi a disparu ; à sa place, une boîte de métal "
		"cerclée de cire. Villard ne la regarde pas. « Scellée. Elle a quelqu'un à garder, là-dedans. Ce "
		"n'est pas à moi de la mettre dehors. » Il reprend son compas. « Je croyais savoir comment elle "
		"était faite. Je savais comment j'aurais fait. »",
		choix("piece_souvenir_fin", "Revenir.", "etabli"))
	return doc


def aelis_archives(doc):
	doc = sans_rev(doc)
	doc["portrait"] = PORTRAIT_AELIS   # le portrait blessé (`humain_f03`) écarté (Auteur, 19/11)
	n = doc["dialogue"]["noeuds"]
	doc.setdefault("services", {})["escorte"] = {"offre": offre_escorte(), "noeuds": {"accepte": "piece_accepte"}}
	ajouter_choix(doc, "accueil", [
		choix("piece_offre", "« Vous ne relevez pas Jumièges, aujourd'hui. »", "piece_01",
			  condition=dict(AVANT, escorte_offerte=True, quete_reussie={"id": JUMIEGES})),
		choix("piece_apres", "« Vos notes de la boîte ? »", "piece_souvenir", condition=APRES),
	], en_tete=True)
	n["piece_01"] = noeud(
		"Aélis repousse les relevés de Jumièges. Dessous, une autre feuille : une boîte vue de six côtés, "
		"couverte de figures. « Maître Villard ne dort plus depuis trois nuits. Il ne dira pas pourquoi à "
		"un apprenti. À moi, il l'a dit : la boîte est partie. Sans ouvrir l'armoire. » Elle tapote le "
		"dessin. « Je l'ai mesurée une fois. Ses angles ne font pas le compte. »",
		choix("piece_compte", "« Pas le compte ? »", "piece_02"))
	n["piece_02"] = noeud(
		"« Six faces, et pourtant la somme de ce que j'ai relevé dépasse ce qu'une boîte peut contenir. » "
		"Elle hausse une épaule. « Les uns diraient que je me suis trompée. J'ai refait le calcul. Je "
		"voudrais aller voir l'armoire, aux Ateliers de Convergence. Et je préférerais ne pas y aller "
		"seule, si quelque chose y attend. »",
		choix("piece_ok", "« Allons-y ensemble. »", action={"service": "escorte", "op": "accepter"}),
		choix("piece_plus_tard", "« Pas tout de suite. »", "fin"))
	n["piece_accepte"] = noeud(
		"Elle range le dessin dans un carnet neuf, glisse son compas à sa ceinture. « Je ne me bats "
		"toujours pas, {prenom}. Vous le savez. Mais je sais regarder. Ça nous fait un partage. »",
		choix("piece_route", "« Aux Ateliers. »", "fin"))
	n["piece_souvenir"] = noeud(
		"Elle ouvre son carnet sur une page couverte d'une écriture qui n'est pas la sienne : les notes "
		"recopiées dans l'atelier intérieur, avec la permission de Villard. « Je les lis tous les soirs. "
		"Je n'en comprends pas le quart. » Elle referme. « Nous croyons qu'un espace, on y entre. Maître "
		"Villard sait le plier. Mais quelqu'un, un jour, a su en bâtir un où l'on vit. » Elle regarde vers "
		"la fenêtre, vers les remparts. « Imaginez ce que cela voudrait dire, pour un monde qui vit "
		"derrière ses murs. »",
		choix("piece_souvenir_fin", "Revenir.", "accueil"))
	return doc


def maelys(doc):
	doc = sans_rev(doc)
	n = doc["dialogue"]["noeuds"]
	ajouter_choix(doc, "accueil", [
		choix("piece_villard", "« Une affaire pour moi, maîtresse ? »", "piece_villard",
			  condition=dict(AVANT, quete_reussie={"id": JUMIEGES})),
		choix("piece_porte", "« Pas de porte rouge, dans la boîte. »", "piece_porte", condition=APRES),
	])
	n["piece_villard"] = noeud(
		"Maëlys ne lève pas les yeux de son registre. « Pas d'épreuve, pas de rang au bout. Un service. » "
		"Elle tourne une page. « Villard de Honnecourt, à la Cour des Arches. Il m'a rendu service, autrefois. "
		"Il a perdu quelque chose et il le cherche avec cette architecte que vous avez ramenée de Jumièges. "
		"Allez le voir. » Puis, au moment où vous vous retournez : « Si vous voyez une porte rouge "
		"là-dedans, vous me le direz. »",
		choix("piece_rouge", "« Une porte rouge ? »", "piece_rouge"),
		choix("piece_villard_fin", "« J'y vais. »", "fin"))
	n["piece_rouge"] = noeud(
		"Elle lève enfin les yeux. Ils ne disent rien. « Une porte. Rouge. Vous me le direz. »",
		choix("piece_rouge_fin", "Prendre congé.", "fin"))
	n["piece_porte"] = noeud(
		"Maëlys repose sa plume. Un instant, la main posée sur la ceinture se détend. « Tant mieux. » Elle "
		"ne dit pas pour qui. « Ou tant pis. » Elle reprend sa plume.",
		choix("piece_porte_fin", "Revenir.", "accueil"))
	return doc


def eleonore(doc):
	doc = sans_rev(doc)
	n = doc["dialogue"]["noeuds"]
	ajouter_choix(doc, "accueil", [
		choix("piece_institut", "« Rien de l'Institut, pour moi ? »", "piece_institut",
			  condition=dict(AVANT, quete_reussie={"id": JUMIEGES})),
	])
	n["piece_institut"] = noeud(
		"Éléonore fait courir son doigt dans le registre. « Une demande de l'Institut, déposée hier : un "
		"maître d'œuvre cherche quelqu'un de discret, déjà passé par un seuil. » Elle relève la tête. « Ce "
		"qui vous désigne assez. Maître Villard de Honnecourt, à la Cour des Arches. Il ne marchande pas, "
		"paraît-il ; il ne parle pas beaucoup non plus. »",
		choix("piece_institut_fin", "« Merci. »", "fin"))
	return doc


def lieu_archives(doc):
	"""Aélis quitte les Archives tant qu'elle est escortée (elle est avec vous)."""
	doc = sans_rev(doc)
	for e in doc.get("pnj") or []:
		if e.get("character") == AELIS_ARCHIVES:
			absente = {"quete_active": {"types": ["escorte"], "cible": SEUIL, "attendu": False}}
			e["conditions"] = [c for c in e.get("conditions") or [] if c != absente] + [absente]
	return doc


# ---------------------------------------------------------------------------------------------
# Lieux neufs
# ---------------------------------------------------------------------------------------------

def lieux_neufs():
	aelis_ici = lambda pid, desc: entree_pnj(pid, "Aélis", PORTRAIT_AELIS, desc, [ESCORTE_ACTIVE])
	ateliers = {
		"_id": ATELIERS, "type": "lieu", "label": "Les Ateliers de Convergence",
		"image": "ateliers_de_convergence01.jpg", "categorie": "institut_des_architectes", "lieu_parent": LUTECIA,
		# Deux variantes tirées au sort à chaque entrée (utils/images_lieu.py, Auteur 19/11).
		"images": ["ateliers_de_convergence01.jpg", "ateliers_de_convergence02.jpg"],
		"pnj": [entree_pnj(AELIS_ATELIERS, "Aélis", PORTRAIT_AELIS_ATELIERS,
						   "Aélis, debout près d'une armoire fermée, un carnet serré contre elle.", [ESCORTE_ACTIVE])],
	}
	cave = {
		"_id": CAVE, "type": "lieu", "label": "La cave aux cinq arches",
		"image": "cave_aux_cinq_arches01.jpg", "categorie": "institut_des_architectes", "lieu_parent": LUTECIA,
		"acces": {"refus": "Le mur est un mur. Rien ne s'y ouvre pour l'instant.", "cycle": 1,
				  "conditions": [{"enigme_resolue": {"id": E_MEUBLE}}]},
		"pnj": [entree_pnj(AELIS_CAVE, "Aélis", PORTRAIT_AELIS_CAVE,
						   "Aélis, une main sur la pierre humide, qui compte les arches à voix basse.", [ESCORTE_ACTIVE]),
				entree_pnj(PUCA, "Le Púca", "puca.jpg",
						   "Une forme sombre dans l'alcôve : un bouc, un chien, un vieil homme — selon où l'on pose les yeux.",
						   [ESCORTE_ACTIVE, {"enigme_resolue": {"id": E_ARCHES}}])],
	}
	maison = {
		"_id": MAISON, "type": "lieu", "label": "La maison pliée",
		"image": "maison_pliee01.jpg", "categorie": "institut_des_architectes", "lieu_parent": LUTECIA,
		"acces": {"refus": "La troisième porte reste une peinture sur la pierre.", "cycle": 1,
				  "conditions": [{"enigme_resolue": {"id": E_PUCA}}]},
		"pnj": [aelis_ici(AELIS_MAISON, "Aélis, sur le seuil d'une pièce de bois clair, qui ne touche à rien."),
				entree_pnj(ZASHIKI, "L'enfant de la maison", "zashiki_warashi.jpg",
						   "Une enfant au visage rouge, en kimono court, assise sur le plancher. Elle vous regarde sans ciller.",
						   [ESCORTE_ACTIVE])],
	}
	seuil = {
		"_id": SEUIL, "type": "lieu", "label": "Le seuil de la boîte",
		"image": "seuil_de_la_boite01.jpg", "categorie": "institut_des_architectes", "lieu_parent": LUTECIA,
		"acces": {"refus": "La porte de la maison ne s'ouvre que de l'intérieur, et pas encore.", "cycle": 1,
				  "conditions": [{"enigme_resolue": {"id": E_SORTIE}}]},
	}
	# Battle map : grille LUE sur `battle_maps/chambre_du_sac.jpg` (1232×864, 20 × 14 cases) :
	# nattes praticables colonnes 3-16 / lignes 2-11 ; murs, cloisons et véranda tout autour ;
	# obstacles = la table basse (haut gauche), la table à thé (droite) et le corps du sac
	# (centre). Lanternes, coussins et jouets restent franchissables.
	dims = (20, 14)
	obstacles = {(4, 3), (5, 3), (6, 3), (4, 4), (5, 4), (6, 4),                 # table basse
				 (15, 6), (16, 6), (15, 7), (16, 7),                             # table à thé
				 (9, 5), (10, 5), (8, 6), (9, 6), (10, 6), (11, 6),              # le sac
				 (8, 7), (9, 7), (10, 7), (11, 7)}
	cells = [[1 if 3 <= x <= 16 and 2 <= y <= 11 and (x, y) not in obstacles else 0 for x in range(dims[0])]
			 for y in range(dims[1])]
	chambre = {
		"_id": CHAMBRE, "type": "lieu", "label": "La chambre du sac",
		"image": "chambre_du_sac.jpg", "categorie": "battle_map",
		"dimensions": {"x": dims[0], "y": dims[1]}, "cells": cells,
		"tags": ["maison", "donjon", "interieur"],
		# Aélis attend sur le seuil, comme à Jumièges (précédent : la nef).
		"proteges_restent_dehors": True,
		"acces": {"gardien": AELIS_MAISON,
				  "refus": "La chambre est vide. Le sac n'y est plus.",
				  "cycle": 1,
				  "conditions": [ESCORTE_ACTIVE, {"enigme_resolue": {"id": E_PLAN_IMPOSSIBLE}},
								 {"combat_gagne": {"lieu": CHAMBRE, "attendu": False}}]},
	}
	liens = [
		lien("link:la_cour_des_arches_to_les_ateliers_de_convergence", COUR, "Retourner dans la cour",
			 ATELIERS, "Descendre aux Ateliers de Convergence"),
		lien("link:les_ateliers_de_convergence_to_cave_aux_cinq_arches", ATELIERS, "Revenir vers l'atelier",
			 CAVE, "Suivre la trace dans le mur"),
		lien("link:cave_aux_cinq_arches_to_maison_pliee", CAVE, "Revenir à la cave", MAISON, "Franchir la troisième porte"),
		lien("link:maison_pliee_to_seuil_de_la_boite", MAISON, "Rentrer dans la maison", SEUIL, "Sortir par la porte de la maison"),
		lien("link:seuil_de_la_boite_to_les_ateliers_de_convergence", ATELIERS, "Revenir au seuil de la boîte",
			 SEUIL, "Retrouver les Ateliers"),
	]
	return [ateliers, cave, maison, seuil, chambre] + liens


# ---------------------------------------------------------------------------------------------
# PNJ neufs : Aélis dans la boîte, le Púca, la Zashiki-warashi
# ---------------------------------------------------------------------------------------------

def pnj_neufs():
	desc_aelis = "Aélis de Montfaucon, architecte de l'Institut, dans l'espace de la boîte de Maître Villard."
	a_ateliers = pnj_doc(AELIS_ATELIERS, "Aélis de Montfaucon", "humain", desc_aelis, PORTRAIT_AELIS_ATELIERS, vocation="lettre", noeuds={
		"accueil": noeud(
			"Les Ateliers de Convergence sentent le cuivre chaud et la poussière de cristal. Des portails en "
			"réduction dorment sous des cloches de verre. Au fond, une armoire de chêne, fermée. Aélis se "
			"tient devant elle, un carnet serré contre elle.",
			choix("quoi", "« Par où commencer ? »", "commencer",
				  condition={"enigme_resolue": {"id": E_RESERVE, "attendu": False}}),
			choix("tissu", "« Le tissu du meuble… »", "tissu", condition={"enigme_resolue": {"id": E_MEUBLE}}),
			choix("fin", "(La laisser travailler.)", "fin")),
		"commencer": noeud(
			"« Par ne rien toucher, et tout regarder. » Elle désigne l'armoire, le sol, la porte du bout de "
			"son crayon. « Villard dit qu'on l'a volée. Une boîte volée laisse un chemin. Cherchez le chemin. "
			"S'il n'y en a pas, ce sera plus intéressant. »",
			choix("ok", "Revenir.", "accueil")),
		"tissu": noeud(
			"Elle déplie le tissu noir sous la lampe. Cousus de fil d'argent, quatre signes, l'un après "
			"l'autre. « Ce n'est pas une broderie. C'est une liste. Et on ne fait pas une liste pour décorer : "
			"on la fait pour ne pas se tromper d'ordre. »",
			choix("ok", "Revenir.", "accueil")),
	})
	a_cave = pnj_doc(AELIS_CAVE, "Aélis de Montfaucon", "humain", desc_aelis, PORTRAIT_AELIS_CAVE, vocation="lettre", noeuds={
		"accueil": noeud(
			"Une cave voûtée, plus grande que les Ateliers qui la contiennent. Cinq arches, chacune gravée "
			"d'un signe : une ligne, un cercle, une spirale, une croix, un triangle. Aélis les compte encore.",
			choix("arches", "« Ce sont les mêmes signes que sur le tissu. »", "arches",
				  condition={"enigme_resolue": {"id": E_ARCHES, "attendu": False}}),
			choix("puca", "« Cette chose, dans l'alcôve… »", "puca", condition={"enigme_resolue": {"id": E_ARCHES}}),
			choix("fin", "(Se taire.)", "fin")),
		"arches": noeud(
			"« Les mêmes. » Elle pose la main sur la voûte. « Une cave qui ne mène nulle part par le plus "
			"court. Je parierais qu'elle mène quelque part par le plus juste. »",
			choix("ok", "Revenir.", "accueil")),
		"puca": noeud(
			"Elle baisse la voix. « Un púca. Les gens de l'ouest des îles en parlent : il prend toutes les "
			"formes, il ne ment jamais tout à fait, et il ne dit jamais rien pour rien. » Elle n'a pas l'air "
			"d'avoir peur. Elle a l'air d'avoir envie de prendre des notes.",
			choix("ok", "Revenir.", "accueil")),
	})
	a_maison = pnj_doc(AELIS_MAISON, "Aélis de Montfaucon", "humain", desc_aelis, PORTRAIT_AELIS, vocation="lettre",
		services={"acces": {"lieu": CHAMBRE, "noeuds": {"ouvre": "chambre_ouverte", "refus": "chambre_close"}}},
		noeuds={
		"accueil": noeud(
			"Une maison de bois clair, aux cloisons de papier. Elle tient dans une boîte, et pourtant on "
			"entend le vent dans un jardin qu'on ne voit pas. Aélis reste sur le seuil.",
			choix("sac", "Écouter, derrière la cloison du fond.", "seuil", condition={"acces_ouvrable": True}),
			choix("apres", "« C'est fini ? »", "apres", condition={"acces_libere": True}),
			choix("fin", "(Se taire.)", "fin")),
		"seuil": noeud(
			"Un froissement de toile, lent, régulier, comme quelqu'un qui remplit un sac sans se presser. "
			"Puis une voix d'homme, très douce, qui fredonne. Aélis vous attrape la manche. « L'enfant. Il "
			"est venu pour l'enfant. »",
			choix("entrer", "« Restez ici. »", action={"service": "acces", "op": "passer"}),
			choix("pas_encore", "« Pas encore. »", "accueil")),
		"chambre_ouverte": noeud(
			"La cloison glisse sans bruit. La chambre est plus profonde que la maison. Au milieu, un homme "
			"en manteau sombre, un grand sac de toile sur l'épaule ; autour de lui, des silhouettes sans "
			"visage se retournent vers vous.",
			choix("arme", "Tirer votre arme.", "fin")),
		"chambre_close": noeud("Aélis secoue la tête. « Pas maintenant. Le plan ne tient pas. »",
							   choix("reculer", "Reculer.", "fin")),
		"apres": noeud(
			"Aélis est entrée dans la chambre vide. Elle relève, à genoux, des figures tracées au plafond, et "
			"recopie dans son carnet des notes trouvées sur une table basse. « Villard m'a permis de prendre "
			"ce que je trouverais. Je prends. » Elle lève les yeux vers la porte de la maison. « Il reste à "
			"sortir. »",
			choix("ok", "Revenir.", "accueil")),
	})
	puca = pnj_doc(PUCA, "Le Púca", "inconnu",
		"Esprit des îles de l'ouest, changeant de forme, qui ne ment jamais tout à fait.", "puca.jpg", noeuds={
		"accueil": noeud(
			"Dans l'alcôve, la forme sombre est un bouc noir aux yeux jaunes. Vous clignez des yeux : c'est "
			"un chien. Puis un vieil homme accroupi, qui sourit. « On cherche une boîte, on trouve une cave. "
			"On cherche une porte, on trouve un púca. C'est toujours ainsi. »",
			choix("ecouter", "« Que s'est-il passé dans l'atelier ? »", "propositions",
				  condition={"enigme_resolue": {"id": E_PUCA, "attendu": False}}),
			choix("apres", "« Et maintenant ? »", "apres", condition={"enigme_resolue": {"id": E_PUCA}}),
			choix("fin", "(Reculer.)", "fin")),
		"propositions": noeud(
			"Le vieil homme compte sur ses doigts noueux. « La porte est ouverte, mais personne ne peut entrer. "
			"Le chemin est visible, mais personne ne peut le suivre. L'objet est présent, mais personne ne peut "
			"le prendre. » Il rit. « Dites-moi ce que cela veut dire, et je vous dirai ce que j'ai vu. »",
			choix("repondre", "Répondre au Púca.", "fin", enigme=E_PUCA),
			choix("retour", "« Pas encore. »", "accueil")),
		"apres": noeud(
			"Le chien s'assied. « Un visage vide est entré dans l'atelier par l'interstice. Il cherchait le "
			"sac, et le sac cherchait l'enfant. Quand la porte s'est fermée, une enfant la tenait. » Le vieil "
			"homme revient, désigne la troisième arche, celle qui n'en était pas une. « Sa maison est là. La "
			"maison était là avant la boîte, si vous voulez mon avis. On ne le demande jamais. »",
			choix("ok", "Revenir.", "accueil")),
	})
	zashiki = pnj_doc(ZASHIKI, "L'enfant de la maison", "inconnu",
		"Une zashiki-warashi : l'esprit-enfant d'une maison. Une maison qu'elle quitte tombe en ruine.",
		"zashiki_warashi.jpg", noeuds={
		"accueil": noeud(
			"L'enfant au visage rouge est assise sur le plancher, un pinceau à la main. Devant elle, une feuille : "
			"une maison de quatre pièces, sans un seul nom. Elle ne dit rien. Elle pousse la feuille vers vous.",
			choix("dessin", "Regarder le dessin.", "dessin",
				  condition={"enigme_resolue": {"id": E_PLAN_MAISON, "attendu": False}}),
			choix("plaque", "Suivre son regard.", "plaque",
				  condition={"enigme_resolue": {"id": E_PLAN_MAISON}}),
			choix("fin", "(La laisser.)", "fin")),
		"dessin": noeud(
			"Quatre pièces, et quatre petits signes posés à côté : un soleil, une étoile, une lune, un cercle "
			"vide. Elle tapote la pièce d'entrée, puis le soleil. Elle tapote la pièce murée, puis le cercle "
			"vide, et secoue la tête : non, pas si simple. Elle attend.",
			choix("placer", "Placer les signes.", "fin", enigme=E_PLAN_MAISON),
			choix("retour", "Revenir.", "accueil")),
		"plaque": noeud(
			"Elle ne regarde plus le dessin. Elle regarde le mur, où pend une plaque de bronze couverte de "
			"lieux et de traits interrompus. Puis elle regarde la cloison du fond, et serre son pinceau.",
			choix("ok", "Revenir.", "accueil")),
	})
	return [a_ateliers, a_cave, a_maison, puca, zashiki]


# ---------------------------------------------------------------------------------------------
# Énigmes (familles : utils/enigmes.py)
# ---------------------------------------------------------------------------------------------

def enigme(id_, nom, famille, lieu, texte, elements, solution, reussite, echec, commentaires,
		   bouton=True, prerequis=None, conditions=None):
	d = {"_id": id_, "type": "enigme", "nom": nom, "famille": famille, "lieux": [lieu], "texte": texte,
		 "elements": elements, "solution": solution, "reussite": reussite, "echec": echec,
		 "conditions": conditions or [ESCORTE_ACTIVE], "commentaires": commentaires}
	if bouton:
		d["bouton"] = True
	if prerequis:
		d["prerequis"] = prerequis
	return d


def enigmes():
	reserve = enigme(E_RESERVE, "La réserve de Villard", "deduction", ATELIERS,
		"L'armoire de chêne est fermée à clé, le sceau de cire de Villard intact sur la serrure. À "
		"l'intérieur, sur un socle de bois, la place vide d'une petite boîte.",
		{"indices": [
			{"id": "socle", "label": "Le socle vide", "fait": "Sous le socle, gravé dans le bois : trois cercles entrelacés. Le même sceau que sur la boîte, dit le carnet."},
			{"id": "sol", "label": "Le sol devant l'armoire", "fait": "Des traces de pas dans la poussière de cristal, qui s'arrêtent net au pied du mur du fond."},
			{"id": "porte", "label": "La porte de l'armoire", "fait": "Aucune effraction : ni rayure à la serrure, ni éclat au bois."},
			{"id": "sceau", "label": "Le sceau de cire", "fait": "Le sceau de Villard est intact. Personne n'a ouvert l'armoire depuis qu'il l'a fermée."},
			{"id": "carnet", "label": "Le carnet de Villard, sur l'établi", "fait": "Une page cornée du carnet : « Pour rouvrir le meuble du fond : le premier tiroir tout au fond, le deuxième à peine tiré, le troisième aux trois quarts. »"},
		], "conclusions": [
			{"id": "voleur", "label": "Un voleur a ouvert l'armoire et refermé derrière lui."},
			{"id": "villard", "label": "Villard a déplacé la boîte et l'a oublié."},
			{"id": "ailleurs", "label": "La boîte a quitté l'armoire sans en passer la porte."},
		]},
		{"conclusion": "ailleurs", "indices": ["porte", "sceau", "sol"], "seuil": 2},
		"Aélis écrit une seule ligne dans son carnet, la souligne deux fois. « Sans passer la porte. Alors "
		"elle est passée ailleurs. » Elle se tourne vers le meuble à trois tiroirs, au fond de l'atelier.",
		"Aélis ne répond pas. Elle regarde la porte de l'armoire, puis vous.",
		[aelis("ouverture", "Ne touchez à rien d'abord. Regardez. Une boîte qui part laisse un chemin, ou n'en laisse pas."),
		 aelis("examen:sol", "Les traces s'arrêtent au mur. Ce n'est pas un mur qu'on traverse. D'habitude."),
		 aelis("examen:carnet", "Villard écrit ses codes comme des recettes. Il a toujours dit que c'était plus sûr."),
		 aelis("echec", "Ce n'est pas ce que disent les choses que nous avons vues."),
		 compagnon("voleur", "examen:porte", "Pas une serrure de ma vie n'a été ouverte aussi proprement. Personne n'y a touché."),
		 compagnon("lettre", "ouverture", "Le carnet sur l'établi. Un maître d'œuvre écrit tout."),
		 compagnon("forestier", "examen:sol", "Des pas qui s'arrêtent sans repartir. Je n'ai jamais vu ça, même dans la neige.")])
	meuble = enigme(E_MEUBLE, "Le meuble aux trois tiroirs", "crans", ATELIERS,
		"Un meuble bas, sans poignée, à trois tiroirs gravés chacun d'un axe. Chaque tiroir glisse sur quatre "
		"crans, de « à peine tiré » à « tout au fond ».",
		{"pieces": [
			{"id": "premier", "label": "Premier tiroir", "crans": 4, "depart": 0},
			{"id": "deuxieme", "label": "Deuxième tiroir", "crans": 4, "depart": 2},
			{"id": "troisieme", "label": "Troisième tiroir", "crans": 4, "depart": 1},
		]},
		{"positions": {"premier": 3, "deuxieme": 0, "troisieme": 2}},
		"Un déclic sous le plateau. Un compartiment s'ouvre que le meuble n'avait pas la place de contenir : "
		"un morceau de tissu noir, cousu de quatre signes d'argent dans un ordre — une spirale, un triangle, "
		"un cercle, une croix — et une pièce de métal froid. Au fond de l'atelier, le mur du fond n'est plus "
		"tout à fait un mur.",
		"Les tiroirs résistent, puis se bloquent avec un bruit sec. Rien ne s'ouvre.",
		[aelis("ouverture", "Ce ne sont pas des décors, ces gravures. Ce sont des axes. Le meuble se règle comme un instrument."),
		 aelis("echec", "Non. Villard l'a écrit quelque part : il écrit tout."),
		 aelis("reussite", "Le compartiment est plus profond que le meuble. Vous avez vu ? Plus profond que le meuble."),
		 compagnon("lettre", "echec", "Le carnet, sur l'établi. « Tout au fond, à peine tiré, aux trois quarts. »")],
		prerequis=[E_RESERVE])
	arches = enigme(E_ARCHES, "Les cinq arches", "graphe", CAVE,
		"Cinq arches, chacune gravée d'un signe. Les franchir mène toujours quelque part : rarement là où l'on "
		"croyait. Les mauvaises vous rendent à l'entrée de la cave.",
		{"salles": [
			{"id": "entree", "label": "l'entrée de la cave"},
			{"id": "humide", "label": "la salle humide"},
			{"id": "racines", "label": "la salle aux racines"},
			{"id": "muette", "label": "la salle sans écho"},
			{"id": "alcove", "label": "l'alcôve"},
		], "arches": [
			{"id": "ligne", "label": "Ligne", "symbole": "│"},
			{"id": "cercle", "label": "Cercle", "symbole": "○"},
			{"id": "spirale", "label": "Spirale", "symbole": "🌀"},
			{"id": "croix", "label": "Croix", "symbole": "✕"},
			{"id": "triangle", "label": "Triangle", "symbole": "△"},
		], "depart": "entree", "cible": "alcove"},
		{"transitions": {"entree": {"spirale": "humide"}, "humide": {"triangle": "racines"},
						 "racines": {"cercle": "muette"}, "muette": {"croix": "alcove"}}},
		"Derrière l'arche à la croix, la cave s'arrête sur une alcôve basse. Quelque chose y est assis, et "
		"vous regarde arriver comme on regarde arriver quelqu'un qu'on attendait.",
		"Le couloir tourne sur lui-même et vous rend à l'entrée de la cave.",
		[aelis("ouverture", "Ni le plus court, ni le plus droit. Le tissu disait un ordre. Je ne crois pas que ce soit un hasard."),
		 aelis("echec", "Revenus au début. Notez l'arche : le journal la garde, au moins."),
		 aelis("salle:racines", "Des racines, sous Lutecia, à cette profondeur ? Il n'y a pas d'arbre au-dessus de nous."),
		 compagnon("forestier", "salle:humide", "L'air change de sens à chaque arche. Ça ne devrait pas."),
		 compagnon("mage", "ouverture", "Le mana ne coule pas, ici. Il tourne en rond.")],
		prerequis=[E_MEUBLE])
	puca = enigme(E_PUCA, "Les propositions du Púca", "association", CAVE,
		"« La porte est ouverte, mais personne ne peut entrer. Le chemin est visible, mais personne ne peut "
		"le suivre. L'objet est présent, mais personne ne peut le prendre. » Associez chaque proposition à "
		"ce qu'elle veut dire.",
		{"gauche": [
			{"id": "porte", "texte": "La porte est ouverte, mais personne ne peut entrer."},
			{"id": "chemin", "texte": "Le chemin est visible, mais personne ne peut le suivre."},
			{"id": "objet", "texte": "L'objet est présent, mais personne ne peut le prendre."},
		], "droite": [
			{"id": "destination", "texte": "L'accès est ouvert, mais ce qui est derrière n'est pas atteignable."},
			{"id": "projection", "texte": "Le chemin est une image, sans lien réel."},
			{"id": "espace", "texte": "L'objet est là, mais dans un espace où l'on n'entre pas."},
		]},
		{"paires": {"porte": "destination", "chemin": "projection", "objet": "espace"}, "seuil": 2},
		"Le Púca éclate de rire, bouc, chien et vieil homme à la fois. « Bien ! Bien. Je vais vous dire ce que "
		"j'ai vu. »",
		"« Non, non, non, » chantonne le Púca. « Essayez encore. Je ne suis pas pressé. Je ne l'ai jamais été. »",
		[aelis("ouverture", "Il ne pose pas de devinette. Il décrit ce qui s'est passé dans l'atelier, avec ses mots à lui."),
		 aelis("echec", "Il rit. C'est donc faux, mais pas loin."),
		 compagnon("menestrel", "ouverture", "Les vieux contes d'outre-mer parlent de lui. Il dit vrai, à condition de bien écouter.")],
		bouton=False, prerequis=[E_ARCHES])
	plan_maison = enigme(E_PLAN_MAISON, "La maison de l'enfant", "placement", MAISON,
		"Une maison de quatre pièces dessinée au pinceau : l'entrée, le couloir, la pièce du fond, la pièce "
		"murée. Quatre signes à poser : un soleil, une étoile, une lune, un cercle vide.",
		{"symboles": [
			{"id": "soleil", "label": "Soleil", "icone": "☀"},
			{"id": "etoile", "label": "Étoile", "icone": "☆"},
			{"id": "lune", "label": "Lune", "icone": "☾"},
			{"id": "vide", "label": "Cercle vide", "icone": "◌"},
		], "emplacements": [
			{"id": "entree", "label": "L'entrée"},
			{"id": "couloir", "label": "Le couloir"},
			{"id": "fond", "label": "La pièce du fond"},
			{"id": "muree", "label": "La pièce murée"},
		]},
		{"placement": {"entree": "soleil", "couloir": "etoile", "fond": "lune", "muree": "vide"}},
		"L'enfant hoche la tête une seule fois. Elle repose son pinceau, se lève, et regarde la plaque de "
		"bronze pendue au mur.",
		"L'enfant efface les signes d'un revers de manche, sans colère, et remet la feuille devant vous.",
		[aelis("ouverture", "Le soleil se lève là où l'on entre. Ce qui ne dort nulle part ne peut être qu'un passage."),
		 aelis("echec", "La lune se cache, d'habitude. Pas à l'entrée."),
		 aelis("reussite", "Ce qui n'a pas de porte ne reçoit rien. Et pourtant elle a une pièce murée. Pour qui ?"),
		 compagnon("pretre", "ouverture", "Une maison bénie a toujours un seuil, un passage, un cœur, et un lieu qu'on ne montre pas.")],
		bouton=False, prerequis=[E_PUCA])
	plan_impossible = enigme(E_PLAN_IMPOSSIBLE, "Le plan impossible", "reseau", MAISON,
		"Une plaque de bronze : six lieux de la maison, reliés par des traits dont certains s'interrompent. "
		"Gravé dessous : « Le jardin dort. L'escalier mène. Ce qui tremble se tient à la pierre. » Une clé "
		"ouvre un trait, une pierre l'ancre, un miroir montre ce que la plaque cache.",
		{"noeuds": [
			{"id": "cour", "label": "Cour"}, {"id": "salle", "label": "Salle"}, {"id": "jardin", "label": "Jardin"},
			{"id": "galerie", "label": "Galerie"}, {"id": "escalier", "label": "Escalier"},
			{"id": "inconnue", "label": "Pièce inconnue"},
		], "liaisons": [
			{"id": "cour_galerie", "a": "cour", "b": "galerie"},
			{"id": "galerie_escalier", "a": "galerie", "b": "escalier"},
			{"id": "cour_jardin", "a": "cour", "b": "jardin"},
			{"id": "jardin_salle", "a": "jardin", "b": "salle"},
			{"id": "salle_galerie", "a": "salle", "b": "galerie"},
		]},
		{"liaisons_cachees": [{"id": "escalier_inconnue", "a": "escalier", "b": "inconnue"},
							  {"id": "jardin_inconnue", "a": "jardin", "b": "inconnue"}],
		 "actives": ["cour_galerie", "galerie_escalier", "escalier_inconnue"], "ancrees": ["escalier_inconnue"]},
		"Les traits de la plaque cessent de bouger. Derrière la cloison du fond, quelque chose cesse aussi : "
		"puis reprend, plus près — le froissement d'un sac qu'on remplit.",
		"Les traits glissent sur le bronze et reprennent leur place d'avant.",
		[aelis("ouverture", "Un plan de liens, pas de murs. Le jardin dort : on ne passe pas par lui. L'escalier mène."),
		 aelis("revele:escalier", "Il y avait un lien sous l'escalier. Il tremble. Une pierre, la plaque le dit."),
		 aelis("echec", "Ce qui tremble se tient à la pierre. Nous avons oublié la pierre, ou mis la pierre ailleurs."),
		 compagnon("illusionniste", "ouverture", "Le miroir ne ment pas, ici. C'est la plaque qui ment."),
		 compagnon("mage", "echec", "Un lien instable lâche dès qu'on le lâche. Il faut l'ancrer.")],
		prerequis=[E_PLAN_MAISON])
	sortie = enigme(E_SORTIE, "La porte de la maison", "placement", MAISON,
		"La porte de la maison n'a pas de poignée. À sa place, une serrure ronde où l'on pose un sceau. Cinq "
		"sceaux de métal pendent à un clou.",
		{"symboles": [
			{"id": "spirale_double", "label": "Spirale double"},
			{"id": "trois_cercles", "label": "Trois cercles entrelacés"},
			{"id": "main", "label": "Main ouverte"},
			{"id": "oeil", "label": "Œil"},
			{"id": "etoile_huit", "label": "Étoile à huit branches"},
		], "emplacements": [{"id": "serrure", "label": "La serrure"}]},
		{"placement": {"serrure": "trois_cercles"}},
		"La porte s'ouvre sur la lumière grise des Ateliers. Derrière vous, l'enfant au visage rouge s'est "
		"levée. Elle ne dit rien. Elle referme la porte de sa maison, doucement, et la boîte de Villard est "
		"là, sur le plancher de l'atelier, à vos pieds.",
		"Le sceau tourne dans la serrure sans rien accrocher.",
		[aelis("ouverture", "Un sceau. Nous en avons vu un, au tout début. Sous le socle."),
		 aelis("echec", "Pas celui-là. Celui de l'armoire. Celui de la boîte."),
		 compagnon("voleur", "ouverture", "Une serrure qui prend un sceau au lieu d'une clé. On ne la crochète pas, celle-là.")],
		prerequis=[E_PLAN_IMPOSSIBLE],
		conditions=[ESCORTE_ACTIVE, {"combat_gagne": {"lieu": CHAMBRE}}])
	return [reserve, meuble, arches, puca, plan_maison, plan_impossible, sortie]


# ---------------------------------------------------------------------------------------------
# Bestiaire et donjon
# ---------------------------------------------------------------------------------------------

def _attrs(V, F, R, Ag, Vol, Int, Cha, Ch):
	cles = ("V", "F", "R", "Ag", "Vol", "Int", "Cha", "Ch")
	return {k: {"min": a, "max": b} for k, (a, b) in zip(cles, (V, F, R, Ag, Vol, Int, Cha, Ch))}


def bestiaire():
	homme = {"_id": HOMME_AU_SAC, "type": "espece", "nom": "Homme au sac", "genre": "m",
			 "image": "homme_au_sac_transparent.webp",
			 "description": "Un homme en manteau sombre, un grand sac de toile sur l'épaule, qui fredonne d'une voix "
							"très douce. On le nomme sur les deux versants des montagnes, dans les vallées du sud et "
							"jusqu'aux ports : l'homme qui emporte les enfants qui ne rentrent pas avant la nuit. "
							"Les uns disent qu'il n'est qu'une histoire pour faire rentrer les enfants ; d'autres, "
							"qu'il cherche toujours le même.",
			 "base_attributes": _attrs((6, 8), (50, 70), (50, 70), (30, 45), (45, 65), (30, 45), (0, 0), (30, 45)),
			 "tags": ["humanoide", "legendaire", "boss"], "items": [], "proprietes": {}}
	nopperabo = {"_id": NOPPERABO, "type": "espece", "nom": "Nopperabō", "genre": "m",
				 "image": "nopperabo_transparent.webp",
				 "description": "Une silhouette de passant, de dos, au bord d'un chemin. Elle se retourne : à la place "
								"du visage, une peau lisse comme un œuf. Les récits de l'Extrême-Orient en parlent ; "
								"ils ne disent pas d'où viennent les nopperabō, seulement qu'ils aiment qu'on les "
								"regarde se retourner.",
				 "base_attributes": _attrs((3, 5), (25, 40), (25, 40), (30, 45), (30, 45), (15, 30), (0, 0), (20, 35)),
				 "tags": ["humanoide", "spectral"], "items": [], "proprietes": {}, "effectif": [2, 4]}
	donjon = {"_id": DONJON, "type": "donjon", "nom": "La maison pliée",
			  "description": "Une maison de bois clair, dans une boîte de métal pas plus grande qu'une main. "
							 "Un homme au sac y est entré pour l'enfant qui la garde.",
			  "portail": MAISON, "niveau_min": 4, "niveau_max": 5,
			  "battle_maps": [{"lieu": CHAMBRE, "especes": [HOMME_AU_SAC, NOPPERABO],
							   "composition": {HOMME_AU_SAC: 1, NOPPERABO: 3}, "niveau_min": 4, "niveau_max": 5}]}
	return [homme, nopperabo, donjon]


# ---------------------------------------------------------------------------------------------
# Contrôles et écriture
# ---------------------------------------------------------------------------------------------

def controler(docs, par_id):
	fautes = []
	es = [d for d in docs if d.get("type") == "enigme"]
	for d in es:
		fautes += [f"{d['_id']} : {f}" for f in enigmes_util.valider_enigme(d)]
	fautes += [f"prérequis circulaires : {c}" for c in enigmes_util.cycles_prerequis(es)]
	for d in docs:
		for t in lint_dialogues.analyser_doc(d):
			if t.get("niveau") == "erreur":
				fautes.append(f"{d['_id']} [{t.get('noeud')}] : {t.get('message')}")
	ids = [d["_id"] for d in docs]
	fautes += [f"_id en double : {i}" for i in set(ids) if ids.count(i) > 1]
	return fautes


def main(argv):
	with open(dernier_dump(argv), encoding="utf-8") as f:
		dump = json.load(f)
	par_id = {d["_id"]: d for d in dump["docs"]}
	for requis in (VILLARD, AELIS_ARCHIVES, MAELYS, ELEONORE, ARCHIVES, COUR, "item:besace_profonde", LUTECIA):
		if requis not in par_id:
			sys.exit(f"ERREUR : {requis} absent du dump")
	neufs = lieux_neufs() + pnj_neufs() + enigmes() + bestiaire()
	collisions = [d["_id"] for d in neufs if d["_id"] in par_id]
	if collisions:
		print("⚠️ ids déjà présents au dump (écrasés par l'import) :", ", ".join(collisions))
	relus = [villard(par_id[VILLARD]), aelis_archives(par_id[AELIS_ARCHIVES]), maelys(par_id[MAELYS]),
			 eleonore(par_id[ELEONORE]), lieu_archives(par_id[ARCHIVES])]
	docs = relus + neufs
	fautes = controler(docs, par_id)
	if fautes:
		sys.exit("ERREUR :\n  " + "\n  ".join(fautes))
	with open(SORTIE, "w", encoding="utf-8", newline="\n") as f:
		f.write(json.dumps(docs, ensure_ascii=False, indent=2) + "\n")
	print(f"{len(docs)} docs → {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
	main(sys.argv)
