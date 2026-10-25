#!/usr/bin/env python
# dev/gen_missions_rang_b_a_lutecia.py
# Épreuves des RANGS B et A de Lutecia, toutes confiées par Maëlys, maîtresse de la Guilde.
# Plusieurs missions par montée (Auteur, 25/10) : `services.<x>.offres` (utils/offres.py) —
# à chaque visite du bureau, une offre tirée par service parmi celles du cran du joueur.
#
#   Rang B (cran C) : apport · la Gargouille de la Seine        (trophée au hasard)
#                     transport `retour` · le pli d'Aix-la-Chapelle (Hôtel de Ville)
#                     escorte · la Porte de Mars (Rhemi, portail mort-né)
#                     transport `retour` · la porte qui ne devait pas s'ouvrir (Enclos du Temple)
#   Rang A (cran B) : apport · le géant de la baie              (trophée au hasard)
#                     apport · la Bête du Gévaudan              (trophée au hasard)
#                     apport · le puits de Chartres             (donjon : 2 Minotaures, grade 4-5)
#                     escorte · l'Ampoule du Sacre (Rhemi → Chapelle Palatine d'Aix)
#                     escorte · la délégation palatine (Lutecia → Hôtel de Ville d'Aix)
#
# Calibrage (Auteur, 25/10) : les planchers de potentiel des épreuves de comptoir ne sont
# qu'une RÉFÉRENCE pour la Gargouille, la Bête et le Géant (folklore gardé, grades élevés
# visés) ; le Minotaure se compense par l'effectif (2, grade Champion-Héros).
#
# 100 % DONNÉE. ⚠️ UN SEUL FICHIER À IMPORTER (CLAUDE.md §18) :
# jsons/missions_rang_b_a_lutecia_a_importer.json — Maëlys et la carte de France RELUES du
# dernier dump (seuls `services` / les choix / `rencontres` bougent), le reste neuf. Les
# positions des portes sur les cartes de cité sont APPROCHÉES (case praticable la plus proche
# d'une cible), à recaler dans /admin/editor. Régénération idempotente.
#
# Usage : python dev/gen_missions_rang_b_a_lutecia.py [jsons/telluris-dump-….json]

import copy
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSONS = os.path.join(RACINE, "jsons")
SORTIE = os.path.join(JSONS, "missions_rang_b_a_lutecia_a_importer.json")

LUTECIA = "lieu:lutecia"
AIX = "lieu:aix_la_chapelle"
RHEMI = "lieu:rhemi"
CHARTRES = "lieu:chartres"
FRANCE = "lieu:france"
MAELYS = "pnj:maelys"
BUREAU = "lieu:le_grand_relais_des_frontieres_bureau_du_maitre"

# ── Quêtes ───────────────────────────────────────────────────────────────────────────────
LETTRE_C = "quete:rang_c_lettre_a_l_institut"   # Jumièges, déjà en jeu
B_GARGOUILLE = "quete:rang_b_gargouille_de_la_seine"
B_AIX = "quete:rang_b_pli_d_aix_la_chapelle"
B_MARS = "quete:rang_b_porte_de_mars"
B_TEMPLE = "quete:rang_b_porte_qui_ne_devait_pas_s_ouvrir"
A_GEANT = "quete:rang_a_geant_de_la_baie"
A_BETE = "quete:rang_a_bete_du_gevaudan"
A_MINOTAURE = "quete:rang_a_minotaure_de_chartres"
A_AMPOULE = "quete:rang_a_ampoule_du_sacre"
A_DELEGATION = "quete:rang_a_delegation_palatine"
# Quête du COMMANDEUR (pas une épreuve de Maëlys) : la descente qui suit la livraison du pli.
CRISTAL_OSSUAIRE = "quete:cristal_de_l_ossuaire"
QUETES_B = (B_GARGOUILLE, B_AIX, B_MARS, B_TEMPLE)
QUETES_A = (A_GEANT, A_BETE, A_MINOTAURE, A_AMPOULE, A_DELEGATION)

# ── Lieux neufs ──────────────────────────────────────────────────────────────────────────
HOTEL = "lieu:hotel_de_ville_d_aix_la_chapelle"
CHAPELLE = "lieu:chapelle_palatine"
PORTE_MARS = "lieu:porte_de_mars"
ENCLOS = "lieu:enclos_du_temple"
CRYPTE = "lieu:crypte_de_chartres"
LABYRINTHE = "lieu:labyrinthe_du_puits_de_chartres"
DONJON_PUITS = "donjon:puits_de_chartres"
AUBERGE_SACRE = "lieu:auberge_du_sacre"     # Rhemi, déjà en jeu : rendez-vous de l'Ampoule

# ── PNJ neufs ────────────────────────────────────────────────────────────────────────────
CHANCELIER = "pnj:chancelier_de_l_hotel_de_ville_d_aix"
GARDIENNE = "pnj:gardienne_des_cinq_portes"
COMMANDEUR = "pnj:commandeur_de_l_enclos_du_temple"
GARDE_MARS = "pnj:gardien_de_la_porte_de_mars"
HUGUES = "pnj:hugues_vaucelle_porte_de_mars"
TEMPLIER_CRYPTE = "pnj:templier_de_la_crypte_de_chartres"

# ── Items ────────────────────────────────────────────────────────────────────────────────
ITEM_LETTRE = "item:lettre_de_mission_de_la_guilde"   # déjà en jeu (Jumièges)
TETE_GARGOUILLE = "item:gargouille_tete"
TETE_GEANT = "item:geant_du_mont_saint_michel_tete"
TETE_BETE = "item:bete_du_gevaudan_tete"
TETE_MINOTAURE = "item:minotaure_tete"
# Preuve de la descente du Temple : le coffre de l'ossuaire (`lieu:catacombes0003`) est la
# SEULE source de ce cristal en jeu (dump du 24/10) — verrouillé par le test.
CRISTAL_JAUNE = "item:cristal_de_mana_jaune"
OSSUAIRE = "lieu:catacombes0003"
GARGOUILLE = "espece:gargouille"
MINOTAURE = "espece:minotaure"

# Récompenses : même rapport cuivre/XP que l'épreuve du rang C recalée (3000 cu pour 150 XP).
RECOMPENSES_B = {"xp": 250, "cuivre": 5000, "rang_guilde": "B"}
RECOMPENSES_A = {"xp": 400, "cuivre": 8000, "rang_guilde": "A"}

# Zone de la carte de France où la Gargouille rejoint les rencontres : les berges (la Seine
# traverse Lutecia et Rouen). Trophée au hasard, grade de la zone (Auteur, 25/10).
ZONE_GARGOUILLE = "zone:riviere"

# Portraits et images : stock existant de templates/resources ; les images DÉFINITIVES des
# lieux neufs (prompts livrés avec la demande) remplaceront ces valeurs.
PORTRAITS = {
	CHANCELIER: "Set442-Lepidstadt-School of Law and Civic Dean Cassian Ornel.jpg",
	GARDIENNE: "templier_elfe_f_magicienne_notre_dame01.jpg",
	COMMANDEUR: "templier_humain_m_garde_temple01.png",
	GARDE_MARS: "Set346-Male-Dwarf-Oread-Torag-08.jpg",
	HUGUES: "Set437-Magister Othmar Vey.jpg",
	TEMPLIER_CRYPTE: "templier_nain_m_garde_temple01.png",
}
IMAGES = {
	HOTEL: "portail_de_temple_europe05.png",
	CHAPELLE: "portail_de_temple_europe08.png",
	PORTE_MARS: "porte_de_ville_chartres_exterieur01.jpg",
	ENCLOS: "portail_de_temple_europe03.png",
	CRYPTE: "portail_de_temple_europe10.png",
	LABYRINTHE: "crypte_de_la_necropole_d_escolives.jpg",
}

# Cibles approchées des portes sur les cartes de cité (x, y) : la case praticable libre la
# plus proche est retenue. Notre-Dame est en (50, 29) à Lutecia : le Temple au nord-est.
CIBLES_PORTES = {
	ENCLOS: (LUTECIA, (56, 22)),
	HOTEL: (AIX, (44, 22)),
	CHAPELLE: (AIX, (46, 27)),
	PORTE_MARS: (RHEMI, (45, 6)),
	CRYPTE: (CHARTRES, (44, 22)),
}

# ── États d'une quête (Auteur, 15/10) ────────────────────────────────────────────────────

def avant(q):
	return {"quete_active": {"id": q, "attendu": False}, "quete_reussie": {"id": q, "attendu": False}}


def pendant(q):
	return {"quete_active": {"id": q}}


def apres(q):
	return {"quete_reussie": {"id": q}}


# Grille provisoire du labyrinthe : enceinte murée, sol praticable. À RECALCULER sur l'image
# définitive (outil d'analyse d'image de /admin/editor) — un placeholder ne doit pas mentir
# sur des murs qu'on ne voit pas.
LARGEUR_LABY, HAUTEUR_LABY = 30, 20


def cells_labyrinthe():
	return [[0 if x in (0, LARGEUR_LABY - 1) or y in (0, HAUTEUR_LABY - 1) else 1
			 for x in range(LARGEUR_LABY)] for y in range(HAUTEUR_LABY)]


# ── Utilitaires ──────────────────────────────────────────────────────────────────────────

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


def poser_choix(noeud, choix, avant_id=None):
	"""Ajoute les choix ABSENTS (par id) — avant `avant_id` s'il existe, sinon en fin. Un choix
	déjà là est REMPLACÉ en place : régénération idempotente."""
	liste = noeud.setdefault("choix", [])
	for c in choix:
		idx = next((i for i, x in enumerate(liste) if x.get("id") == c["id"]), None)
		if idx is not None:
			liste[idx] = c
			continue
		pos = next((i for i, x in enumerate(liste) if x.get("id") == avant_id), len(liste))
		liste.insert(pos, c)


def case_libre(cite_doc, cible, occupees):
	"""Case praticable (valeur 1) la plus proche de `cible`, hors des cases déjà prises par une
	porte de la cité (spirale de Chebyshev)."""
	cells = cite_doc["cells"]
	h, w = len(cells), len(cells[0])
	cx, cy = cible
	for r in range(max(w, h)):
		for y in range(cy - r, cy + r + 1):
			for x in range(cx - r, cx + r + 1):
				if max(abs(x - cx), abs(y - cy)) != r:
					continue
				if 0 <= x < w and 0 <= y < h and cells[y][x] == 1 and (x, y) not in occupees:
					return [x, y]
	sys.exit(f"ERREUR : aucune case praticable près de {cible} sur {cite_doc['_id']}")


def id_lien(cite, sous_lieu):
	return f"link:{sous_lieu.split(':', 1)[1]}_to_{cite.split(':', 1)[1]}"


def cases_occupees(par_id, cite):
	"""Cases de la cité déjà prises par une porte — hors les NÔTRES : après import, elles sont
	au dump, et les compter déplacerait chaque porte à chaque régénération."""
	nos_liens = {id_lien(c, l) for l, (c, _) in CIBLES_PORTES.items()}
	out = set()
	for d in par_id.values():
		if d.get("type") != "connection" or d.get("_id") in nos_liens:
			continue
		for n in d.get("nodes") or []:
			if n.get("lieu") == cite and isinstance(n.get("pos"), list):
				out.add(tuple(n["pos"]))
	return out


