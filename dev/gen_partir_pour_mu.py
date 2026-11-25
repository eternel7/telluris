#!/usr/bin/env python
# dev/gen_partir_pour_mu.py
# « Partir pour Mu » — troisième quête d'Aélis après Jumièges, rang A
# (docs/lore/personnages/20261119_la_piece_derriere_le_mur.md, § Quatrième arbitrage, Auteur 22/11).
#
#   Départs : Aélis aux Archives des Seuils (elle tient l'offre d'escorte, troisième entrée de sa
#   liste `offres`) ET Maëlys à la Guilde, qui le fait savoir et renvoie aux Archives — le modèle
#   de « La pièce derrière le mur », où la réception et Maëlys indiquaient le chemin. Condition :
#   « Les vestiges du premier passage » réussie, rang A de Lutecia.
#   Voyage : passage gardé par Aénor de Sully à Notre-Dame. La porte de Mu est un lien portail
#   qui TOUCHE l'ancrage : jamais tirée au sort, elle s'ajoute au tableau, toujours ouverte, pour
#   qui en franchit la barrière (escorte en cours, ou quête réussie) — routers/pnj._portes_de_l_ancrage.
#   Aucun combat ; un cristal jaune payé par le joueur. Arrivée au seuil de Mu = escorte déposée.
#   Mu-la-Centrale, première livraison : le seuil (un Templier de Mu y tient le RETOUR, tableau
#   fixe, un cristal), une auberge, un marché restreint. Institut de Mu et Sept Sages : plus tard.
#
#   ⚠️ Mu est sous la mer : aucune route n'en sort. Le marché vend donc le cristal jaune (proposé,
#   non tranché par l'Auteur) — sans lui, un personnage arrivé sans cristal de réserve y resterait.
#
# ⚠️ UN SEUL FICHIER À IMPORTER : jsons/partir_pour_mu_a_importer.json, DELTA seul (CLAUDE.md §18).
# PNJ et lieux déjà en base RELUS du dernier dump (seuls les choix, nœuds, services et présences
# ajoutés changent : régénération idempotente) + docs neufs COMPLETS (PUT, CLAUDE.md §11).
#
# Usage : python dev/gen_partir_pour_mu.py [jsons/telluris-dump-….json]

import importlib.util
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)


def _vestiges():
	chemin = os.path.join(RACINE, "dev", "gen_vestiges_premier_passage.py")
	spec = importlib.util.spec_from_file_location("gen_vestiges_premier_passage", chemin)
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod


V = _vestiges()
choix, noeud, ajouter_choix, sans_rev = V.choix, V.noeud, V.ajouter_choix, V.sans_rev
pnj_doc, entree_pnj = V.pnj_doc, V.entree_pnj

SORTIE = os.path.join(RACINE, "jsons", "partir_pour_mu_a_importer.json")

QUETE = "quete:partir_pour_mu"
VESTIGES = V.QUETE
LUTECIA = V.LUTECIA
MU = "lieu:mu"
CRISTAL = "item:cristal_de_mana_jaune"

ARCHIVES = V.ARCHIVES
ANCRAGE = "lieu:notre_dame_portail"
SEUIL = "lieu:seuil_de_mu"
AUBERGE = "lieu:fare_des_marees"
MARCHE = "lieu:marche_du_dome"

AELIS_ARCHIVES = V.AELIS_ARCHIVES
AELIS_VOIX = "pnj:aelis_de_montfaucon_vers_mu"     # sa voix tant qu'elle est escortée (`voix_protege`)
AELIS_MU = "pnj:aelis_de_montfaucon_mu"            # à l'auberge de Mu, la quête faite
MAELYS = "pnj:maelys"
AENOR = "pnj:aenor_de_sully"
TEMPLIER_MU = "pnj:hemi_taurua"
AUBERGISTE = "pnj:moana_teriitahi"
MARCHANDE = "pnj:kahu_rehua"

PORTRAIT_AELIS = V.PORTRAIT_AELIS
PORTRAIT_AELIS_DIALOGUE = V.PORTRAIT_AELIS_DIALOGUE
# Images à livrer par l'Auteur (prompts dans la séance, § 7 quater).
IMAGE_SEUIL = "seuil_de_mu01.jpg"
IMAGE_AUBERGE = "fare_des_marees01.jpg"
IMAGE_MARCHE = "marche_du_dome01.jpg"
PORTRAIT_TEMPLIER = "templier_ogre_m_seuil_de_mu01.jpg"
PORTRAIT_AUBERGISTE = "aubergiste_nain_f_fare_des_marees01.jpg"
PORTRAIT_MARCHANDE = "marchande_hobbit_f_marche_du_dome01.jpg"

