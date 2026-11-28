#!/usr/bin/env python
# dev/gen_quetes_de_l_hekla.py
# L'arc de l'Hekla (rang A), jouable de bout en bout et relié à Mu (demande du 28/11/2026).
# Conception : docs/plan_hekla.md, docs/hekla_neuf_cercles.md ; récit canon :
# docs/lore/cites/20260820_decrire_l_histoire_de_reykjavik.md § Le gouffre de l'Hekla.
#
#   Le chemin (arbitré le 28/11)
#     Mu : Aélis (fare des Marées) lit l'Hekla « demeure » sur la copie du relevé, et donne rendez-vous au seuil.
#     Notre-Dame tire Reykjavik (Hallgrímskirkja), Nidaros ou Bruges : un lien portail Hallgrímskirkja ↔ Nidaros,
#     un second Nidaros ↔ Bruges (la Hanse, retour par Bruges → Orléans → la route). Nidaros = son seul portail.
#     Reykjavik : la commanderie (texte seul). Islande : la forteresse templière au sud (cour, cellules, seuil),
#     ouverte à qui porte la copie, ou a passé l'épreuve.
#   L'épreuve d'accès — deux apports exclusifs, 400 XP, aucun objet :
#     A. La chasse au Malebranche (Gizurr) : trois traces sur l'Islande (déduction, bouton 🔍 de la carte), puis
#        la cavité du volcan (combat à l'arrivée : un Malebranche qui fuit à 30 %) ; la dépouille reste aux Templiers.
#     B. Le démon qui ment (Sæmundr) : la déduction du registre des gardes, aux cellules ; le démon avoue,
#        Sæmundr reçoit l'aveu recopié.
#   La descente — apport d'Aélis (seuil), 800 XP (600 l'entretien + 200 le récit : une seule quête, Auteur 28/11) :
#     Lucifer remet un éclat de givre du Cocyte qui ne fond pas ; le rendre à Aélis, c'est le récit.
#
#   L'Enfer : SALLES GARDÉES ENCHAÎNÉES (Auteur, 28/11). Le moteur n'ouvre une salle de donjon classique que par
#   le service `acces` d'un PNJ, un par salle, et ne note aucune victoire dans un donjon à étages : chaque espace
#   des cercles est donc un LIEU EXPLORABLE (la carte de l'Auteur, grille relevée à l'œil) où l'on marche ; les
#   geôliers secondaires y attaquent À L'ARRIVÉE (`combat_arrivee`, ils reprennent leur poste après le délai) ;
#   le gardien est un PNJ POSTÉ sur sa carte (`cases`) qui ouvre sa salle gardée (même carte, doc `battle_map`) —
#   vaincu (`combat_gagne`), il ne revient pas et le passage suivant s'ouvre pour toujours. Quatre seuils entre
#   donjons (lieux illustrés) : le Haut-Enfer, la porte du festin, la porte des tombeaux, le puits des Géants.
#   Les détenus ne se combattent jamais (sauf Ciacco) ; ils parlent, et ne s'accordent sur rien.
#
#   Registre des entrées (plan § 8 bis) : la condition `intro_raison` ; la prison TUTOIE (seule exception voulue
#   au « vous » du jeu) ; aucune conséquence mécanique.
#
# ⚠️ UN SEUL FICHIER À IMPORTER : jsons/quetes_de_l_hekla_a_importer.json, DELTA seul (CLAUDE.md §18) :
# espèces (dev/gen_monstres_hekla.py), Aélis de Mu et la carte de Bruges RELUES du dump, docs neufs COMPLETS.
# Images : dev/gen_images_hekla.py (manifeste dev/batch/hekla/manifeste.json) ; portraits des gardiens copiés de
# leur image de monstre (`pnj/<slug>_hekla01.webp`). Hallgrímskirkja et Nidaros : portails génériques PROVISOIRES.
#
# Usage : python dev/gen_quetes_de_l_hekla.py [jsons/telluris-dump-….json]

import importlib.util
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.join(RACINE, "dev"))


def _charger(nom):
	spec = importlib.util.spec_from_file_location(nom, os.path.join(RACINE, "dev", nom + ".py"))
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod


V = _charger("gen_vestiges_premier_passage")
import gen_monstres_hekla as M  # noqa: E402

choix, noeud, ajouter_choix, sans_rev = V.choix, V.noeud, V.ajouter_choix, V.sans_rev
pnj_doc, entree_pnj, compagnon = V.pnj_doc, V.entree_pnj, V.compagnon

SORTIE = os.path.join(RACINE, "jsons", "quetes_de_l_hekla_a_importer.json")

# ── Déjà en base ──
REYKJAVIK, ISLANDE, BRUGES = "lieu:reykjavik", "lieu:islande", "lieu:bruges"
SCANDINAVIE = "lieu:scandinavie_meridionale"
AELIS_MU = "pnj:aelis_de_montfaucon_mu"
Q_PAROLE = "quete:la_mere_des_serpents"            # Mu : la voie de la parole
E_SCELLEMENT = "enigme:scellement_de_la_porte"     # Mu : la chambre du sceau comprise
COPIE = "item:copie_partielle_du_releve_des_seuils"
PORTRAIT_AELIS = "architecte_Aélis_de_Montfaucon_souriante_transparent.webp"
PORTRAIT_SAEMUNDR = "maitre_saemundr_d_akureyri01.jpg"

# ── Surface ──
NIDAROS = "lieu:sanctuaire_portail_de_nidaros"
HALLGRIM = "lieu:hallgrimskirkja"
COMMANDERIE = "lieu:commanderie_de_reykjavik"
FORTERESSE = "lieu:forteresse_de_l_hekla"
COUR = "lieu:cour_de_la_forteresse_de_l_hekla"
CELLULES = "lieu:cellules_de_la_forteresse_de_l_hekla"
SEUIL = "lieu:seuil_de_l_hekla"
CAVITE = "lieu:cavite_du_malebranche"
# Cases relues sur les grilles du dump du 27/11 (vérifiées par `_portes_praticables`).
POS_HALLGRIM, POS_COMMANDERIE = (55, 24), (37, 28)        # Reykjavik
POS_FORTERESSE, POS_CAVITE = (41, 38), (37, 37)           # Islande (le volcan au sud, la cavité sur sa route)
POS_BRUGES_VOISIN = (44, 26)                               # porte d'Orléans à Bruges : le portail de Nidaros à côté

# ── L'Enfer : seuils entre donjons (lieux illustrés) ──
HAUT_ENFER = "lieu:haut_enfer"
PORTE_FESTIN = "lieu:porte_du_festin"
PORTE_TOMBEAUX = "lieu:porte_des_tombeaux"
PUITS_GEANTS = "lieu:puits_des_geants"
COCYTE = "lieu:coeur_du_cocyte"

# ── Quêtes ──
Q_CHASSE = "quete:chasse_au_malebranche"
Q_RUSE = "quete:le_demon_qui_ment"
Q_DESCENTE = "quete:la_descente_de_l_hekla"
QUETES = (Q_CHASSE, Q_RUSE, Q_DESCENTE)

# ── Objets ──
DEPOUILLE = "item:malebranche"                      # butin de l'espèce (gen_monstres_hekla)
AVEU = "item:aveu_du_demon_captif"
GIVRE = "item:eclat_de_givre_du_cocyte"

# ── PNJ ──
GIZURR = "pnj:gizurr_thorvaldsson"
SAEMUNDR = "pnj:saemundr_hekla"                     # Sæmundr AFFECTÉ à la forteresse (celui d'Akureyri reste)
DEMON = "pnj:demon_captif_de_l_hekla"
AELIS_HEKLA = "pnj:aelis_de_montfaucon_hekla"
LUCIFER = "pnj:lucifer"
VIEILLARD = "pnj:vieillard_des_limbes"
FEMME_TOMBEAU = "pnj:femme_du_tombeau"
CORNU = "pnj:prisonnier_cornu"
ENCHAINE = "pnj:gardien_enchaine"

# ── Énigmes ──
E_TRACES = "enigme:traces_du_malebranche"
E_DEMON = "enigme:le_demon_qui_ment"

PORTRAITS = {
	GIZURR: "commandeur_elfe_m_forteresse_de_l_hekla01.webp",
	SAEMUNDR: PORTRAIT_SAEMUNDR,
	DEMON: "demon_captif_forteresse_de_l_hekla01.webp",
	AELIS_HEKLA: PORTRAIT_AELIS,
	LUCIFER: "lucifer_cocyte03.webp",
	VIEILLARD: "vieillard_des_limbes01.webp",
	FEMME_TOMBEAU: "femme_du_tombeau_dite01.webp",
	CORNU: "prisonnier_cornu_malebolge01.webp",
	ENCHAINE: "gardien_enchaine_malebolge01.webp",
}

IMG = {
	HALLGRIM: "portail_de_temple_europe01.png",      # PROVISOIRE : aucune image de la Hallgrímskirkja
	NIDAROS: "portail_de_temple_europe02.png",       # PROVISOIRE : aucune image de Nidaros
	COMMANDERIE: "commanderie_de_reykjavik01.webp",
	FORTERESSE: "forteresse_de_l_hekla01.webp",
	COUR: "cour_de_la_forteresse_de_l_hekla01.webp",
	CELLULES: "cellules_de_la_forteresse_de_l_hekla01.webp",
	SEUIL: "seuil_de_l_hekla01.webp",
	HAUT_ENFER: "entree_du_haut_enfer01.webp",
	PORTE_FESTIN: "porte_du_festin01.webp",
	PORTE_TOMBEAUX: "porte_des_tombeaux02.webp",
	PUITS_GEANTS: "puits_des_geants01.webp",
	COCYTE: "coeur_du_cocyte02.webp",
}

# ---------------------------------------------------------------------------------------------
# Grilles des cartes de combat (30 × 17, relevées à l'œil le 28/11 sur les images de l'Auteur ;
# à retoucher dans l'éditeur). 0 = vide, roche, lave, eau profonde ; 1 = sol ; 3 = fange ; 5 = eau peu
# profonde. Une seule composante praticable est gardée (`_principale`) : une case isolée ne peut ni
# accueillir un combattant, ni le piéger.
# ---------------------------------------------------------------------------------------------
L_CARTE, H_CARTE = 30, 17


def _vide():
	return [[0] * L_CARTE for _ in range(H_CARTE)]


def _spans(rangs, valeur=1, g=None):
	g = g or _vide()
	for y, spans in rangs.items():
		for a, b in spans:
			for x in range(max(a, 0), min(b, L_CARTE - 1) + 1):
				g[y][x] = valeur
	return g


def _poser(g, cases, valeur):
	for x, y in cases:
		if 0 <= x < L_CARTE and 0 <= y < H_CARTE:
			g[y][x] = valeur
	return g


def _rect(x0, x1, y0, y1):
	return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]


def _principale(g):
	"""Seule la plus grande composante praticable (4-voisins) reste ; le reste passe à 0."""
	vus, comps = set(), []
	for y in range(H_CARTE):
		for x in range(L_CARTE):
			if g[y][x] and (x, y) not in vus:
				comp, pile = [], [(x, y)]
				vus.add((x, y))
				while pile:
					cx, cy = pile.pop()
					comp.append((cx, cy))
					for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
						if 0 <= nx < L_CARTE and 0 <= ny < H_CARTE and g[ny][nx] and (nx, ny) not in vus:
							vus.add((nx, ny))
							pile.append((nx, ny))
				comps.append(comp)
	garde = set(max(comps, key=len)) if comps else set()
	return [[g[y][x] if (x, y) in garde else 0 for x in range(L_CARTE)] for y in range(H_CARTE)]


def grille_cavite():
	return _principale(_spans({0: [(13, 15)], 1: [(13, 15)], 2: [(13, 15)], 3: [(13, 15)], 4: [(4, 26)],
							   **{y: [(3, 27)] for y in range(5, 13)}, 13: [(4, 26)], 14: [(9, 17)],
							   15: [(11, 16)], 16: [(11, 16)]}))


def grille_acheron():
	"""La rive basse, le ponton et la barque ; l'Achéron (eau noire) et l'autre rive restent hors d'atteinte."""
	return _principale(_spans({9: [(11, 16)], 10: [(10, 16)], 11: [(14, 16)], **{y: [(0, 29)] for y in range(12, 17)}}))


def grille_corniches():
	return _principale(_spans({
		1: [(14, 15)], 2: [(14, 15)], 3: [(1, 4), (14, 15)], 4: [(1, 17)], 5: [(7, 10), (14, 16)],
		6: [(7, 8), (12, 17), (19, 20)], 7: [(3, 8), (12, 27)], 8: [(2, 3), (8, 27)], 9: [(2, 3), (12, 17), (26, 28)],
		10: [(2, 3), (26, 28)], 11: [(2, 5), (25, 27)], 12: [(3, 5), (25, 28)], 13: [(0, 4), (26, 29)],
		14: [(0, 3), (27, 29)]}))


def grille_fange():
	g = _spans({y: [(0, 29)] for y in range(1, 16)}, valeur=3)
	for zone in (_rect(13, 15, 1, 3), _rect(8, 12, 5, 7), _rect(8, 13, 9, 10), _rect(24, 26, 4, 6), _rect(17, 19, 9, 12)):
		_poser(g, zone, 1)
	for zone in (_rect(17, 23, 2, 3), _rect(13, 16, 12, 13), _rect(0, 2, 10, 12)):
		_poser(g, zone, 5)
	return _principale(g)