def lien(cite, sous_lieu, pos, label_cite, label_retour, type_):
	return {
		"_id": id_lien(cite, sous_lieu),
		"type": "connection",
		"nodes": [
			{"lieu": cite, "pos": list(pos), "label": label_cite},
			{"lieu": sous_lieu, "pos": [0, 0], "label": label_retour},
		],
		"metadata": {"type": type_, "status": "ouvert"},
	}


def choix_fin(label="(Prendre congé.)"):
	return {"id": "fin", "label": label, "next": "fin"}


def retour_accueil():
	return [
		{"id": "retour", "label": "« Une autre question… »", "next": "accueil"},
		{"id": "fin", "label": "« Je ne vous retiens pas plus. »", "next": "conge"},
	]


# ── Maëlys : neuf épreuves, une offre par service à chaque visite ────────────────────────

def _apport(qid, titre, description, item, rang, rec, noeuds):
	return {"offre": {"id": qid, "titre": titre, "description": description, "item": item,
					  "quantite": 1, "unique": True, "rang": rang, "recompenses": dict(rec)},
			"noeuds": noeuds}


def _transport(qid, titre, description, destination, duree, rang, rec, noeuds):
	return {"offre": {"id": qid, "titre": titre, "description": description,
					  "destination": destination,
					  "cargaison": [{"item": ITEM_LETTRE, "quantite": 1, "poids": 0.05}],
					  "duree": duree, "proba": 1, "unique": True, "retour": True,
					  "rang": rang, "recompenses": dict(rec)},
			"noeuds": noeuds}


def _escorte(qid, titre, description, destination, proteges, rang, rec, noeuds, rencontre=None):
	offre = {"id": qid, "titre": titre, "description": description, "destination": destination,
			 "proteges": proteges, "unique": True, "proba": 1, "rang": rang,
			 "recompenses": dict(rec)}
	if rencontre:
		offre["rencontre"] = rencontre
	return {"offre": offre, "noeuds": noeuds}


PROTEGE_HUGUES = {
	"prenom": "Hugues", "nom": "Vaucelle", "race": "humain", "sex": "M",
	"image": PORTRAITS[HUGUES],
	"description": "Architecte de la Cour des Arches, spécialiste des portails qui n'ont jamais fonctionné. Un sac de craies de couleur, un niveau d'eau, et la conviction qu'un échec bien mesuré vaut mieux qu'une réussite qu'on ne comprend pas. Il ne sait pas se battre.",
}
PROTEGES_AMPOULE = [
	{"prenom": "Gervais", "nom": "de Sillery", "race": "hobbit", "sex": "M",
	 "description": "Gardien de l'Ampoule du Sacre. Il porte contre sa poitrine un coffret de bois noir qu'il ne lâche jamais, même pour manger. Il ne sait pas se battre."},
	{"prenom": "Aude", "nom": "de Cormicy", "race": "elfe", "sex": "F",
	 "description": "Paladine de Rhemi, escorte de l'Ampoule. Elle marche toujours à la gauche du gardien, l'épée au clair dès que la route se resserre.",
	 "se_defend": True,
	 "equipement": {"torse": "item:Cotte_de_mailles", "main_droite": "item:Epee_longue_ordre",
					"main_gauche": "item:Bouclier_ordre"}},
	{"prenom": "Baudouin", "nom": "de Verzy", "race": "ogre", "sex": "M",
	 "description": "Paladin de Rhemi, escorte de l'Ampoule. Il parle peu et se place toujours entre le coffret et ce qui s'en approche.",
	 "se_defend": True,
	 "equipement": {"torse": "item:Cotte_de_mailles", "main_droite": "item:Epee_longue_ordre",
					"main_gauche": "item:Bouclier_ordre"}},
]
PROTEGES_DELEGATION = [
	{"prenom": "Anselme", "nom": "Gerbier", "race": "nain", "sex": "M",
	 "description": "Maître architecte de la Cour des Arches, envoyé à l'Hôtel de Ville d'Aix pour y étudier les portes des cités sœurs. Il compte ses pas et se plaint de chacun. Il ne sait pas se battre."},
	{"prenom": "Clémence", "nom": "d'Orval", "race": "elfe", "sex": "F",
	 "description": "Jeune architecte de la Cour, seconde de maître Gerbier. Elle relève tout ce qu'elle voit, y compris ce que personne ne lui a demandé de relever. Elle ne sait pas se battre."},
]


def entrees_maelys():
	"""(service → [entrées]) des épreuves B et A. L'entrée du rang C (Jumièges) est reprise
	du doc relu, en tête de la liste du transport."""
	n_apport = lambda p: {"accepte": f"{p}_accepte", "remis": f"{p}_remis", "partiel": f"{p}_partiel"}
	n_transport = lambda p: {"accepte": f"{p}_accepte", "trop_charge": f"{p}_trop_charge", "rapporte": f"{p}_rapporte"}
	n_escorte = lambda p: {"accepte": f"{p}_accepte"}
	return {
		"apport": [
			_apport(B_GARGOUILLE, "Rang B : la Gargouille de la Seine",
					"Maëlys veut la tête d'une gargouille. Elles hantent les berges des rivières de France, et d'abord celles de la Seine, entre Lutecia et Rouen. Rapportez-la au bureau de la maîtresse : le rang B est au bout.",
					TETE_GARGOUILLE, "B", RECOMPENSES_B, n_apport("b_gargouille")),
			_apport(A_GEANT, "Rang A : le géant de la baie",
					"Maëlys veut la tête du géant qui hante la baie du Mont, à l'ouest de la Normandie, là où les grèves se couvrent et se découvrent. Rapportez-la au bureau de la maîtresse : le rang A est au bout.",
					TETE_GEANT, "A", RECOMPENSES_A, n_apport("a_geant")),
			_apport(A_BETE, "Rang A : la Bête",
					"Maëlys veut la tête de la Bête qui rôde dans les régions les plus dangereuses de France, des monts du Gévaudan aux confins de la carte. Rapportez-la au bureau de la maîtresse : le rang A est au bout.",
					TETE_BETE, "A", RECOMPENSES_A, n_apport("a_bete")),
			_apport(A_MINOTAURE, "Rang A : le puits de Chartres",
					"Les Templiers de Chartres demandent à la Guilde une descente dans le puits de la crypte, jusqu'au labyrinthe du Minotaure. Présentez-vous au Templier de la crypte, descendez, et rapportez une tête au bureau de la maîtresse : le rang A est au bout.",
					TETE_MINOTAURE, "A", RECOMPENSES_A, n_apport("a_minotaure")),
		],
		"transport": [
			_transport(B_AIX, "Rang B : le pli d'Aix-la-Chapelle",
					   "Maëlys vous confie un pli scellé pour le chancelier de l'Hôtel de Ville d'Aix-la-Chapelle, au-delà de la plaine européenne. Remettez-le en main propre, puis revenez rendre compte au bureau de la maîtresse avec la réponse. Le rang B est au bout.",
					   HOTEL, 604800, "B", RECOMPENSES_B, n_transport("b_aix")),
			_transport(B_TEMPLE, "Rang B : la porte qui ne devait pas s'ouvrir",
					   "Maëlys vous confie un pli pour le commandeur de l'Enclos du Temple, la maison des Templiers de Lutecia. Elle veut savoir ce qui se passe au fond des catacombes. Remettez-le, écoutez ce qu'il dira, puis revenez rendre compte. Le rang B est au bout.",
					   ENCLOS, 172800, "B", RECOMPENSES_B, n_transport("b_temple")),
		],
		"escorte": [
			_escorte(B_MARS, "Rang B : la Porte de Mars",
					 "La Cour des Arches envoie l'architecte Hugues Vaucelle relever la Porte de Mars, à Rhemi : un portail qui ne s'est jamais allumé. Conduisez-le jusqu'à la porte et déposez-le vivant. Il ne sait pas se battre. Le rang B est au bout.",
					 PORTE_MARS, [dict(PROTEGE_HUGUES)], "B", RECOMPENSES_B, n_escorte("b_mars")),
			_escorte(A_AMPOULE, "Rang A : l'Ampoule du Sacre",
					 "Aix-la-Chapelle a demandé l'Ampoule du Sacre pour un couronnement. Retrouvez son gardien et ses deux paladins à l'Auberge du Sacre, à Rhemi, puis conduisez-les jusqu'à la Chapelle Palatine d'Aix. Le gardien ne sait pas se battre ; les paladins, si. Le rang A est au bout.",
					 CHAPELLE, [dict(p) for p in PROTEGES_AMPOULE], "A", RECOMPENSES_A,
					 n_escorte("a_ampoule"), rencontre={"lieu": AUBERGE_SACRE}),
			_escorte(A_DELEGATION, "Rang A : la délégation palatine",
					 "La Cour des Arches envoie deux architectes étudier les portes des cités sœurs, à l'Hôtel de Ville d'Aix-la-Chapelle. Conduisez maître Gerbier et Clémence d'Orval jusqu'à l'Hôtel de Ville et déposez-les vivants. Ils ne savent pas se battre. Le rang A est au bout.",
					 HOTEL, [dict(p) for p in PROTEGES_DELEGATION], "A", RECOMPENSES_A,
					 n_escorte("a_delegation")),
		],
	}


def _offre_choix(cid, label, flag, qid, suivant):
	return {"id": cid, "label": label, "condition": {flag: True, "offre": qid}, "next": suivant}