# Portes sur la carte de Mu-la-Centrale (88 × 48 cases de 16 px, `towns/mu_capital.jpg`) : la place
# dorée au centre du dôme, les canaux du sud-ouest, les quais de l'est. Cases praticables vérifiées
# sur la grille du dump (⚠️ grille à repeindre : elle ne suit pas encore le dôme).
POS_SEUIL = (45, 24)
POS_AUBERGE = (30, 28)
POS_MARCHE = (54, 28)

# Mu vend le cristal du retour : 1 or (10 000 cu), le prix de ce qui ne se trouve nulle part
# ailleurs que dans deux coffres de France. Calibrage proposé, à éprouver.
PRIX_CRISTAL = 10_000

RANG_A = {"cite": LUTECIA, "rang": "A"}
ESCORTE_ACTIVE = {"quete_active": {"types": ["escorte"], "cible": SEUIL}}
AVANT = {"quete_active": {"id": QUETE, "attendu": False}, "quete_reussie": {"id": QUETE, "attendu": False}}
PENDANT = {"quete_active": {"id": QUETE}}
APRES = {"quete_reussie": {"id": QUETE}}
# AVANT chez Maëlys, qui ne tient pas l'offre (pas de condition `offre` pour fermer l'après) : un
# dict de condition ne porte qu'UNE `quete_reussie`, prise par les vestiges ; l'après se ferme par
# `passages` — qui a fait la quête est entré au seuil de Mu (on n'y entre que par elle).
AVANT_MAELYS = {"quete_active": {"id": QUETE, "attendu": False}, "quete_reussie": {"id": VESTIGES},
				"rang_min": RANG_A, "passages": {"lieu": SEUIL, "max": 0}}


# ---------------------------------------------------------------------------------------------
# L'offre d'escorte (Aélis aux Archives)
# ---------------------------------------------------------------------------------------------

def offre_escorte():
	return {
		"id": QUETE,
		"titre": "Partir pour Mu",
		"description": "L'Institut offre à Aélis de Montfaucon de parfaire sa formation à Mu, et elle "
					   "veut que vous l'accompagniez. On y passe par le portail de Notre-Dame : Aénor de "
					   "Sully, commanderesse des Templiers, ouvre le seuil à qui pose un cristal de mana "
					   "jaune sur l'autel d'ancrage. Le cristal est à votre charge. Conduisez Aélis jusqu'au "
					   "seuil de Mu.",
		"destination": SEUIL,
		"proteges": [{"prenom": "Aélis", "nom": "de Montfaucon", "race": "humain", "sex": "F",
					  "image": PORTRAIT_AELIS,
					  "description": "Architecte de l'Institut, appelée à Mu. Un compas, un carnet, une "
									 "lettre scellée de la coupole. Elle ne sait pas se battre."}],
		"unique": True,
		"proba": 1,
		"rang_min": RANG_A,
		# Une marche au-dessus des vestiges (200 XP, 3 000 cu) ; le voyage coûte un cristal, et
		# le retour un second. Calibrage proposé, non tranché.
		"recompenses": {"xp": 300, "cuivre": 4500},
	}


# ---------------------------------------------------------------------------------------------
# PNJ et lieux relus du dump
# ---------------------------------------------------------------------------------------------