def grille_festin():
	g = _spans({3: [(11, 19)], 4: [(2, 27)], **{y: [(1, 28)] for y in range(5, 17)}})
	for zone in (_rect(5, 7, 5, 8), _rect(10, 11, 6, 8), _rect(18, 19, 6, 8), _rect(22, 24, 5, 8),
				 _rect(2, 4, 10, 14), _rect(9, 10, 11, 14), _rect(19, 21, 11, 14), _rect(24, 26, 11, 14),
				 _rect(4, 5, 4, 7), _rect(25, 26, 4, 7)):
		_poser(g, zone, 0)
	return _principale(g)


def grille_arene():
	g = _spans({4: [(8, 23)], 5: [(6, 24)], **{y: [(5, 25)] for y in range(6, 11)}, 11: [(6, 24)], 12: [(8, 22)],
				**{y: [(12, 15)] for y in range(13, 17)}})
	for zone in (_rect(9, 10, 5, 6), _rect(13, 15, 4, 6), [(9, 9)], _rect(13, 14, 9, 11)):
		_poser(g, zone, 0)
	return _principale(g)


def grille_passerelles():
	g = _spans({
		**{y: [(0, 2)] for y in range(0, 17)}, 0: [(0, 2), (26, 29)], 1: [(0, 2), (26, 29)],
		2: [(0, 23), (26, 29)], 3: [(0, 29)], 4: [(0, 3), (19, 20), (24, 29)], 5: [(0, 3), (18, 19), (24, 29)],
		6: [(0, 8), (17, 19), (24, 29)], 7: [(0, 2), (4, 12), (16, 19), (24, 29)], 8: [(0, 2), (10, 18), (24, 29)],
		9: [(0, 3), (12, 19), (24, 25)], 10: [(0, 3), (10, 13), (16, 18), (22, 25)], 11: [(0, 3), (9, 11), (17, 19), (22, 25)],
		12: [(0, 2), (8, 10), (18, 19), (22, 24)], 13: [(0, 10), (18, 19)], 14: [(0, 10), (18, 19)],
		15: [(0, 24)], 16: [(0, 24)]})
	return _principale(g)


def grille_portes_dite():
	return _principale(_spans({7: [(0, 29)], 8: [(19, 21)], 9: [(19, 21)], 10: [(19, 21)], 11: [(2, 27)],
							   12: [(3, 25)], 13: [(6, 22)], 14: [(8, 21)], 15: [(11, 19)], 16: [(12, 18)]}))


def grille_tour():
	g = _vide()
	for y in range(H_CARTE):
		for x in range(L_CARTE):
			if ((x - 15) / 6.6) ** 2 + ((y - 8.5) / 5.8) ** 2 <= 1:
				g[y][x] = 1
	for zone in (_rect(10, 13, 7, 10), _rect(10, 11, 2, 5), _rect(14, 15, 2, 4), _rect(18, 19, 3, 5)):
		_poser(g, zone, 0)
	return _principale(g)


def grille_tombeaux():
	g = _spans({y: [(1, 28)] for y in (2, 8, 11, 13, 15, 16)})
	return _principale(_spans({y: [(14, 16), (6, 6), (22, 22)] for y in range(1, 17)}, g=g))


def grille_phlegethon():
	g = _spans({y: [(0, 29)] for y in range(H_CARTE)})
	riviere = {1: [(0, 3), (12, 20)], 2: [(0, 5), (11, 21)], 3: [(0, 21)], 4: [(1, 22)], 5: [(2, 12), (15, 23)],
			   6: [(3, 10), (20, 24)], 7: [(6, 9), (20, 24)], 8: [(20, 25)], 9: [(20, 25)], 10: [(20, 26)],
			   11: [(21, 29)], 12: [(22, 29)], 13: [(25, 29)]}
	_spans(riviere, valeur=0, g=g)
	# Le gué : des pierres plates de la berge basse jusqu'à la rive droite.
	_poser(g, [(21, 8), (22, 8), (23, 8), (21, 9), (22, 9), (23, 9), (24, 9), (25, 9), (21, 10), (22, 10), (20, 11),
			   (21, 11)], 1)
	return _principale(g)


def grille_foret():
	return _principale(_spans({
		4: [(2, 10), (20, 27)], 5: [(2, 2), (27, 27)], 6: [(2, 2), (27, 27)], 7: [(2, 2), (8, 10), (19, 21), (27, 27)],
		8: [(2, 2), (10, 11), (18, 19), (27, 27)], 9: [(2, 2), (11, 12), (17, 18), (27, 27)],
		10: [(2, 2), (12, 13), (16, 17), (27, 27)], 11: [(2, 2), (13, 16), (27, 27)], 12: [(2, 2), (13, 16), (27, 27)],
		13: [(2, 27)], 14: [(13, 16)], 15: [(13, 16)], 16: [(13, 16)]}))


def grille_desert():
	bord = {2: 24, 3: 21, 4: 20, 5: 19, 6: 18, 7: 17, 8: 16, 9: 15, 10: 13, 11: 13, 12: 12, 13: 12, 14: 12, 15: 11, 16: 10}
	debut = {2: 4, 3: 4, 4: 3}
	g = _spans({y: [(debut.get(y, 0), b)] for y, b in bord.items()})
	for zone in (_rect(9, 12, 5, 6), _rect(14, 16, 6, 7), _rect(5, 7, 9, 11), _rect(1, 3, 10, 12),
				 _rect(10, 12, 11, 12), _rect(7, 8, 14, 16)):
		_poser(g, zone, 0)
	_poser(g, [(4, 6), (5, 6), (6, 6), (6, 7), (7, 7), (8, 7), (9, 7), (9, 8), (10, 8), (11, 8), (11, 9), (12, 9),
			   (13, 9), (13, 10)], 5)  # le ruisseau rouge, guéable
	return _principale(g)


def grille_poix():
	g = _spans({y: [(0, 29)] for y in range(1, 17)})
	_poser(g, _rect(0, 1, 0, 3), 0)
	for y in range(H_CARTE):
		for x in range(L_CARTE):
			if ((x - 16) / 9) ** 2 + ((y - 8) / 5.5) ** 2 <= 1 or (19 <= x <= 28 and y <= 5):
				g[y][x] = 0
	_poser(g, [(16, 2), (17, 2), (18, 2), (16, 3), (17, 3), (18, 3), (19, 2), (20, 2), (21, 3), (19, 3), (20, 3),
			   (21, 4), (22, 4), (23, 5), (22, 5), (24, 6), (23, 6), (25, 6), (24, 7), (25, 7)], 1)  # le pont intact
	return _principale(g)


def grille_serpents():
	g = _spans({y: [(0, 29)] for y in range(H_CARTE)})
	for zone in (_rect(6, 21, 0, 2), _rect(7, 21, 3, 6), _rect(7, 21, 10, 16), _rect(0, 3, 0, 4), _rect(4, 5, 0, 4),
				 [(0, 12), (0, 13), (0, 14)], _rect(21, 22, 13, 14)):
		_poser(g, zone, 0)
	return _principale(g)


def grille_ponts():
	bord_droit = {**{y: 22 for y in range(0, 12)}, 12: 22, 13: 21, 14: 19, 15: 18, 16: 16}
	g = _vide()
	for y in range(H_CARTE):
		for x in range(L_CARTE):
			g[y][x] = 1 if (x <= 6 or x >= bord_droit[y]) else 0
	_poser(g, _rect(7, 9, 10, 11) + _rect(10, 12, 9, 10) + _rect(13, 17, 6, 10) + _rect(17, 19, 6, 7) + _rect(20, 22, 4, 6), 1)
	return _principale(g)


def grille_puits():
	g = _spans({1: [(8, 23)], 2: [(6, 25)], **{y: [(4, 26)] for y in range(3, 11)}, **{y: [(1, 28)] for y in range(11, 17)}})
	for y in range(H_CARTE):
		for x in range(L_CARTE):
			if ((x - 16) / 5) ** 2 + ((y - 6.5) / 4) ** 2 <= 1:
				g[y][x] = 0
	return _principale(g)


# ---------------------------------------------------------------------------------------------
# Les espaces des cercles : (lieu explorable, carte, grille, combat à l'arrivée, cercle)
# ---------------------------------------------------------------------------------------------
# Profils des geôliers secondaires (grade 3-4, docs/plan_hekla.md § 12) : rien ne borne autrement le grade
# d'un lieu sans zone d'influence.
PROFILS_SECONDAIRES = {"profil:veteran": 2, "profil:champion": 1}


def arrivee(espece, accompagnants=(), nb=0, reapparition=30):
	d = {"espece": espece, "reapparition_min": reapparition, "profil_weights": dict(PROFILS_SECONDAIRES)}
	if accompagnants:
		d["accompagnants"] = list(accompagnants)
		d["nb_accompagnants"] = nb
	return d


ACHERON, CORNICHES, FANGE, FESTIN = "lieu:rive_de_l_acheron", "lieu:corniches_du_vent", "lieu:fange_de_la_gourmandise", "lieu:salle_du_festin"
ARENE, PASSERELLES = "lieu:arene_de_l_avarice", "lieu:passerelles_du_styx"
PORTES_DITE, TOMBEAUX, TOUR = "lieu:portes_de_dite", "lieu:champ_des_tombeaux", "lieu:tour_des_furies"
PHLEGETHON, FORET, DESERT = "lieu:rive_du_phlegethon", "lieu:foret_des_suicides", "lieu:desert_de_feu"
POIX, SERPENTS, PONTS = "lieu:fosse_de_poix", "lieu:fosse_des_serpents", "lieu:ponts_des_flammes"
BORD_PUITS = "lieu:bord_du_puits_des_geants"

ESPACES = {
	CAVITE: ("cavite_du_malebranche01.webp", grille_cavite, None),
	ACHERON: ("rive_de_l_acheron01.webp", grille_acheron, None),
	CORNICHES: ("corniches_du_vent01.webp", grille_corniches, arrivee("espece:lonza", ["espece:lonza"], 1)),
	FANGE: ("fange_de_la_gourmandise01.webp", grille_fange, arrivee("espece:goule", ["espece:goule"], 3)),
	FESTIN: ("salle_du_festin01.webp", grille_festin, None),
	ARENE: ("arene_de_l_avarice01.webp", grille_arene, arrivee("espece:louve_maigre")),
	PASSERELLES: ("passerelles_du_styx01.webp", grille_passerelles,
				  arrivee("espece:demon_guerrier", ["espece:demon_guerrier"], 2)),
	PORTES_DITE: ("portes_de_dite01.webp", grille_portes_dite, arrivee("espece:ange_dechu", ["espece:ange_dechu"], 2)),
	TOMBEAUX: ("champ_des_tombeaux01.webp", grille_tombeaux, None),
	TOUR: ("tour_des_furies01.webp", grille_tour, None),
	PHLEGETHON: ("rive_du_phlegethon01.webp", grille_phlegethon, arrivee("espece:centaure", ["espece:centaure"], 2)),
	FORET: ("foret_des_suicides01.webp", grille_foret, arrivee("espece:harpie", ["espece:chienne_noire"], 2)),
	DESERT: ("desert_de_feu01.webp", grille_desert, arrivee("espece:lion_des_enfers")),
	POIX: ("fosse_de_poix01.webp", grille_poix, arrivee("espece:malebranche", ["espece:malebranche"], 3)),
	SERPENTS: ("fosse_des_serpents01.webp", grille_serpents, arrivee("espece:serpent_geant", ["espece:serpent_geant"], 1)),
	PONTS: ("ponts_des_flammes01.webp", grille_ponts, None),
	BORD_PUITS: ("bord_du_puits_d_antee01.webp", grille_puits, None),
}
# Le fugitif de la cavité : seul, sans accompagnant, au grade d'une épreuve de rang A.
COMBAT_CAVITE = {"espece": "espece:malebranche", "reapparition_min": 5,
				 "profil_weights": {"profil:veteran": 1, "profil:champion": 2}}

# ---------------------------------------------------------------------------------------------
# Les gardiens : (salle gardée, espace, PNJ, composition, grade min, grade max, cases du PNJ)
# ---------------------------------------------------------------------------------------------
GARDIENS = {
	"charon": ("lieu:combat_de_charon", ACHERON, "pnj:charon", {"espece:charon": 1}, 4, 4, _rect(14, 16, 9, 11)),
	"minos": ("lieu:combat_de_minos", CORNICHES, "pnj:minos", {"espece:minos": 1}, 4, 4, _rect(13, 16, 7, 8)),
	"ciacco": ("lieu:combat_de_ciacco", FESTIN, "pnj:ciacco", {"espece:ciacco": 1, "espece:goule": 2}, 4, 4,
			   _rect(12, 18, 3, 4)),
	"plutus": ("lieu:combat_de_plutus", ARENE, "pnj:plutus", {"espece:plutus": 1}, 4, 5, _rect(16, 22, 6, 9)),
	"phlegyas": ("lieu:combat_de_phlegyas", PASSERELLES, "pnj:phlegyas", {"espece:phlegyas": 1}, 4, 5,
				 _rect(22, 25, 9, 11)),
	"furies": ("lieu:combat_des_furies", TOUR, "pnj:les_furies",
			   {"espece:furie_tisiphone": 1, "espece:furie_megere": 1, "espece:furie_alecto": 1}, 4, 5,
			   _rect(14, 18, 5, 8)),
	"geryon": ("lieu:combat_de_geryon", DESERT, "pnj:geryon", {"espece:geryon": 1, "espece:centaure": 2}, 5, 5,
			   [(13, 8), (14, 8), (15, 8), (13, 9), (14, 9), (15, 9)]),
	"malacoda": ("lieu:combat_de_malacoda", PONTS, "pnj:malacoda", {"espece:malacoda": 1, "espece:malebranche": 3},
				 5, 5, _rect(13, 17, 6, 10)),
	"antee": ("lieu:combat_d_antee", BORD_PUITS, "pnj:antee", {"espece:antee": 1}, 5, 5, _rect(6, 11, 11, 13)),
}
PORTRAITS.update({pid: ("furies" if cle == "furies" else cle) + "_hekla01.webp"
				  for cle, (_s, _e, pid, *_r) in GARDIENS.items()})


