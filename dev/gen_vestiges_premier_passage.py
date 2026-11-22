#!/usr/bin/env python
# dev/gen_vestiges_premier_passage.py
# « Les vestiges du premier passage » — deuxième quête d'Aélis après Jumièges, rang B
# (docs/lore/personnages/20261119_la_piece_derriere_le_mur.md, arbitrages de l'Auteur du 21/11,
# § Troisième arbitrage ; système d'énigmes : docs/conception_enigmes.md).
#
#   Départ : Aélis SEULE (Archives des Seuils), « La pièce derrière le mur » réussie et rang B de
#   Lutecia. Son escorte devient une liste `offres` (la pièce + les vestiges, utils/offres.py).
#   Chemin : l'Enclos du Temple → la GALERIE DU COMMANDEUR (creusée par lui jusqu'au fond de
#   l'ossuaire ; c'est lui qui l'ouvre, service `acces`) — jamais par les étages des catacombes :
#   un passage d'étage ne consulte aucune barrière, il serait ouvert à toute descente (Auteur, 21/11).
#
#   Chaîne (trois énigmes + un retour) :
#     galerie : les gravures de la porte (association ; ce qu'on a vu dans la boîte de Villard)
#     → les trois anneaux (crans ; l'ordre du tissu, les signes des cinq arches)
#     → l'antichambre, porte entrouverte : l'arche éteinte (réseau ; règle gravée sur le seuil)
#     → trois penanggalan, Aélis DANS la salle, à protéger
#     → la serrure du retour (placement ; les trois cercles entrelacés de la boîte)
#     → devant la porte refermée (dépose).
#   Aélis prononce le nom de Mu devant l'arche éteinte, une fois le réseau résolu.
#
# ⚠️ UN SEUL FICHIER À IMPORTER : jsons/vestiges_premier_passage_a_importer.json. PNJ et lieu
# déjà en base RELUS du dernier dump (seuls les choix, nœuds, services et présences ajoutés
# changent : régénération idempotente) + docs neufs COMPLETS (l'import est un PUT, CLAUDE.md §11).
# `gen_piece_derriere_le_mur.py` réécrivait l'escorte d'Aélis en offre SEULE : il est retiré
# (`dev/retires/`), son rejeu aurait effacé l'offre des vestiges.
#
# Usage : python dev/gen_vestiges_premier_passage.py [jsons/telluris-dump-….json]

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
SORTIE = os.path.join(JSONS, "vestiges_premier_passage_a_importer.json")

QUETE = "quete:vestiges_du_premier_passage"
PIECE = "quete:piece_derriere_le_mur"
CRISTAL = "quete:cristal_de_l_ossuaire"
LUTECIA = "lieu:lutecia"

ENCLOS = "lieu:enclos_du_temple"
ARCHIVES = "lieu:les_archives_des_seuils"
GALERIE = "lieu:galerie_du_commandeur"
ANTICHAMBRE = "lieu:antichambre_de_l_arche"
SALLE = "lieu:salle_de_l_arche_eteinte"
RETOUR = "lieu:devant_la_porte_refermee"
DONJON = "donjon:arche_eteinte"

COMMANDEUR = "pnj:commandeur_de_l_enclos_du_temple"
AELIS_ARCHIVES = "pnj:aelis_de_montfaucon_archives"
AELIS_GALERIE = "pnj:aelis_de_montfaucon_galerie"
AELIS_ANTICHAMBRE = "pnj:aelis_de_montfaucon_antichambre"
AELIS_ESCORTE = "pnj:aelis_de_montfaucon_escorte"   # sa voix tant qu'elle est escortée (`voix_protege`)

PENANGGALAN = "espece:penanggalan"

E_GRAVURES = "enigme:gravures_de_la_porte_tiede"
E_ANNEAUX = "enigme:anneaux_de_la_porte_tiede"
E_ARCHE = "enigme:arche_eteinte"
E_RETOUR = "enigme:serrure_du_retour"

PORTRAIT_AELIS = "architecte_Aélis_de_Montfaucon_dans_les_invalides.jpg"  # sans blessure (Auteur, 19/11)
# Portrait DÉTOURÉ (fond transparent, tiré de celui de la maison pliée) : celui de TOUS les dialogues
# de la quête (Auteur, 21/11). L'escortée garde PORTRAIT_AELIS (jeton de combat, panneau 👥).
PORTRAIT_AELIS_DIALOGUE = "architecte_Aélis_de_Montfaucon_transparent.webp"
PORTRAIT_COMMANDEUR = "templier_humain_m_commandeur_enclos01.png"
# Images à livrer par l'Auteur (prompts dans la séance, § Prompts d'image des vestiges).
IMAGE_GALERIE = "galerie_du_commandeur01.jpg"
IMAGE_ANTICHAMBRE = "antichambre_de_l_arche01.jpg"
IMAGE_SALLE = "salle_de_l_arche_eteinte.jpg"

# Présences et conditions — les trois états (AVANT · PENDANT · APRÈS, telluris-quetes-pnj).
ESCORTE_ACTIVE = {"quete_active": {"types": ["escorte"], "cible": RETOUR}}
AVANT = {"quete_active": {"id": QUETE, "attendu": False}, "quete_reussie": {"id": QUETE, "attendu": False}}
PENDANT = {"quete_active": {"id": QUETE}}
APRES = {"quete_reussie": {"id": QUETE}}
RANG_B = {"cite": LUTECIA, "rang": "B"}


# ---------------------------------------------------------------------------------------------
# Outils (mêmes formes que gen_piece_derriere_le_mur.py)
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