def aelis_archives(doc):
	doc = sans_rev(doc)
	n = doc["dialogue"]["noeuds"]
	esc = doc.setdefault("services", {}).setdefault("escorte", {})
	# Remplacée À SA PLACE (régénération idempotente), sinon ajoutée en dernier.
	offres = list(esc.get("offres") or [])
	entree = {"offre": offre_escorte(), "noeuds": {"accepte": "mu_accepte"}}
	rang = next((i for i, o in enumerate(offres) if (o.get("offre") or {}).get("id") == QUETE), None)
	offres = [o for o in offres if (o.get("offre") or {}).get("id") != QUETE]
	offres.insert(len(offres) if rang is None else rang, entree)
	doc["services"]["escorte"] = {"offres": offres}
	ajouter_choix(doc, "accueil", [
		choix("mu_offre", "« Une lettre de la coupole ? »", "mu_01",
			  condition=dict(AVANT, escorte_offerte=True, offre=QUETE, rang_min=RANG_A,
							 quete_reussie={"id": VESTIGES})),
	], en_tete=True)
	n["mu_01"] = noeud(
		"Aélis tient une lettre au cachet intact, et ne l'a pas posée depuis que vous êtes entré. « Elle "
		"vient des vieux maîtres. Ceux qui sourient quand je demande. » Elle la retourne. « On m'offre de "
		"finir ma formation. À Mu. Ils l'écrivent sans lever les yeux, cette fois : un nom, une date, et "
		"\"par Notre-Dame\". »",
		choix("mu_02", "« Vous y allez ? »", "mu_02"))
	n["mu_02"] = noeud(
		"« Bien sûr que j'y vais. » Elle rit, un peu trop vite. « Une arche éteinte m'a dit ce nom sous "
		"Lutecia, {prenom}. Je ne vais pas refuser quand c'est la coupole qui le dit. » Elle replie la "
		"lettre. « La commanderesse de Notre-Dame ouvre le seuil contre un cristal jaune. Je n'en ai pas. "
		"Et je n'ai jamais franchi un portail sans vous à côté. Venez-vous ? »",
		choix("mu_ok", "« Je viens. »", action={"service": "escorte", "op": "accepter"}),
		choix("mu_plus_tard", "« Pas encore. »", "fin"))
	n["mu_accepte"] = noeud(
		"Elle range son compas, son carnet, la lettre, et laisse le reste en piles sur la table, comme si "
		"elle devait revenir le soir même. « À Notre-Dame, voir Aénor de Sully. Prenez un cristal jaune "
		"pour le passage. Les vieux maîtres disent qu'on en trouve là-bas aussi, mais ils ne disent pas à "
		"quel prix. »",
		choix("mu_route", "« À Notre-Dame. »", "fin"))
	return doc


def lieu_archives(doc):
	"""Aélis quitte les Archives : avec vous pendant l'escorte, à Mu ensuite."""
	doc = sans_rev(doc)
	absente = [{"quete_active": {"types": ["escorte"], "cible": SEUIL, "attendu": False}},
			   {"quete_reussie": {"id": QUETE, "attendu": False}}]
	for e in doc.get("pnj") or []:
		if e.get("character") == AELIS_ARCHIVES:
			e["conditions"] = [c for c in e.get("conditions") or [] if c not in absente] + absente
	return doc


def maelys(doc):
	"""Maëlys le fait savoir et renvoie aux Archives : l'offre est tenue par Aélis seule."""
	doc = sans_rev(doc)
	n = doc["dialogue"]["noeuds"]
	ajouter_choix(doc, "accueil", [
		choix("mu_offre", "« On parle de l'Institut, au Grand Relais. »", "mu_01",
			  condition=AVANT_MAELYS),
		choix("mu_relance", "« Notre-Dame, alors. »", "mu_relance", condition=PENDANT),
		choix("mu_souvenir", "« Je reviens de Mu. »", "mu_souvenir", condition=APRES),
	])
	n["mu_01"] = noeud(
		"Maëlys repose sa plume. « On en parle parce que j'en parle. L'Institut m'a écrit : une de ses "
		"architectes est appelée ailleurs, et elle a demandé que la Guilde lui prête quelqu'un. Elle vous "
		"a nommé. » Elle ne sourit pas. « Aélis de Montfaucon. Elle vous attend aux Archives des Seuils. "
		"Où elle va, la lettre ne le dit pas. Moi, je le devine, et je préfère ne pas l'écrire. »",
		choix("mu_ou", "« Où ? »", "mu_02"),
		choix("mu_ok", "« J'y vais. »", "fin"))
	n["mu_02"] = noeud(
		"« Là où vont les Architectes quand ils ont fini d'apprendre ce qu'on enseigne ici. Ceux qui en "
		"reviennent ne le racontent pas. Ce n'est pas un interdit, disent-ils : ça ne s'explique pas. » "
		"Elle tapote la broche en forme de porte ouverte. « La Guilde n'y a pas de maison. Là-bas, vous ne "
		"serez pas aventurier de rang A : vous serez l'invité d'une architecte. »",
		choix("mu_ok2", "« Aux Archives, donc. »", "fin"))
	n["mu_relance"] = noeud(
		"« Aénor de Sully tient le cercle, sous les voûtes. Elle ne fait pas crédit : un cristal jaune, ou "
		"rien. » Maëlys reprend sa plume. « Et ramenez-vous en un seul morceau. L'architecte aussi, si elle "
		"veut revenir. »",
		choix("mu_relance_fin", "Prendre congé.", "fin"))
	n["mu_souvenir"] = noeud(
		"Maëlys vous regarde un long moment, sans rien demander. « Mon prédécesseur cherchait des portes. "
		"Il n'en est pas revenu. Vous, si. » Elle range la lettre de l'Institut dans un tiroir qu'elle "
		"ferme à clé. « Je ne vous demanderai pas ce qu'il y a là-bas. Si un jour vous voulez le dire, "
		"vous saurez où me trouver. »",
		choix("mu_souvenir_fin", "Revenir.", "accueil"))
	return doc