def gagne(cle, attendu=True):
	c = {"combat_gagne": {"lieu": GARDIENS[cle][0]}}
	if not attendu:
		c["combat_gagne"]["attendu"] = False
	return c


# Portes sur chaque espace : (lieu, case d'arrivée / de départ) — cases praticables vérifiées.
PORTES = {
	CAVITE: (14, 15),
	ACHERON: {"entree": (14, 15), "barque": (15, 9)},
	CORNICHES: {"entree": (2, 3), "escalier": (14, 1)},
	FANGE: {"entree": (2, 8), "festin": (27, 8)},
	FESTIN: {"entree": (14, 15), "porte": (14, 3)},
	ARENE: {"entree": (14, 16), "pente": (5, 8)},
	PASSERELLES: {"entree": (1, 3), "barque": (23, 12)},
	PORTES_DITE: {"entree": (15, 16), "rempart": (15, 7)},
	TOMBEAUX: {"entree": (15, 2), "tour": (2, 15), "porte": (15, 16)},
	TOUR: {"entree": (13, 11)},
	PHLEGETHON: {"entree": (5, 14), "foret": (28, 16)},
	FORET: {"entree": (14, 16), "desert": (2, 4)},
	DESERT: {"entree": (3, 13), "falaise": (15, 8)},
	POIX: {"entree": (3, 8), "serpents": (27, 14)},
	SERPENTS: {"entree": (2, 8), "ponts": (26, 8)},
	PONTS: {"entree": (3, 9), "puits": (25, 8)},
	BORD_PUITS: {"entree": (14, 14), "cocyte": (16, 11)},
}


# ---------------------------------------------------------------------------------------------
# Conditions
# ---------------------------------------------------------------------------------------------

def avant(q):
	return {"quete_active": {"id": q, "attendu": False}, "quete_reussie": {"id": q, "attendu": False}}


def pendant(q):
	return {"quete_active": {"id": q}}


def apres(q):
	return {"quete_reussie": {"id": q}}


def apport_actif(item, objectif_atteint=None):
	f = {"types": ["collect"], "cible": item}
	if objectif_atteint is False:
		f["objectif_atteint"] = False
	return {"quete_active": f}


EPREUVE_FAITE = {"ou": [apres(Q_CHASSE), apres(Q_RUSE)]}


def libre_de_l_autre(q_autre):
	"""Les deux épreuves s'excluent : une seule suffit (plan § 4)."""
	return {"quete_active": {"id": q_autre, "attendu": False}, "quete_reussie": {"id": q_autre, "attendu": False}}


# ---------------------------------------------------------------------------------------------
# Constructeurs
# ---------------------------------------------------------------------------------------------

def lieu(id_, label, texte, categorie="chemin", parent=FORTERESSE, acces=None, pnj=None, image=None, **extra):
	d = {"_id": id_, "type": "lieu", "label": label, "image": image or IMG[id_], "categorie": categorie,
		 "lieu_parent": parent, "texte": texte}
	if acces:
		d["acces"] = acces
	if pnj:
		d["pnj"] = pnj
	d.update(extra)
	return d


def espace(id_, label, texte, tags, acces=None, pnj=None):
	image, grille, combat = ESPACES[id_]
	d = lieu(id_, label, texte, acces=acces, pnj=pnj, image=image,
			 dimensions={"x": L_CARTE, "y": H_CARTE}, cells=grille(), nav={}, tags=tags)
	if combat:
		d["combat_arrivee"] = combat
	return d


def salle(cle, label, tags):
	sid, eid, pid, *_ = GARDIENS[cle]
	image, grille, _c = ESPACES[eid]
	return {"_id": sid, "type": "lieu", "label": label, "image": image, "categorie": "battle_map",
			"dimensions": {"x": L_CARTE, "y": H_CARTE}, "cells": grille(), "tags": tags,
			"acces": {"gardien": pid, "cycle": 1, "refus": "Le gardien n'est plus là.",
					  "conditions": [gagne(cle, attendu=False)]}}


def donjon(cle, nom, description):
	sid, eid, _pid, compo, nmin, nmax, _cases = GARDIENS[cle]
	return {"_id": "donjon:" + sid.split(":", 1)[1], "type": "donjon", "nom": nom, "description": description,
			"portail": eid, "niveau_min": nmin, "niveau_max": nmax, "musique": "Ambience_Cave_00.mp3",
			"musique_volume": 0.45,
			"battle_maps": [{"lieu": sid, "especes": list(compo), "composition": compo,
							 "niveau_min": nmin, "niveau_max": nmax}]}


def lien(a, pos_a, label_a, b, label_b, pos_b=(0, 0), type_="chemin", bouton_a=None, slug=None):
	s = lambda x: x.split(":", 1)[1]  # noqa: E731
	na = {"lieu": a, "pos": list(pos_a), "label": label_a}
	if bouton_a is not None:
		na["bouton"] = bouton_a
	return {"_id": f"link:{slug or s(b) + '_to_' + s(a)}", "type": "connection",
			"nodes": [na, {"lieu": b, "pos": list(pos_b), "label": label_b}],
			"metadata": {"type": type_, "status": "ouvert"}}


def present(pid, nom, description, conditions=None, cases=None):
	e = entree_pnj(pid, nom, PORTRAITS[pid], description, conditions or [])
	if cases:
		e["cases"] = [list(c) for c in cases]
	return e


def item_quete(id_, nom, description, icon="📜", poids=0.2, categorie="document"):
	return {"_id": id_, "type": "item", "nom": nom, "sous_categorie": "", "icon": icon, "description": description,
			"rarete": "rare", "categorie": categorie, "slots": [], "poids": poids, "tags": ["quete", "hekla"]}


def offre_apport(q, titre, description, item, xp):
	return {"id": q, "titre": titre, "description": description, "item": item, "quantite": 1, "unique": True,
			"recompenses": {"xp": xp, "cuivre": 0}}


def enigme(id_, nom, famille, lieu_id, texte, elements, solution, reussite, echec, commentaires, conditions,
		   bouton=True):
	return V.enigme(id_, nom, famille, lieu_id, texte, elements, solution, reussite, echec, commentaires,
					bouton=bouton, conditions=conditions)


def temoin(pid, nom, race, description, vocation, accueil, repliques):
	noeuds = {"accueil": noeud(accueil, *[choix(i, lab, i, **({"condition": c} if c else {}))
										  for i, lab, c, _ in repliques],
							   choix("fin", "(S'éloigner.)", "fin"))}
	for i, _, _, texte in repliques:
		noeuds[i] = noeud(texte, choix("ok", "Revenir.", "accueil"))
	return pnj_doc(pid, nom, race, description, PORTRAITS[pid], noeuds, vocation=vocation)


def gardien(cle, nom, race, description, accueil, combattre_label, ouvre, extra_choix=(), extra_noeuds=None,
			refus="Le passage est derrière vous."):
	"""PNJ gardien posté sur sa carte : quelques répliques, puis le combat (service `acces` de sa salle)."""
	sid = GARDIENS[cle][0]
	noeuds = {
		"accueil": noeud(accueil, *extra_choix,
						 choix("combattre", combattre_label, condition={"acces_ouvrable": True},
							   action={"service": "acces", "op": "passer"}),
						 choix("fin", "(Reculer.)", "fin")),
		"ouvre": noeud(ouvre, choix("arme", "Lever votre arme.", "fin")),
		"refus": noeud(refus, choix("ok", "Revenir.", "accueil")),
	}
	noeuds.update(extra_noeuds or {})
	return pnj_doc(GARDIENS[cle][2], nom, race, description, PORTRAITS[GARDIENS[cle][2]], noeuds, vocation="monstre",
				   services={"acces": {"lieu": sid, "noeuds": {"ouvre": "ouvre", "refus": "refus"}}})


def present_gardien(cle, nom, description, conditions=None):
	_sid, _eid, pid, *_r, cases = GARDIENS[cle]
	return present(pid, nom, description, [gagne(cle, attendu=False)] + list(conditions or []), cases)


# ---------------------------------------------------------------------------------------------
# Le chemin : portails, Reykjavik, l'Islande, la forteresse
# ---------------------------------------------------------------------------------------------

def surface(par_id):
	nidaros = lieu(NIDAROS, "Le sanctuaire-portail de Nidaros",
		"Une nef de pierre grise au bord d'un fjord, battue de pluie, où deux arches de lumière se font face. "
		"L'une tremble d'un éclat de vapeur et de soufre : Reykjavik, au-delà des mers. L'autre sent le hareng "
		"et la cire : Bruges, où les marchands de la Hanse tiennent comptoir. On ne sort pas d'ici par une "
		"porte de bois.", categorie="portail", parent=SCANDINAVIE)
	hallgrim = lieu(HALLGRIM, "La Hallgrímskirkja",
		"La haute tour de Reykjavik, celle qui surveille le ciel. Sous ses voûtes, une arche de lumière mène à "
		"Nidaros. Le bâtiment est partagé : les Templiers gardent l'accès au monde, les Paladins les routes de "
		"l'Islande. Par les portes, la vapeur des sources chaudes monte entre les toits.",
		categorie="portail", parent=REYKJAVIK)
	commanderie = lieu(COMMANDERIE, "La commanderie des Templiers",
		"Une grande salle de pierre et de bois noirci, une cheminée où brûle la tourbe, des cartes de l'île "
		"épinglées aux murs et des registres scellés. Officiers et scribes travaillent sans lever la tête. On "
		"vous écoute poliment, puis on vous répond toujours la même chose : la forteresse du volcan, au sud, "
		"ne relève pas d'ici. Le commandeur Gizurr Þórvaldsson y tient la garde, et c'est à lui qu'il faut "
		"parler.", categorie="commanderie", parent=REYKJAVIK)
	forteresse = lieu(FORTERESSE, "La forteresse de l'Hekla",
		"Des murs de basalte noir sur les pentes du volcan, des tours trapues, une seule porte bardée de fer. "
		"Derrière, le cône de l'Hekla fume sous un ciel bas. La forteresse semble faite pour garder quelque "
		"chose à l'intérieur plutôt que pour se défendre du dehors.",
		categorie="forteresse", parent=ISLANDE,
		acces={"cycle": 1, "refus": "La porte reste close. « La forteresse n'est ouverte qu'à qui sait déjà ce "
									"qu'elle garde. »",
			   "conditions": [{"ou": [{"item": {"item": COPIE}}, EPREUVE_FAITE]}]},
		pnj=[present(GIZURR, "Gizurr Þórvaldsson", "Un elfe grand et sec en armure sombre, les mains sur le pommeau d'une épée plantée devant lui.")])
	cour = lieu(COUR, "La cour de la forteresse",
		"Des pavés de basalte saupoudrés de cendre, un puits, une forge sous un appentis, des gardes qui "
		"s'entraînent. Au fond, une grande porte de fer s'enfonce dans la montagne.",
		pnj=[present(SAEMUNDR, "Sæmundr", "Un homme maigre au manteau brûlé aux manches, qui regarde la porte de fer sans la quitter des yeux.")])
	cellules = lieu(CELLULES, "Les cellules",
		"Un couloir creusé dans la roche tiède, des grilles gravées de motifs de protection, un poste de garde "
		"où dort le registre de la nuit. Dans la dernière cellule, deux yeux de braise vous suivent.",
		pnj=[present(DEMON, "Le démon captif", "Une silhouette accroupie derrière les barreaux, qui sourit trop.")])
	seuil = lieu(SEUIL, "Le seuil de l'Hekla",
		"Au fond d'une grotte immense, une muraille de basalte encercle un gouffre d'où monte une lueur rouge et "
		"une chaleur qui fait trembler l'air. Au-dessus, des chaires de pierre attendent les magiciens d'un "
		"déversement. Une seule porte de fer dans la muraille.",
		acces={"cycle": 1, "refus": "Un garde se met en travers de la porte de fer. « Pas sans l'accord du "
									"commandeur. »", "conditions": [EPREUVE_FAITE]},
		pnj=[present(AELIS_HEKLA, "Aélis", "Aélis, assise devant une table de cuivre et de verre, qui mesure le gouffre sans le regarder.")])
	cavite = espace(CAVITE, "La cavité du volcan",
		"Une cavité de basalte sur la route du volcan, fendue de lave qui refroidit. Des restes d'animaux, des "
		"griffures, des résidus sombres et huileux. Quelque chose vous a vu arriver avant que vous ne le voyiez.",
		["sous-terrain", "volcan", "couvert", "pieges_2_2"],
		acces={"cycle": 1, "refus": "Aucune trace ne mène plus par ici.",
			   "conditions": [apport_actif(DEPOUILLE, objectif_atteint=False), {"enigme_resolue": {"id": E_TRACES}}]})
	cavite["lieu_parent"] = ISLANDE
	cavite["combat_arrivee"] = dict(COMBAT_CAVITE)
	liens = [
		lien(HALLGRIM, (0, 0), "L'arche vers Nidaros", NIDAROS, "L'arche vers Reykjavik", type_="portail",
			 slug="nidaros_to_hallgrimskirkja"),
		lien(BRUGES, _pos_bruges(par_id), "L'arche vers Nidaros", NIDAROS, "L'arche vers Bruges", type_="portail",
			 slug="nidaros_to_bruges"),
		lien(REYKJAVIK, POS_HALLGRIM, "Entrer à la Hallgrímskirkja", HALLGRIM, "Sortir dans la ville"),
		lien(REYKJAVIK, POS_COMMANDERIE, "Entrer à la commanderie des Templiers", COMMANDERIE, "Ressortir dans la ville"),
		lien(ISLANDE, POS_FORTERESSE, "Monter à la forteresse de l'Hekla", FORTERESSE, "Redescendre du volcan"),
		lien(FORTERESSE, (0, 0), "Ressortir de la cour", COUR, "Entrer dans la cour"),
		lien(COUR, (0, 0), "Remonter dans la cour", CELLULES, "Descendre aux cellules"),
		lien(COUR, (0, 0), "Remonter dans la cour", SEUIL, "Passer la porte de fer"),
		lien(ISLANDE, POS_CAVITE, "Entrer dans la cavité", CAVITE, "Ressortir sur la route du volcan", pos_b=PORTES[CAVITE]),
	]
	return [nidaros, hallgrim, commanderie, forteresse, cour, cellules, seuil, cavite] + liens