def choix_accueil_maelys():
	"""Choix de l'accueil, par quête : l'offre (flag + `offre`), la relance, la remise ou le
	rapport, le souvenir (APRÈS)."""
	c = []
	# AVANT : une offre par service, celle du tirage — le flag ne suffit pas, deux épreuves
	# du même service se départagent par `offre`.
	c += [
		_offre_choix("b_gargouille_offre", "« Une épreuve pour le rang B ? On parle d'une gargouille. »", "apport_offert", B_GARGOUILLE, "b_gargouille_propose"),
		_offre_choix("b_aix_offre", "« Une épreuve pour le rang B ? Un pli pour Aix, dit-on. »", "transport_offert", B_AIX, "b_aix_propose"),
		_offre_choix("b_temple_offre", "« Une épreuve pour le rang B ? Il paraît que le Temple vous inquiète. »", "transport_offert", B_TEMPLE, "b_temple_propose"),
		_offre_choix("b_mars_offre", "« Une épreuve pour le rang B ? Quelqu'un à conduire à Rhemi ? »", "escorte_offerte", B_MARS, "b_mars_propose"),
		_offre_choix("a_geant_offre", "« Le rang A. Qu'attendez-vous de moi ? » (le géant de la baie)", "apport_offert", A_GEANT, "a_geant_propose"),
		_offre_choix("a_bete_offre", "« Le rang A. Qu'attendez-vous de moi ? » (la Bête)", "apport_offert", A_BETE, "a_bete_propose"),
		_offre_choix("a_minotaure_offre", "« Le rang A. Qu'attendez-vous de moi ? » (le puits de Chartres)", "apport_offert", A_MINOTAURE, "a_minotaure_propose"),
		_offre_choix("a_ampoule_offre", "« Le rang A. Qu'attendez-vous de moi ? » (une escorte depuis Rhemi)", "escorte_offerte", A_AMPOULE, "a_ampoule_propose"),
		_offre_choix("a_delegation_offre", "« Le rang A. Qu'attendez-vous de moi ? » (une délégation pour Aix)", "escorte_offerte", A_DELEGATION, "a_delegation_propose"),
	]
	# PENDANT.
	for p, q, objet in (("b_gargouille", B_GARGOUILLE, "la tête de la gargouille"),
						("a_geant", A_GEANT, "la tête du géant"),
						("a_bete", A_BETE, "la tête de la Bête"),
						("a_minotaure", A_MINOTAURE, "la tête du Minotaure")):
		c += [
			{"id": f"{p}_remise", "label": f"Poser {objet} sur la table.",
			 "condition": {"apport_possible": True, "offre": q},
			 "action": {"service": "apport", "op": "remettre"}},
			{"id": f"{p}_relance", "label": "« Au sujet de l'épreuve… »",
			 "condition": {"apport_en_cours": True, "apport_possible": False, "offre": q},
			 "next": f"{p}_relance"},
		]
	for p, q, preuve in (("b_aix", B_AIX, None), ("b_temple", B_TEMPLE, CRISTAL_OSSUAIRE)):
		rapport = {"transport_a_rapporter": True, "offre": q}
		if preuve:
			rapport["quete_reussie"] = {"id": preuve}
		c += [
			{"id": f"{p}_relance", "label": "« Au sujet du pli… »",
			 "condition": {"transport_en_cours": True, "offre": q}, "next": f"{p}_relance"},
			{"id": f"{p}_rapport", "label": "« Le pli est remis. Voici la réponse. »",
			 "condition": rapport,
			 "action": {"service": "transport", "op": "rapporter"}},
		]
		if preuve:
			# Le pli remis mais la descente pas faite : Maëlys renvoie au commandeur (modèle du
			# couple `rang_c_attente` / `rang_c_rapport` de Jumièges).
			c.append({"id": f"{p}_attente", "label": "« Le pli est remis. »",
					  "condition": {"transport_a_rapporter": True, "offre": q,
									"quete_reussie": {"id": preuve, "attendu": False}},
					  "next": f"{p}_pas_encore"})
	for p, q in (("b_mars", B_MARS), ("a_ampoule", A_AMPOULE), ("a_delegation", A_DELEGATION)):
		c.append({"id": f"{p}_relance", "label": "« Au sujet de l'escorte… »",
				  "condition": {"escorte_en_cours": True, "offre": q}, "next": f"{p}_relance"})
	# APRÈS.
	for p, q, label in (("b_gargouille", B_GARGOUILLE, "« La gargouille… »"),
						("b_aix", B_AIX, "« La réponse d'Aix… »"),
						("b_temple", B_TEMPLE, "« La porte des catacombes… »"),
						("b_mars", B_MARS, "« La Porte de Mars… »"),
						("a_geant", A_GEANT, "« Le géant de la baie… »"),
						("a_bete", A_BETE, "« La Bête… »"),
						("a_minotaure", A_MINOTAURE, "« Le puits de Chartres… »"),
						("a_ampoule", A_AMPOULE, "« L'Ampoule… »"),
						("a_delegation", A_DELEGATION, "« Les architectes d'Aix… »")):
		c.append({"id": f"{p}_souvenir", "label": label, "condition": apres(q), "next": f"{p}_souvenir"})
	return c


def _accepter(service, label):
	return {"id": "accepter", "label": label, "action": {"service": service, "op": "accepter"}}


def _plus_tard(label="« Pas aujourd'hui. »"):
	return {"id": "plus_tard", "label": label, "next": "accueil"}


def _ok(label, suivant="fin"):
	return [{"id": "ok", "label": label, "next": suivant}]