def lien(id_, a, label_a, b, label_b, type_="temple_templier"):
	return {"_id": id_, "type": "connection",
			"nodes": [{"lieu": a, "pos": [0, 0], "label": label_a}, {"lieu": b, "pos": [0, 0], "label": label_b}],
			"metadata": {"type": type_, "status": "ouvert"}}


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
# L'offre d'escorte (Aélis seule, Auteur 21/11)
# ---------------------------------------------------------------------------------------------

def offre_escorte():
	return {
		"id": QUETE,
		"titre": "Les vestiges du premier passage",
		"description": "Au fond de l'ossuaire des catacombes, une paroi s'est ouverte sur une porte de "
					   "pierre tiède, gravée de signes que les Templiers ne savent pas lire. Aélis de "
					   "Montfaucon les a reconnus : ce sont ceux de la boîte de Maître Villard. Le "
					   "commandeur de l'Enclos du Temple garde le chemin. Accompagnez-la jusqu'à la "
					   "porte et ramenez-la vivante. Elle ne sait pas se battre.",
		"destination": RETOUR,
		"proteges": [{"prenom": "Aélis", "nom": "de Montfaucon", "race": "humain", "sex": "F",
					  "image": PORTRAIT_AELIS,
					  "description": "Architecte de l'Institut. Elle a relu tous les soirs les pages "
									 "recopiées dans la boîte de Villard. Un compas, un carnet, un "
									 "crayon. Elle ne sait pas se battre."}],
		"unique": True,
		"proba": 1,
		"rang_min": RANG_B,
		# Environ deux fois « La pièce derrière le mur » (120 XP, 1 500 cu), sans objet (Auteur, 21/11).
		"recompenses": {"xp": 200, "cuivre": 3000},
	}


# ---------------------------------------------------------------------------------------------
# PNJ et lieu relus du dump
# ---------------------------------------------------------------------------------------------

def aelis_archives(doc):
	doc = sans_rev(doc)
	n = doc["dialogue"]["noeuds"]
	esc = doc.setdefault("services", {}).get("escorte") or {}
	# Escorte SEULE (forme de gen_piece_derriere_le_mur) → liste `offres`, la pièce gardée telle quelle.
	offres = list(esc.get("offres") or [])
	if esc.get("offre"):
		offres.append({"offre": esc["offre"], "noeuds": esc.get("noeuds") or {"accepte": "piece_accepte"}})
	offres = [o for o in offres if (o.get("offre") or {}).get("id") != QUETE]
	offres.append({"offre": offre_escorte(), "noeuds": {"accepte": "vestiges_accepte"}})
	doc["services"]["escorte"] = {"offres": offres}
	# Le choix d'offre de la pièce porte désormais `offre` : `escorte_offerte` vaut pour les deux.
	for c in n["accueil"]["choix"]:
		if c.get("id") == "piece_offre":
			c.setdefault("condition", {})["offre"] = PIECE
	ajouter_choix(doc, "accueil", [
		choix("vestiges_offre", "« Vous ne lisez plus vos notes de la boîte. Vous les comparez. »", "vestiges_01",
			  condition=dict(AVANT, escorte_offerte=True, offre=QUETE, quete_reussie={"id": PIECE},
							 rang_min=RANG_B)),
		choix("vestiges_apres", "« Ce nom, sous la coupole… »", "vestiges_souvenir", condition=APRES),
	], en_tete=True)
	n["vestiges_01"] = noeud(
		"Aélis a posé côte à côte deux feuilles. Sur l'une, son écriture : les pages recopiées dans la boîte "
		"de Villard. Sur l'autre, un relevé maladroit, au fusain, d'une main qui n'a pas l'habitude. « Les "
		"Templiers de l'Enclos ont fait porter ceci à l'Institut. Une porte, au fond de l'ossuaire, derrière "
		"une paroi qui s'est ouverte toute seule. Personne chez eux ne sait la lire. » Elle pose le doigt sur "
		"trois cercles entrelacés. « Moi non plus. Mais je l'ai déjà vue. »",
		choix("vestiges_ou", "« Dans la boîte. »", "vestiges_02"))
	n["vestiges_02"] = noeud(
		"« Sous le socle de la réserve, sur le tissu du meuble, dans le dessin de l'enfant. Les mêmes signes, "
		"{prenom}, à cent pieds sous Lutecia, sur une porte que personne n'a bâtie depuis qu'on y creuse. » "
		"Elle range les deux feuilles dans son carnet. « Le commandeur de l'Enclos garde le chemin. Il "
		"m'ouvrira peut-être, si quelqu'un qu'il connaît m'accompagne. Et je préférerais ne pas descendre "
		"seule. »",
		choix("vestiges_ok", "« Je descends avec vous. »", action={"service": "escorte", "op": "accepter"}),
		choix("vestiges_plus_tard", "« Pas tout de suite. »", "fin"))
	n["vestiges_accepte"] = noeud(
		"Elle glisse son compas à sa ceinture et prend une lanterne sourde sur l'étagère. « À l'Enclos du "
		"Temple, d'abord, voir le commandeur : c'est lui qui garde le chemin. Pas par les catacombes, il "
		"a sa propre galerie. Ensuite, nous verrons bien ce qu'une porte a à dire à une architecte. »",
		choix("vestiges_route", "« À l'Enclos. »", "fin"))
	n["vestiges_souvenir"] = noeud(
		"Aélis lève les yeux vers la coupole peinte des Archives, vers le signe tracé au-dessus de la porte "
		"des vieux maîtres. « Je passais dessous tous les jours. On nous apprend à dire Mu en levant les "
		"yeux, comme on dit un nom qu'on respecte et qu'on n'explique pas. » Elle baisse les yeux sur son "
		"carnet. « Sur l'arche, il disait peut-être où elle menait. Ou qui l'avait bâtie. Les vieux maîtres "
		"ne répondent pas quand je demande. Ils sourient, et ils parlent d'autre chose. »",
		choix("vestiges_souvenir_fin", "Revenir.", "accueil"))
	return doc