def _pos_bruges(par_id):
	"""Case praticable de Bruges la plus proche de la porte d'Orléans, hors des portes déjà posées."""
	b = par_id[BRUGES]
	cells = b.get("cells") or []
	# Le lien de Nidaros lui-même, une fois importé, n'est pas une porte « prise » (régénération idempotente).
	prises = {tuple(n.get("pos") or ()) for i, d in par_id.items()
			  if d.get("type") == "connection" and i != "link:nidaros_to_bruges"
			  for n in d.get("nodes") or [] if n.get("lieu") == BRUGES}
	x0, y0 = POS_BRUGES_VOISIN
	cand = sorted((abs(x - x0) + abs(y - y0), (x, y)) for y, rang in enumerate(cells) for x, v in enumerate(rang)
				  if v == 1 and (x, y) not in prises and (x, y) != (x0, y0))
	if not cand:
		sys.exit("ERREUR : aucune case praticable à Bruges pour le portail de Nidaros")
	return cand[0][1]


# ---------------------------------------------------------------------------------------------
# L'épreuve — Gizurr, Sæmundr, le démon captif
# ---------------------------------------------------------------------------------------------

def gizurr():
	offre = offre_apport(Q_CHASSE, "La chasse au Malebranche",
		"Une fluctuation passagère du seuil a laissé sortir un Malebranche, un démon subalterne qui se terre "
		"dans les cavités du volcan. Relevez ses traces sur la route du volcan, trouvez-le, et rapportez sa "
		"dépouille au commandeur Gizurr Þórvaldsson. Elle restera aux Templiers.", DEPOUILLE, 400)
	q = Q_CHASSE
	noeuds = {
		"accueil": noeud(
			"Un elfe grand et sec, les cheveux d'un blond cendré tirés en arrière, une cicatrice pâle sur la "
			"mâchoire. Il ne se lève pas. Derrière lui, par une meurtrière, le volcan fume.",
			choix("qui", "« Vous commandez ici ? »", "qui"),
			choix("copie", "Lui montrer la copie du relevé des seuils.", "copie", condition=avant(q)),
			choix("offre", "« Que faut-il pour passer ? »", "propose",
				  condition=dict(libre_de_l_autre(Q_RUSE), apport_offert=True)),
			choix("rappel", "« Le Malebranche… »", "rappel", condition={"apport_en_cours": True, "apport_possible": False}),
			choix("remettre", "Déposer devant lui la dépouille du Malebranche.", condition={"apport_possible": True},
				  action={"service": "apport", "op": "remettre"}),
			choix("ruse_fait", "« Sæmundr a son aveu. »", "ruse_fait", condition=apres(Q_RUSE)),
			choix("descente", "« Je remonte de l'autre côté. »", "descente_apres", condition=apres(Q_DESCENTE)),
			choix("passage", "« Et maintenant ? »", "passage",
				  condition=dict(apres(q), quete_reussie={"id": Q_DESCENTE, "attendu": False})),
			choix("fin", "(Prendre congé.)", "fin")),
		"qui": noeud(
			"« Gizurr Þórvaldsson. Je commande la garde du volcan. » Il vous détaille sans hâte. « Je ne suis "
			"pas ici pour comprendre ce qui se trouve derrière cette porte. Je suis ici pour m'assurer que cela y "
			"reste. Si vous cherchez quelqu'un qui comprend, Sæmundr est dans la cour. »",
			choix("ok", "Revenir.", "accueil")),
		"copie": noeud(
			"Il lit les quatre lignes, et s'arrête sur la troisième. Il ne demande pas d'où vient la copie. « La "
			"porte d'ici, marquée demeure. » Il vous la rend. « Ce papier prouve que vous savez ce que nous "
			"taisons. Il ne vous donne pas le droit d'entrer. Personne n'entre sans épreuve. »",
			choix("ok", "Revenir.", "accueil")),
		"propose": noeud(
			"« Deux épreuves. Une seule suffit, et vous choisissez. » Il lève un doigt. « Il y a trois nuits, "
			"le seuil a fluctué. Rien de grave, rien de durable : un Malebranche en a profité, un seul, et il "
			"rôde dans les cavités du volcan. Rapportez-moi sa dépouille. » Un second doigt. « Ou bien voyez "
			"Sæmundr. Il a un démon qui ment, et il aime qu'on le confonde. »",
			choix("accepter", "« Je chasse le Malebranche. »", action={"service": "apport", "op": "accepter"}),
			choix("plus_tard", "« Je vais voir Sæmundr d'abord. »", "fin")),
		"accepte": noeud(
			"« Il a laissé des traces sur la route du volcan. Des griffures, des résidus sombres, des restes de "
			"bêtes. Lisez-les avant d'entrer quelque part. » Il reprend sa lecture. « Sa dépouille reste ici. Ce "
			"n'est pas un trophée, c'est une preuve. »",
			choix("route", "« J'y vais. »", "fin")),
		"rappel": noeud("« Ses traces sont sur la route du volcan. Sa dépouille, ici. Rien d'autre ne m'intéresse. »",
						choix("ok", "Revenir.", "accueil")),
		"partiel": noeud("« Ce n'est pas lui. »", choix("ok", "Revenir.", "accueil")),
		"remis": noeud(
			"Gizurr fait emporter la dépouille sans la regarder longtemps. « Il a fui, ou il a essayé. Ils "
			"réfléchissent, ces choses-là. » Il signe un ordre. « Le seuil vous est ouvert. Je préviens : "
			"aucune équipe n'ira vous chercher de l'autre côté. Personne. »",
			choix("fin", "(Hocher la tête.)", "fin")),
		"ruse_fait": noeud(
			"« Il m'a montré. » Gizurr range un pli. « Vous avez fait mentir un menteur. Cela suffit. Le seuil "
			"vous est ouvert. Aucune équipe n'ira vous chercher de l'autre côté. »",
			choix("ok", "Revenir.", "accueil")),
		"passage": noeud(
			"« Le seuil est derrière la porte de fer de la cour. L'architecte de Lutecia y attend, avec ses "
			"instruments. » Il hausse à peine les épaules. « Elle étudie. Moi, je compte ceux qui reviennent. »",
			choix("ok", "Revenir.", "accueil")),
		"descente_apres": noeud(
			"Vous lui parlez de l'issue dans la glace, qui remonte droit au seuil. Il se tait longtemps. « Une "
			"porte que nous ne connaissions pas. » Il appelle un officier, donne trois ordres à voix basse. « Elle "
			"sera gardée dès ce soir. Une porte qu'on ignorait est une porte de trop. » Il vous regarde. « Je ne "
			"vous demanderai pas ce que vous avez vu. Je ne veux pas le savoir. »",
			choix("ok", "Revenir.", "accueil")),
	}
	return pnj_doc(GIZURR, "Gizurr Þórvaldsson", "elfe",
		"Commandeur des Templiers de Reykjavik à la forteresse de l'Hekla. Pragmatique, il n'est l'ennemi de personne.",
		PORTRAITS[GIZURR], noeuds, vocation="guerrier",
		services={"apport": {"offre": offre, "noeuds": {"accepte": "accepte", "partiel": "partiel", "remis": "remis"}}})


def saemundr():
	offre = offre_apport(Q_RUSE, "Le démon qui ment",
		"La forteresse garde un démon captif, pris lors d'une évasion ancienne. Il prétend savoir comment le "
		"Malebranche est sorti, et avoir fermé la porte extérieure pour l'en empêcher. Confrontez ses dires au "
		"registre des gardes, aux cellules, et rapportez son aveu à Sæmundr.", AVEU, 400)
	q = Q_RUSE
	noeuds = {
		"accueil": noeud(
			"Un homme maigre, le manteau brûlé aux manches, qui regarde la porte de fer de la cour comme on "
			"regarde un feu qu'on a appris à tenir. Il vous sourit sans se retourner.",
			choix("qui", "« Sæmundr ? On parle de vous à Akureyri. »", "qui"),
			choix("offre", "« Le commandeur parle d'un démon qui ment. »", "propose",
				  condition=dict(libre_de_l_autre(Q_CHASSE), apport_offert=True)),
			choix("chasse", "« Le Malebranche, que faut-il savoir ? »", "chasse", condition=pendant(Q_CHASSE)),
			choix("rappel", "« Le démon… »", "rappel", condition={"apport_en_cours": True, "apport_possible": False}),
			choix("remettre", "Lui tendre l'aveu du démon.", condition={"apport_possible": True},
				  action={"service": "apport", "op": "remettre"}),
			# Une condition de DIALOGUE ne connaît pas `ou` : une variante par épreuve (elles s'excluent).
			*[choix(f"enfer_{s}", "« Qu'y a-t-il derrière la porte ? »", "enfer", condition=apres(qe))
			  for s, qe in (("chasse", Q_CHASSE), ("ruse", Q_RUSE))],
			*[choix(f"dante_{s}", "« Un poète florentin, dit-on, en serait revenu. »", "dante", condition=apres(qe))
			  for s, qe in (("chasse", Q_CHASSE), ("ruse", Q_RUSE))],
			choix("fin", "(Le laisser veiller.)", "fin")),
		"qui": noeud(
			"« Natif d'Akureyri, et j'en garde le nom. » Il rit. « Les Islandais racontent qu'un Sæmundr le "
			"Savant a berné le diable en personne. Ce n'était qu'un démon mineur, et pas si bête. Moi, je "
			"connais les démons et ce qui remue au seuil. On m'a affecté ici. Je n'ai pas demandé à partir. »",
			choix("ok", "Revenir.", "accueil")),
		"propose": noeud(
			"« Il est aux cellules. Un fugitif d'autrefois, qu'on garde pour l'étudier. » Sæmundr se tourne enfin "
			"vers vous. « Il prétend savoir comment le Malebranche est sorti, et avoir fermé lui-même la porte "
			"extérieure pour l'en empêcher. Le registre des gardes est au poste. » Il sourit. « Ne cherchez pas à "
			"savoir s'il ment. Partez du principe qu'il ment. Cherchez ce qu'il ne peut pas dire sans se "
			"contredire. »",
			choix("accepter", "« Je le ferai mentir. »", action={"service": "apport", "op": "accepter"}),
			choix("plus_tard", "« Je préfère la chasse. »", "fin")),
		"accepte": noeud(
			"« Trois gardes, trois postes, une nuit en trois tranches. Le registre en dit un peu, lui le reste. "
			"Une seule façon fait tenir les deux ensemble. » Il retourne à sa porte. « Quand il avouera, "
			"recopiez ses mots. Il les reniera demain. »",
			choix("route", "« Aux cellules. »", "fin")),
		"chasse": noeud(
			"« Ne le prenez pas pour une bête. Il réfléchit, il observe, et il sait quand il doit fuir. » Sæmundr "
			"compte sur ses doigts. « Il pose des pièges, il frappe de loin, et quand il perd l'avantage, il "
			"détale. Empêchez-le de fuir, ou rattrapez-le. »",
			choix("ok", "Revenir.", "accueil")),
		"rappel": noeud("« Le registre au poste, ses dires dans la cellule. Ce qu'il ne peut pas dire sans se contredire. »",
						choix("ok", "Revenir.", "accueil")),
		"partiel": noeud("« Ce ne sont pas ses mots. »", choix("ok", "Revenir.", "accueil")),
		"remis": noeud(
			"Sæmundr lit l'aveu deux fois, et range la feuille avec un plaisir visible. « Il a menti, et il l'a "
			"dit. Sur le fugitif, rien de sûr : il n'en savait pas plus que nous. Ils n'en savent jamais plus que "
			"nous, c'est ce qui me rassure. » Il hoche la tête. « Je préviens le commandeur. Le seuil vous est "
			"ouvert. »",
			choix("fin", "(Prendre congé.)", "fin")),
		"enfer": noeud(
			"« Une prison. » Il dit le mot sans emphase. « Les portes s'ouvrent et se ferment, les détenus restent "
			"détenus, les geôliers font leur travail. Ce n'est pas une ruine. » Il regarde la porte de fer. « Ce "
			"que je ne comprends pas, c'est pour qui ils le font. »",
			choix("ok", "Revenir.", "accueil")),
		"dante": noeud(
			"« Un poète, guidé par un poète plus ancien. » Sæmundr baisse la voix. « Les Templiers jugent ce récit "
			"dangereux. Moi, je le trouve exact par endroits, et faux ailleurs. Qu'il ait vécu ce qu'il raconte "
			"ou qu'il l'ait recueilli, personne n'en sait rien. Le lieu ne lui obéit pas tout à fait. »",
			choix("ok", "Revenir.", "accueil")),
	}
	return pnj_doc(SAEMUNDR, "Sæmundr", "humain",
		"Élémentaliste natif d'Akureyri, affecté à la forteresse de l'Hekla : il connaît les démons et les manifestations du seuil.",
		PORTRAITS[SAEMUNDR], noeuds, vocation="elementaliste",
		services={"apport": {"offre": offre, "noeuds": {"accepte": "accepte", "partiel": "partiel", "remis": "remis"}}})