def noeuds_maelys():
	n = {}
	# ── B · la Gargouille ──
	n["b_gargouille_propose"] = {
		"texte": "Maëlys ouvre un registre ancien, relié de cuir noir, et le tourne vers vous. Sur la page, une gravure : une bête de pierre, ailes repliées, gueule ouverte sur une ville au bord d'un fleuve. « Rouen raconte qu'une gargouille ravageait ses quais, autrefois. On la brûla. Le corps brûla ; la tête et le cou, non. On les cloua au rempart pour qu'on s'en souvienne. » Elle referme le registre. « Il y en a d'autres. Le long de la Seine, de Lutecia à la mer, et sur d'autres rivières. Rapportez-moi une tête, {prenom}. Le rang B ne se gagne pas sur un loup. »",
		"choix": [
			{"id": "infos", "label": "« Comment la trouver ? »", "next": "b_gargouille_infos"},
			_accepter("apport", "« Je vous la rapporte. »"),
			_plus_tard(),
		],
	}
	n["b_gargouille_infos"] = {
		"texte": "« On ne la trouve pas : on la croise. » Elle suit du doigt le tracé de la Seine sur la carte du mur. « Elle se tient immobile sur les berges, comme une pierre parmi les pierres. Ceux qui la cherchent passent devant sans la voir ; ceux qui ne la cherchent pas la réveillent. Marchez le long de l'eau, et regardez ce qui ne bouge pas. »",
		"choix": [_accepter("apport", "« Je vous la rapporte. »"), _plus_tard("« Laissez-moi y réfléchir. »")],
	}
	n["b_gargouille_accepte"] = {
		"texte": "Maëlys trace une ligne dans son registre. « Une tête. Pas une aile, pas une griffe : je veux savoir que la bête ne se relèvera pas. » Elle lève les yeux. « Et ne la cherchez pas seule, si vous pouvez l'éviter. La pierre ne saigne pas. »",
		"choix": _ok("« Compris. »"),
	}
	n["b_gargouille_relance"] = {
		"texte": "« La gargouille. » Maëlys ne lève pas les yeux. « Le long de l'eau, {prenom}. Ce qui ne bouge pas. »",
		"choix": _ok("« J'y retourne. »"),
	}
	n["b_gargouille_partiel"] = {
		"texte": "Maëlys regarde ce que vous avez posé, puis vous. « Ce n'est pas tout. Il reste {reste} pièce à rapporter. »",
		"choix": _ok("« Je reviens avec. »"),
	}
	n["b_gargouille_remis"] = {
		"texte": "La tête de pierre frappe la table avec un bruit de dalle qu'on pose. Maëlys en fait le tour, du bout des doigts, sans la toucher tout à fait. « Rouen avait raison : elle ne brûle pas. » Elle ouvre son registre, y trace une ligne, puis fait glisser vers vous {prime} pièces de cuivre. « Rang B. » Un temps. « Faites-la porter aux Archives des Seuils. Les architectes voudront savoir de quelle pierre elle est faite, et pourquoi elle bougeait. »",
		"choix": _ok("« Merci, maîtresse. »"),
	}
	n["b_gargouille_souvenir"] = {
		"texte": "« Les Archives ont gardé la tête. » Maëlys hausse une épaule. « Un architecte jure que c'est de la pierre, rien d'autre, animée par un portail qu'on n'a jamais trouvé. Un autre, qu'une gargouille est une bête qui finit en pierre comme nous finissons en os. Ils ne se parlent plus. »",
		"choix": retour_accueil(),
	}
	# ── B · le pli d'Aix ──
	n["b_aix_propose"] = {
		"texte": "Maëlys pose devant vous un pli scellé, épais, à la cire de la porte ouverte. « Aix-la-Chapelle. Au-delà de la plaine, sur les routes que tiennent les cités carolingiennes. Leur Hôtel de Ville garde des portes vers les cités sœurs ; aucune ne mène ici. » Elle tapote le pli. « J'ai une question à poser à leur chancelier, et je ne la confierai ni à un portail, ni à un messager. Portez-la à {destination}, rapportez-moi sa réponse. C'est loin, {prenom}. C'est le but. »",
		"choix": [
			{"id": "infos", "label": "« Quelle question ? »", "next": "b_aix_infos"},
			_accepter("transport", "« Donnez-moi ce pli. »"),
			_plus_tard(),
		],
	}
	n["b_aix_infos"] = {
		"texte": "Maëlys vous regarde un long moment. « Une question sur une porte. » Ce sera tout. Puis, parce que vous attendez encore : « Le chemin, en revanche, je peux vous le donner. Le nord-est, par la plaine européenne, la route d'Aix-la-Chapelle. Vous ne la manquerez pas : les Carolingiens entretiennent leurs routes mieux que nous. »",
		"choix": [_accepter("transport", "« Donnez-moi ce pli. »"), _plus_tard("« Laissez-moi y réfléchir. »")],
	}
	n["b_aix_accepte"] = {
		"texte": "Elle vous tend le pli. « Au chancelier, en main propre. S'il l'ouvre devant vous, regardez son visage. » Puis, déjà retournée vers ses cartes : « C'est sa réponse que je veux. Son visage, c'est pour vous. »",
		"choix": _ok("« Compris. »"),
	}
	n["b_aix_trop_charge"] = {
		"texte": "Maëlys regarde votre sac, puis vous. « Un pli, {prenom}. Il n'y a plus la place ? Allégez-vous d'abord. »",
		"choix": _ok("« Je reviens le sac plus léger. »"),
	}
	n["b_aix_relance"] = {
		"texte": "« Aix-la-Chapelle attend toujours. » Ce n'est pas une question. « Le nord-est, par la plaine. Et le chancelier, en main propre. »",
		"choix": _ok("« J'y vais. »"),
	}
	n["b_aix_rapporte"] = {
		"texte": "Maëlys brise le sceau de la réponse et lit, debout, sans rien laisser paraître. Une fois. Deux fois. Elle plie la lettre en quatre et la range dans une poche intérieure de sa veste, pas dans un registre. « Il n'a rien vu. Aucune de leurs portes n'a changé de couleur. » Un temps. « C'est une bonne nouvelle. Je ne sais pas encore pourquoi elle ne me rassure pas. » Elle ouvre son registre, y trace une ligne, et fait glisser vers vous {prime} pièces de cuivre. « Rang B. Vous avez vu Aix. La plupart des membres de cette guilde mourront sans l'avoir vue. »",
		"choix": _ok("« Merci, maîtresse. »"),
	}
	n["b_aix_souvenir"] = {
		"texte": "« Aix. » Maëlys effleure la poche de sa veste. « Le chancelier m'a écrit de nouveau. Une de leurs portes, la nuit, a pâli. Une seule fois, une heure, puis elle est redevenue comme avant. Leurs architectes disent que c'est l'hiver. » Elle ne dit pas ce qu'elle en pense.",
		"choix": retour_accueil(),
	}
	# ── B · la porte qui ne devait pas s'ouvrir ──
	n["b_temple_propose"] = {
		"texte": "Maëlys garde la main sur le pli un instant avant de le poser. « L'Enclos du Temple. La maison des Templiers, ici, à Lutecia. Ce sont eux qui gardent ce qu'il y a sous nos pieds, les catacombes et leur donjon, et qui en remontent les cristaux jaunes. » Elle se tait. « Depuis trois mois, leur commandeur ne répond plus aux lettres de la Guilde que par des politesses. Quand un Templier devient poli, {prenom}, il se passe quelque chose au fond. Portez-lui ceci à {destination}. S'il vous envoie en bas, descendez : je ne veux pas sa réponse, je veux ce que vous aurez vu. »",
		"choix": [
			{"id": "infos", "label": "« Pourquoi moi ? »", "next": "b_temple_infos"},
			_accepter("transport", "« Donnez-moi ce pli. »"),
			_plus_tard(),
		],
	}
	n["b_temple_infos"] = {
		"texte": "« Parce qu'on ne ment pas de la même façon à une lettre et à quelqu'un qui revient du fond. » Elle hausse une épaule. « Et parce que le rang B, c'est le jour où je peux vous envoyer chez des gens plus puissants que la Guilde, et savoir que vous en reviendrez avec ce que je cherche. »",
		"choix": [_accepter("transport", "« Donnez-moi ce pli. »"), _plus_tard("« Laissez-moi y réfléchir. »")],
	}
	n["b_temple_accepte"] = {
		"texte": "Elle vous tend le pli. « Au commandeur. Et s'il vous envoie dans les catacombes, allez jusqu'au fond. Le rang B, c'est l'ossuaire, pas l'antichambre. »",
		"choix": _ok("« Compris. »"),
	}
	n["b_temple_trop_charge"] = {
		"texte": "Maëlys regarde votre sac, puis vous. « Un pli, {prenom}. Allégez-vous d'abord. »",
		"choix": _ok("« Je reviens le sac plus léger. »"),
	}
	n["b_temple_relance"] = {
		"texte": "« Le commandeur n'a pas eu ma lettre. » Elle ne lève pas les yeux. « L'Enclos du Temple, {prenom}. Ce n'est pas loin. C'est ce qui m'inquiète. »",
		"choix": _ok("« J'y vais. »"),
	}
	n["b_temple_pas_encore"] = {
		"texte": "Maëlys lève les yeux de ses registres. « Remis, oui. Le commandeur me l'a fait savoir. » Un temps. « Il me fait savoir aussi que son cristal n'est pas remonté de l'ossuaire. » Elle referme le registre. « Allez au fond, {prenom}, et rapportez-le-lui. Ensuite seulement, revenez ici. »",
		"choix": _ok("« J'y vais. »"),
	}
	n["b_temple_rapporte"] = {
		"texte": "Maëlys brise le sceau du commandeur, lit, puis vous écoute sans vous interrompre : les trois étages, ce qui rôdait, l'ossuaire, le coffre, la paroi ouverte et la porte qui n'était pas là, le symbole, la chaleur de la pierre. Quand vous parlez du symbole, elle prend une feuille et vous demande de le dessiner. Vous le faites. Elle le regarde longtemps, puis le glisse dans le registre, à une page qu'elle ne vous montre pas. « Rang B. » Elle fait glisser vers vous {prime} pièces de cuivre. « Ils continueront d'extraire. Ils n'ont pas le choix : sans cristaux jaunes, la moitié des portes de cette ville s'éteindrait. » Un temps. « Personne n'a le choix. C'est ce qui rend les portes si patientes. »",
		"choix": _ok("« Merci, maîtresse. »"),
	}
	n["b_temple_souvenir"] = {
		"texte": "« La porte des catacombes est toujours fermée. » Maëlys referme un tiroir. « Le commandeur pense qu'elle a toujours été là, et qu'on l'a seulement découverte en creusant. Son second pense que c'est l'extraction qui la fait pousser, comme une racine vers l'eau. Chacun espère avoir raison. »",
		"choix": retour_accueil(),
	}
	# ── B · la Porte de Mars ──
	n["b_mars_propose"] = {
		"texte": "« Rhemi a une porte qui ne s'est jamais ouverte. » Maëlys déroule sur la table un vieux relevé : une arche triple, sans rien derrière. « La Porte de Mars. Des architectes de Rome l'ont bâtie pour relier Rhemi à Rome. Elle ne s'est jamais allumée. Rhemi dit que la craie boit le mana. » Elle roule le relevé. « La Cour des Arches veut la mesurer à nouveau, et envoie l'un des siens : Hugues Vaucelle. Il attend ici même, dans l'antichambre. Conduisez-le à Rhemi, et déposez-le vivant au pied de l'arche. »",
		"choix": [
			{"id": "infos", "label": "« Pourquoi la mesurer, si elle n'a jamais marché ? »", "next": "b_mars_infos"},
			_accepter("escorte", "« Je l'y conduis. »"),
			_plus_tard(),
		],
	}
	n["b_mars_infos"] = {
		"texte": "« Parce que certains jurent qu'elle a marché une fois. » Maëlys hausse une épaule. « Une nuit, il y a longtemps, un garde aurait vu de la lumière sous l'arche. Personne ne l'a jamais revue. » Elle vous regarde. « Un portail qui ne marche pas n'intéresse personne. Un portail qui a marché une fois, et qu'on ne comprend pas, intéresse tout le monde. Y compris des gens que je préfère ne pas croiser sur la route de Rhemi. »",
		"choix": [_accepter("escorte", "« Je l'y conduis. »"), _plus_tard("« Laissez-moi y réfléchir. »")],
	}
	n["b_mars_accepte"] = {
		"texte": "Maëlys ouvre la porte de l'antichambre. Un humain maigre se lève d'un banc, un sac de craies de couleur à l'épaule et un niveau d'eau sous le bras. « Vaucelle. Voici qui vous conduira. » L'architecte vous serre la main, longtemps, en vous regardant comme on mesure un mur. « Parfait. Je marche lentement, je m'arrête souvent, et je ne sais pas me battre. Je vous préviens maintenant : cela évitera les déceptions. » Maëlys a déjà refermé la porte.",
		"choix": _ok("« En route pour Rhemi. »"),
	}
	n["b_mars_relance"] = {
		"texte": "« Vaucelle n'est pas encore à Rhemi. » Maëlys ne lève pas les yeux. « Il marche lentement, je sais. C'est vous qui comptez les jours, pas lui. »",
		"choix": _ok("« Nous y serons bientôt. »"),
	}
	n["b_mars_souvenir"] = {
		"texte": "« Vaucelle est toujours à Rhemi. » Maëlys a presque un sourire. « Il m'a écrit. Trois pages de mesures et une seule ligne qui compte : la porte n'est pas morte. Elle attend. Le gardien de l'arche lui a répondu qu'une porte qui attend depuis des siècles, à Rhemi, on appelle ça une porte morte. »",
		"choix": retour_accueil(),
	}
	# ── A · le géant de la baie ──
	n["a_geant_propose"] = {
		"texte": "Maëlys déroule une carte de la côte ouest : une baie immense, un rocher au milieu des grèves. « Le Mont. Les pêcheurs de la baie disent qu'un géant y vit, qu'il est venu d'Ibérie et qu'il mange les gens du pays. Les vieilles chansons disent qu'Arthur l'a tué. » Elle pose le doigt sur la baie. « Il y a toujours un géant sur le Mont. Le même qui revient, ou un autre qui a pris sa place. Le rang A, {prenom}, c'est la tête de ce géant sur cette table. »",
		"choix": [
			{"id": "infos", "label": "« Que sait-on de lui ? »", "next": "a_geant_infos"},
			_accepter("apport", "« Je vous la rapporte. »"),
			_plus_tard(),
		],
	}
	n["a_geant_infos"] = {
		"texte": "« Qu'il est plus grand que tout ce que vous avez abattu, et plus fort. Qu'il porte une massue de fer qu'un ogre ne soulèverait pas. Et qu'il ne quitte jamais la baie. » Elle vous regarde droit dans les yeux. « N'y allez pas sans compagnons. Ce n'est pas un conseil. »",
		"choix": [_accepter("apport", "« Je vous la rapporte. »"), _plus_tard("« Laissez-moi y réfléchir. »")],
	}
	n["a_geant_accepte"] = {
		"texte": "Maëlys trace une ligne dans son registre. « La baie, à l'ouest. Les grèves se couvrent vite : surveillez la marée autant que le géant. » Un temps. « Et rapportez-moi aussi les compagnons que vous emmènerez. »",
		"choix": _ok("« Compris. »"),
	}
	n["a_geant_relance"] = {
		"texte": "« La baie. » Maëlys ne lève pas les yeux. « Le géant ne viendra pas jusqu'ici, {prenom}. »",
		"choix": _ok("« J'y retourne. »"),
	}
	n["a_geant_partiel"] = {
		"texte": "« Il reste {reste} pièce à rapporter. » Maëlys n'a même pas regardé ce que vous avez posé.",
		"choix": _ok("« Je reviens avec. »"),
	}
	n["a_geant_remis"] = {
		"texte": "Il faut deux employés du Grand Relais pour monter la tête jusqu'au bureau. Maëlys les congédie d'un geste, puis reste un long moment devant ce visage énorme, aux yeux fermés. « Arthur l'a tué, disent les chansons. » Elle ouvre son registre et y trace une ligne, lentement. « Rang A. » Elle fait glisser vers vous {prime} pièces de cuivre. « À partir d'aujourd'hui, la Guilde de Lutecia n'a plus grand-chose à vous apprendre sur la France. Le reste du monde, en revanche… » Elle ne finit pas sa phrase.",
		"choix": _ok("« Merci, maîtresse. »"),
	}
	n["a_geant_souvenir"] = {
		"texte": "« Les pêcheurs de la baie m'ont fait porter un panier de poissons. » Maëlys désigne un coin du bureau, vide. « Je l'ai donné aux cuisines. Ils disent que le Mont est silencieux, maintenant. Ils disent aussi qu'il l'était, la dernière fois, avant qu'un autre revienne. »",
		"choix": retour_accueil(),
	}
	# ── A · la Bête ──
	n["a_bete_propose"] = {
		"texte": "« La Bête. » Maëlys ne précise pas laquelle. Elle tire d'un casier une liasse de rapports, dont certains ont jauni. « Une bête rousse, une raie noire sur le dos, plus rapide qu'un cheval et plus rusée qu'un chasseur. On l'a vue dans le Gévaudan, au sud-ouest de Lyon, puis partout où la France est la plus dangereuse. Les battues reviennent bredouilles. » Elle repose la liasse. « Rapportez-moi sa tête, {prenom}. Le rang A est au bout. »",
		"choix": [
			{"id": "infos", "label": "« Un loup-garou ? »", "next": "a_bete_infos"},
			_accepter("apport", "« Je vous la rapporte. »"),
			_plus_tard(),
		],
	}
	n["a_bete_infos"] = {
		"texte": "« Peut-être. » Maëlys n'hésite pas. « Les uns disent qu'on court le garou dans le Gévaudan comme ailleurs. Les autres, que c'est une bête, une vraie, et qu'on cherche un homme sous la fourrure pour se rassurer : un homme, on peut le juger. » Elle hausse une épaule. « Je ne vous demande pas ce qu'elle est. Je vous demande sa tête. »",
		"choix": [_accepter("apport", "« Je vous la rapporte. »"), _plus_tard("« Laissez-moi y réfléchir. »")],
	}
	n["a_bete_accepte"] = {
		"texte": "Maëlys trace une ligne dans son registre. « Elle ne se laisse pas chercher. Laissez-la vous trouver, et soyez sur vos gardes quand elle le fera. » Puis, sans lever les yeux : « Et si, une fois tombée, elle a un visage, je veux le savoir aussi. »",
		"choix": _ok("« Compris. »"),
	}
	n["a_bete_relance"] = {
		"texte": "« La Bête court toujours. » Maëlys ne lève pas les yeux de ses rapports. « Les régions les plus dangereuses, {prenom}. Elle n'aime pas les autres. »",
		"choix": _ok("« J'y retourne. »"),
	}
	n["a_bete_partiel"] = {
		"texte": "« Il reste {reste} pièce à rapporter. »",
		"choix": _ok("« Je reviens avec. »"),
	}
	n["a_bete_remis"] = {
		"texte": "La tête est celle d'une bête : un museau long, des crocs, une fourrure rousse et la raie noire. Rien d'autre. Maëlys la regarde longtemps, comme si elle attendait qu'elle change. Elle ne change pas. « Une bête. » Elle ouvre son registre et y trace une ligne. « Rang A. » Elle fait glisser vers vous {prime} pièces de cuivre. « On dira dans le Gévaudan que vous avez tué un loup, et que la vraie Bête court toujours. On le dit à chaque fois. »",
		"choix": _ok("« Merci, maîtresse. »"),
	}
	n["a_bete_souvenir"] = {
		"texte": "« Le Gévaudan est calme. » Maëlys tourne une page. « Une rebouteuse du Gévaudan m'a écrit qu'elle a veillé la tête une nuit avant que les Archives la prennent, et qu'elle a saigné. Un archiviste m'a écrit qu'une tête ne saigne pas trois semaines après la mort. L'un des deux ment, ou se trompe. Je ne cherche pas à savoir lequel. »",
		"choix": retour_accueil(),
	}
	# ── A · le puits de Chartres ──
	n["a_minotaure_propose"] = {
		"texte": "« Chartres. » Maëlys pose sur la table une lettre au sceau des Templiers. « Sous la cathédrale, dans la crypte, il y a un puits. On y entre en descendant, et l'on arrive dans un labyrinthe que personne n'a creusé. Depuis la Vague, un Minotaure l'habite. Les premiers qui sont descendus, on les appelle encore les Forts. Ils ne sont pas remontés. » Elle replie la lettre. « Les Templiers demandent qu'on descende. Je vous le demande. Rapportez-moi une tête, {prenom}. »",
		"choix": [
			{"id": "infos", "label": "« Et le héros de la légende ? Celui qui l'a tué ? »", "next": "a_minotaure_infos"},
			_accepter("apport", "« Je descendrai. »"),
			_plus_tard(),
		],
	}
	n["a_minotaure_infos"] = {
		"texte": "« Personne ne l'a tué. » Maëlys ne sourit pas. « Ailleurs, on raconte qu'un héros est entré dans un labyrinthe avec un fil, et qu'il en est ressorti. À Chartres, on raconte seulement que les Forts sont entrés. » Elle vous tend la lettre. « Le Templier de la crypte vous attend. C'est lui qui ouvre le puits, et il ne l'ouvre qu'à ceux que la Guilde envoie. »",
		"choix": [_accepter("apport", "« Je descendrai. »"), _plus_tard("« Laissez-moi y réfléchir. »")],
	}
	n["a_minotaure_accepte"] = {
		"texte": "Maëlys trace une ligne dans son registre. « La crypte de Chartres, le Templier, le puits. » Elle lève les yeux. « Emmenez du monde. Et si vous perdez la tête en remontant, le Templier vous laissera redescendre la chercher. Il me l'a promis. »",
		"choix": _ok("« Compris. »"),
	}
	n["a_minotaure_relance"] = {
		"texte": "« Chartres attend. » Maëlys ne lève pas les yeux. « Le Templier de la crypte, {prenom}. Il ouvrira le puits. »",
		"choix": _ok("« J'y vais. »"),
	}
	n["a_minotaure_partiel"] = {
		"texte": "« Il reste {reste} pièce à rapporter. »",
		"choix": _ok("« Je reviens avec. »"),
	}
	n["a_minotaure_remis"] = {
		"texte": "Maëlys écoute le récit de la descente : le puits, l'échelle, le labyrinthe, et les deux silhouettes cornues là où l'on n'en attendait qu'une. À ce mot, deux, sa plume s'arrête. Puis elle trace une ligne dans son registre. « Rang A. » Elle fait glisser vers vous {prime} pièces de cuivre. « Les Templiers vont devoir réécrire leurs registres. Un Minotaure, ils savaient le garder. Deux, ils ne savent pas d'où ils viennent. »",
		"choix": _ok("« Merci, maîtresse. »"),
	}
	n["a_minotaure_souvenir"] = {
		"texte": "« Le puits de Chartres. » Maëlys secoue la tête. « Les Templiers ne s'accordent pas. Les uns disent que le second est un fils, et qu'il y en aura d'autres. Les autres, que le labyrinthe en refait un chaque fois qu'on en tue un, comme une porte rouvre ce qu'on y a fermé. Ils ont doublé la garde de la crypte. »",
		"choix": retour_accueil(),
	}
	# ── A · l'Ampoule ──
	n["a_ampoule_propose"] = {
		"texte": "« Rhemi garde une Ampoule dont l'huile ne s'épuise pas. On en oint ceux que les cités voisines reconnaissent pour gouverner : c'est le Sacre. » Maëlys pose devant vous une lettre aux armes d'Aix. « Aix-la-Chapelle va couronner quelqu'un, et demande l'Ampoule. Rhemi accepte de la prêter, sous escorte de deux de ses paladins, à condition que la Guilde de Lutecia en réponde. » Elle vous regarde. « La Guilde, c'est vous. Rendez-vous à l'Auberge du Sacre, à Rhemi ; conduisez-les jusqu'à la Chapelle Palatine d'Aix. »",
		"choix": [
			{"id": "infos", "label": "« D'où vient cette huile ? »", "next": "a_ampoule_infos"},
			_accepter("escorte", "« J'en réponds. »"),
			_plus_tard(),
		],
	}
	n["a_ampoule_infos"] = {
		"texte": "« Une colombe l'aurait apportée à Remi, le jour du premier Sacre. » Maëlys hausse une épaule. « Les uns disent qu'un portail s'est ouvert un instant dans le ciel. D'autres, que quelqu'un l'a donnée, et qu'on ne sait plus qui. D'autres encore, qu'elle vient de Rome, par la porte de Saint-Pierre. Ce que je sais, moi, c'est que tous ceux qui la convoitent ont la même certitude : elle vaut plus qu'une cité. »",
		"choix": [_accepter("escorte", "« J'en réponds. »"), _plus_tard("« Laissez-moi y réfléchir. »")],
	}
	n["a_ampoule_accepte"] = {
		"texte": "Maëlys trace une ligne dans son registre, puis une seconde, qu'elle souligne. « Le gardien s'appelle Gervais. Les deux paladins se défendront ; lui, non. S'il tombe, l'Ampoule tombe avec lui. » Elle referme le registre. « Rhemi, l'Auberge du Sacre. Ensuite Aix. Et pas de détour. »",
		"choix": _ok("« Compris. »"),
	}
	n["a_ampoule_relance"] = {
		"texte": "« L'Ampoule n'est pas encore à Aix. » Maëlys ne lève pas les yeux. « Pas de détour, {prenom}. »",
		"choix": _ok("« Nous y serons bientôt. »"),
	}
	n["a_ampoule_souvenir"] = {
		"texte": "« L'Ampoule est rentrée à Rhemi. » Maëlys referme une lettre. « Aix a couronné qui elle voulait couronner. On dit là-bas que l'huile a brillé d'une lumière qu'on n'avait jamais vue. À Rhemi, on dit qu'elle brille toujours ainsi, et qu'il faut seulement être là pour la voir. »",
		"choix": retour_accueil(),
	}
	# ── A · la délégation palatine ──
	n["a_delegation_propose"] = {
		"texte": "« L'Hôtel de Ville d'Aix tient des portes vers les cités sœurs. Charlemagne les a fait bâtir, un siècle après la Vague, et aucune ne mène à un donjon. » Maëlys pose devant vous un ordre de mission de la Cour des Arches. « La Cour veut comprendre comment on bâtit une porte qui tient depuis si longtemps. Elle envoie deux des siens : maître Gerbier et Clémence d'Orval. Ils attendent dans l'antichambre. Conduisez-les à l'Hôtel de Ville d'Aix, et déposez-les vivants. »",
		"choix": [
			{"id": "infos", "label": "« Pourquoi n'y vont-ils pas par une porte ? »", "next": "a_delegation_infos"},
			_accepter("escorte", "« Je les y conduis. »"),
			_plus_tard(),
		],
	}
	n["a_delegation_infos"] = {
		"texte": "« Parce qu'aucune porte d'Aix ne mène ici. » Maëlys a presque un sourire. « Et parce que celle de Notre-Dame ne s'ouvre pas pour deux architectes curieux. Pas encore. » Elle vous regarde. « Pour vous non plus, d'ailleurs. Pas encore. »",
		"choix": [_accepter("escorte", "« Je les y conduis. »"), _plus_tard("« Laissez-moi y réfléchir. »")],
	}
	n["a_delegation_accepte"] = {
		"texte": "Maëlys ouvre la porte de l'antichambre. Un nain trapu se lève en grommelant, une elfe très jeune derrière lui, un carnet déjà ouvert. « Maître Gerbier, Clémence d'Orval. Voici qui vous conduira. » Le nain vous toise. « J'ai compté : il y a quatre cent douze mille pas d'ici à Aix. » L'elfe, sans lever les yeux de son carnet : « Quatre cent onze. Il compte toujours le premier deux fois. » Maëlys a déjà refermé la porte.",
		"choix": _ok("« En route pour Aix. »"),
	}
	n["a_delegation_relance"] = {
		"texte": "« Gerbier et d'Orval ne sont pas encore à Aix. » Maëlys ne lève pas les yeux. « Ne les laissez pas compter les pas à voix haute. Ils attirent les bêtes. »",
		"choix": _ok("« Nous y serons bientôt. »"),
	}
	n["a_delegation_souvenir"] = {
		"texte": "« La Cour a reçu le premier rapport de Gerbier. » Maëlys soupèse un cahier épais. « Il conclut que les portes d'Aix tiennent parce qu'elles ont été bâties par des gens qui savaient ce qu'ils faisaient. D'Orval a ajouté une note en marge : qu'elles tiennent peut-être parce que quelque chose, de l'autre côté, les tient aussi. Gerbier a barré la note. La Cour l'a recopiée. »",
		"choix": retour_accueil(),
	}
	return n