def aenor(doc):
	"""Aénor : la porte de Mu au tableau (pendant), le souvenir (après). Le seuil lui-même vient du
	service `portail` existant ; `refus_acces` sert si la barrière tombe entre affichage et clic."""
	doc = sans_rev(doc)
	n = doc["dialogue"]["noeuds"]
	doc["services"]["portail"].setdefault("noeuds", {})["refus_acces"] = "mu_refus"
	ajouter_choix(doc, "accueil", [
		choix("mu_pendant", "« L'Institut envoie Aélis de Montfaucon à Mu. »", "mu_pendant", condition=PENDANT),
		choix("mu_apres", "« Mu… »", "mu_apres", condition=APRES),
	], en_tete=True)
	n["mu_pendant"] = noeud(
		"Aénor quitte la roue des yeux pour la première fois. Elle regarde Aélis, la lettre au cachet de la "
		"coupole, puis vous. « Je vous ai dit qu'un seul lieu menait ici. » Elle pose la paume sur une rune "
		"que vous n'aviez pas vue s'allumer. « Celle-ci ne tourne pas avec les autres. Elle ne s'ouvre qu'à "
		"ceux qu'on attend de l'autre côté. Le prix ne change pas : un cristal jaune. »",
		choix("seuils", "« Montrez-moi les seuils. »", "seuils"),
		choix("mu_retour", "« Et pour revenir de là-bas ? »", "mu_retour"))
	n["mu_retour"] = noeud(
		"« De ce côté-là aussi, quelqu'un tient une roue. Il vous demandera la même chose que moi. » Elle "
		"hausse à peine les épaules. « Ils ont de quoi payer, là-bas. Ils ne le donnent pas. »",
		choix("seuils", "« Montrez-moi les seuils. »", "seuils"),
		choix("accueil", "« Autre chose. »", "accueil"))
	n["mu_apres"] = noeud(
		"« Ne le dites pas trop fort, sous ces voûtes. » Aénor fait tourner la roue d'un cran. « Les "
		"Templiers de Notre-Dame gardent ce nom depuis plus longtemps que je ne garde ce cercle. Vous êtes "
		"revenu par la rune qui ne tourne pas. Elle s'ouvrira encore pour vous, au même prix. »",
		choix("seuils", "« Montrez-moi les seuils. »", "seuils"),
		choix("accueil", "« Autre chose. »", "accueil"))
	n["mu_refus"] = noeud(
		"La rune qui ne tourne pas s'est éteinte sous la main d'Aénor. « Pas pour vous, pas maintenant. »",
		choix("seuils", "« Les autres seuils ? »", "seuils"),
		choix("fin", "(Prendre congé.)", "fin"))
	return doc


# ---------------------------------------------------------------------------------------------
# Lieux neufs : le seuil, l'auberge, le marché ; liens
# ---------------------------------------------------------------------------------------------

def _lien(id_, a, pos_a, label_a, b, pos_b, label_b, type_):
	return {"_id": id_, "type": "connection",
			"nodes": [{"lieu": a, "pos": list(pos_a), "label": label_a},
					  {"lieu": b, "pos": list(pos_b), "label": label_b}],
			"metadata": {"type": type_, "status": "ouvert"}}