def commandeur(doc):
	doc = sans_rev(doc)
	n = doc["dialogue"]["noeuds"]
	doc.setdefault("services", {})["acces"] = {"lieu": GALERIE,
											   "noeuds": {"ouvre": "vestiges_ouvre", "refus": "vestiges_refus"}}
	ajouter_choix(doc, "accueil", [
		choix("vestiges_connu", "« Aélis de Montfaucon veut voir votre porte. »", "vestiges_01_connu",
			  condition=dict(PENDANT, quete_reussie={"id": CRISTAL})),
		choix("vestiges_inconnu", "« L'Institut voudrait voir votre porte. »", "vestiges_01_inconnu",
			  condition=dict(PENDANT, quete_reussie={"id": CRISTAL, "attendu": False})),
		choix("vestiges_apres", "« La porte, au fond de la galerie ? »", "vestiges_souvenir", condition=APRES),
	])
	n["vestiges_01_connu"] = noeud(
		"Le commandeur regarde Aélis, puis vous. « Vous l'avez touchée. Moi aussi. Et maintenant l'Institut "
		"veut la lire. » Il pose la main à plat sur la table, près du cristal. « Pas par les catacombes : "
		"trois étages, ce serait vous perdre avant d'arriver. Par ma galerie. Je l'ai creusée moi-même, "
		"jusqu'au fond de l'ossuaire, pour remonter les cristaux sans passer par les morts. »",
		choix("vestiges_suite", "« Vous nous l'ouvrez ? »", "vestiges_02"))
	n["vestiges_01_inconnu"] = noeud(
		"Le commandeur considère Aélis un long moment. « Une porte de pierre, au fond de l'ossuaire, derrière "
		"une paroi qui s'est ouverte le mois dernier. Tiède sous la main. Gravée d'un signe que nul ici ne "
		"sait lire. Elle n'était pas là : j'ai creusé moi-même ce couloir. » Il pose la main à plat sur la "
		"table. « Ma galerie descend jusqu'à elle. On n'y passe pas par les morts. »",
		choix("vestiges_suite", "« Vous nous l'ouvrez ? »", "vestiges_02"))
	n["vestiges_02"] = noeud(
		"« À une condition. » Il se tourne vers Aélis. « Vous me direz ce qu'elle dit, même si ça ne me plaît "
		"pas. Surtout si ça ne me plaît pas. » Aélis hoche la tête. Il décroche une clé de fer du mur.",
		choix("vestiges_passer", "Prendre la clé de la galerie.", condition={"acces_ouvrable": True},
			  action={"service": "acces", "op": "passer"}),
		choix("vestiges_deja", "« Nous avons déjà la clé. »", "vestiges_deja", condition={"acces_ouvert": True}),
		choix("vestiges_attendre", "« Plus tard. »", "fin"))
	n["vestiges_ouvre"] = noeud(
		"Il vous tend la clé. « La porte au fond de la cour, sous la tour. Fermez derrière vous. Ce qui est "
		"en bas n'a jamais demandé à monter, et je voudrais que ça dure. »",
		choix("vestiges_ouvre_fin", "« Merci, commandeur. »", "fin"))
	n["vestiges_refus"] = noeud(
		"« Pas sans l'architecte. » Il raccroche la clé. « C'est elle qui sait lire. Vous, vous savez "
		"revenir. Il me faut les deux. »",
		choix("vestiges_refus_fin", "Prendre congé.", "fin"))
	n["vestiges_deja"] = noeud("« Alors descendez. Et revenez. »", choix("vestiges_deja_fin", "Prendre congé.", "fin"))
	n["vestiges_souvenir"] = noeud(
		"« Refermée. » Le commandeur fait tourner le cristal jaune sur la table. « Mes hommes l'ont entendue "
		"de l'autre bout de la galerie : un bruit de pierre qu'on repose. Elle est toujours tiède. » Il lève "
		"les yeux. « Votre architecte m'a tout dit, comme promis. Une arche, et un nom. Mon second dit que ce "
		"nom ne veut rien dire, que c'est une prière de bâtisseurs. Moi, je dis qu'on ne grave pas une "
		"prière sur une clé de voûte. Nous continuons d'extraire. »",
		choix("vestiges_souvenir_fin", "Revenir.", "accueil"))
	return doc


def lieu_archives(doc):
	"""Aélis quitte les Archives tant qu'elle est escortée vers la porte (elle est avec vous)."""
	doc = sans_rev(doc)
	absente = {"quete_active": {"types": ["escorte"], "cible": RETOUR, "attendu": False}}
	for e in doc.get("pnj") or []:
		if e.get("character") == AELIS_ARCHIVES:
			e["conditions"] = [c for c in e.get("conditions") or [] if c != absente] + [absente]
	return doc


# ---------------------------------------------------------------------------------------------
# Lieux neufs
# ---------------------------------------------------------------------------------------------