def demon_captif():
	q = Q_RUSE
	noeuds = {
		"accueil": noeud(
			"Un démon de taille d'homme, maigre, la peau rouge et craquelée comme une lave qui refroidit, de "
			"petites cornes recourbées. Il se penche vers les barreaux, les poignets dans des fers gravés. Son "
			"sourire est trop large et trop aimable.",
			choix("parler", "« Qui êtes-vous ? »", "parler"),
			choix("examiner", "« Parlez-moi de la nuit où le Malebranche est sorti. »", "fin",
				  condition={"quete_active": {"id": q}, "enigme_resolue": {"id": E_DEMON, "attendu": False}},
				  enigme=E_DEMON),
			choix("aveu", "« Recommencez. Sans mentir, cette fois. »",
				  condition={"quete_active": {"id": q}, "enigme_resolue": {"id": E_DEMON}, "don_recu": False},
				  action={"service": "don"}),
			choix("apres", "« Vous mentez encore ? »", "apres", condition=apres(q)),
			choix("fin", "(Reculer.)", "fin")),
		"parler": noeud(
			"« Un ami de la maison. » Il rit doucement. « Je suis sorti, autrefois, quand le seuil était moins bien "
			"tenu. On m'a repris. Depuis, on m'étudie. Je me laisse étudier. C'est un échange. » Il penche la "
			"tête. « Je sais beaucoup de choses. Certaines sont vraies. »",
			choix("ok", "Revenir.", "accueil")),
		"donne": noeud(
			"Le sourire tombe. « Bien. J'ai menti. La porte n'a jamais été sans garde, et je n'ai rien fermé du "
			"tout. » Il hausse les épaules dans ses fers. « Comment il est sorti ? Je n'en sais rien. Je voulais "
			"qu'on me croie utile. » Vous recopiez ses mots. Il vous regarde faire, et le sourire revient. "
			"« Demain, je dirai autre chose. »",
			choix("fin", "(Ranger la feuille.)", "fin")),
		"trop_lourd": noeud("« Vous ne pouvez rien porter de plus, pas même mes mots. »", choix("fin", "(Reculer.)", "fin")),
		"apres": noeud(
			"« Toujours. » Il sourit. « Mais vous, au moins, vous savez maintenant quand. C'est plus que la "
			"plupart. Revenez me voir. Je m'ennuie. »",
			choix("ok", "Revenir.", "accueil")),
	}
	return pnj_doc(DEMON, "Le démon captif", "demon",
		"Un démon mineur, fugitif d'autrefois, que la forteresse garde pour l'étudier. Il ment.", PORTRAITS[DEMON],
		noeuds, vocation="monstre",
		services={"don": {"item": AVEU, "quantite": 1, "cout_cuivre": 0, "unique": True, "unique_porteurs": True,
						  "noeuds": {"fait": "donne", "sans_fonds": "donne", "trop_charge": "trop_lourd"}}})


def enigme_demon():
	return enigme(E_DEMON, "Le démon qui ment", "deduction", CELLULES,
		"Le registre des gardes est ouvert sur la table du poste : trois gardes, trois postes (le couloir de garde, "
		"les cellules, la porte extérieure), une nuit en trois tranches (le soir, minuit, l'aube). Chaque garde "
		"tient chaque poste une fois, et chaque poste a un garde par tranche. Le registre ne dit pas tout. Le "
		"démon, lui, dit beaucoup.",
		{"indices": [
			{"id": "soir", "label": "Le registre : le soir", "fait": "Le soir, Hrafn tient le couloir de garde, et Ásta les cellules. Kolbeinn est donc à la porte extérieure."},
			{"id": "minuit", "label": "Le registre : minuit", "fait": "À minuit, Ásta tient la porte extérieure."},
			{"id": "aube", "label": "Le registre : l'aube", "fait": "À l'aube, Kolbeinn tient les cellules. Hrafn, qui a déjà fait le couloir, est donc à la porte, et Ásta au couloir."},
			{"id": "dire_porte", "label": "Ce que dit le démon de la porte", "fait": "« À minuit, la porte extérieure était sans garde. Je l'ai fermée moi-même, pour que le Malebranche ne sorte pas. »"},
			{"id": "dire_couloir", "label": "Ce que dit le démon du couloir", "fait": "« À l'aube, Kolbeinn dormait dans le couloir. Je l'ai entendu ronfler. »"},
			{"id": "grille", "label": "La grille de sa cellule", "fait": "Des griffures fraîches au bas de la grille. Elles ne disent rien de la porte extérieure."},
			{"id": "fers", "label": "Ses fers", "fait": "Les fers sont gravés et intacts. Il n'a pas quitté sa cellule cette nuit."},
		], "conclusions": [
			{"id": "vrai", "label": "Il dit vrai : la porte était sans garde à minuit, et il l'a fermée."},
			{"id": "asta", "label": "Ásta a quitté son poste à minuit, et le démon a vu juste."},
			{"id": "ment", "label": "Il ment : à minuit, Ásta tenait la porte, et il n'a rien fermé du tout."},
		]},
		{"conclusion": "ment", "indices": ["minuit", "dire_porte"], "seuil": 2},
		"À minuit, Ásta tenait la porte extérieure : le registre le dit. Elle n'a jamais été sans garde, et le "
		"démon, dans ses fers intacts, n'a rien fermé. À l'aube, Kolbeinn était aux cellules, pas dans le couloir. "
		"Tout ce qu'il a dit pour paraître utile se contredit. Il cesse de sourire.",
		"Le démon sourit plus largement. Ce n'est pas encore ce qu'il ne peut pas dire.",
		[compagnon("lettre", "examen:minuit", "Le registre est sec, précis. C'est lui qu'il faut croire, pas la voix."),
		 compagnon("voleur", "examen:fers", "Des fers qu'on ne crochète pas. Il n'a rien fermé d'ici."),
		 compagnon("mage", "ouverture", "Il ment comme on respire. Cherchez ce qui ne peut pas tenir ensemble."),
		 compagnon("guerrier", "echec", "Un garde à son poste ne laisse pas une porte ouverte. Regardez qui tenait laquelle.")],
		[apport_actif(AVEU)], bouton=False)


def enigme_traces():
	return enigme(E_TRACES, "Les traces du Malebranche", "deduction", ISLANDE,
		"Sur la route du volcan, à l'est de Reykjavik, la lande de lave porte des marques que personne n'a encore "
		"lues. Le Malebranche est passé par ici. Où s'est-il terré ?",
		{"indices": [
			{"id": "griffures", "label": "Les griffures sur la roche", "fait": "Des griffures doubles, à hauteur d'homme, sur les blocs de lave. Elles vont vers le sud, vers le volcan, jamais vers la côte."},
			{"id": "residus", "label": "Les résidus sombres", "fait": "Des traces noires, huileuses, qui sentent la poix. Elles s'arrêtent net au pied d'un éboulis, là où monte une odeur de soufre."},
			{"id": "restes", "label": "Les restes d'animaux", "fait": "Deux moutons dépecés, proprement, et les os rangés en tas. Il ne mange pas à la hâte : il s'installe."},
			{"id": "fumee", "label": "La fumée des sources", "fait": "Une source chaude fume plus loin vers l'ouest. Rien n'y mène : les traces l'évitent."},
			{"id": "corbeaux", "label": "Les corbeaux", "fait": "Des corbeaux tournent au-dessus d'un vallon au nord. Ils tournent toujours quelque part, en Islande."},
		], "conclusions": [
			{"id": "cote", "label": "Il a gagné la côte, pour fuir par la mer."},
			{"id": "source", "label": "Il se cache près de la source chaude, à l'ouest."},
			{"id": "cavite", "label": "Il s'est installé dans une cavité au pied du volcan, derrière l'éboulis."},
		]},
		{"conclusion": "cavite", "indices": ["griffures", "residus", "restes"], "seuil": 2},
		"Les griffures vont au volcan, la poix s'arrête au pied de l'éboulis, les os rangés disent un repaire. "
		"Derrière l'éboulis, une ouverture noire souffle une chaleur de forge. Il est là.",
		"La lande ne dit pas ça. Les traces vont ailleurs.",
		[compagnon("forestier", "ouverture", "Il ne fuit pas : il se cache. Celui qui fuit ne range pas les os."),
		 compagnon("forestier", "examen:residus", "De la poix. Ça ne vient pas d'ici, ça."),
		 compagnon("guerrier", "examen:restes", "Il a pris son temps. Il nous attend, peut-être."),
		 compagnon("voleur", "reussite", "Un éboulis devant une cavité, c'est une porte. Méfiez-vous du seuil : il aura posé des pièges.")],
		[apport_actif(DEPOUILLE)])


# ---------------------------------------------------------------------------------------------
# Aélis : le départ de Mu, le seuil, la descente et le récit
# ---------------------------------------------------------------------------------------------

def aelis_mu(doc):
	doc = sans_rev(doc)
	n = doc["dialogue"]["noeuds"]
	ajouter_choix(doc, "accueil", [
		choix("hekla", "« L'Hekla, sur la copie du relevé… »", "hekla_01", condition={"enigme_resolue": {"id": E_SCELLEMENT}}),
	], en_tete=True)
	n["hekla_01"] = noeud(
		"Aélis pose son crayon. « La troisième ligne. L'Hekla, marquée demeure, comme la porte d'ici. » Elle "
		"déroule une carte du nord. « Au sud de l'Islande, sous le volcan. Les Templiers de Reykjavik gardent une "
		"forteresse au-dessus, et personne ne dit ce qu'il y a dessous. Ici, la demeure était vide. Là-bas ? »",
		choix("hekla_02", "« Comment y aller ? »", "hekla_02"))
	n["hekla_02"] = noeud(
		"« Par Notre-Dame, avec un cristal jaune. Le tableau des seuils tire parfois Reykjavik, ou Nidaros, d'où "
		"une arche y mène. » Elle sourit. « Je vous y précède. Je vous attendrai au seuil, à la forteresse. Je "
		"n'irai pas plus loin. Ce n'est pas de la prudence : quelqu'un doit rester pour écouter le récit. »",
		choix("accueil", "Revenir.", "accueil"))
	return doc


def offre_descente():
	return offre_apport(Q_DESCENTE, "La descente de l'Hekla",
		"Derrière le seuil de l'Hekla s'étend un autre monde, dont personne ne connaît les règles. Descendez, "
		"voyez ce qu'il y a au fond, et revenez raconter à Aélis de Montfaucon ce que vous avez vu. Rapportez-lui "
		"une preuve que vous êtes allé jusqu'au bout.", GIVRE, 800)