def lieux_neufs():
	seuil = {
		"_id": SEUIL, "type": "lieu", "label": "Le seuil de Mu",
		"image": IMAGE_SEUIL, "categorie": "portail", "sous_categorie": "temple", "lieu_parent": MU,
		"texte": "Une salle basse taillée dans une pierre veinée d'or, où l'air sent le sel et la pierre "
				 "mouillée. Au centre, un cercle gravé, et au-dessus une arche dont le vide tremble à peine, "
				 "comme l'eau d'un bassin qu'on n'a pas touché. Contre la paroi, une vasque où pousse une "
				 "branche de corail qui luit d'un jaune très doux. Au-delà des portes, la lumière du dôme.",
		# Escorte en cours (porte de l'ancrage, Aénor) OU quête réussie (retour par la même rune).
		"acces": {"cycle": 1,
				  "refus": "La rune qui ne tourne pas reste éteinte.",
				  "conditions": [{"ou": [ESCORTE_ACTIVE, APRES]}]},
		"pnj": [
			{"character": TEMPLIER_MU, "nom": "Hemi Taurua", "portrait": PORTRAIT_TEMPLIER, "probabilite": 1,
			 "description": "Un ogre en manteau d'écailles grises, une main posée sur une roue de pierre plus "
							"petite que celle de Notre-Dame, qui ne vous quitte pas des yeux."},
		],
	}
	auberge = {
		"_id": AUBERGE, "type": "lieu", "label": "Le fare des Marées",
		"image": IMAGE_AUBERGE, "categorie": "auberge", "lieu_parent": MU,
		"pnj": [
			{"character": AUBERGISTE, "nom": "Moana Teriitahi", "portrait": PORTRAIT_AUBERGISTE,
			 "probabilite": 1,
			 "description": "Une naine aux tresses nouées de fil de nacre, derrière un comptoir de pierre polie."},
			entree_pnj(AELIS_MU, "Aélis", PORTRAIT_AELIS_DIALOGUE,
					   "Aélis, à une table près du bassin, le carnet ouvert sur un plan qu'elle ne finit pas.",
					   [APRES]),
		],
	}
	marche = {
		"_id": MARCHE, "type": "lieu", "label": "Le marché du Dôme",
		"image": IMAGE_MARCHE, "categorie": "marche", "lieu_parent": MU,
		"pnj": [
			{"character": MARCHANDE, "nom": "Kahu Rehua", "portrait": PORTRAIT_MARCHANDE, "probabilite": 1,
			 "description": "Une hobbit assise sous un auvent de toile pâle, devant des paniers de nacre, de "
							"perles et de sel, et un coffret fermé qu'elle n'ouvre pas pour tout le monde."},
		],
	}
	# Porte de l'ancrage : aucun bouton d'aucun côté (`bouton: false`, lieux.depart_interdit) — on
	# ne la franchit que par Aénor (Notre-Dame) ou Hemi Taurua (Mu), contre un cristal.
	porte = _lien("link:seuil_de_mu_to_notre_dame_portail",
				  ANCRAGE, (0, 0), "Le portail de Notre-Dame", SEUIL, (0, 0), "Le seuil de Mu", "portail")
	for nd in porte["nodes"]:
		nd["bouton"] = False
	liens = [
		porte,
		# Libellé d'un nœud = le bouton qui MÈNE à ce nœud.
		_lien("link:seuil_de_mu_to_mu", MU, POS_SEUIL, "Sortir dans la cité",
			  SEUIL, (0, 0), "Entrer au seuil de Mu", "temple"),
		_lien("link:fare_des_marees_to_mu", MU, POS_AUBERGE, "Ressortir sur le quai",
			  AUBERGE, (0, 0), "Entrer au fare des Marées", "auberge"),
		_lien("link:marche_du_dome_to_mu", MU, POS_MARCHE, "Quitter le marché",
			  MARCHE, (0, 0), "Entrer au marché du Dôme", "boutique"),
	]
	return [seuil, auberge, marche] + liens


# ---------------------------------------------------------------------------------------------
# PNJ neufs
# ---------------------------------------------------------------------------------------------

def aelis_voix():
	"""La VOIX d'Aélis tant qu'elle est sous votre protection (`voix_protege`) : Notre-Dame,
	Aénor, le cristal, et où en trouver un."""
	doc = pnj_doc(AELIS_VOIX, "Aélis de Montfaucon", "humain",
		"Aélis de Montfaucon, architecte de l'Institut, en route pour Mu.",
		PORTRAIT_AELIS_DIALOGUE, vocation="lettre", noeuds={
		"accueil": noeud(
			"Aélis marche à votre hauteur, la lettre de la coupole glissée dans son carnet. Elle la touche "
			"de temps en temps, comme pour vérifier qu'elle est toujours là.",
			choix("route", "« Où allons-nous ? »", "route"),
			choix("cristal", "« Et le cristal ? »", "cristal"),
			choix("mu", "« Que savez-vous de Mu ? »", "mu"),
			choix("fin", "(Reprendre la route.)", "fin")),
		"route": noeud(
			"« À Notre-Dame. Sous les voûtes, au fond de la nef, Aénor de Sully tient l'autel d'ancrage. Les "
			"Templiers du parvis ne laissent passer que les aventuriers de rang A de Lutecia : vous l'êtes. "
			"Moi, je suis avec vous. »",
			choix("ok", "Revenir.", "accueil")),
		"cristal": noeud(
			"« Un cristal jaune pour le passage, et il fond dans la roue. Les Templiers en tirent du fond de "
			"l'ossuaire, et l'on dit qu'il y en a un dans le coffre du puits de Chartres. » Elle hésite. « Et "
			"pour revenir, il en faudra un autre. Je ne sais pas encore si je reviendrai. Vous, si. »",
			choix("ok", "Revenir.", "accueil")),
		"mu": noeud(
			"« Ce qu'on en dit sous la coupole : un endroit où l'on finit d'apprendre. Ce qu'on en dit dans "
			"les tavernes : une ville engloutie, ou un conte. » Elle sourit. « Ce qu'en disent les vieux "
			"maîtres : rien. Nous serons les premiers de ma promotion à savoir lequel a raison. »",
			choix("ok", "Revenir.", "accueil")),
	})
	doc["voix_protege"] = {"quete": QUETE, "prenom": "Aélis"}
	return doc