def lieux_neufs():
	galerie = {
		"_id": GALERIE, "type": "lieu", "label": "La galerie du commandeur",
		"image": IMAGE_GALERIE, "categorie": "temple_templier", "lieu_parent": LUTECIA,
		"acces": {"gardien": COMMANDEUR, "cycle": 1,
				  "refus": "Une porte de fer, au pied de la tour carrée. Fermée à clé.",
				  "conditions": [ESCORTE_ACTIVE]},
		"pnj": [entree_pnj(AELIS_GALERIE, "Aélis", PORTRAIT_AELIS_DIALOGUE,
						   "Aélis, la lanterne levée devant une porte de pierre, qui ne la touche pas encore.",
						   [ESCORTE_ACTIVE])],
	}
	antichambre = {
		"_id": ANTICHAMBRE, "type": "lieu", "label": "L'antichambre de l'arche",
		"image": IMAGE_ANTICHAMBRE, "categorie": "temple_templier", "lieu_parent": LUTECIA,
		# Aucun gardien (pas de laissez-passer) : revérifié à chaque pas. Hors de l'escorte, la porte
		# est refermée, pour toujours (Auteur, 21/11 : « entrouverte, puis refermée »).
		"acces": {"cycle": 1,
				  "refus": "La porte de pierre est refermée. Tiède sous la main, comme avant.",
				  "conditions": [ESCORTE_ACTIVE, {"enigme_resolue": {"id": E_ANNEAUX}}]},
		"pnj": [entree_pnj(AELIS_ANTICHAMBRE, "Aélis", PORTRAIT_AELIS_DIALOGUE,
						   "Aélis, immobile sous une arche de pierre noire, le carnet ouvert et le crayon arrêté.",
						   [ESCORTE_ACTIVE])],
	}
	retour = {
		"_id": RETOUR, "type": "lieu", "label": "Devant la porte refermée",
		# Même lieu que la galerie, vu de l'autre côté de la quête : son image (Auteur, à livrer).
		"image": IMAGE_GALERIE, "categorie": "temple_templier", "lieu_parent": LUTECIA,
		"acces": {"cycle": 1,
				  "refus": "La porte de l'antichambre ne s'ouvre que de l'intérieur, et pas encore.",
				  "conditions": [{"enigme_resolue": {"id": E_RETOUR}}]},
	}
	# Battle map : grille LUE sur `battle_maps/salle_de_l_arche_eteinte.jpg` (1232×864, 20 × 14
	# cases de 61,6 px) : dallage colonnes 2-17 / lignes 2-11, murs de roche tout autour ; le
	# massif de pierre de l'arche (x ≈ 445-785 px, jusqu'à y ≈ 250 px) ferme les colonnes 7-12 des
	# lignes 2-3 ; les piliers du chambranle de la porte avancent dans la salle (8,11 et 11,11) ;
	# le couloir de la porte descend sous la salle (colonnes 9-10, lignes 12-13).
	# Flaques, vase et lanternes d'angle restent franchissables.
	dims = (20, 14)
	arche = {(x, y) for x in range(7, 13) for y in (2, 3)} | {(8, 11), (11, 11)}
	couloir = {(x, y) for x in (9, 10) for y in (12, 13)}
	cells = [[1 if (2 <= x <= 17 and 2 <= y <= 11 and (x, y) not in arche) or (x, y) in couloir else 0
			  for x in range(dims[0])] for y in range(dims[1])]
	salle = {
		"_id": SALLE, "type": "lieu", "label": "La salle de l'arche éteinte",
		"image": IMAGE_SALLE, "categorie": "battle_map",
		"dimensions": {"x": dims[0], "y": dims[1]}, "cells": cells,
		"tags": ["sous-terrain", "donjon", "couvert", "humide"],
		# PAS de `proteges_restent_dehors` : Aélis est dans la salle, à protéger (Auteur, 21/11).
		"acces": {"gardien": AELIS_ANTICHAMBRE,
				  "refus": "L'arche est éteinte. Rien n'en sort plus.",
				  "cycle": 1,
				  "conditions": [ESCORTE_ACTIVE, {"enigme_resolue": {"id": E_ARCHE}},
								 {"combat_gagne": {"lieu": SALLE, "attendu": False}}]},
	}
	liens = [
		lien("link:enclos_du_temple_to_galerie_du_commandeur", ENCLOS, "Remonter dans la cour de l'Enclos",
			 GALERIE, "Descendre par la galerie du commandeur"),
		lien("link:galerie_du_commandeur_to_antichambre_de_l_arche", GALERIE, "Revenir dans la galerie",
			 ANTICHAMBRE, "Franchir la porte entrouverte"),
		lien("link:antichambre_de_l_arche_to_devant_la_porte_refermee", ANTICHAMBRE, "Rentrer dans l'antichambre",
			 RETOUR, "Ressortir par la porte"),
		# Libellé d'un nœud = ce qu'on lit en allant VERS lui (lieux.passages_carte, nœud destination).
		lien("link:devant_la_porte_refermee_to_galerie_du_commandeur", GALERIE, "Remonter la galerie",
			 RETOUR, "Revenir devant la porte refermée"),
	]
	# Sortie SANS GARDIEN vers l'Enclos : l'escorte finie, l'antichambre et la galerie (escorte
	# OU clé du commandeur) sont closes, et qui n'a pas pris la clé restait sans aucune sortie.
	# `bouton: false` côté Enclos : on en ressort par là, on n'y redescend pas (lieux.depart_interdit).
	sortie = lien("link:devant_la_porte_refermee_to_enclos_du_temple", ENCLOS, "Remonter dans la cour de l'Enclos",
				  RETOUR, "Redescendre devant la porte refermée")
	sortie["nodes"][0]["bouton"] = False
	liens.append(sortie)
	return [galerie, antichambre, retour, salle] + liens