def aelis_hekla():
	q = Q_DESCENTE
	noeuds = {
		"accueil": noeud(
			"Aélis est assise devant une table de cuivre et de verre, au bord de la muraille. Elle mesure les "
			"fluctuations du gouffre sans le regarder. Elle lève les yeux, et vous vouvoie comme toujours. « Vous "
			"voilà. »",
			choix("offre", "« Je descends. »", "propose", condition=dict(avant(q), apport_offert=True)),
			choix("rappel", "« Vous m'attendez ? »", "rappel", condition={"apport_en_cours": True, "apport_possible": False}),
			choix("remettre", "Poser devant elle l'éclat de givre, et raconter.", condition={"apport_possible": True},
				  action={"service": "apport", "op": "remettre"}),
			choix("mesures", "« Que mesurez-vous ? »", "mesures"),
			choix("apres", "« Et maintenant ? »", "apres", condition=apres(q)),
			choix("fin", "(La laisser mesurer.)", "fin")),
		"mesures": noeud(
			"« Le souffle du seuil. Il fluctue, comme une respiration. » Elle tapote une aiguille. « À Mu, la "
			"porte était fermée et l'on sentait quelque chose pousser. Ici, la porte est ouverte, et rien ne "
			"pousse. On dirait que quelqu'un, de l'autre côté, tient la porte avec soin. »",
			choix("ok", "Revenir.", "accueil")),
		"propose": noeud(
			"Elle repose son compas. « À Mu, nous avions affaire à une porte qu'on avait fermée. Ici, nous allons "
			"entrer dans un lieu dont personne ne connaît les règles. Ne supposez pas que ce que vous avez appris "
			"à Mu vaut ici. » Un temps. « Je reste. Allez jusqu'au fond, et revenez me dire ce qu'il y a. "
			"Rapportez-moi quelque chose de là-bas, que je puisse mesurer. »",
			choix("accepter", "« Je reviendrai. »", action={"service": "apport", "op": "accepter"}),
			choix("plus_tard", "« Pas encore. »", "fin")),
		"accepte": noeud(
			"« Neuf cercles, si le poète florentin dit vrai. Il ne dit pas tout vrai. » Elle vous tend une "
			"lanterne. « On dit qu'en bas, la glace remplace le feu. Je n'en sais rien. Je vous attends ici. »",
			choix("route", "Passer la porte de fer.", "fin")),
		"rappel": noeud("« Je vous attends ici. Jusqu'au fond, et revenez. »", choix("ok", "Revenir.", "accueil")),
		"partiel": noeud("« Ce n'est pas d'en bas. »", choix("ok", "Revenir.", "accueil")),
		"remis": noeud(
			"Aélis prend l'éclat à deux mains. Il ne fond pas, et le froid lui monte aux poignets. Vous racontez : "
			"les cercles, les geôliers, les détenus qui ne s'accordent sur rien, et au fond, dans la glace, celui "
			"dont ils ont conservé le nom. Elle écrit tout, sans vous interrompre une seule fois.",
			choix("comparer_parole", "« À Mu, j'ai vu un trône vide. »", "comparer_parole",
				  condition={"quete_reussie": {"id": Q_PAROLE}}),
			choix("comparer_combat", "« À Mu, nous n'avons vu que des fresques. »", "comparer_combat",
				  condition={"quete_reussie": {"id": Q_PAROLE, "attendu": False}})),
		"comparer_parole": noeud(
			"« Une demeure abandonnée, vue. Une prison habitée, vue. » Elle pose sa plume. « Hadès a quitté sa "
			"maison. Lucifer est captif dans la sienne, et ses geôliers le servent encore. » Elle regarde le "
			"gouffre. « Alors qu'est-il arrivé aux autres demeures du relevé ? Saint-Pierre. Un arbre du nord. »",
			choix("fin", "(Ne rien répondre.)", "fin")),
		"comparer_combat": noeud(
			"« Les fresques, et un seul mot sur une liste : demeure. » Elle relit sa page. « Ici, une prison "
			"habitée, vue. À Mu, une maison vide, peut-être. Pour vous, la comparaison reste une hypothèse. » Elle "
			"regarde le gouffre. « Si Hadès a quitté la sienne et si Lucifer est captif dans la sienne, qu'est-il "
			"arrivé aux autres demeures du relevé ? »",
			choix("fin", "(Ne rien répondre.)", "fin")),
		"apres": noeud(
			"Aélis vous observe un moment, plus longtemps que d'habitude. « Vous avez changé. » Elle cherche un mot, "
			"ne le trouve pas. « Je ne sais pas quoi. Vous non plus, peut-être. » Elle revient à ses aiguilles. "
			"« Rome garde une autre porte marquée demeure. Celle de Saint-Pierre. »",
			choix("ok", "Revenir.", "accueil")),
	}
	return pnj_doc(AELIS_HEKLA, "Aélis de Montfaucon", "humain",
		"Aélis de Montfaucon, architecte, au seuil de l'Hekla : elle étudie le portail et attend le récit, sans le franchir.",
		PORTRAITS[AELIS_HEKLA], noeuds, vocation="lettre",
		services={"apport": {"offre": offre_descente(), "noeuds": {"accepte": "accepte", "partiel": "partiel", "remis": "remis"}}})


# ---------------------------------------------------------------------------------------------
# L'Enfer — les espaces, les gardiens, les détenus, Lucifer
# ---------------------------------------------------------------------------------------------

def les_gardiens():
	charon = gardien("charon", "Charon", "demon", "Le nocher de l'Achéron, au premier cercle.",
		"Debout dans une longue barque noire, un vieillard immense et décharné, la barbe blanche, les yeux "
		"cerclés de braise. Il s'appuie sur sa rame. « Ce n'est pas ta barque. Les vivants ne passent pas. »",
		"« Je passerai quand même. »",
		"Il lève la rame à deux mains, et l'eau noire se met à battre contre le ponton.",
		extra_choix=(choix("apres", "« Passeras-tu les vivants, maintenant ? »", "apres", condition={"acces_libere": True}),),
		extra_noeuds={"apres": noeud(
			"Charon s'est rassis. Il rame sans un regard pour vous, et la barque attend, contre le ponton. Il ne "
			"meurt pas. Il rame.", choix("ok", "Revenir.", "accueil"))})
	minos = gardien("minos", "Minos", "demon", "Le juge des arrivants, au deuxième cercle.",
		"Sur la plateforme au-dessus du vide, un démon colossal à l'allure de vieux roi, la couronne de fer noir, "
		"assis sur un trône de juge. Sa longue queue s'enroule autour de lui, se déroule, s'enroule encore. Elle "
		"s'arrête quand il vous voit.",
		"« Je descendrai sans votre sentence. »",
		"« Alors je te la donnerai autrement. » La queue claque comme un fouet, et le vent se lève.",
		extra_choix=(
			choix("registre", "« Jugez-moi, alors. »", "registre_01"),
			choix("sentence", "« La sentence de mon exil était-elle juste ? »", "exil_01",
				  condition={"intro_raison": "exil"}),
			choix("aucune", "« Qu'y a-t-il dans votre registre, à mon nom ? »", "aucune_01",
				  condition={"intro_raison": None}),
		),
		extra_noeuds={
			"registre_01": noeud(
				"La queue s'enroule pour assigner un cercle, et s'arrête à mi-tour. Minos vous regarde longtemps. "
				"« Tu n'es pas entré ici pour la première fois aujourd'hui. » La voix est celle de la route, au "
				"tout début, celle qui te tutoyait. « Tu es entré quand tu as quitté les tiens. »",
				choix("comment", "« Comment le savez-vous ? »", "registre_02")),
			"registre_02": noeud(
				"« La prison tient registre de chaque entrée. » Il ne dit pas comment. Il ne le dira pas.",
				choix("ok", "Revenir.", "accueil")),
			"exil_01": noeud(
				"« Je peux te le dire. » Minos se penche. « Veux-tu l'entendre ? Un juge peut se tromper. La loi "
				"de cette prison a dérivé depuis longtemps. Et toi aussi. »",
				choix("entendre", "« Dites-le. »", "exil_02"),
				choix("refuser", "« Je ne veux pas l'entendre. »", "exil_refus")),
			"exil_02": noeud(
				"La queue s'enroule, une fois, deux fois, sept fois. « Le septième cercle. » Il ne nomme aucun "
				"acte. « C'est tout ce que je dis. Le reste, c'est toi qui le portes. »",
				choix("ok", "Revenir.", "accueil")),
			"exil_refus": noeud("« Sage, ou lâche. Je ne juge pas cela. » La queue se déroule.",
								choix("ok", "Revenir.", "accueil")),
			"aucune_01": noeud(
				"Minos feuillette un registre que vous ne voyez pas. Longtemps. « Rien. Tu n'es entré nulle "
				"part. » Il relève la tête. « Ton passé tient en peu de mots. Qui les a écrits ? »",
				choix("ok", "(Ne rien répondre.)", "accueil")),
		})
	ciacco = gardien("ciacco", "Ciacco", "humain", "Le détenu devenu maître du troisième cercle.",
		"Au bout de la salle du festin, sur l'estrade, un homme énorme et bouffi, ruisselant de pluie froide, une "
		"couronne de couverts tordus sur la tête. Il rit en vous voyant. « Un vivant ! À ma table ! Ici, personne "
		"ne mange jamais. »",
		"« Rendez cette salle. »",
		"« Ma salle ! » Il se lève, et la fange déborde de sous les tables. Des goules montent avec elle.",
		extra_choix=(
			choix("famine", "« Chez moi, la terre ne nourrissait plus. »", "famine", condition={"intro_raison": "famine"}),
			choix("qui", "« Vous êtes un détenu ? »", "qui"),
		),
		extra_noeuds={
			"famine": noeud(
				"Ciacco rit jusqu'à tousser. « La terre ne refuse jamais. Le grain va toujours quelque part. » Il "
				"s'essuie la bouche. « Toujours quelque part, chez quelqu'un. Tu ne t'es jamais demandé chez qui ? »",
				choix("ok", "Revenir.", "accueil")),
			"qui": noeud(
				"« Je l'étais. Je le suis encore, si tu veux. » Il hausse ses épaules énormes. « Les geôliers me "
				"laissent ma fange et ma salle. Ils trouvent ça juste, je crois. Je ne demande pas pourquoi. »",
				choix("ok", "Revenir.", "accueil")),
		})
	plutus = gardien("plutus", "Plutus", "demon", "Le gardien des biens confisqués, au quatrième cercle.",
		"Devant l'entrepôt des biens confisqués, un démon-loup bouffi dressé sur ses pattes, des clés et des "
		"cadenas pendus à son cou. Il hurle des mots que personne ne comprend : « Papè Satàn, papè Satàn "
		"aleppe ! »",
		"Passer outre ses hurlements.",
		"Il ne se tait pas. Il bondit.")
	phlegyas = gardien("phlegyas", "Phlégyas", "demon", "Le passeur du Styx, au cinquième cercle.",
		"Au signal du feu allumé sur la tour, une barque surgit des eaux noires, menée par un ancien roi géant, la "
		"mâchoire serrée, une couronne de bronze cabossée. « Te voilà, toi aussi ! » La colère lui sort de partout.",
		"« Menez-moi aux portes de Dité. »",
		"« Mener ? » Il saute de sa barque sur l'embarcadère, et sa perche ferrée siffle.")
	furies = gardien("furies", "Les Furies", "demon", "Alecto, Mégère et Tisiphone, en haut d'une tour de Dité.",
		"Sur la plateforme de la tour, trois femmes ailées à la chevelure de serpents. Tisiphone, devant, déroule "
		"un fouet. Mégère pointe un doigt griffu. Alecto lève une torche. Ensemble, elles crient un nom vers la "
		"cité : Méduse. Détournez les yeux.",
		"Garder les yeux baissés, et avancer.",
		"Elles fondent sur vous toutes les trois. Quelque part en dessous, une chose qu'il ne faut pas regarder "
		"attend qu'on lève la tête.")
	geryon = gardien("geryon", "Géryon", "monstre", "Le monstre de la fraude, au bord du gouffre du septième cercle.",
		"Au bord de la falaise, une créature monte du gouffre : un visage d'homme juste, bienveillant, serein, des "
		"pattes velues, un corps de serpent peint de nœuds et de cercles, et derrière, une queue de scorpion. Elle "
		"vous sourit. On a envie de la croire. À ses pieds, un détenu enchaîné parle tout seul d'un incendie.",
		"« Vous ne me tromperez pas. »",
		"Le visage sourit encore quand la queue frappe.",
		extra_choix=(
			choix("detenu", "Écouter le détenu enchaîné.", "detenu"),
			choix("pillage", "« Mon village a brûlé, lui aussi. Des pillards. »", "pillage", condition={"intro_raison": "pillage"}),
		),
		extra_noeuds={
			"detenu": noeud(
				"« Le feu est venu du sud », marmonne le détenu, « et il n'y avait personne. Personne, vous "
				"entendez ? Juste le feu. »",
				choix("ok", "Revenir.", "accueil")),
			"pillage": noeud(
				"Le détenu relève la tête vers vous. « Des pillards ? » Il rit, sans joie. « Ceux qui n'ont rien vu "
				"disent toujours des pillards. » Géryon sourit, et ne dit rien.",
				choix("ok", "Revenir.", "accueil")),
		})
	malacoda = gardien("malacoda", "Malacoda", "demon", "Le chef des Malebranche, au huitième cercle.",
		"Sur la plateforme entre les deux ponts, un démon noir plus grand que les autres, ailes repliées, harpon à "
		"la main. Il s'incline avec une politesse parfaite. « Des voyageurs ! Le pont de la sixième fosse est "
		"intact, je vous assure. Prenez-le. Mes garçons vous escorteront. »",
		"« Votre pont n'existe plus. »",
		"Son sourire ne bouge pas. « Quel dommage. » Les Malebranche sortent de la poix autour de vous.",
		extra_choix=(choix("pont", "« Quel pont ? »", "pont"),),
		extra_noeuds={"pont": noeud(
			"« Celui-là, là-bas. » Il désigne un pont effondré dont il ne reste que les piles. « Parfaitement "
			"solide. » Il ment avec un plaisir visible.", choix("ok", "Revenir.", "accueil"))})
	antee = gardien("antee", "Antée", "geant", "Le seul géant non enchaîné, au bord du puits du neuvième cercle.",
		"Au bord du puits, un géant immense, torse nu, la barbe prise de glace, les pieds plantés dans la roche. "
		"Autour de lui, ses frères sont enchaînés. Pas lui. « Les vivants ne descendent pas. »",
		"« Je descendrai. »",
		"Il serre les poings, et la glace craque sous ses pieds.")
	return [charon, minos, ciacco, plutus, phlegyas, furies, geryon, malacoda, antee]