def aelis_mu():
	"""Aélis à l'auberge de Mu, la quête faite : en attendant que l'Institut de Mu la reçoive."""
	return pnj_doc(AELIS_MU, "Aélis de Montfaucon", "humain",
		"Aélis de Montfaucon, architecte de l'Institut de Lutecia, invitée à Mu.",
		PORTRAIT_AELIS_DIALOGUE, vocation="lettre", noeuds={
		"accueil": noeud(
			"Aélis lève les yeux de son carnet. Au-dessus d'elle, à travers les hautes baies, la lumière du "
			"dôme ondule sur le plafond comme au fond d'une piscine. « Vous êtes encore là. Tant mieux. »",
			choix("institut", "« L'Institut de Mu ? »", "institut"),
			choix("ville", "« Que pensez-vous de la ville ? »", "ville"),
			choix("fin", "(La laisser travailler.)", "fin")),
		"institut": noeud(
			"« On m'a reçue sur le seuil, on a lu ma lettre, et on m'a dit d'attendre ici qu'on vienne me "
			"chercher. » Elle referme son carnet sur son crayon. « Polis. Pas pressés. J'ai l'impression "
			"qu'on vérifie d'abord si je vaux le voyage. Vous, ils vous laisseront où vous êtes : un invité "
			"n'entre pas partout. »",
			choix("ok", "Revenir.", "accueil")),
		"ville": noeud(
			"« Il y a de l'eau partout, et elle va où on lui dit d'aller. » Elle montre la vasque près du "
			"comptoir, où pousse une branche de corail jaune. « Et ça. Chez nous, on paierait une fortune "
			"pour un éclat mort. Ici, ils le laissent pousser dans une auberge. Personne ne m'a encore dit "
			"pourquoi. »",
			choix("ok", "Revenir.", "accueil")),
	})


def templier_mu():
	"""Hemi Taurua, Templier de Mu : le RETOUR vers Notre-Dame, tableau fixe, un cristal."""
	return pnj_doc(TEMPLIER_MU, "Hemi Taurua", "ogre",
		"Templier de Mu, gardien du seuil où arrivent ceux qui viennent de Notre-Dame. Méfiant envers "
		"l'étranger, comme presque tous ceux de son ordre.",
		PORTRAIT_TEMPLIER, vocation="paladin",
		services={"portail": {
			"ancrage": SEUIL, "fixe": True,
			"cout": {"item": CRISTAL, "quantite": 1},
			"choix": "franchir",
			"noeuds": {"ouvert": "ouvert", "refus_acces": "refus_acces", "ferme": "seuils",
					   "refus_cristal": "refus_cristal"},
		}},
		noeuds={
		"accueil": noeud(
			"L'ogre ne lâche pas la roue de pierre. Ses yeux passent sur vos armes, puis sur votre visage, "
			"sans s'y arrêter plus que sur les armes. « Hemi Taurua. Je garde ce seuil. Vous êtes "
			"l'invité de l'architecte. Ici, ça veut dire qu'on vous laisse passer. Pas qu'on vous attendait. »",
			choix("seuils", "« Je voudrais repartir pour Lutecia. »", "seuils"),
			choix("corail", "« Ce corail, dans la vasque ? »", "corail"),
			choix("fin", "(Prendre congé.)", "fin")),
		"corail": noeud(
			"« Il pousse. » Hemi Taurua regarde la vasque comme on regarde un enfant qui dort. « Ce n'est "
			"pas à vendre, et ce n'est pas à toucher. Si vous voulez repartir, on vous vendra au marché de "
			"quoi payer la roue. Pas celui-là. »",
			choix("accueil", "Revenir.", "accueil")),
		"seuils": noeud(
			"« Une seule porte, ici, et elle ne mène qu'à un endroit. » Il pose la main à plat sur la roue. "
			"« Un {cristal}, comme de l'autre côté. »",
			choix("franchir", "Franchir le seuil.", condition={"cristal_jaune_porte": True},
				  action={"service": "portail", "op": "franchir"}),
			choix("sans_cristal", "« Je n'ai pas de cristal jaune. »",
				  condition={"cristal_jaune_porte": False}, next="refus_cristal"),
			choix("accueil", "« Pas maintenant. »", "accueil")),
		"ouvert": noeud(
			"Le cristal fond dans la roue. Le vide de l'arche se tend comme une eau qu'on traverse, et vous "
			"arrivez à {destination}, sous les voûtes, devant une elfe en manteau blanc qui ne paraît pas "
			"surprise.",
			choix("fin", "Avancer.", "fin")),
		"refus_acces": noeud(
			"« La porte ne s'ouvre pas pour vous. » Hemi Taurua retire la main de la roue.",
			choix("fin", "(Prendre congé.)", "fin")),
		"refus_cristal": noeud(
			"« Alors vous restez. » Il ne le dit pas méchamment. « Le marché du Dôme en vend à ceux qui "
			"peuvent payer. Pas à tous les prix, et pas à tout le monde. »",
			choix("accueil", "Revenir.", "accueil"),
			choix("fin", "(Prendre congé.)", "fin")),
	})