# ---------------------------------------------------------------------------------------------
# PNJ neufs : Aélis dans la galerie et dans l'antichambre
# ---------------------------------------------------------------------------------------------

def pnj_neufs():
	desc = "Aélis de Montfaucon, architecte de l'Institut, sous l'ossuaire de Lutecia."
	a_galerie = pnj_doc(AELIS_GALERIE, "Aélis de Montfaucon", "humain", desc, PORTRAIT_AELIS_DIALOGUE, vocation="lettre", noeuds={
		"accueil": noeud(
			"La galerie descend en pente douce, étayée de poutres neuves, jusqu'à une paroi éventrée. "
			"Derrière, une porte de pierre grise, sans gonds ni poignée, couverte de gravures. L'air est "
			"froid ; la porte ne l'est pas. Aélis tient sa lanterne à bout de bras.",
			choix("porte", "« Vous la reconnaissez ? »", "porte",
				  condition={"enigme_resolue": {"id": E_GRAVURES, "attendu": False}}),
			choix("anneaux", "« Ces anneaux, autour du signe… »", "anneaux",
				  condition={"enigme_resolue": {"id": E_GRAVURES}}),
			choix("fin", "(La laisser regarder.)", "fin")),
		"porte": noeud(
			"« Pas elle. Ce qui est écrit dessus. » Elle approche la lanterne sans toucher la pierre. « Les "
			"Templiers ont relevé un signe. Il y en a quatre, et je les ai tous déjà vus, dans un endroit qui "
			"tenait dans la main de Villard. » Elle ouvre son carnet aux pages recopiées. « Comparons. »",
			choix("ok", "Revenir.", "accueil")),
		"anneaux": noeud(
			"« Trois anneaux de pierre, l'un dans l'autre. Ils tournent. » Elle en effleure un, et retire la "
			"main. « On dit que les Frères déplaçaient la destination d'un portail en faisant tourner une bolas. "
			"Leurs héritiers ont peut-être gardé le geste, à défaut de la main. »",
			choix("ok", "Revenir.", "accueil")),
	})
	a_antichambre = pnj_doc(AELIS_ANTICHAMBRE, "Aélis de Montfaucon", "humain", desc, PORTRAIT_AELIS_DIALOGUE, vocation="lettre",
		services={"acces": {"lieu": SALLE, "noeuds": {"ouvre": "salle_ouverte", "refus": "salle_close"}}},
		noeuds={
		"accueil": noeud(
			"Derrière la porte, une salle ronde que personne n'a creusée : la pierre est d'un seul tenant, "
			"lisse comme du verre noir. Au fond se dresse une arche, plus haute que trois hommes. Rien ne la "
			"traverse que l'obscurité. Aélis s'est arrêtée sur le seuil.",
			choix("arche", "« Un portail ? »", "arche",
				  condition={"enigme_resolue": {"id": E_ARCHE, "attendu": False}}),
			choix("cle", "« Ce signe, sur la clé de voûte… »", "cle",
				  condition={"enigme_resolue": {"id": E_ARCHE}}),
			choix("venir", "Écouter ce qui vient de l'arche.", "venir", condition={"acces_ouvrable": True}),
			choix("apres", "« C'est fini ? »", "apres", condition={"acces_libere": True}),
			choix("fin", "(Se taire.)", "fin")),
		"arche": noeud(
			"« Ce qu'il en reste. » Elle ne s'approche pas. « Un logement pour un cristal, sous la clé, et il "
			"est vide. Les portails des Frères s'en passaient ; ceux de leurs héritiers, jamais. Celui-ci a été "
			"bâti par quelqu'un qui avait appris d'eux. » Elle regarde le seuil, gravé de lignes. « Et il a "
			"laissé le mode d'emploi. »",
			choix("ok", "Revenir.", "accueil")),
		"cle": noeud(
			"Aélis lève la lanterne vers la clé de voûte. Un seul signe y est gravé, plus profond que les "
			"autres. Elle le regarde longtemps. « Celui-là, je le connais d'ailleurs que de la boîte. Il est "
			"peint sous la coupole des Archives, au-dessus de la porte des vieux maîtres. » Elle baisse la "
			"voix, comme sous la coupole. « Ils l'appellent Mu. »",
			choix("mu", "« Mu ? »", "mu")),
		"mu": noeud(
			"« Un nom qu'on apprend à dire en levant les yeux, à l'Institut. Un endroit où l'on finit "
			"d'apprendre, disent les uns ; une image qu'on révère, disent les autres. Je n'en sais pas plus. » "
			"Elle referme son carnet sur son crayon. « Ici, il dit peut-être où menait l'arche. Ou qui l'a "
			"bâtie. Ou les deux. Je ne sais pas lequel. Et je crois que je ne veux pas choisir trop vite. »",
			choix("ok", "Revenir.", "accueil")),
		"venir": noeud(
			"Un souffle sort de l'arche éteinte, chargé d'une odeur de sel et de vase, comme une marée qui "
			"monterait sous Lutecia. Puis des formes pâles glissent dans le noir, à hauteur d'homme : des têtes "
			"de femmes, qui traînent sous elles ce qui leur reste de corps. Aélis recule d'un pas, et pas d'un "
			"de plus. « Elles sentent la mer. Ici. »",
			choix("entrer", "« Restez derrière moi. »", action={"service": "acces", "op": "passer"}),
			choix("pas_encore", "« Reculons. »", "accueil")),
		"salle_ouverte": noeud(
			"Elles fondent sur vous en silence. Aélis serre son compas comme une arme qu'elle ne sait pas "
			"tenir, et ne quitte pas votre dos.",
			choix("arme", "Tirer votre arme.", "fin")),
		"salle_close": noeud("Aélis secoue la tête. « L'arche dort. Elle ne répond qu'à ce qu'on lui a appris. »",
							 choix("reculer", "Reculer.", "fin")),
		"apres": noeud(
			"Aélis s'est assise sur le seuil gravé, le carnet sur les genoux, et elle recopie la clé de voûte "
			"trait par trait. Ses mains tremblent un peu ; son écriture, non. « Elles sont venues par là. Je "
			"ne sais pas d'où. » Elle désigne la porte par laquelle vous êtes entrés. « Elle ne s'ouvre que "
			"d'ici, maintenant. Et elle demande un sceau. »",
			choix("ok", "Revenir.", "accueil")),
	})
	return [a_galerie, a_antichambre, aelis_escorte()]