def maelys(doc):
	doc = sans_rev(doc)
	services = doc.setdefault("services", {})
	ancien = services.get("transport") or {}
	# L'épreuve du rang C (Jumièges) passe en tête de la liste du transport, sans changer d'id.
	entree_c = next((e for e in ancien.get("offres") or [] if (e.get("offre") or {}).get("id") == LETTRE_C), None)
	if entree_c is None:
		if (ancien.get("offre") or {}).get("id") != LETTRE_C:
			sys.exit("ERREUR : pnj:maelys n'a plus l'épreuve du rang C (services.transport.offre)")
		entree_c = {"offre": ancien["offre"], "noeuds": ancien.get("noeuds") or {}}
	entrees = entrees_maelys()
	services["transport"] = {"offres": [entree_c] + entrees["transport"]}
	services["apport"] = {"offres": entrees["apport"]}
	services["escorte"] = {"offres": entrees["escorte"]}

	noeuds = doc["dialogue"]["noeuds"]
	# Les choix du rang C nomment désormais leur offre : sans `offre`, une course du rang B
	# allumerait `transport_offert` et ferait reparler Maëlys de Jumièges.
	for c in noeuds["accueil"]["choix"]:
		if c.get("id", "").startswith("rang_c_") and c["id"] != "rang_c_souvenir":
			c.setdefault("condition", {})["offre"] = LETTRE_C
	poser_choix(noeuds["accueil"], choix_accueil_maelys(), avant_id="rien")
	noeuds.update(noeuds_maelys())
	return doc