def aubergiste():
	return pnj_doc(AUBERGISTE, "Moana Teriitahi", "nain",
		"Aubergiste du fare des Marées, à Mu-la-Centrale. Elle sert les invités de l'Institut, et ne "
		"cache pas qu'elle préférait le temps où il n'en venait pas.",
		PORTRAIT_AUBERGISTE, noeuds={
		"accueil": noeud(
			"La naine essuie un bol de pierre et le repose sans bruit. « Encore un de Notre-Dame. » Elle "
			"ne demande pas votre nom. « Une table, un lit, de l'eau douce. Le reste de la ville n'est pas "
			"pour les invités. »",
			choix("eau", "« De l'eau douce, sous la mer ? »", "eau"),
			choix("ville", "« Que peut-on voir, ici ? »", "ville"),
			choix("fin", "(Prendre congé.)", "fin")),
		"eau": noeud(
			"« Elle descend des conduites, comme tout ce qui coule à Mu. » Elle verse un gobelet et le pousse "
			"vers vous. « Vous, là-haut, vous la trouvez dans le ciel. Nous, nous la gardons. Ne la gaspillez "
			"pas. »",
			choix("accueil", "Revenir.", "accueil")),
		"ville": noeud(
			"« Le quai, le marché du Dôme, et la place devant le seuil. » Elle compte sur ses doigts, et "
			"s'arrête à trois. « Les jardins, les archives, les quartiers des Sages, c'est pour ceux d'ici, "
			"et pour ceux que les Sages invitent eux-mêmes. Ça arrive. Pas souvent. »",
			choix("accueil", "Revenir.", "accueil")),
	})