def aelis_escorte():
	"""La VOIX d'Aélis tant qu'elle est sous votre protection (`voix_protege`, utils/escorte) :
	« 🗣 Parler à Aélis » où que vous soyez, sauf dans la galerie et l'antichambre, où ses voix
	de lieu parlent déjà. Elle dit où aller d'après l'avancement : galerie jamais visitée, puis
	énigme par énigme."""
	# Cinq étapes EXCLUSIVES, une clé d'énigme et une clé de passages chacune (un dict de condition
	# ne porte qu'une `enigme_resolue`) : l'antichambre ne s'ouvre qu'anneaux réglés, l'arche ne
	# se résout que dedans.
	etapes = {
		"enclos": {"passages": {"lieu": GALERIE, "max": 0}},
		"galerie": {"passages": {"lieu": GALERIE, "min": 1},
					"enigme_resolue": {"id": E_GRAVURES, "attendu": False}},
		"anneaux": {"enigme_resolue": {"id": E_GRAVURES}, "passages": {"lieu": ANTICHAMBRE, "max": 0}},
		"arche": {"passages": {"lieu": ANTICHAMBRE, "min": 1},
				  "enigme_resolue": {"id": E_ARCHE, "attendu": False}},
		"serrure": {"enigme_resolue": {"id": E_ARCHE}, "passages": {"lieu": RETOUR, "max": 0}},
	}
	doc = pnj_doc(AELIS_ESCORTE, "Aélis de Montfaucon", "humain",
		"Aélis de Montfaucon, architecte de l'Institut, qui vous accompagne jusqu'à la porte tiède.",
		PORTRAIT_AELIS_DIALOGUE, vocation="lettre", noeuds={
		"accueil": noeud(
			"Aélis marche à votre hauteur, la lanterne sourde à la ceinture et le carnet sous le bras. Elle "
			"lève les yeux quand vous ralentissez.",
			choix("enclos", "« Où allons-nous ? »", "enclos", condition=etapes["enclos"]),
			*[choix(cle, "« Où en sommes-nous ? »", cle, condition=etapes[cle])
			  for cle in ("galerie", "anneaux", "arche", "serrure")],
			choix("fin", "(Reprendre la route.)", "fin")),
		"enclos": noeud(
			"« À l'Enclos du Temple, voir le commandeur. » Elle désigne la tour carrée qui dépasse des toits "
			"de Lutecia. « Ses hommes extraient les cristaux jaunes au fond de l'ossuaire, et il a creusé sa "
			"propre galerie jusqu'à la porte. On n'y descend pas par les catacombes : trois étages de morts, "
			"et la porte n'est pas au bout de leur chemin. Il faut qu'il nous ouvre. S'il vous a déjà donné "
			"sa clé, la galerie part de la cour de l'Enclos. »",
			choix("ok", "Revenir.", "accueil")),
		"galerie": noeud(
			"« Au bout de la galerie du commandeur, depuis la cour de l'Enclos. La porte nous attend. » Elle "
			"tapote son carnet. « Les quatre gravures, d'abord. Je les ai toutes vues dans la boîte de "
			"Villard, et vous aussi : il suffit de se souvenir où. »",
			choix("ok", "Revenir.", "accueil")),
		"anneaux": noeud(
			"« Les gravures sont lues. Il reste les trois anneaux, au fond de la galerie : une spirale, un "
			"triangle, un cercle, l'ordre du tissu de Villard. On règle cette porte, on ne la force pas. "
			"Quand elle s'entrouvre, on passe. »",
			choix("ok", "Revenir.", "accueil")),
		"arche": noeud(
			"« Derrière la porte entrouverte, il y a l'arche. Sa règle est gravée sur le seuil : on monte par "
			"la gauche, on ne touche pas au logement du cristal, et ce qui tremble se tient à la pierre. Je "
			"n'avancerai pas sans vous. »",
			choix("ok", "Revenir.", "accueil")),
		"serrure": noeud(
			"« Si quelque chose sort de l'arche, je reste derrière vous. » Elle serre son compas. « Ensuite, "
			"la porte ne s'ouvre plus que de l'intérieur. Elle demande un sceau, celui de la boîte : les "
			"trois cercles. »",
			choix("ok", "Revenir.", "accueil")),
	})
	# Voix de l'Aélis escortée pour CETTE quête ; muette là où une Aélis du lieu parle déjà.
	doc["voix_protege"] = {"quete": QUETE, "prenom": "Aélis", "sauf_lieux": [GALERIE, ANTICHAMBRE]}
	return doc


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
	gravures = enigme(E_GRAVURES, "Les gravures de la porte tiède", "association", GALERIE,
		"Quatre gravures couvrent la porte de pierre. Aélis ouvre son carnet aux pages de la boîte de "
		"Villard. Chacune de ces gravures, vous l'avez déjà vue là-dedans : dites où.",
		{"gauche": [
			{"id": "cercles", "texte": "Trois cercles entrelacés."},
			{"id": "file", "texte": "Une spirale, un triangle et un cercle, en file."},
			{"id": "astres", "texte": "Un soleil, une étoile, une lune et un cercle vide."},
			{"id": "traits", "texte": "Six lieux reliés de traits, dont certains s'interrompent."},
		], "droite": [
			{"id": "socle", "texte": "Sous le socle vide, dans la réserve de Villard."},
			{"id": "tissu", "texte": "Sur le tissu noir du meuble aux trois tiroirs."},
			{"id": "dessin", "texte": "Sur le dessin de l'enfant de la maison."},
			{"id": "plaque", "texte": "Sur la plaque de bronze de la maison pliée."},
		]},
		{"paires": {"cercles": "socle", "file": "tissu", "astres": "dessin", "traits": "plaque"}, "seuil": 3},
		"Aélis referme le carnet. « Toute la boîte est écrite sur cette porte. Ou toute la porte était "
		"écrite dans la boîte. » Au centre, autour du signe que les Templiers ont relevé, trois anneaux de "
		"pierre portent chacun les cinq signes des arches de la cave. Au-dessus, la file : une spirale, un "
		"triangle, un cercle.",
		"Aélis secoue la tête, le doigt sur une page. « Pas là. Je m'en souviens, j'y étais. »",
		[aelis("ouverture", "Prenez votre temps. Ce que nous avons vu dans la boîte, nous l'avons vu ensemble."),
		 aelis("echec", "Une seule de travers. Le dessin de l'enfant n'avait pas de traits, la plaque n'avait pas d'astres."),
		 compagnon("lettre", "ouverture", "Ce n'est pas une écriture. Ce sont des renvois, comme dans un registre."),
		 compagnon("mage", "ouverture", "La pierre est tiède parce que quelque chose la traverse encore. Très peu.")])
	anneaux = enigme(E_ANNEAUX, "Les trois anneaux", "crans", GALERIE,
		"Trois anneaux de pierre, l'un dans l'autre, autour du signe central. Sur chacun, les cinq signes "
		"des arches de la cave se suivent dans le même ordre, du premier cran au cinquième : la Ligne, le "
		"Cercle, la Spirale, la Croix, le Triangle.",
		{"pieces": [
			{"id": "exterieur", "label": "Anneau extérieur", "crans": 5, "depart": 0},
			{"id": "median", "label": "Anneau du milieu", "crans": 5, "depart": 2},
			{"id": "interieur", "label": "Anneau intérieur", "crans": 5, "depart": 4},
		]},
		# La file gravée au-dessus (spirale, triangle, cercle) = l'ordre du tissu, moins la croix.
		{"positions": {"exterieur": 2, "median": 4, "interieur": 1}},
		"Le dernier anneau s'enclenche avec un bruit de pierre qu'on repose. La porte ne s'ouvre pas : elle "
		"recule d'un doigt dans la paroi, et un souffle tiède passe par l'interstice. Elle est entrouverte.",
		"Les anneaux tournent, puis reviennent d'eux-mêmes à leur place, lentement.",
		[aelis("ouverture", "La file, au-dessus. Une spirale, un triangle, un cercle. C'est l'ordre du tissu de Villard."),
		 aelis("echec", "Le tissu avait quatre signes. La porte n'a que trois anneaux. Le quatrième est peut-être de l'autre côté."),
		 aelis("reussite", "On ne l'a pas ouverte. On l'a réglée. Comme on règle un instrument, ou une destination."),
		 compagnon("voleur", "ouverture", "Une serrure à combinaison. Mais qui revient seule en place : on ne l'a pas faite pour qu'on la force."),
		 compagnon("forestier", "echec", "Elle respire, cette porte. Plus fort quand on approche du bon cran.")],
		prerequis=[E_GRAVURES])
	arche = enigme(E_ARCHE, "L'arche éteinte", "reseau", ANTICHAMBRE,
		"Gravé sur le seuil, le plan de l'arche : six points reliés de traits. Dessous, une règle : « On "
		"monte par la gauche ; la droite est rompue. Ce qui attendait la pierre jaune est vide : n'y "
		"touchez pas. Ce qui mène au-delà tremble : tenez-le à la pierre. » Une clé ouvre un trait, une "
		"pierre l'ancre, un miroir montre ce que le seuil ne montre pas.",
		{"noeuds": [
			{"id": "seuil", "label": "Seuil"}, {"id": "pied_gauche", "label": "Pied gauche"},
			{"id": "pied_droit", "label": "Pied droit"}, {"id": "cle", "label": "Clé de voûte"},
			{"id": "logement", "label": "Logement du cristal"}, {"id": "au_dela", "label": "Au-delà"},
		], "liaisons": [
			{"id": "seuil_pied_gauche", "a": "seuil", "b": "pied_gauche"},
			{"id": "seuil_pied_droit", "a": "seuil", "b": "pied_droit"},
			{"id": "pied_gauche_cle", "a": "pied_gauche", "b": "cle"},
			{"id": "pied_droit_cle", "a": "pied_droit", "b": "cle"},
			{"id": "logement_cle", "a": "logement", "b": "cle"},
		]},
		{"liaisons_cachees": [{"id": "cle_au_dela", "a": "cle", "b": "au_dela"},
							  {"id": "logement_au_dela", "a": "logement", "b": "au_dela"}],
		 "actives": ["seuil_pied_gauche", "pied_gauche_cle", "cle_au_dela"], "ancrees": ["cle_au_dela"]},
		"Les traits du seuil cessent de bouger. L'arche ne s'allume pas. Mais tout au fond, dans le noir "
		"qu'elle encadre, quelque chose a entendu.",
		"Les traits glissent dans la pierre et reprennent leur place d'avant.",
		[aelis("ouverture", "Un plan de liens. On monte par la gauche, la règle le dit. Et le logement du cristal reste vide."),
		 aelis("revele:cle", "Il y avait un lien au-dessus de la clé. Il tremble. Une pierre, dit le seuil."),
		 aelis("revele:logement", "Le logement mène au-delà, lui aussi. Mais il est vide : « n'y touchez pas »."),
		 aelis("echec", "Ce qui tremble se tient à la pierre. Et rien par la droite : elle est rompue."),
		 compagnon("mage", "ouverture", "Il reste du mana dans ces traits. Pas assez pour un passage. Assez pour un appel."),
		 compagnon("lettre", "revele:cle", "Les héritiers des Frères ancraient leurs arches à la clé. On le lit dans les vieux traités.")],
		prerequis=[E_ANNEAUX])
	retour = enigme(E_RETOUR, "La serrure du retour", "placement", ANTICHAMBRE,
		"De ce côté, la porte n'a pas d'anneaux. Une serrure ronde, où l'on pose un sceau, et une niche où "
		"reposent cinq sceaux de pierre.",
		{"symboles": [
			{"id": "spirale_double", "label": "Spirale double"},
			{"id": "trois_cercles", "label": "Trois cercles entrelacés"},
			{"id": "sept_traits", "label": "Sept traits sous un arc"},
			{"id": "vague", "label": "Une vague"},
			{"id": "bolas", "label": "Deux pierres reliées d'un trait"},
		], "emplacements": [{"id": "serrure", "label": "La serrure"}]},
		{"placement": {"serrure": "trois_cercles"}},
		"La porte recule, pivote, et vous rend la galerie du commandeur. Vous êtes à peine passés qu'elle "
		"revient d'elle-même, sans hâte, et se referme avec un bruit de pierre qu'on repose. Elle est "
		"toujours tiède.",
		"Le sceau tourne dans la serrure sans rien accrocher.",
		[aelis("ouverture", "Un sceau. Le premier signe de la porte, et le premier de la boîte : celui du socle."),
		 aelis("echec", "Pas celui-là. Celui que Villard posait sur l'armoire."),
		 compagnon("voleur", "ouverture", "Une serrure qui prend un sceau au lieu d'une clé. On ne la crochète pas, celle-là.")],
		prerequis=[E_ARCHE],
		conditions=[ESCORTE_ACTIVE, {"combat_gagne": {"lieu": SALLE}}])
	return [gravures, anneaux, arche, retour]