def les_detenus():
	vieillard = temoin(VIEILLARD, "Le vieillard des Limbes", "humain", "Un détenu des Limbes, sans âge.", "lettre",
		"Un vieillard d'une maigreur extrême, assis sur une pierre, la peau grise comme de la cendre. Il lève les "
		"yeux vers vous avec une curiosité lente.",
		[("qui", "« Depuis quand êtes-vous ici ? »", None,
		  "« Avant lui. Avant l'ange dans la glace. » Il réfléchit. « J'ai oublié mon crime. J'ai oublié l'époque. "
		  "Les gardiens, eux, ont toujours été là. »"),
		 ("juge", "« Qui vous a jugé ? »", None,
		  "« Personne. C'est pour ça que je suis ici. Ceux qui n'avaient pas de juge. » Il sourit. « On attend. On "
		  "ne sait pas quoi. »")])
	femme = temoin(FEMME_TOMBEAU, "La femme du tombeau", "humain", "Une détenue de Dité, couverte de cendres.", "pretre",
		"Une femme assise sur le bord d'un tombeau ouvert, couverte de cendres de la tête aux pieds. Elle vous "
		"regarde comme si elle cherchait à se souvenir de vous.",
		[("qui", "« Pourquoi êtes-vous ici ? »", None,
		  "« On m'a enfermée quand mon dieu a disparu. » Elle regarde ses mains grises. « Ou bien je suis morte. Ou "
		  "condamnée. Ou j'attends. Je ne sais pas. »"),
		 ("dieu", "« Quel dieu ? »", None,
		  "Elle ouvre la bouche, la referme. « Je ne me souviens plus de son nom. Je me souviens qu'il est parti. »")])
	cornu = temoin(CORNU, "Le prisonnier cornu", "humain", "Un détenu de Malebolge, aux cornes brisées.", "voleur",
		"Un prisonnier aux deux cornes de bélier brisées, un collier de fer au cou, adossé à la pierre. Il vous "
		"regarde avec un demi-sourire.",
		[("geoliers", "« Les geôliers vous laissent parler ? »", None,
		  "« Ils sont libres de partir, tu sais. » Il rit. « Rien ne les retient. Ils restent par dévotion. Pas par "
		  "obligation. Demande-leur pour qui. Ils ne te le diront pas. »"),
		 ("lui", "« Et Lucifer ? »", None,
		  "« Leur maître. Leur prisonnier. Les deux. » Il hausse les épaules. « Ne me demande pas comment c'est "
		  "possible. Je suis enchaîné, pas instruit. »")])
	enchaine = temoin(ENCHAINE, "Le gardien enchaîné", "humain", "Un ancien serviteur puni, aux ailes brisées.", "guerrier",
		"Un ancien gardien en armure ternie, agenouillé, les ailes brisées pendant dans son dos, enchaîné aux "
		"poignets. Il vous regarde avec défi.",
		[("qui", "« Qui vous a enchaîné ? »", None,
		  "« J'ai désobéi. » Il ne dit pas à qui. « On punit ici aussi ceux qui gardent. »"),
		 ("lucifer", "« Lucifer est-il prisonnier ? »", None,
		  "Il se tait longtemps. « Il n'a pas toujours été prisonnier. » Il détourne les yeux. « Je n'en dirai pas "
		  "plus. »")])
	return [vieillard, femme, cornu, enchaine]


def lucifer():
	q = Q_DESCENTE
	questions = [
		("qui", "« Qui êtes-vous ? »", "« Celui dont ils ont conservé le nom. »"),
		("emprisonne", "« Qui vous a emprisonné ? »", "« Ceux qui ont décidé que je devais l'être. »"),
		("geoliers", "« Pourquoi les geôliers vous servent-ils ? »",
		 "« Ils servent ce qu'ils croient être leur devoir. Ne confondez pas fidélité et liberté. »"),
		("prisonniers", "« Pourquoi les prisonniers sont-ils ici ? »", "« Parce que quelqu'un a jugé qu'ils devaient y rester. »"),
		("maitre", "« Êtes-vous le maître de l'Enfer ? »", "« Le maître ? Regardez donc mes chaînes. »"),
		("liberer", "« Pourquoi ne vous libérez-vous pas ? »", "« Vous croyez que ces chaînes retiennent mon corps ? »"),
	]
	noeuds = {
		"accueil": noeud(
			"Au centre du lac gelé, un être colossal pris dans la glace jusqu'aux hanches, les bras croisés, des "
			"chaînes rouillées tendues de toutes parts. Ses ailes immenses sont couvertes de givre ; le vent glacé "
			"vient d'elles. Il vous regarde venir, calme, presque immobile. Il n'y a rien à combattre ici.",
			*[choix(i, label, i) for i, label, _ in questions],
			choix("jette", "« Qui jette ? »", "jette"),
			choix("secret", "(Écouter.)", "secret", condition={"intro_raison": "secret"}),
			choix("givre", "« Je dois rapporter quelque chose d'ici. »",
				  condition={"quete_active": {"id": q}, "don_recu": False}, action={"service": "don"}),
			choix("sortie", "« Comment repartir ? »", "sortie"),
			choix("fin", "(Se taire.)", "fin")),
		"jette": noeud(
			"« Ceux qui étaient avant. » Il ne dit pas avant quoi. « Ils ont conservé mon nom. Ils ont conservé mon "
			"trône. Ils ont conservé mes geôliers. Mais rien de tout cela ne leur appartient davantage qu'à moi. » "
			"Il penche la tête. « Et toi, qui t'a jeté sur la route ? »",
			choix("ok", "(Ne rien répondre.)", "accueil")),
		"secret": noeud(
			"Il vous tutoie, avec la voix de la route, au tout début. « Tu as refusé de le dire. Même à toi ? » Il "
			"attend. Rien ne vous oblige à répondre.",
			choix("taire", "(Se taire encore.)", "secret_tu"),
			choix("dire", "« Je ne m'en souviens plus. »", "secret_oubli")),
		"secret_tu": noeud("« Ce qu'on tait, on finit par l'oublier. » Il ferme les yeux.", choix("ok", "Revenir.", "accueil")),
		"secret_oubli": noeud("« Voilà. » Il n'ajoute rien.", choix("ok", "Revenir.", "accueil")),
		"donne": noeud(
			"Il souffle. Un éclat de glace se détache de ses chaînes et roule jusqu'à vos pieds, froid comme rien "
			"ne l'est là-haut. « Il ne fondra pas. Montrez-le à qui vous attend. Elle ne saura pas le mesurer. »",
			choix("ok", "Le ramasser.", "accueil")),
		"trop_lourd": noeud("« Vous portez trop de choses d'en haut. »", choix("ok", "Revenir.", "accueil")),
		"sortie": noeud(
			"Derrière lui, la glace s'ouvre sur une issue qui remonte droit vers le haut. « Vous êtes venu par la "
			"porte qu'ils ont construite. Vous pouvez repartir par celle qu'ils ont oubliée. » Elle ne s'ouvre que "
			"du dedans, pour qui lui a parlé et n'est pas détenu.",
			choix("ok", "Revenir.", "accueil")),
	}
	for i, _label, texte in questions:
		noeuds[i] = noeud(texte, choix("ok", "Revenir.", "accueil"))
	return pnj_doc(LUCIFER, "Lucifer", "ange",
		"L'ancien ange de lumière, captif dans la glace du Cocyte, au fond de l'Enfer sous l'Hekla. On ne le combat pas : on lui parle.",
		PORTRAITS[LUCIFER], noeuds, vocation="mage",
		services={"don": {"item": GIVRE, "quantite": 1, "cout_cuivre": 0, "unique": True, "unique_porteurs": True,
						  "noeuds": {"fait": "donne", "sans_fonds": "donne", "trop_charge": "trop_lourd"}}})


def les_lieux_de_l_enfer():
	haut = lieu(HAUT_ENFER, "Le Haut-Enfer",
		"Un escalier immense descend vers une plaine grise sous une lumière sans source. Au loin, un fleuve noir "
		"et un château à sept murs que personne n'habite. Des ombres assises ne lèvent pas les yeux.",
		pnj=[present(VIEILLARD, "Le vieillard des Limbes", "Un vieillard gris assis sur une pierre, qui attend.")])
	festin = lieu(PORTE_FESTIN, "La porte du festin",
		"Au fond de la salle du festin, une porte de pierre ouverte sur une pente vers des eaux noires. Autour de "
		"l'encadrement, des pierres très anciennes luisent faiblement : une structure faite pour tenir debout le "
		"voyageur, pas pour l'abriter.", acces={"cycle": 1, "refus": "La porte du fond ne bouge pas.",
												"conditions": [gagne("ciacco")]})
	tombeaux = lieu(PORTE_TOMBEAUX, "La porte des tombeaux",
		"Une porte de fer au fond du champ des tombeaux enflammés. Derrière, un chemin descend vers une lueur "
		"rouge et la rumeur d'un fleuve bouillant. Autour, les pierres anciennes luisent.",
		acces={"cycle": 1, "refus": "La porte de fer ne s'ouvre pas tant que la tour veille.", "conditions": [gagne("furies")]},
		pnj=[present(FEMME_TOMBEAU, "La femme du tombeau", "Une femme couverte de cendres, assise sur un tombeau ouvert.")])
	puits = lieu(PUITS_GEANTS, "Le puits des Géants",
		"Autour d'un trou noir et sans fond, d'immenses géants enchaînés se dressent comme des tours : Éphialte, "
		"Briarée aux cent bras, et un troisième qui marmonne une langue que personne ne comprend, « Raphel maì "
		"amècche zabì almi ». Les Templiers le disent Nemrod, celui de Babel. Rien ne le confirme.",
		acces={"cycle": 1, "refus": "Les ponts mentent ; le puits ne se trouve pas.", "conditions": [gagne("malacoda")]},
		pnj=[present(CORNU, "Le prisonnier cornu", "Un prisonnier aux cornes brisées, adossé à la pierre."),
			 present(ENCHAINE, "Le gardien enchaîné", "Un ancien gardien aux ailes brisées, agenouillé dans ses chaînes.")])
	cocyte = lieu(COCYTE, "Le cœur du Cocyte",
		"Un lac gelé immense, où des silhouettes sont prises dans la glace jusqu'au cou, plus profond à mesure "
		"qu'on avance. Au centre, une figure colossale enchaînée. Le vent glacé vient de ses ailes.",
		acces={"cycle": 1, "refus": "Le géant tient encore le bord du puits.", "conditions": [gagne("antee")]},
		pnj=[present(LUCIFER, "Lucifer", "Une figure colossale prise dans la glace, enchaînée, qui vous regarde venir.")])

	def g(cle, nom, desc, cond=None):
		return [present_gardien(cle, nom, desc, cond)]

	acheron = espace(ACHERON, "La rive de l'Achéron",
		"Une plaine grise sous une lumière sans source, et un fleuve noir qu'on ne franchit pas à pied. Une longue "
		"barque attend contre un ponton vermoulu.", ["enfer", "eau", "couvert"],
		pnj=[present(GARDIENS["charon"][2], "Charon", "Un vieillard immense debout dans sa barque.", cases=GARDIENS["charon"][6])])
	corniches = espace(CORNICHES, "Les corniches du vent",
		"Une falaise sur un vent qui ne cesse jamais. Des silhouettes passent dans la tourmente sans jamais toucher "
		"le sol. Les corniches sont étroites.", ["enfer", "vent", "falaise"],
		acces={"cycle": 1, "refus": "La barque ne vous a pas encore passé.", "conditions": [gagne("charon")]},
		pnj=g("minos", "Minos", "Un démon colossal sur un trône de juge, dont la queue s'enroule et se déroule."))
	fange = espace(FANGE, "La fange de la gourmandise",
		"Une pluie froide, de la grêle et de la neige sale sur une fange qui sent la pourriture. Quelques îlots "
		"secs. Ici, on ne mange jamais.", ["enfer", "boue", "pluie"],
		acces={"cycle": 1, "refus": "Le juge n'a pas rendu sa sentence.", "conditions": [gagne("minos")]})
	salle_festin = espace(FESTIN, "La salle du festin",
		"Une salle de festin aux tables vides, sous la pluie qui goutte du plafond. Sur l'estrade, une table haute "
		"où quelqu'un a fait sa cour.", ["enfer", "salle"],
		pnj=g("ciacco", "Ciacco", "Un homme énorme et bouffi sur l'estrade, couronné de couverts tordus."))
	arene = espace(ARENE, "L'arène de l'avarice",
		"Une arène circulaire partagée par une ligne au sol. Des détenus y poussent d'énormes poids l'un contre "
		"l'autre, se heurtent, repartent. Sur le côté, un entrepôt de biens confisqués qu'on ne rendra jamais.",
		["enfer", "arene"], pnj=g("plutus", "Plutus", "Un démon-loup bouffi devant l'entrepôt, qui hurle des mots incompréhensibles."))
	passerelles = espace(PASSERELLES, "Les passerelles du Styx",
		"Un marais noir, des passerelles de planches et des rebords de pierre. Dans la boue, les coléreux se "
		"frappent sans fin ; sous l'eau, d'autres soupirent et font bouillonner la surface. Au loin, les tours "
		"rouges de Dité.", ["enfer", "marais", "boue"],
		acces={"cycle": 1, "refus": "L'arène garde encore la pente.", "conditions": [gagne("plutus")]},
		pnj=g("phlegyas", "Phlégyas", "Une barque arrive au signal du feu, menée par un ancien roi furieux."))
	portes = espace(PORTES_DITE, "Les portes de Dité",
		"Une cité de fer rouge, des remparts où veillent des anges déchus qui ferment les portes aux vivants. Un "
		"escalier monte au chemin de ronde.", ["enfer", "rempart", "cite"],
		acces={"cycle": 1, "refus": "Le passeur ne vous a pas mené jusqu'ici.", "conditions": [gagne("phlegyas")]})
	champ = espace(TOMBEAUX, "Le champ des tombeaux",
		"Derrière les remparts, des rangées de tombeaux ouverts d'où sortent des flammes. Une tour domine le "
		"champ ; au fond, une porte de fer.", ["enfer", "tombeaux", "feu"])
	tour = espace(TOUR, "La tour des Furies",
		"Le sommet d'une tour de fer rouge, bordé de créneaux. Trois perchoirs tordus, des chaînes, des fouets. "
		"Au-delà, le vide et les toits de Dité.", ["enfer", "tour"],
		pnj=g("furies", "Les Furies", "Trois femmes ailées à la chevelure de serpents, qui crient un nom vers la cité."))
	phlegethon = espace(PHLEGETHON, "La rive du Phlégéthon",
		"Un fleuve de sang bouillant, une berge de roche brune, des arbres morts et un gué de pierres plates. Des "
		"traces de sabots dans la poussière.", ["enfer", "fleuve", "sang"])
	foret = espace(FORET, "La forêt des suicidés",
		"Des arbres noirs, noueux, couverts d'épines, aux branches brisées qui saignent. Des fourrés épais, des "
		"sentiers étroits, et quelque part, des aboiements.", ["enfer", "foret"])
	desert = espace(DESERT, "Le désert de feu",
		"Un sable brûlant sous une lente pluie de feu, des rochers noirs, et au bord, une falaise qui plonge dans "
		"un gouffre sans fond. Un ruisseau rouge s'y jette.", ["enfer", "desert", "feu"],
		pnj=g("geryon", "Géryon", "Une créature au visage d'homme juste, qui monte du gouffre."))
	poix = espace(POIX, "La fosse de poix",
		"Dix fosses de pierre grise reliées par des ponts, et ici, la poix noire qui bouillonne. Un pont intact, "
		"un autre effondré. Des harpons abandonnés sur les rives.", ["enfer", "fosse", "poix"],
		acces={"cycle": 1, "refus": "La falaise reste impraticable.", "conditions": [gagne("geryon")]})
	serpents = espace(SERPENTS, "La fosse des serpents",
		"Une fosse grouillante de serpents de toutes tailles, un pont de pierre étroit qui la traverse, des "
		"recoins d'ombre.", ["enfer", "fosse", "serpents"])
	ponts = espace(PONTS, "Les ponts des flammes",
		"Deux ponts de pierre au-dessus d'une fosse où flottent des flammes qui parlent. Elles conseillaient mal, "
		"autrefois. Sur la plateforme entre les ponts, quelqu'un vous attend.", ["enfer", "fosse", "feu"],
		pnj=g("malacoda", "Malacoda", "Un démon noir plus grand que les autres, qui s'incline avec politesse."))
	bord = espace(BORD_PUITS, "Le bord du puits",
		"Une margelle de roche couverte de givre, assez vaste pour un géant, autour d'un puits noir. Des anneaux de "
		"fer scellés dans la roche, des chaînes brisées.", ["enfer", "glace"],
		pnj=g("antee", "Antée", "Un géant immense au bord du puits, le seul que rien n'enchaîne."))
	return [haut, festin, tombeaux, puits, cocyte, acheron, corniches, fange, salle_festin, arene, passerelles,
			portes, champ, tour, phlegethon, foret, desert, poix, serpents, ponts, bord]