# ── Carte de France : la Gargouille rejoint les berges ───────────────────────────────────

def france(doc):
	doc = sans_rev(doc)
	rencontres = doc.setdefault("rencontres", [])
	existante = next((r for r in rencontres if r.get("espece") == GARGOUILLE), None)
	if existante is None:
		rencontres.append({"espece": GARGOUILLE, "zones": [ZONE_GARGOUILLE]})
	elif ZONE_GARGOUILLE not in existante.setdefault("zones", []):
		existante["zones"].append(ZONE_GARGOUILLE)
	return doc


# ── PNJ neufs ────────────────────────────────────────────────────────────────────────────

def chancelier():
	return {
		"_id": CHANCELIER, "type": "pnj", "nom": "Le chancelier de l'Hôtel de Ville",
		"race": "humain", "vocation": "lettre", "portrait": PORTRAITS[CHANCELIER],
		"description": "Chancelier de l'Hôtel de Ville d'Aix-la-Chapelle, gardien des registres des portes vers les cités sœurs. Robe noire, chaîne d'office, et la patience des gens qui ont vu passer trente couronnements.",
		"services": {"transport": {"noeuds": {"livre": "pli_lu", "incomplet": "pli_absent"}}},
		"dialogue": {
			"noeud_depart": "accueil",
			"noeuds": {
				"accueil": {
					"texte": "La grande salle de l'Hôtel de Ville est voûtée, fraîche, et sent le soufre des thermes voisins. Le long des murs, des arches de pierre noire, chacune sous une bannière différente : les portes des cités sœurs. Derrière une table chargée de registres, un homme en robe noire lève les yeux. « Aix-la-Chapelle vous salue. Que puis-je pour vous ? »",
					"choix": [
						{"id": "bonjour", "label": "« Ces arches… ce sont des portes ? »", "next": "portes"},
						{"id": "pli", "label": "Lui remettre le pli de la Guilde de Lutecia.",
						 "condition": {"transport_a_livrer": True},
						 "action": {"service": "transport", "op": "livrer"}},
						{"id": "attente", "label": "« Votre réponse est en route pour Lutecia. »",
						 "condition": {"quete_active": {"id": B_AIX}, "transport_a_livrer": False}, "next": "attente"},
						{"id": "apres_pli", "label": "« Vos portes ont-elles changé ? »", "condition": apres(B_AIX), "next": "apres_pli"},
						{"id": "delegation", "label": "« La Cour des Arches vous envoie deux architectes. »",
						 "condition": pendant(A_DELEGATION), "next": "delegation_attendue"},
						{"id": "apres_delegation", "label": "« Et vos deux architectes de Lutecia ? »",
						 "condition": apres(A_DELEGATION), "next": "apres_delegation"},
						choix_fin(),
					],
				},
				"portes": {
					"texte": "« Les portes des cités sœurs. » Il les désigne d'un geste large. « Charlemagne les a fait bâtir, un siècle après la Vague, pour que les cités carolingiennes se portent secours. Aucune ne mène à un donjon : cela, nous le laissons à d'autres. » Il revient à ses registres. « Elles tiennent. C'est tout ce qu'on demande à une porte. »",
					"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}, choix_fin()],
				},
				"pli_lu": {
					"texte": "Le chancelier rompt le sceau de la porte ouverte et lit. Son visage ne bouge pas. Seule sa main, posée à plat sur la table, se crispe un instant. « Votre maîtresse pose de bonnes questions. » Il trempe sa plume, écrit quelques lignes, scelle. « Voici ma réponse. Elle est courte. Dites-lui que je l'ai écrite moi-même. »",
					"choix": [{"id": "visage", "label": "« Vous avez l'air inquiet. »", "next": "pli_visage"}, choix_fin("(Prendre la réponse.)")],
				},
				"pli_visage": {
					"texte": "« Inquiet ? » Il sourit à peine. « Aucune de nos portes n'a changé de couleur. C'est ce que j'ai écrit. » Il se lève et va poser la main sur l'arche la plus proche, comme on flatte un cheval. « Je n'ai pas écrit que votre maîtresse est la troisième à me le demander cette année. »",
					"choix": [choix_fin("(Prendre congé.)")],
				},
				"pli_absent": {
					"texte": "Le chancelier attend, la main tendue, puis la laisse retomber. « La Guilde de Lutecia m'écrit, dit-on. Sans pli, je n'ai rien à lire. »",
					"choix": [choix_fin("« Je reviens avec. »")],
				},
				"attente": {
					"texte": "« Elle l'est. » Il ne lève pas les yeux. « Bonne route jusqu'à Lutecia. Et ne la perdez pas : je ne l'écrirai pas deux fois. »",
					"choix": [choix_fin()],
				},
				"apres_pli": {
					"texte": "« Changé ? » Le chancelier pose sa plume. « Non. » Un temps. « Une, la nuit dernière, a pâli. Une heure. Nos architectes disent que c'est le froid sur la pierre. Le vieux portier dit qu'il l'a déjà vue faire, une fois, il y a quarante ans, la veille d'un hiver où le Rhin a gelé. » Il reprend sa plume. « Chacun a la théorie de son métier. »",
					"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}, choix_fin()],
				},
				"delegation_attendue": {
					"texte": "« Je sais. La Cour m'a écrit. » Il soupire. « Un maître et une élève, et des instruments qu'il faudra empêcher de toucher à nos arches. Amenez-les-moi. Vivants, de préférence : la paperasse est plus simple. »",
					"choix": [choix_fin()],
				},
				"apres_delegation": {
					"texte": "Le chancelier désigne, au fond de la salle, un nain et une elfe penchés sur la même arche, qui se disputent à voix basse. « Ils mesurent depuis dix jours. Le maître dit que nos portes tiennent parce qu'elles sont bien faites. L'élève dit qu'elles tiennent parce que quelque chose, de l'autre côté, les tient aussi. » Il hausse les épaules. « Je n'ai pas d'avis. Je tiens les registres. »",
					"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}, choix_fin()],
				},
			},
		},
	}


def gardienne():
	return {
		"_id": GARDIENNE, "type": "pnj", "nom": "La gardienne des cinq portes",
		"race": "elfe", "vocation": "magicien", "portrait": PORTRAITS[GARDIENNE],
		"description": "Templière de la Chapelle Palatine, gardienne des cinq portes en pentagramme. Elle ne dit jamais où elles mènent avant qu'on ait le droit de les franchir.",
		"dialogue": {
			"noeud_depart": "accueil",
			"noeuds": {
				"accueil": {
					"texte": "La Chapelle Palatine est octogonale, haute, dorée jusqu'à la coupole. Au sol, cinq arches de pierre dessinent une étoile, chacune ouverte sur une lueur calme. Une elfe en manteau de Templière se tient au centre, les mains croisées. « Bienvenue à la Chapelle. Ne marchez pas dans l'étoile. »",
					"choix": [
						{"id": "portes", "label": "« Où mènent-elles ? »", "condition": avant(A_AMPOULE), "next": "portes"},
						{"id": "ampoule", "label": "« Vous attendez l'Ampoule de Rhemi ? »", "condition": pendant(A_AMPOULE), "next": "ampoule_attendue"},
						{"id": "apres", "label": "« Le couronnement a eu lieu ? »", "condition": apres(A_AMPOULE), "next": "apres"},
						choix_fin(),
					],
				},
				"portes": {
					"texte": "« Loin. » Elle sourit. « Plus loin qu'aucune porte de France. Un des Frères les a posées ici, et elles n'ont jamais bougé, ni avant la Vague, ni après. » Elle regarde la lueur la plus proche. « Ceux qui les franchissent, leur guilde les envoie. Vous y viendrez peut-être. Pas encore. »",
					"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}, choix_fin()],
				},
				"ampoule_attendue": {
					"texte": "« Nous l'attendons. » Elle ne quitte pas l'étoile des yeux. « On ne couronne pas sans elle, depuis Charlemagne. Amenez-la, et son gardien avec. L'un sans l'autre ne nous sert à rien. »",
					"choix": [choix_fin()],
				},
				"apres": {
					"texte": "« Il a eu lieu. » Elle se tait un moment. « Quand on a ouvert le coffret, les cinq portes ont brillé ensemble. Elles ne l'avaient jamais fait. Le gardien de l'Ampoule dit que c'est l'huile qui les a reconnues. Mes frères Templiers disent que ce sont les portes qui ont reconnu l'huile. » Elle sourit à peine. « Ce n'est pas la même chose, et personne ici ne sait laquelle des deux est la plus inquiétante. »",
					"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}, choix_fin()],
				},
			},
		},
	}