# ---------------------------------------------------------------------------------------------
# Donjon : trois penanggalan, salle à composition fixe
# ---------------------------------------------------------------------------------------------
# Mesuré (`potentiel.potentiel_menace`, dump du 21/11) : penanggalan ≈ 128 au grade 4 (champion),
# ≈ 136-141 au grade 5 → chacune de rang C (105–175) ; trois ensemble passent le plancher B (175).
# Calibrage à éprouver en jeu : Aélis est dans la salle, et les penanggalan volent et mordent.

def donjon():
	return {"_id": DONJON, "type": "donjon", "nom": "L'arche éteinte",
			"description": "Une salle ronde sous l'ossuaire de Lutecia, d'une pierre que personne n'a creusée, "
						   "et au fond une arche bâtie par un héritier des Frères, éteinte.",
			"portail": ANTICHAMBRE, "niveau_min": 4, "niveau_max": 5,
			"musique": "Ambience_Cave_00.mp3", "musique_volume": 0.45,
			"battle_maps": [{"lieu": SALLE, "especes": [PENANGGALAN],
							 "composition": {PENANGGALAN: 3}, "niveau_min": 4, "niveau_max": 5}]}


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
	for requis in (COMMANDEUR, AELIS_ARCHIVES, ARCHIVES, ENCLOS, LUTECIA, PENANGGALAN):
		if requis not in par_id:
			sys.exit(f"ERREUR : {requis} absent du dump")
	neufs = lieux_neufs() + pnj_neufs() + enigmes() + [donjon()]
	# Une fois importés, les docs neufs sont au dump : on les réémet (régénération idempotente),
	# en le disant — un doc retouché depuis à la main serait écrasé par l'import.
	collisions = [d["_id"] for d in neufs if d["_id"] in par_id]
	if collisions:
		print("⚠️ ids déjà présents au dump (écrasés par l'import) :", ", ".join(collisions))
	relus = [aelis_archives(par_id[AELIS_ARCHIVES]), commandeur(par_id[COMMANDEUR]), lieu_archives(par_id[ARCHIVES])]
	docs = relus + neufs
	fautes = controler(docs, par_id)
	if fautes:
		sys.exit("ERREUR :\n  " + "\n  ".join(fautes))
	# DELTA seul (CLAUDE.md §18) : un doc identique à celui du dump n'a rien à réimporter.
	docs = [d for d in docs if d["_id"] not in par_id or sans_rev(par_id[d["_id"]]) != d]
	if not docs:
		print("Rien à importer : le dump est à jour.")
		return
	with open(SORTIE, "w", encoding="utf-8", newline="\n") as f:
		f.write(json.dumps(docs, ensure_ascii=False, indent=2) + "\n")
	print(f"{len(docs)} docs → {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
	main(sys.argv)