def marchande():
	"""Kahu Rehua : le marché restreint (`vente` à prix fixe), dont le cristal du retour."""
	articles = [
		{"item": CRISTAL, "cout_cuivre": PRIX_CRISTAL},
		{"item": "item:perles", "cout_cuivre": 180},
		{"item": "item:Nacre", "cout_cuivre": 54},
		{"item": "item:Corail", "cout_cuivre": 60},
		{"item": "item:Sel", "cout_cuivre": 3},
	]
	return pnj_doc(MARCHANDE, "Kahu Rehua", "hobbit",
		"Marchande du Dôme, à Mu-la-Centrale. Curieuse des gens d'en haut, qu'elle regarde comme des "
		"poissons d'une autre mer.",
		PORTRAIT_MARCHANDE,
		services={"vente": {"articles": articles,
							"noeuds": {"fait": "vendu", "sans_fonds": "sans_fonds", "trop_charge": "trop_charge"}}},
		noeuds={
		"accueil": noeud(
			"La hobbit lève la tête de ses paniers et vous détaille sans se cacher, de la tête aux bottes. "
			"« Des bottes ! Ça fait longtemps. » Elle sourit. « Je vends ce que la mer donne, et ce que "
			"l'Institut me permet de vendre aux invités. Ce n'est pas la même liste que pour ceux d'ici. »",
			choix("panier", "« Que vendez-vous ? »", "panier"),
			choix("coffret", "« Et dans le coffret ? »", "coffret"),
			choix("fin", "(Prendre congé.)", "fin")),
		"panier": noeud(
			"« Perles, nacre, corail mort, sel. Le corail mort, c'est pour les bijoutiers de chez vous : "
			"ici, il ne sert plus à rien. »",
			choix("perles", "Acheter une perle.",
				  action={"service": "vente", "op": "acheter", "item": "item:perles"}),
			choix("nacre", "Acheter de la nacre.", action={"service": "vente", "op": "acheter", "item": "item:Nacre"}),
			choix("corail", "Acheter du corail.", action={"service": "vente", "op": "acheter", "item": "item:Corail"}),
			choix("sel", "Acheter un sachet de sel.", action={"service": "vente", "op": "acheter", "item": "item:Sel"}),
			choix("accueil", "Revenir.", "accueil")),
		"coffret": noeud(
			"Elle pose la main sur le coffret sans l'ouvrir. « Des éclats de corail du seuil, morts et durcis. "
			"Chez vous, on dit cristal jaune. » Elle hausse les épaules. « Ici, on les vend à ceux qui veulent "
			"repartir. Cher, parce que la roue d'Hemi n'en prend pas d'autre, et parce que le Conseil n'aime "
			"pas qu'il en sorte trop. Un or l'éclat. »",
			choix("cristal", "Acheter un cristal de mana jaune.",
				  action={"service": "vente", "op": "acheter", "item": CRISTAL}),
			choix("accueil", "Revenir.", "accueil")),
		"vendu": noeud(
			"Elle emballe {objet} dans une feuille d'algue sèche et vous la tend. « {prix}. Merci, l'invité. »",
			choix("accueil", "Revenir.", "accueil"),
			choix("fin", "(Prendre congé.)", "fin")),
		"sans_fonds": noeud(
			"Elle compte ce que vous lui tendez, et vous le rend. « Pas assez. Les invités paient comme tout "
			"le monde. »",
			choix("accueil", "Revenir.", "accueil")),
		"trop_charge": noeud(
			"« Vous ne porterez pas ça en plus. » Elle repose {objet} dans son panier.",
			choix("accueil", "Revenir.", "accueil")),
	})


def pnj_neufs():
	return [aelis_voix(), aelis_mu(), templier_mu(), aubergiste(), marchande()]


# ---------------------------------------------------------------------------------------------
# Contrôles et écriture
# ---------------------------------------------------------------------------------------------

REQUIS = (AELIS_ARCHIVES, ARCHIVES, MAELYS, AENOR, ANCRAGE, MU, CRISTAL, LUTECIA,
		  "item:perles", "item:Nacre", "item:Corail", "item:Sel")


def generer(par_id):
	for requis in REQUIS:
		if requis not in par_id:
			sys.exit(f"ERREUR : {requis} absent du dump")
	cells = par_id[MU].get("cells") or []
	for nom, (x, y) in (("seuil", POS_SEUIL), ("auberge", POS_AUBERGE), ("marché", POS_MARCHE)):
		if not (0 <= y < len(cells) and 0 <= x < len(cells[y]) and cells[y][x] == 1):
			sys.exit(f"ERREUR : porte du {nom} ({x}, {y}) sur une case non praticable de Mu")
	relus = [aelis_archives(par_id[AELIS_ARCHIVES]), lieu_archives(par_id[ARCHIVES]),
			 maelys(par_id[MAELYS]), aenor(par_id[AENOR])]
	return relus + lieux_neufs() + pnj_neufs()


def main(argv):
	with open(V.dernier_dump(argv), encoding="utf-8") as f:
		dump = json.load(f)
	par_id = {d["_id"]: d for d in dump["docs"]}
	docs = generer(par_id)
	neufs = [d["_id"] for d in docs if d["_id"] not in par_id]
	print("Neufs :", ", ".join(neufs) or "aucun")
	fautes = V.controler(docs, par_id)
	if fautes:
		sys.exit("ERREUR :\n  " + "\n  ".join(fautes))
	docs = [d for d in docs if d["_id"] not in par_id or sans_rev(par_id[d["_id"]]) != d]
	if not docs:
		print("Rien à importer : le dump est à jour.")
		return
	with open(SORTIE, "w", encoding="utf-8", newline="\n") as f:
		f.write(json.dumps(docs, ensure_ascii=False, indent=2) + "\n")
	print(f"{len(docs)} docs → {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
	main(sys.argv)