def commandeur():
	# Le pli livré, il envoie à l'OSSUAIRE (étage 3 des catacombes, `lieu:catacombes0003`) :
	# la preuve de la descente est le cristal jaune de son coffre garanti — seule source du
	# cristal en jeu (Auteur, 25/10 : on descend dans les catacombes EXISTANTES).
	pli_livre = {"quete_active": {"id": B_TEMPLE}, "transport_a_livrer": False}
	return {
		"_id": COMMANDEUR, "type": "pnj", "nom": "Le commandeur de l'Enclos",
		"race": "humain", "vocation": "templier", "portrait": PORTRAITS[COMMANDEUR],
		"description": "Commandeur de l'Enclos du Temple, la maison des Templiers de Lutecia. Ses hommes gardent les catacombes et leur donjon, et en remontent les cristaux jaunes.",
		"services": {
			"transport": {"noeuds": {"livre": "pli_lu", "incomplet": "pli_absent"}},
			"apport": {
				"offre": {
					"id": CRISTAL_OSSUAIRE,
					"titre": "Le cristal de l'ossuaire",
					"description": "Le commandeur de l'Enclos du Temple veut que vous descendiez dans les catacombes de Lutecia jusqu'à l'ossuaire, le dernier étage, et que vous lui rapportiez le cristal jaune de son coffre. Ensuite seulement, il écrira sa réponse à la Guilde.",
					"item": CRISTAL_JAUNE,
					"quantite": 1,
					"unique": True,
					"rang": "B",
					"recompenses": {"xp": 60, "cuivre": 1200},
				},
				"noeuds": {"accepte": "cristal_accepte", "remis": "cristal_remis", "partiel": "cristal_partiel"},
			},
		},
		"dialogue": {
			"noeud_depart": "accueil",
			"noeuds": {
				"accueil": {
					"texte": "L'Enclos du Temple est une ville dans la ville : une tour carrée, des murs épais, une cour où des Templiers déchargent des caisses qui tintent. Le commandeur vous reçoit debout, dans une salle sans fenêtre éclairée par un cristal jaune posé sur la table. « La paix sur vous. »",
					"choix": [
						{"id": "bonjour", "label": "« Que gardez-vous, ici ? »", "condition": avant(B_TEMPLE), "next": "garde"},
						{"id": "pli", "label": "Lui remettre le pli de la Guilde.",
						 "condition": {"transport_a_livrer": True},
						 "action": {"service": "transport", "op": "livrer"}},
						{"id": "descente", "label": "« Vous vouliez que je descende ? »",
						 "condition": {"apport_offert": True, **pli_livre}, "next": "cristal_propose"},
						{"id": "cristal", "label": "Poser le cristal jaune de l'ossuaire sur la table.",
						 "condition": {"apport_possible": True},
						 "action": {"service": "apport", "op": "remettre"}},
						{"id": "relance", "label": "« Au sujet de l'ossuaire… »",
						 "condition": {"apport_en_cours": True, "apport_possible": False}, "next": "cristal_relance"},
						{"id": "attente", "label": "« Votre réponse part pour la Guilde. »",
						 "condition": {**pli_livre, "quete_reussie": {"id": CRISTAL_OSSUAIRE}}, "next": "attente"},
						{"id": "apres", "label": "« L'ossuaire ? »", "condition": apres(B_TEMPLE), "next": "apres"},
						choix_fin(),
					],
				},
				"garde": {
					"texte": "« Ce qu'il y a sous vos pieds. » Il pose la main sur le cristal. « Les catacombes, et ce qu'elles sont devenues depuis la Vague. Nous en remontons ceci. Sans eux, les portes de cette ville s'éteindraient l'une après l'autre. » Il retire la main. « C'est un travail de patience. Bonne journée. »",
					"choix": [choix_fin()],
				},
				"pli_lu": {
					"texte": "Le commandeur lit la lettre de Maëlys deux fois, puis la pose sur la table, sous le cristal. « Elle a raison. Je suis devenu poli. » Il vous regarde. « Au fond de l'ossuaire, là où nous extrayons depuis vingt ans, une paroi s'est ouverte le mois dernier. Derrière, une porte de pierre, fermée, gravée d'un signe que nul ici ne sait lire. Elle n'était pas là : j'ai creusé moi-même ce couloir. » Il repousse la lettre. « Je ne répondrai pas à votre maîtresse sur ma parole. Je répondrai sur la vôtre. »",
					"choix": [{"id": "suite", "label": "« C'est-à-dire ? »", "next": "cristal_propose"}],
				},
				"cristal_propose": {
					"texte": "« Descendez. » Il désigne le sol. « Par la porte des catacombes, comme tout le monde : trois étages, jusqu'à l'ossuaire. Mes hommes n'y vont plus depuis que la paroi s'est ouverte ; ce qui rôde en bas s'y est rassemblé. Au fond, il y a un coffre. Nous y laissions le cristal du mois. Rapportez-le-moi, et dites-moi ce que vous avez vu. Ensuite, j'écrirai à la Guilde. »",
					"choix": [
						{"id": "accepter", "label": "« Je descends. »", "action": {"service": "apport", "op": "accepter"}},
						{"id": "plus_tard", "label": "« Pas aujourd'hui. »", "next": "fin"},
					],
				},
				"cristal_accepte": {
					"texte": "Le commandeur hoche la tête. « Trois étages. Ne vous attardez pas au deuxième, et n'ouvrez le coffre qu'une fois la salle vide : certains coffres, en bas, ont des dents. » Il revient à son cristal. « Je vous attends. »",
					"choix": [choix_fin("« Compris. »")],
				},
				"cristal_relance": {
					"texte": "« L'ossuaire. » Il ne lève pas les yeux. « Le troisième étage, le coffre du fond. Je ne réponds pas à la Guilde avant. »",
					"choix": [choix_fin("« J'y retourne. »")],
				},
				"cristal_partiel": {
					"texte": "« Il en manque. » Le commandeur compte : il reste {reste} pièce à rapporter.",
					"choix": [choix_fin("« Je reviens avec. »")],
				},
				"cristal_remis": {
					"texte": "Le commandeur prend le cristal, le pose à côté du sien, et les regarde briller ensemble. Il vous écoute : les étages, ce qui rôdait, l'ossuaire, la paroi ouverte et la porte derrière, tiède sous la main. « Vous l'avez touchée. Moi aussi. » Il fait glisser vers vous {prime} pièces de cuivre, trempe sa plume et écrit vite. « Voici ma réponse. Tout y est, sauf une chose : je ne sais pas s'il faut cesser d'extraire. Si nous cessons, Lutecia s'éteint. Si nous continuons… » Il scelle la lettre. « Une porte qui ne devait pas s'ouvrir, on ne sait jamais ce qui la retient. »",
					"choix": [choix_fin("(Prendre la réponse.)")],
				},
				"pli_absent": {
					"texte": "Le commandeur attend. « La Guilde m'écrit, dit-on. Sans pli, je n'ai rien à lire, et rien à répondre. »",
					"choix": [choix_fin("« Je reviens avec. »")],
				},
				"attente": {
					"texte": "« Portez-la vite. » Il ne lève pas les yeux du cristal. « Et dites-lui que je ne suis plus poli. »",
					"choix": [choix_fin()],
				},
				"apres": {
					"texte": "« Toujours fermée. Toujours tiède. » Le commandeur a l'air plus vieux. « Je crois qu'elle a toujours été là, et que nous l'avons seulement découverte en creusant. Mon second croit que c'est l'extraction qui la fait venir, comme l'eau fait venir une racine. Nous continuons d'extraire, tous les deux, et chacun espère avoir raison. »",
					"choix": [choix_fin()],
				},
			},
		},
	}


def garde_mars():
	return {
		"_id": GARDE_MARS, "type": "pnj", "nom": "Le gardien de la Porte de Mars",
		"race": "nain", "vocation": "guerrier", "portrait": PORTRAITS[GARDE_MARS],
		"description": "Vieux gardien nain de la Porte de Mars, à Rhemi. Il garde une porte qui ne mène nulle part, et il en est fier.",
		"dialogue": {
			"noeud_depart": "accueil",
			"noeuds": {
				"accueil": {
					"texte": "Une arche triple, haute comme trois maisons, sculptée de scènes que la craie a usées jusqu'à l'os. Derrière, rien : la rue continue. Un vieux nain en cuirasse est assis sur un tabouret au pied du pilier central, une hallebarde en travers des genoux. « La Porte de Mars. Regardez, ça ne coûte rien. Ça ne mène nulle part non plus. »",
					"choix": [
						{"id": "bonjour", "label": "« Pourquoi la garder, alors ? »", "condition": avant(B_MARS), "next": "pourquoi"},
						{"id": "architecte", "label": "« Un architecte de Lutecia arrive pour la mesurer. »", "condition": pendant(B_MARS), "next": "attendu"},
						{"id": "apres", "label": "« Vaucelle a trouvé quelque chose ? »", "condition": apres(B_MARS), "next": "apres"},
						choix_fin(),
					],
				},
				"pourquoi": {
					"texte": "« Parce que c'est une porte. » Il tapote le pilier. « Les Romains l'ont bâtie pour aller chez eux d'un pas. Elle ne s'est jamais allumée : la craie boit le mana, à Rhemi, tout le monde le sait. » Il crache par terre. « Un portail mort-né, qu'ils disent à Lutecia. Moi je dis qu'une porte qu'on garde n'est jamais tout à fait morte. Bonne journée. »",
					"choix": [choix_fin()],
				},
				"attendu": {
					"texte": "« Encore un. » Le nain soupire. « Il en vient un tous les dix ans, avec ses craies et ses ficelles. Il mesure, il repart, il écrit qu'elle est morte. Amenez-le-moi. Je lui montrerai où le dernier a marqué ses traits. »",
					"choix": [choix_fin()],
				},
				"apres": {
					"texte": "« Votre architecte ? Il est toujours là. Il dort sous l'arche. » Le nain hausse les épaules. « Il dit qu'elle n'est pas morte, qu'elle attend. Moi je lui dis qu'une porte qui attend depuis des siècles, à Rhemi, on appelle ça une porte morte. » Il regarde l'arche, longtemps. « Mais je la garde quand même. »",
					"choix": [choix_fin()],
				},
			},
		},
	}


def hugues():
	return {
		"_id": HUGUES, "type": "pnj", "nom": "Hugues Vaucelle",
		"race": "humain", "vocation": "lettre", "portrait": PORTRAITS[HUGUES],
		"description": "Architecte de la Cour des Arches, installé sous la Porte de Mars avec ses craies, ses ficelles et ses doutes.",
		"dialogue": {
			"noeud_depart": "accueil",
			"noeuds": {
				"accueil": {
					"texte": "Sous l'arche centrale, des ficelles tendues d'un pilier à l'autre, des traits de craie de six couleurs sur les pierres. Hugues Vaucelle est accroupi au milieu, un niveau d'eau à la main. Il vous reconnaît et se relève, les genoux blancs de poussière. « Vous ! Venez voir. Mais ne marchez pas sur le bleu. »",
					"choix": [
						{"id": "trouve", "label": "« Alors ? »", "next": "trouve"},
						choix_fin(),
					],
				},
				"trouve": {
					"texte": "« Elle n'est pas morte. » Il le dit à voix basse, comme un secret. « La craie boit le mana, c'est vrai. Mais pas partout pareil : sous l'arche, elle en boit moins. Comme si la porte en avait gardé un peu, depuis le temps, pour elle. » Il hésite. « Ou comme si quelqu'un, de l'autre côté, avait essayé de passer, une fois, et laissé la trace de son pied. Le gardien dit que je rêve. Il a peut-être raison. Je reste quand même. »",
					"choix": [choix_fin("« Bonne chance, Hugues. »")],
				},
			},
		},
	}