def les_salles_et_donjons():
	tags = ["donjon", "enfer"]
	salles = [
		salle("charon", "Charon, sur l'Achéron", tags + ["eau"]),
		salle("minos", "Minos, sur les corniches", tags + ["vent"]),
		salle("ciacco", "Ciacco, dans la salle du festin", tags),
		salle("plutus", "Plutus, dans l'arène", tags),
		salle("phlegyas", "Phlégyas, sur le Styx", tags + ["boue"]),
		salle("furies", "Les Furies, sur la tour", tags),
		salle("geryon", "Géryon, au bord du gouffre", tags + ["feu"]),
		salle("malacoda", "Malacoda, sur les ponts", tags + ["feu"]),
		salle("antee", "Antée, au bord du puits", tags + ["glace"]),
	]
	donjons = [
		donjon("charon", "La barque de Charon", "Le premier cercle de l'Enfer sous l'Hekla : la rive de l'Achéron."),
		donjon("minos", "Le tribunal de Minos", "Le deuxième cercle : les corniches battues du vent."),
		donjon("ciacco", "La salle de Ciacco", "Le troisième cercle : la salle du festin, où l'on ne mange jamais."),
		donjon("plutus", "L'arène de Plutus", "Le quatrième cercle : l'arène des biens confisqués."),
		donjon("phlegyas", "Le Styx de Phlégyas", "Le cinquième cercle : les eaux noires du Styx."),
		donjon("furies", "La tour des Furies", "Le sixième cercle : la cité de fer rouge de Dité."),
		donjon("geryon", "Le gouffre de Géryon", "Le septième cercle : le désert de feu et son gouffre."),
		donjon("malacoda", "Les ponts de Malacoda", "Le huitième cercle : Malebolge, les fosses de la fraude."),
		donjon("antee", "Le puits d'Antée", "Le neuvième cercle : le bord du puits, au-dessus du Cocyte."),
	]
	return salles + donjons


def liens_de_l_enfer():
	P = PORTES
	return [
		lien(SEUIL, (0, 0), "Remonter au seuil", HAUT_ENFER, "Descendre dans le gouffre"),
		lien(HAUT_ENFER, (0, 0), "Remonter l'escalier", ACHERON, "Descendre à la rive de l'Achéron", pos_b=P[ACHERON]["entree"]),
		lien(ACHERON, P[ACHERON]["barque"], "Monter dans la barque", CORNICHES, "Revenir à la barque", pos_b=P[CORNICHES]["entree"]),
		lien(CORNICHES, P[CORNICHES]["escalier"], "Descendre l'escalier de la falaise", FANGE, "Remonter vers les corniches",
			 pos_b=P[FANGE]["entree"]),
		lien(FANGE, P[FANGE]["festin"], "Entrer dans la salle du festin", FESTIN, "Ressortir dans la fange", pos_b=P[FESTIN]["entree"]),
		lien(FESTIN, P[FESTIN]["porte"], "Passer la porte du fond", PORTE_FESTIN, "Revenir dans la salle du festin"),
		lien(PORTE_FESTIN, (0, 0), "Remonter vers la porte du festin", ARENE, "Descendre la pente", pos_b=P[ARENE]["entree"]),
		lien(ARENE, P[ARENE]["pente"], "Descendre vers les eaux noires", PASSERELLES, "Remonter vers l'arène",
			 pos_b=P[PASSERELLES]["entree"]),
		lien(PASSERELLES, P[PASSERELLES]["barque"], "Prendre la barque de Phlégyas", PORTES_DITE, "Revenir à l'embarcadère",
			 pos_b=P[PORTES_DITE]["entree"]),
		lien(PORTES_DITE, P[PORTES_DITE]["rempart"], "Passer le chemin de ronde", TOMBEAUX, "Remonter sur le rempart",
			 pos_b=P[TOMBEAUX]["entree"]),
		lien(TOMBEAUX, P[TOMBEAUX]["tour"], "Monter à la tour", TOUR, "Redescendre au champ des tombeaux", pos_b=P[TOUR]["entree"]),
		lien(TOMBEAUX, P[TOMBEAUX]["porte"], "Passer la porte de fer", PORTE_TOMBEAUX, "Revenir au champ des tombeaux"),
		lien(PORTE_TOMBEAUX, (0, 0), "Remonter vers la porte des tombeaux", PHLEGETHON, "Descendre vers le fleuve de sang",
			 pos_b=P[PHLEGETHON]["entree"]),
		lien(PHLEGETHON, P[PHLEGETHON]["foret"], "Entrer dans la forêt", FORET, "Revenir au fleuve", pos_b=P[FORET]["entree"]),
		lien(FORET, P[FORET]["desert"], "Sortir vers le désert", DESERT, "Revenir dans la forêt", pos_b=P[DESERT]["entree"]),
		lien(DESERT, P[DESERT]["falaise"], "Descendre la falaise", POIX, "Remonter la falaise", pos_b=P[POIX]["entree"]),
		lien(POIX, P[POIX]["serpents"], "Passer à la fosse suivante", SERPENTS, "Revenir à la fosse de poix",
			 pos_b=P[SERPENTS]["entree"]),
		lien(SERPENTS, P[SERPENTS]["ponts"], "Passer aux ponts des flammes", PONTS, "Revenir à la fosse des serpents",
			 pos_b=P[PONTS]["entree"]),
		lien(PONTS, P[PONTS]["puits"], "Aller vers le puits", PUITS_GEANTS, "Revenir aux ponts"),
		lien(PUITS_GEANTS, (0, 0), "Remonter vers les géants", BORD_PUITS, "S'approcher du bord", pos_b=P[BORD_PUITS]["entree"]),
		lien(BORD_PUITS, P[BORD_PUITS]["cocyte"], "Descendre dans le puits", COCYTE, "Remonter vers le bord du puits"),
		# L'issue dans la glace : SENS UNIQUE, du dedans (aucun départ depuis le seuil).
		lien(SEUIL, (0, 0), "L'issue dans la glace", COCYTE, "Prendre l'issue dans la glace", bouton_a=False,
			 slug="coeur_du_cocyte_to_seuil_de_l_hekla_issue"),
	]


def objets():
	return [
		item_quete(AVEU, "Aveu du démon captif", "Les mots du démon captif de la forteresse de l'Hekla, recopiés de "
				   "votre main : il a menti, la porte n'a jamais été sans garde, il n'a rien fermé."),
		item_quete(GIVRE, "Éclat de givre du Cocyte", "Un éclat de glace détaché des chaînes de Lucifer, au fond de "
				   "l'Enfer sous l'Hekla. Il ne fond pas, et le froid monte aux poignets de qui le tient.",
				   icon="🧊", poids=0.5, categorie="composant"),
	]


# ---------------------------------------------------------------------------------------------
# Contrôles et écriture
# ---------------------------------------------------------------------------------------------

def _praticable(cells, pos):
	x, y = pos
	return 0 <= y < len(cells) and 0 <= x < len(cells[y]) and cells[y][x] in (1, 3, 5)


def controler_portes(docs, par_id):
	"""Toute porte posée sur une grille tombe sur une case praticable ; les cases des gardiens aussi."""
	tous = {**par_id, **{d["_id"]: d for d in docs}}
	fautes = []
	for d in docs:
		if d.get("type") != "connection":
			continue
		for n in d["nodes"]:
			cells = (tous.get(n["lieu"]) or {}).get("cells")
			if cells and tuple(n["pos"]) != (0, 0) and not _praticable(cells, n["pos"]):
				fautes.append(f"{d['_id']} : {n['lieu']} {n['pos']} n'est pas praticable")
	for cle, (_s, eid, _p, *_r, cases) in GARDIENS.items():
		cells = ESPACES[eid][1]()
		mortes = [c for c in cases if not _praticable(cells, c)]
		if len(mortes) == len(cases):
			fautes.append(f"gardien {cle} : aucune de ses cases n'est praticable sur {eid}")
	return fautes


REQUIS = (REYKJAVIK, ISLANDE, BRUGES, SCANDINAVIE, AELIS_MU, COPIE, "pnj:echidna", "espece:goule", "espece:centaure",
		  "espece:harpie", "espece:serpent_geant", "espece:demon_guerrier")


def generer(par_id, rangs_fn=None):
	for requis in REQUIS:
		if requis not in par_id:
			sys.exit(f"ERREUR : {requis} absent du dump")
	relus = [aelis_mu(par_id[AELIS_MU])]
	neufs = (surface(par_id) + [gizurr(), saemundr(), demon_captif(), enigme_demon(), enigme_traces(), aelis_hekla(),
								 lucifer()]
			 + les_gardiens() + les_detenus() + les_lieux_de_l_enfer() + les_salles_et_donjons() + liens_de_l_enfer()
			 + objets())
	return M.docs_monstres(par_id, rangs_fn) + relus + neufs


def main(argv):
	with open(V.dernier_dump(argv), encoding="utf-8") as f:
		dump = json.load(f)
	par_id = {d["_id"]: d for d in dump["docs"]}
	docs = generer(par_id)
	fautes = V.controler(docs, par_id) + controler_portes(docs, par_id)
	if fautes:
		sys.exit("ERREUR :\n  " + "\n  ".join(fautes))
	docs = [d for d in docs if d["_id"] not in par_id or sans_rev(par_id[d["_id"]]) != d]
	if not docs:
		print("Rien à importer : le dump est à jour.")
		return
	print("Neufs :", len([d for d in docs if d["_id"] not in par_id]), "· retouchés :",
		  ", ".join(d["_id"] for d in docs if d["_id"] in par_id) or "aucun")
	with open(SORTIE, "w", encoding="utf-8", newline="\n") as f:
		f.write(json.dumps(docs, ensure_ascii=False, indent=2) + "\n")
	print(f"{len(docs)} docs → {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
	try:
		sys.stdout.reconfigure(encoding="utf-8")
	except Exception:
		pass
	main(sys.argv)