def templier_crypte():
	quete_a_faire = {"quete_active": {"types": ["collect"], "cible": TETE_MINOTAURE, "objectif_atteint": False}}
	return {
		"_id": TEMPLIER_CRYPTE, "type": "pnj", "nom": "Le Templier de la crypte",
		"race": "nain", "vocation": "templier", "portrait": PORTRAITS[TEMPLIER_CRYPTE],
		"description": "Templier nain de la crypte de Chartres, gardien du puits. Il en a vu descendre ; il en a vu peu remonter.",
		"services": {"acces": {"lieu": LABYRINTHE, "noeuds": {"ouvre": "puits_ouvert", "refus": "puits_clos"}}},
		"dialogue": {
			"noeud_depart": "accueil",
			"noeuds": {
				"accueil": {
					"texte": "La crypte de Chartres est longue, basse, éclairée de lampes à huile. Au fond, une margelle de pierre noire et un treuil de fer : le puits. Un Templier nain se tient devant, la main sur la manivelle, comme s'il craignait qu'elle tourne toute seule. « Le puits n'est pas une curiosité. Regardez-le de loin. »",
					"choix": [
						{"id": "bonjour", "label": "« Qu'y a-t-il au fond ? »", "condition": avant(A_MINOTAURE), "next": "fond"},
						{"id": "guilde", "label": "« La Guilde de Lutecia m'envoie descendre. »",
						 "condition": {"acces_ouvrable": True}, "next": "seuil"},
						{"id": "apres", "label": "« Ils sont morts. Tous les deux. »", "condition": apres(A_MINOTAURE), "next": "apres"},
						choix_fin(),
					],
				},
				"fond": {
					"texte": "« Un labyrinthe que personne n'a creusé. » Il ne lâche pas la manivelle. « Avant la Vague, ce n'était qu'un puits, au milieu du labyrinthe qu'on a tracé autour. Puis il a changé de couleur. Les premiers qui sont descendus, on les appelle les Forts. On a gardé leurs noms. Pas leurs corps. » Il désigne la sortie. « Bonne journée. »",
					"choix": [choix_fin()],
				},
				"seuil": {
					"texte": "Le Templier lit votre ordre de mission, le rend, et tourne la manivelle. La chaîne descend longtemps. « En bas, des couloirs. Ils tournent toujours du même côté, et ne ramènent jamais où l'on croit. » Il bloque le treuil. « Quand vous remonterez, tirez trois fois sur la chaîne. Si vous ne tirez pas, je ne remonte rien. »",
					"choix": [
						{"id": "descendre", "label": "Descendre dans le puits.", "condition": {"acces_ouvrable": True},
						 "action": {"service": "acces", "op": "passer"}},
						{"id": "attendre", "label": "« Pas encore. »", "next": "accueil"},
					],
				},
				"puits_ouvert": {
					"texte": "L'échelle de fer s'arrête au-dessus d'un sol de dalles. L'air est chaud, et sent l'étable. Un mugissement, très loin, rebondit sur des murs que vous ne voyez pas. Puis un second, plus près, qui ne vient pas du même côté. Il y en a deux.",
					"choix": [{"id": "ok", "label": "Tirer votre arme.", "next": "fin"}],
				},
				"puits_clos": {
					"texte": "Le Templier ne touche pas la manivelle. « Le puits ne s'ouvre qu'à ceux que la Guilde envoie, et qui ont quelque chose à y faire. »",
					"choix": [choix_fin("Reculer.")],
				},
				"apres": {
					"texte": "« Deux. » Le Templier le répète, comme pour s'habituer au mot. « Nos registres n'en ont jamais compté qu'un. » Il regarde la chaîne. « Le prieur dit que le second était un fils. Notre frère archiviste, que le labyrinthe en refait un chaque fois qu'on en tue un, comme une porte rouvre ce qu'on lui ferme. Ils ont doublé la garde. Moi, je garde la manivelle. »",
					"choix": [choix_fin()],
				},
			},
		},
		"_barriere": quete_a_faire,
	}


# ── Lieux neufs ──────────────────────────────────────────────────────────────────────────

def lieux_neufs(par_id):
	positions = {}
	for lieu, (cite, cible) in CIBLES_PORTES.items():
		occupees = cases_occupees(par_id, cite) | {tuple(p) for (c, p) in positions.values() if c == cite}
		positions[lieu] = (cite, case_libre(par_id[cite], cible, occupees))
	tc = templier_crypte()
	barriere = tc.pop("_barriere")
	docs = [
		{"_id": HOTEL, "type": "lieu", "label": "L'Hôtel de Ville d'Aix-la-Chapelle",
		 "image": IMAGES[HOTEL], "categorie": "hotel_de_ville", "lieu_parent": AIX,
		 "pnj": [{"character": CHANCELIER, "nom": "Le chancelier", "portrait": PORTRAITS[CHANCELIER],
				  "probabilite": 1,
				  "description": "Un homme en robe noire derrière une table chargée de registres."}]},
		lien(AIX, HOTEL, positions[HOTEL][1], "L'Hôtel de Ville", "Retourner dans la ville", "hotel_de_ville"),
		{"_id": CHAPELLE, "type": "lieu", "label": "La Chapelle Palatine",
		 "image": IMAGES[CHAPELLE], "categorie": "chapelle_palatine", "lieu_parent": AIX,
		 "pnj": [{"character": GARDIENNE, "nom": "La gardienne des cinq portes", "portrait": PORTRAITS[GARDIENNE],
				  "probabilite": 1,
				  "description": "Une elfe en manteau de Templière, debout au centre de l'étoile des cinq portes."}]},
		lien(AIX, CHAPELLE, positions[CHAPELLE][1], "La Chapelle Palatine", "Retourner dans la ville", "chapelle_palatine"),
		{"_id": PORTE_MARS, "type": "lieu", "label": "La Porte de Mars",
		 "image": IMAGES[PORTE_MARS], "categorie": "monument", "lieu_parent": RHEMI,
		 "pnj": [
			 {"character": GARDE_MARS, "nom": "Le gardien de la Porte", "portrait": PORTRAITS[GARDE_MARS],
			  "probabilite": 1,
			  "description": "Un vieux nain en cuirasse, assis au pied du pilier central, une hallebarde en travers des genoux."},
			 # Vaucelle reste sous l'arche une fois déposé : le monde a changé (Auteur, 15/10).
			 {"character": HUGUES, "nom": "Hugues Vaucelle", "portrait": PORTRAITS[HUGUES],
			  "probabilite": 1, "conditions": [apres(B_MARS)],
			  "description": "Un architecte accroupi sous l'arche, au milieu de ficelles tendues et de traits de craie."},
		 ]},
		lien(RHEMI, PORTE_MARS, positions[PORTE_MARS][1], "La Porte de Mars", "Retourner dans la ville", "monument"),
		{"_id": ENCLOS, "type": "lieu", "label": "L'Enclos du Temple",
		 "image": IMAGES[ENCLOS], "categorie": "temple_templier", "lieu_parent": LUTECIA,
		 "pnj": [{"character": COMMANDEUR, "nom": "Le commandeur", "portrait": PORTRAITS[COMMANDEUR],
				  "probabilite": 1,
				  "description": "Un Templier grisonnant, debout près d'une table où brille un cristal jaune."}]},
		lien(LUTECIA, ENCLOS, positions[ENCLOS][1], "L'Enclos du Temple", "Retourner dans la ville", "temple_templier"),
		{"_id": CRYPTE, "type": "lieu", "label": "La crypte de Chartres",
		 "image": IMAGES[CRYPTE], "categorie": "temple_templier", "lieu_parent": CHARTRES,
		 "pnj": [{"character": TEMPLIER_CRYPTE, "nom": "Le Templier de la crypte", "portrait": PORTRAITS[TEMPLIER_CRYPTE],
				  "probabilite": 1,
				  "description": "Un Templier nain, la main sur la manivelle du treuil du puits."}]},
		lien(CHARTRES, CRYPTE, positions[CRYPTE][1], "La crypte de Chartres", "Remonter dans la ville", "temple_templier"),
		chancelier(), gardienne(), commandeur(), garde_mars(), hugues(), tc,
		{"_id": LABYRINTHE, "type": "lieu", "label": "Le labyrinthe du puits de Chartres",
		 "image": IMAGES[LABYRINTHE], "categorie": "battle_map",
		 "dimensions": {"x": LARGEUR_LABY, "y": HAUTEUR_LABY},
		 "cells": cells_labyrinthe(), "nav": {},
		 "tags": ["labyrinthe", "souterrain", "portail", "donjon"],
		 # Barrière de la descente (modèle de la clairière du Morvan) : ouverte tant que la tête
		 # n'est pas remise, SANS `combat_gagne` — une tête perdue au sol ne bloque pas la quête.
		 "acces": {"gardien": TEMPLIER_CRYPTE,
				   "refus": "La chaîne pend, immobile. En bas, rien ne mugit plus.",
				   "cycle": 1, "conditions": [barriere]}},
		{"_id": DONJON_PUITS, "type": "donjon", "nom": "Le puits de Chartres",
		 "description": "Sous la crypte de Chartres, un puits devenu portail à la Vague, ouvert sur un labyrinthe que personne n'a creusé. Un Minotaure l'habite, disent les registres des Templiers.",
		 "portail": CRYPTE,
		 # Calibrage (Auteur, 25/10) : un Minotaure armé plafonne vers 150 de potentiel ; deux,
		 # grade Champion-Héros, passent le plancher du rang A. Salle à espèce UNIQUE : la tête
		 # est garantie.
		 "niveau_min": 4, "niveau_max": 5,
		 "battle_maps": [{"lieu": LABYRINTHE, "especes": [MINOTAURE], "nb_monstres": 2,
						  "niveau_min": 4, "niveau_max": 5}]},
	]
	return docs


REQUIS = (MAELYS, FRANCE, LUTECIA, AIX, RHEMI, CHARTRES, AUBERGE_SACRE, ITEM_LETTRE,
		  TETE_GARGOUILLE, TETE_GEANT, TETE_BETE, TETE_MINOTAURE, GARGOUILLE, MINOTAURE,
		  CRISTAL_JAUNE, OSSUAIRE,
		  ZONE_GARGOUILLE, "item:Cotte_de_mailles", "item:Epee_longue_ordre", "item:Bouclier_ordre")


def generer(par_id):
	for requis in REQUIS:
		if requis not in par_id:
			sys.exit(f"ERREUR : {requis} absent du dump")
	return [maelys(par_id[MAELYS]), france(par_id[FRANCE])] + lieux_neufs(par_id)


def main(argv):
	dump = charger(dernier_dump(argv))
	par_id = {d["_id"]: d for d in dump["docs"]}
	docs = generer(par_id)
	collisions = [d["_id"] for d in docs[2:] if d["_id"] in par_id]
	if collisions:
		print("⚠️ ids déjà présents au dump (écrasés par l'import) :", ", ".join(collisions))
	ecrire(SORTIE, docs)
	print(f"{len(docs)} docs → {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
	main(sys.argv)
