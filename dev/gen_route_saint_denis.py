#!/usr/bin/env python
# dev/gen_route_saint_denis.py
# La route de Saint-Denis — l'escorte du rang C, quatrième de la chaîne de Bouchard de
# Clignancourt (docs/lore/personnages/20261108_la_route_de_saint_denis.md, arbitrage de
# l'Auteur du 08/11 : les neuf recommandations retenues).
#
#   Montmartre : une fois « La route silencieuse » réussie, Bouchard (variante
#   `pnj:bouchard_de_clignancourt_saint_denis`) propose, au RANG C de Lutecia (`rang_min` de
#   l'offre), d'escorter trois voyageurs jusqu'au Relais de Saint-Denis → sur la carte de
#   France, le Chemin du Saint (visible pendant l'escorte seulement) : loups et corneilles ont
#   rabattu le convoi vers le vieux chemin → Perrine Lenoir (voix de la protégée, gardienne
#   du service `acces`) mène au coude → combat : le serpent de Marcel, UN être unique, les
#   protégés DANS la salle (Aubry Tanneguy se défend) → le Relais de Saint-Denis s'ouvre
#   (`combat_gagne` du coude, comme les Archives des Seuils après Jumièges) → dépose, Frère
#   Hilduin → le rapport à Bouchard, puis la réplique de Dame Geneviève.
#
# 100 % DONNÉE : escorte écrite ordinaire (`services.escorte.offre`), barrières `acces`,
# salle de donjon. Le DOUTE (Auteur) : trois voix contradictoires, jamais tranchées —
# Bouchard (elle était là avant la route), Frère Hilduin (la bête de Denis, mais c'est lui
# qui a écrit la légende), le faubourg par Geneviève (Marcel l'y a menée). Pourquoi les loups
# rabattent MAINTENANT reste sans réponse.
#
# Images D'ATTENTE (à remplacer quand les prompts du § 6 de la séance seront livrés) : le
# coude emprunte la carte et la grille de `lieu:chemin1`, le chemin et le relais des images
# du stock, le serpent l'image du serpent géant, Hilduin et Perrine des portraits de
# marchands. Constantes `IMAGE_*` / `PORTRAIT_*` ci-dessous.
#
# ⚠️ UN SEUL FICHIER À IMPORTER (CLAUDE.md §18) : jsons/route_saint_denis_a_importer.json —
# `lieu:montmartre` et `pnj:genevieve_du_sacre_coeur` RELUS du dernier dump (seules la
# présence des deux Bouchard et les choix/nœuds `saint_denis_*` de Geneviève changent :
# régénération idempotente) + les docs neufs, chacun COMPLET (l'import est un PUT, §11).
# La découpe de la carcasse du serpent est produite DANS CE FICHIER (`gen_carcasses_parties`).
# ⚠️ `gen_genres_especes.py` et `gen_jetons_especes.py` (tables exhaustives) citent déjà
# l'espèce neuve : ils échouent tant que l'import n'est pas fait et qu'un dump frais ne l'a
# pas relue.
#
# Usage : python dev/gen_route_saint_denis.py [jsons/telluris-dump-….json]

import copy
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gen_carcasses_parties as carcasses  # noqa: E402
from gen_genres_especes import accord_de  # noqa: E402
from gen_jetons_especes import TABLE as JETONS  # noqa: E402
from gen_loups_garous import _carcasse  # noqa: E402
from gen_vampires import _attrs  # noqa: E402

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSONS = os.path.join(RACINE, "jsons")
SORTIE = os.path.join(JSONS, "route_saint_denis_a_importer.json")

QUETE = "quete:escorte_montmartre_route_de_saint_denis"
QUETE_PRECEDENTE = "quete:escorte_montmartre_route_silencieuse"
CITE = "lieu:lutecia"
RANG = "C"
MONTMARTRE = "lieu:montmartre"
BOUCHARD_PRECEDENT = "pnj:bouchard_de_clignancourt_route_silencieuse"
BOUCHARD = "pnj:bouchard_de_clignancourt_saint_denis"
GENEVIEVE = "pnj:genevieve_du_sacre_coeur"
CHEMIN = "lieu:chemin_du_saint"
COUDE = "lieu:coude_du_chemin_du_saint"
DONJON = "donjon:chemin_du_saint"
RELAIS = "lieu:relais_de_saint_denis"
LIEN_CHEMIN = "link:france_to_chemin_du_saint"
LIEN_RELAIS = "link:france_to_relais_de_saint_denis"
PERRINE = "pnj:perrine_lenoir_chemin_du_saint"
HILDUIN = "pnj:frere_hilduin"
SLUG_SERPENT = "serpent_de_marcel"
SERPENT = "espece:" + SLUG_SERPENT

# Carte de France : Lutecia occupe (44,12)-(45,13). Saint-Denis est à deux lieues au nord,
# dans la même case que la capitale à cette échelle (≈ 0,2° par case) : le Chemin et le
# relais prennent les deux cases libres juste au nord de la porte nord-est.
POS_CHEMIN = [45, 11]
POS_RELAIS = [45, 10]

# Images d'attente (cf. en-tête).
GRILLE_EMPRUNTEE = "lieu:chemin1"
IMAGE_CHEMIN = "chemin_vers_les_collines_boisees01.png"
IMAGE_RELAIS = "auberge_europe05.jpg"
IMAGE_SERPENT = "serpent_geant_transparent.png"
PORTRAIT_BOUCHARD = "paladin_Bouchard_de_Clignancourt_nain_m.jpg"
IMAGE_BOUCHARD = "pnj_paladin_Bouchard_de_Clignancourt_nain_m_montmartre.jpg"
PORTRAIT_PERRINE = "marchand_dame_bertrade_atelier_cirier.png"
PORTRAIT_HILDUIN = "marchand_elfe_m_grand_scriptorium01.jpg"

# Barème des quêtes écrites (gen_recalage_primes.py) : C ≈ 3 000 cu.
RECOMPENSES = {"xp": 200, "cuivre": 3000}

# Trois états de chaque PNJ (Auteur, 15/10). La conjonction des deux `attendu: false` dit
# « jamais confiée » (une quête abandonnée ou ratée y retombe).
AVANT = {"quete_active": {"id": QUETE, "attendu": False}, "quete_reussie": {"id": QUETE, "attendu": False}}
EN_COURS = {"quete_active": {"id": QUETE}}
APRES = {"quete_reussie": {"id": QUETE}}
# Les barrières n'ont pas de filtre `id` : l'escorte se reconnaît à sa destination.
ESCORTE_EN_ROUTE = {"quete_active": {"types": ["escorte"], "cible": RELAIS}}
COUDE_GAGNE = {"combat_gagne": {"lieu": COUDE}}
COUDE_INTACT = {"combat_gagne": {"lieu": COUDE, "attendu": False}}

# ── Le serpent de Marcel ─────────────────────────────────────────────────────────────────
# Être unique, boss du rang C. Mesuré (`potentiel.rang_espece`, dump du 08/11) : 125,8 au
# grade de référence (combattant, niveau 2) → rang C (105–175) ; 158,7 au niveau 3. Le
# loup-garou du Morvan (rang E) vaut 99,1 au même grade.
SERPENT_SPEC = {
	"nom": "Serpent de Marcel",
	"description": "Serpent monstrueux des abords de Lutecia, gros comme un tronc de chêne et "
				   "long de plusieurs chariots, aux écailles vert-de-gris couvertes de lichen, et "
				   "dont on ne voit les quatre courtes pattes griffues qu'une fois qu'il se dresse. On "
				   "raconte dans les faubourgs qu'un vieil homme au bâton le fit sortir jadis de la "
				   "ville et le perdit de vue ; au Relais de Saint-Denis, on dit qu'il suivit un "
				   "paladin décapité jusqu'au coude du vieux chemin, et qu'il ne l'a jamais passé. "
				   "Les loups et les corneilles du pays vivent de ses restes.",
	"base_attributes": _attrs((5, 7), (65, 95), (65, 95), (25, 40), (50, 70), (20, 35), (0, 0), (35, 55)),
	"tags": ["monstre", "reptile", "legendaire", "boss"],
	"carcasse": ([600, 1500], "rare"),
}

# ── Bouchard : la quatrième escorte ──────────────────────────────────────────────────────

PROTEGES = [
	{"prenom": "Perrine", "nom": "Lenoir", "race": "humain", "sex": "F",
	 "description": "Marchande de cire et de chandelles pour le relais. Elle a déjà fait la route "
					"deux fois et a été rabattue deux fois. Elle refuse qu'on la plaigne.",
	 "inventaire": ["item:Cierge", "item:Cire_d_abeille"]},
	{"prenom": "Aubry", "nom": "Tanneguy", "race": "nain", "sex": "M",
	 "description": "Charretier. Il conduit le chariot et ne le quittera pour rien au monde, pas "
					"même quand il le faudrait.",
	 "se_defend": True,
	 "equipement": {"torse": "item:Cuirasse_cuir_brut", "main_droite": "item:Hachette"}},
	# Un novice n'a qu'un nom : en `nom`, prénom vide (`escorte.creer_protege` recopie le
	# prénom dans un nom vide, la carte afficherait « Ysoré Ysoré »).
	{"prenom": "", "nom": "Ysoré", "race": "elfe", "sex": "M",
	 "description": "Novice qui rejoint le relais. Il récite la marche de Denis à voix basse, et la "
					"récite de travers quand il a peur.",
	 "inventaire": ["item:Cierge"]},
]


def offre_bouchard() -> dict:
	return {
		"id": QUETE,
		"titre": "La route de Saint-Denis",
		"description": "Trois convois sont arrivés au Relais de Saint-Denis, au nord de Lutecia, "
					   "griffés, blessés, mais sans un mort : des bêtes les ont fait sortir de la "
					   "grande route, toujours au même coude. Escortez une marchande, un charretier "
					   "et un novice jusqu'au relais, et regardez où l'on vous emmène avant de "
					   "regarder qui vous pousse.",
		"destination": RELAIS,
		"proteges": copy.deepcopy(PROTEGES),
		"unique": True,
		"proba": 1,
		"rang_min": {"cite": CITE, "rang": RANG},
		"recompenses": dict(RECOMPENSES),
	}


def bouchard(precedent: dict) -> dict:
	"""La variante de Bouchard. Les scènes d'après « La route silencieuse » (rapport, suite,
	son passé, ses principes) sont RECOPIÉES du doc précédent relu au dump : la variante
	précédente disparaît de Montmartre dès que sa quête est réussie (présences du lieu), ses
	scènes vivent désormais ici, sous `quete_reussie` de la route silencieuse."""
	anciens = precedent["dialogue"]["noeuds"]
	rapport_rs = copy.deepcopy(anciens["route_rapport"])
	suite_rs = copy.deepcopy(anciens["route_suite"])
	for c in suite_rs["choix"]:
		c.pop("next", None)
		c["next"] = "accueil"
	passe = copy.deepcopy(anciens["passe"])
	principes = copy.deepcopy(anciens["principes"])
	rs_reussie = {"quete_reussie": {"id": QUETE_PRECEDENTE}}
	return {
		"_id": BOUCHARD,
		"type": "pnj",
		"nom": precedent.get("nom", "Bouchard de Clignancourt"),
		"race": precedent.get("race", "nain"),
		"vocation": precedent.get("vocation", "paladin"),
		"portrait": precedent.get("portrait", PORTRAIT_BOUCHARD),
		"description": "Paladin des routes, responsable des escortes terrestres au départ de "
					   "Montmartre. Il vous confie désormais les convois que les escortes "
					   "ordinaires ne savent plus mener.",
		"services": {"escorte": {"offre": offre_bouchard(), "noeuds": {"accepte": "saint_denis_accepte"}}},
		"dialogue": {
			"noeud_depart": "accueil",
			"noeuds": {
				"accueil": {
					"texte": "Bouchard a déroulé une carte sur le registre, sous l'auvent, et la tient "
							 "à plat de ses deux larges mains. Il lève les yeux en vous entendant. "
							 "« {prenom}. »",
					"choix": [
						{"id": "saint_denis_annonce", "label": "« Qu'est-ce que vous regardez ? »",
						 "condition": {"escorte_offerte": True}, "next": "saint_denis_annonce"},
						{"id": "saint_denis_annonce_rang", "label": "« Qu'est-ce que vous regardez ? »",
						 "condition": {"escorte_rang_insuffisant": True}, "next": "saint_denis_annonce"},
						{"id": "saint_denis_relance", "label": "« Au sujet de Saint-Denis… »",
						 "condition": {"escorte_en_cours": True}, "next": "saint_denis_relance"},
						{"id": "saint_denis_rapport", "label": "« Le coude du vieux chemin… »",
						 "condition": {"escorte_accomplie": True}, "next": "saint_denis_rapport"},
						{"id": "saint_denis_souvenir", "label": "« Des nouvelles du relais ? »",
						 "condition": {"escorte_accomplie": True}, "next": "saint_denis_souvenir"},
						{"id": "route_rapport", "label": "« Ceux que je vous ai ramenés de la route de Rhemi… »",
						 "condition": rs_reussie, "next": "route_rapport"},
						{"id": "preparation", "label": "« Pourquoi insistez-vous tant sur la préparation ? »",
						 "condition": rs_reussie, "next": "passe"},
						{"id": "principes", "label": "« Vos consignes, encore une fois ? »", "next": "principes"},
						{"id": "rien", "label": "« Je repasserai. »", "next": "fin"},
					],
				},
				"saint_denis_annonce": {
					"texte": "Il tapote trois croix au crayon, serrées au même endroit, juste au nord de "
							 "la capitale. « Trois convois pour le Relais de Saint-Denis. Tous arrivés. "
							 "Des chariots griffés, des blessés, et pas un mort. » Il retire ses mains, "
							 "la carte se roule toute seule. « Une bête qui attaque, elle tue ou elle "
							 "mange. Celles-là poussaient. Elles faisaient sortir les chariots de la "
							 "route, toujours au même coude. Je n'aime pas ce que je ne comprends pas. »",
					"choix": [
						{"id": "saint_denis_offre", "label": "« Qui faut-il conduire ? »",
						 "condition": {"escorte_offerte": True}, "next": "saint_denis_propose"},
						{"id": "saint_denis_rang", "label": "« Qui faut-il conduire ? »",
						 "condition": {"escorte_rang_insuffisant": True}, "next": "saint_denis_rang_insuffisant"},
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
					],
				},
				"saint_denis_propose": {
					"texte": "« Trois voyageurs : {protege}. Une marchande de cire qui a déjà été "
							 "rabattue deux fois et qui y retourne quand même, un charretier qui ne "
							 "lâchera pas son chariot, un novice pour le relais. » Il les désigne du "
							 "menton, sur le banc. « Les loups ferment la grande route au coude depuis "
							 "trois lunes. Vous passerez par où ils vous pousseront, il n'y a pas "
							 "d'autre chemin. Mais cette fois, quelqu'un regardera où ils mènent. »",
					"choix": [
						{"id": "loups", "label": "« Des loups qui ne tuent pas ? »", "next": "saint_denis_loups"},
						{"id": "instructions", "label": "« Où est ce coude ? »", "next": "saint_denis_instructions"},
						{"id": "refus", "label": "« Ce n'est pas pour moi. »", "next": "accueil"},
					],
				},
				"saint_denis_loups": {
					"texte": "« Des loups, et des corneilles au-dessus. » Il tire sur une de ses nattes. "
							 "« Les corneilles volent devant, les loups suivent. Les vieux chasseurs "
							 "disent que ça se fait, entre ces deux-là : l'une trouve, l'autre ouvre, "
							 "et chacune mange. » Il secoue la tête. « Ce que je ne sais pas, c'est "
							 "pour qui ils ouvrent la route, cette fois. »",
					"choix": [{"id": "instructions", "label": "« Où est ce coude ? »", "next": "saint_denis_instructions"}],
				},
				"saint_denis_instructions": {
					"texte": "« Sortez par la Porte Montmartre et prenez au nord. Deux lieues à peine. "
							 "Quand le vieux chemin quitte la grande route, vous le reconnaîtrez : des "
							 "ronces, un muret, et des corneilles sur toutes les bornes. » Il roule la "
							 "carte. « Amenez-les tous au relais, {destination}. {xp} points "
							 "d'expérience et {prime} pièces de cuivre. Et dites-moi ce qu'il y a au "
							 "bout du coude. »",
					"choix": [
						{"id": "accepter", "label": "« On part ce matin. »",
						 "action": {"service": "escorte", "op": "accepter"}},
						{"id": "refus", "label": "« Laissez-moi me préparer. »", "next": "accueil"},
					],
				},
				"saint_denis_accepte": {
					"texte": "Le greffier inscrit votre nom au bas de la ligne. Le charretier nain monte "
							 "sur son siège sans un mot ; la marchande vérifie ses caisses de cire, "
							 "deux fois ; le jeune elfe serre son cierge contre lui. Bouchard vient "
							 "jusqu'au chariot. « Ne les laissez pas s'éparpiller quand les loups "
							 "viendront. Une bête qui rabat cherche toujours celui qui s'écarte. »",
					"choix": [{"id": "ok", "label": "« Je les ramènerai au relais. »", "next": "fin"}],
				},
				"saint_denis_rang_insuffisant": {
					"texte": "Il secoue la tête, sans dureté. « Pas encore. Ce qui attend au bout de ce "
							 "coude, je ne le connais pas, et je n'y envoie que quelqu'un dont la Guilde "
							 "répond au rang {rang_requis}. Revenez quand le Grand Relais vous l'aura "
							 "accordé. Les convois attendront. Ils ont l'habitude. »",
					"choix": [
						{"id": "retour", "label": "« J'y travaillerai. »", "next": "accueil"},
						{"id": "fin", "label": "« Je reviendrai. »", "next": "fin"},
					],
				},
				"saint_denis_relance": {
					"texte": "Il ne lève pas les yeux de la carte. « {protege}. Encore ici ? » Il pose le "
							 "doigt sur les trois croix. « Le relais attend sa cire, et les loups, eux, "
							 "n'attendent personne. Allez, {prenom}. »",
					"choix": [{"id": "ok", "label": "« J'y retourne. »", "next": "fin"}],
				},
				"saint_denis_rapport": {
					"texte": "Bouchard écoute jusqu'au bout : les corneilles sur les bornes, les loups sur "
							 "les flancs, le vieux chemin sous les ronces, et ce qui attendait au coude. "
							 "Il ne vous interrompt qu'une fois, pour demander si les loups sont entrés "
							 "dans le combat. Vous lui dites que non, qu'ils sont restés à la lisière. "
							 "Il hoche la tête. « Pas un donjon à deux lieues. J'ai fait demander à "
							 "l'Enclos du Temple : les Templiers n'ont rien. » Il replie la carte. « Elle "
							 "était là avant la route. Avant le relais, peut-être avant les murs. On a "
							 "fait un coude pour l'éviter, puis on a oublié pourquoi, et un jour "
							 "quelqu'un a coupé au plus court. »",
					"choix": [
						{"id": "pourquoi", "label": "« Et pourquoi maintenant ? »", "next": "saint_denis_pourquoi"},
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
					],
				},
				"saint_denis_pourquoi": {
					"texte": "« Les loups ? » Il hausse les épaules. « Je n'en sais rien. Une bête vieillit, "
							 "elle a faim, elle a moins faim. Un hiver dure trop. Ou quelque chose que "
							 "nous ne voyons pas d'ici. » Il range la carte dans le registre. « Je ne "
							 "demande pas aux routes de m'expliquer pourquoi elles tuent. Je demande "
							 "qu'on ramène les gens. Vous les avez ramenés. »",
					"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}],
				},
				"saint_denis_souvenir": {
					"texte": "« Le relais a eu sa cire. » Bouchard a presque un sourire dans la barbe. "
							 "« Et le frère portier m'a écrit une lettre de trois pages pour me "
							 "raconter que c'était la bête de Denis. Il écrit beaucoup, ce frère. » Il "
							 "range la lettre sous le registre. « Moi, je dis qu'une route qui fait un "
							 "coude a toujours une raison. On la retrouve rarement. »",
					"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}],
				},
				"route_rapport": rapport_rs,
				"route_suite": suite_rs,
				"passe": passe,
				"principes": principes,
			},
		},
	}


# ── Montmartre : la variante précédente cède la place ────────────────────────────────────

def montmartre(doc: dict) -> dict:
	doc = copy.deepcopy(doc)
	doc.pop("_rev", None)
	entrees = doc.setdefault("pnj", [])
	precedent = next((e for e in entrees if e.get("character") == BOUCHARD_PRECEDENT), None)
	if precedent is None:
		sys.exit(f"ERREUR : {BOUCHARD_PRECEDENT} absent des PNJ de {MONTMARTRE}")
	cachee = {"quete_reussie": {"id": QUETE_PRECEDENTE, "attendu": False}}
	conds = precedent.setdefault("conditions", [])
	if cachee not in conds:
		conds.append(cachee)
	nouvelle = {
		"character": BOUCHARD,
		"nom": precedent.get("nom", "Bouchard de Clignancourt"),
		"portrait": precedent.get("portrait", PORTRAIT_BOUCHARD),
		"image": precedent.get("image", IMAGE_BOUCHARD),
		"probabilite": 1,
		"description": "Le paladin nain, sous l'auvent, une carte de la route du nord tenue à plat "
					   "de ses deux mains.",
		"conditions": [{"quete_reussie": {"id": QUETE_PRECEDENTE}}],
	}
	idx = next((i for i, e in enumerate(entrees) if e.get("character") == BOUCHARD), None)
	if idx is None:
		entrees.insert(entrees.index(precedent) + 1, nouvelle)
	else:
		entrees[idx] = nouvelle
	return doc


# ── Dame Geneviève : la route vue du ciel ────────────────────────────────────────────────

CHOIX_GENEVIEVE = [
	{"id": "saint_denis_pendant", "label": "« On m'envoie au Relais de Saint-Denis. »",
	 "condition": EN_COURS, "next": "saint_denis_pendant"},
	{"id": "saint_denis_apres", "label": "« Le Chemin du Saint… »",
	 "condition": APRES, "next": "saint_denis_apres"},
]

NOEUDS_GENEVIEVE = {
	"saint_denis_pendant": {
		"texte": "Elle ne quitte pas le ciel des yeux. « Au nord. » Elle tend le bras, sans hâte, vers "
				 "un point au-delà des toits des faubourgs. « Regardez là. Des corneilles qui tournent "
				 "toujours au même endroit, depuis trois lunes. D'ici, on dirait qu'elles attendent "
				 "quelque chose. » Elle baisse le bras. « Un griffon, je saurais quoi en faire. Ça, je "
				 "ne sais pas. »",
		"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}],
	},
	"saint_denis_apres": {
		"texte": "Elle ne quitte pas le ciel des yeux. « D'ici, le Chemin du Saint dessine un coude "
				 "autour de rien. Je le regarde depuis des années. » Un silence. « Les vieux du "
				 "faubourg disent qu'on l'a emmenée là. Marcel, avec son bâton. Le frère portier de "
				 "Saint-Denis dit qu'elle s'est arrêtée derrière Denis. » Elle hausse les épaules. "
				 "« Moi, je dis qu'une bête ne s'arrête pas pour un mort. Les corneilles sont parties, "
				 "en tout cas. »",
		"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}],
	},
}


def poser_choix(noeud: dict, choix: list):
	"""Insère les choix juste AVANT le dernier choix du nœud (la sortie). Idempotent."""
	liste = noeud.setdefault("choix", [])
	for c in choix:
		idx = next((i for i, x in enumerate(liste) if x.get("id") == c["id"]), None)
		if idx is not None:
			liste[idx] = copy.deepcopy(c)
		else:
			liste.insert(max(0, len(liste) - 1), copy.deepcopy(c))


def genevieve(doc: dict) -> dict:
	doc = copy.deepcopy(doc)
	doc.pop("_rev", None)
	noeuds = doc["dialogue"]["noeuds"]
	poser_choix(noeuds[doc["dialogue"]["noeud_depart"]], CHOIX_GENEVIEVE)
	noeuds.update(copy.deepcopy(NOEUDS_GENEVIEVE))
	return doc


# ── Le Chemin du Saint et sa gardienne (la voix de Perrine) ──────────────────────────────

def perrine() -> dict:
	return {
		"_id": PERRINE,
		"type": "pnj",
		"nom": "Perrine Lenoir",
		"race": "humain",
		"vocation": "marchand",
		"portrait": PORTRAIT_PERRINE,
		"description": "Perrine Lenoir, marchande de cire, debout sur le chariot pour voir par-dessus les ronces.",
		"services": {"acces": {"lieu": COUDE, "noeuds": {"ouvre": "coude_ouvert", "refus": "coude_vide"}}},
		"dialogue": {
			"noeud_depart": "accueil",
			"noeuds": {
				"accueil": {
					"texte": "La marchande s'est hissée debout sur le chariot, une main sur une caisse de "
							 "cire, et regarde le vieux chemin par-dessus les ronces. Derrière vous, "
							 "sur le talus de la grande route, des loups sont assis et ne bougent plus. "
							 "« Voilà. Ils s'arrêtent toujours là. »",
					"choix": [
						{"id": "ici", "label": "« C'est ici qu'ils vous ont poussés ? »",
						 "condition": {"acces_ouvrable": True}, "next": "ici"},
						{"id": "libre", "label": "« Le coude est libre. »",
						 "condition": {"acces_libere": True}, "next": "libre"},
						{"id": "fin", "label": "(Rester sur le chemin.)", "next": "fin"},
					],
				},
				"ici": {
					"texte": "« Deux fois. Les deux fois, ils nous ont laissés là, et les deux fois on a "
							 "suivi le chemin, parce qu'on ne pouvait pas faire autrement. » Elle descend "
							 "du chariot. « Après le muret, il fait un coude. Au coude, la première fois, "
							 "j'ai senti l'odeur. La deuxième, j'ai vu bouger le lierre. On a fouetté "
							 "les bêtes et on est passés. Le convoi d'après, il a laissé un homme dans "
							 "les ronces, à ce qu'on m'a dit. Il est revenu, mais il ne parle plus. »",
					"choix": [
						{"id": "avancer", "label": "« Restez derrière moi. »", "next": "seuil"},
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
					],
				},
				"seuil": {
					"texte": "Vous passez le muret de pierres sèches. Le chemin s'enfonce sous les ronces "
							 "et le lierre, les ornières pleines d'eau verte. Les corneilles se sont "
							 "toutes posées sur les branches, d'un coup, et se taisent. Le jeune novice "
							 "a commencé à réciter quelque chose, et s'est trompé deux fois. Le coude "
							 "est devant vous.",
					"choix": [
						{"id": "entrer", "label": "Avancer jusqu'au coude.", "condition": {"acces_ouvrable": True},
						 "action": {"service": "acces", "op": "passer"}},
						{"id": "attendre", "label": "« Pas encore. »", "next": "accueil"},
					],
				},
				"coude_ouvert": {
					"texte": "Ce que vous preniez pour un talus couvert de lierre se soulève. Une tête plate "
							 "et grise, large comme une porte de grange, se tourne lentement vers le "
							 "chariot ; le corps derrière elle n'en finit pas de se dérouler hors des "
							 "ronces. Aubry a déjà la hachette à la main. Perrine ne crie pas.",
					"choix": [{"id": "ok", "label": "Tirer votre arme.", "next": "fin"}],
				},
				"coude_vide": {
					"texte": "Le coude est vide. Le lierre est arraché sur toute sa longueur, et les "
							 "corneilles sont parties.",
					"choix": [{"id": "ok", "label": "Reculer.", "next": "fin"}],
				},
				"libre": {
					"texte": "Perrine regarde longtemps le lierre arraché. « Deux fois, je suis passée à "
							 "côté de ça. » Elle remonte sur le chariot. « Le relais est juste derrière "
							 "la colline. On voit déjà la basilique. »",
					"choix": [{"id": "fin", "label": "« Allons-y. »", "next": "fin"}],
				},
			},
		},
	}


# ── Le Relais de Saint-Denis et Frère Hilduin ────────────────────────────────────────────

def hilduin() -> dict:
	return {
		"_id": HILDUIN,
		"type": "pnj",
		"nom": "Frère Hilduin",
		"race": "elfe",
		"vocation": "lettre",
		"portrait": PORTRAIT_HILDUIN,
		"description": "Frère Hilduin, frère portier du Relais de Saint-Denis, un très vieil elfe à la peau de parchemin.",
		"dialogue": {
			"noeud_depart": "accueil",
			"noeuds": {
				"accueil": {
					"texte": "Sous le porche du relais, un elfe si vieux que sa peau semble de parchemin "
							 "tient le registre des arrivées, une plume à la main. « Soyez le "
							 "bienvenu au Relais de Saint-Denis. La soupe est chaude, et la porte "
							 "ferme à la nuit. »",
					"choix": [
						{"id": "bonjour", "label": "« Merci, mon frère. »", "condition": AVANT, "next": "bonjour"},
						{"id": "convoi", "label": "« Je vous amène le convoi de Montmartre. »",
						 "condition": EN_COURS, "next": "convoi"},
						{"id": "apres", "label": "« Le coude du vieux chemin est libre. »",
						 "condition": APRES, "next": "apres"},
						{"id": "denis", "label": "« Qui était Denis ? »", "next": "denis"},
						{"id": "fin", "label": "(Le laisser à son registre.)", "next": "fin"},
					],
				},
				"bonjour": {
					"texte": "Il incline la tête et revient à son registre. « Que la route vous soit "
							 "légère. »",
					"choix": [{"id": "fin", "label": "(Entrer.)", "next": "fin"}],
				},
				"convoi": {
					"texte": "Le frère portier pose sa plume. « Vous êtes passés par le Chemin du Saint. » "
							 "Ce n'est pas une question. Il vous mène jusqu'à une dalle usée, au pied "
							 "de la basilique, et la touche du bout de sa sandale. « Il est tombé ici, "
							 "sa tête entre les mains. La bête qui le suivait s'est arrêtée au coude, "
							 "et elle n'a jamais passé ce point. C'est pour cela qu'on a bâti le relais "
							 "ici, et pas ailleurs. Pour que la route ne l'oublie pas. »",
					"choix": [
						{"id": "vrai", "label": "« Vous en êtes sûr ? »", "next": "vrai"},
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
					],
				},
				"vrai": {
					"texte": "Il sourit à peine. « C'est moi qui ai écrit sa Vie, pour les novices. Il y a "
							 "bien longtemps. J'y ai mis ce qu'on m'a raconté, et ce que les vieux "
							 "frères avaient écrit avant moi, qui l'avaient entendu raconter aussi. » "
							 "Il revient vers son registre. « Je ne jurerais pas que tout est vrai. "
							 "Mais la bête, elle, ne passe pas le coude. Ça, je l'ai vu. »",
					"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}],
				},
				"apres": {
					"texte": "Le frère portier écrit longtemps avant de répondre. « Alors elle ne passera "
							 "plus le coude. » Il lève sa plume. « Ou bien elle n'a jamais voulu le "
							 "passer, et c'est nous qui avons vu un miracle dans une bête qui avait "
							 "son territoire, comme un loup a le sien. » Il trempe la plume dans "
							 "l'encre. « J'écrirai les deux. Les novices choisiront. »",
					"choix": [{"id": "fin", "label": "(Le laisser écrire.)", "next": "fin"}],
				},
				"denis": {
					"texte": "« Un paladin de la Butte, du temps où il n'y avait pas encore de portes "
							 "entre les cités, seulement des murs et des routes. » Il parle comme on "
							 "récite. « Une bête l'a décapité sur la Butte, là où l'on veille "
							 "aujourd'hui sur le ciel de Lutecia. Il s'est relevé, il a pris sa tête "
							 "dans ses mains, et il a marché vers le nord. La bête l'a suivi sans "
							 "jamais le rattraper. » Il hausse ses épaules étroites. « Dans les "
							 "faubourgs, ils racontent une autre histoire : un vieil homme au bâton, "
							 "un Marcel, qui aurait emmené un serpent hors de la ville. Les deux "
							 "histoires ne peuvent pas être vraies. Ou alors il y a deux bêtes. »",
					"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}],
				},
			},
		},
	}


def docs_neufs(base: dict) -> list:
	grille = base[GRILLE_EMPRUNTEE]
	coude = {
		"_id": COUDE,
		"type": "lieu",
		"label": "Le coude du Chemin du Saint",
		"image": grille["image"],
		"categorie": "battle_map",
		"dimensions": copy.deepcopy(grille["dimensions"]),
		"cells": copy.deepcopy(grille["cells"]),
		"nav": copy.deepcopy(grille.get("nav") or {}),
		"tags": ["chemin", "foret", "bois", "ruines", "donjon"],
		"acces": {
			"gardien": PERRINE,
			"refus": "Le coude est vide. Le lierre est arraché sur toute sa longueur.",
			"cycle": 1,
			"conditions": [copy.deepcopy(ESCORTE_EN_ROUTE), copy.deepcopy(COUDE_INTACT)],
		},
	}
	return [
		bouchard(base[BOUCHARD_PRECEDENT]),
		{
			"_id": CHEMIN,
			"type": "lieu",
			"label": "Le Chemin du Saint",
			"image": IMAGE_CHEMIN,
			"categorie": "chemin",
			"lieu_parent": "lieu:france",
			"texte": "La grande route du nord fait un coude ; un vieux chemin s'en détache tout droit, "
					 "sous les ronces et le lierre, entre deux murets de pierres sèches. Des "
					 "corneilles sont posées sur chaque borne. Sur les talus, derrière vous, des loups "
					 "sont assis et vous regardent passer.",
			"pnj": [{
				"character": PERRINE, "nom": "Perrine", "portrait": PORTRAIT_PERRINE, "probabilite": 1,
				"description": "Perrine Lenoir, debout sur le chariot, qui regarde le vieux chemin.",
				"conditions": [copy.deepcopy(ESCORTE_EN_ROUTE)],
			}],
			"acces": {
				"refus": "La route du nord file vers Saint-Denis ; un vieux chemin s'en écarte sous les ronces.",
				"cycle": 1,
				"conditions": [copy.deepcopy(ESCORTE_EN_ROUTE)],
			},
		},
		{
			"_id": LIEN_CHEMIN,
			"type": "connection",
			"nodes": [
				{"lieu": "lieu:france", "pos": list(POS_CHEMIN), "label": "Reprendre la route"},
				{"lieu": CHEMIN, "pos": [0, 0], "label": "Des loups sur les talus"},
			],
			"metadata": {"type": "chemin", "status": "ouvert"},
		},
		perrine(),
		coude,
		{
			"_id": DONJON,
			"type": "donjon",
			"nom": "Le coude du Chemin du Saint",
			"description": "Au nord de Lutecia, là où le vieux chemin de Saint-Denis fait un coude sous "
						   "les ronces, une bête plus vieille que la route. Les loups et les corneilles "
						   "lui rabattent les convois.",
			"portail": CHEMIN,
			# Un être unique, rang C : niveaux 2-3 (combattant → vétéran), cf. SERPENT_SPEC.
			"niveau_min": 2,
			"niveau_max": 3,
			"battle_maps": [{
				"lieu": COUDE,
				"especes": [SERPENT],
				"nb_monstres": 1,
				"niveau_min": 2,
				"niveau_max": 3,
			}],
		},
		{
			"_id": RELAIS,
			"type": "lieu",
			"label": "Le Relais de Saint-Denis",
			"image": IMAGE_RELAIS,
			"categorie": "chemin",
			"lieu_parent": "lieu:france",
			"texte": "Un monastère-relais fortifié, au pied d'une haute basilique de pierre claire : "
					 "une cour, une écurie, un réfectoire où la soupe est toujours chaude, et une "
					 "porte qu'on ferme à la nuit. Au pied de la basilique, une dalle usée que les "
					 "voyageurs évitent de piétiner.",
			"pnj": [{
				"character": HILDUIN, "nom": "Frère Hilduin", "portrait": PORTRAIT_HILDUIN, "probabilite": 1,
				"description": "Le frère portier, sous le porche, son registre ouvert.",
			}],
			"acces": {
				"refus": "Loups sur les talus, corneilles sur les bornes : la grande route du nord est fermée.",
				"cycle": 1,
				"conditions": [copy.deepcopy(COUDE_GAGNE)],
			},
		},
		{
			"_id": LIEN_RELAIS,
			"type": "connection",
			"nodes": [
				{"lieu": "lieu:france", "pos": list(POS_RELAIS), "label": "Reprendre la route"},
				{"lieu": RELAIS, "pos": [0, 0], "label": "Le Relais de Saint-Denis"},
			],
			"metadata": {"type": "chemin", "status": "ouvert"},
		},
		hilduin(),
	]


def docs_serpent(base: dict) -> list:
	"""L'espèce, sa carcasse et la découpe de la carcasse (même cœur que gen_dragons_serpents)."""
	accord = accord_de(SLUG_SERPENT)
	espece = {"_id": SERPENT, "type": "espece", "nom": SERPENT_SPEC["nom"], "genre": accord["genre"],
			  **{k: True for k in ("nom_propre", "pluriel", "h_aspire") if accord.get(k)}}
	taille, forme = JETONS[SLUG_SERPENT]
	espece.update({
		"jeton": {"taille": taille, "forme": forme},
		"image": IMAGE_SERPENT,
		"description": SERPENT_SPEC["description"],
		"base_attributes": copy.deepcopy(SERPENT_SPEC["base_attributes"]),
		"tags": list(SERPENT_SPEC["tags"]),
		"proprietes": {},
		"animation": "animation:son_bete_12",
	})
	carc = _carcasse(SERPENT, SERPENT_SPEC["nom"], *SERPENT_SPEC["carcasse"])
	carcasses.controler_profils()
	vue = {**base, SERPENT: espece, carc["_id"]: carc}
	sortie, _resume, _ign, _orph, _inch = carcasses.generer(list(vue.values()), [SLUG_SERPENT])
	par_id = {d["_id"]: d for d in sortie}
	carc = par_id.pop(carc["_id"], carc)  # enrichie de `decoupe`
	return [espece, carc] + sorted(par_id.values(), key=lambda d: d["_id"])


def charger(chemin):
	with open(chemin, encoding="utf-8") as f:
		return json.load(f)


def dernier_dump(argv):
	if len(argv) > 1:
		return argv[1]
	dumps = sorted(glob.glob(os.path.join(JSONS, "telluris-dump-*.json")))
	if not dumps:
		sys.exit("Aucun dump jsons/telluris-dump-*.json")
	return dumps[-1]


def generer(base: dict) -> list:
	for requis in (MONTMARTRE, BOUCHARD_PRECEDENT, GENEVIEVE, GRILLE_EMPRUNTEE, "lieu:france", CITE,
				   "item:Cierge", "item:Cire_d_abeille", "item:Cuirasse_cuir_brut", "item:Hachette"):
		if requis not in base:
			sys.exit(f"ERREUR : {requis} absent du dump")
	if SLUG_SERPENT not in JETONS:
		sys.exit(f"ERREUR : {SERPENT} absente de gen_jetons_especes.TABLE")
	return [montmartre(base[MONTMARTRE]), genevieve(base[GENEVIEVE])] + docs_neufs(base) + docs_serpent(base)


def main(argv):
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	source = dernier_dump(argv)
	base = {d["_id"]: d for d in charger(source)["docs"]}
	docs = generer(base)
	ids = [d["_id"] for d in docs]
	if len(ids) != len(set(ids)):
		sys.exit("ERREUR : _id en double dans la sortie")
	relus = {MONTMARTRE, GENEVIEVE}
	collisions = [i for i in ids if i in base and i not in relus]
	if collisions:
		print("⚠️ ids neufs déjà présents au dump (écrasés par l'import) :", ", ".join(collisions))
	with open(SORTIE, "w", encoding="utf-8", newline="\n") as f:
		f.write(json.dumps(docs, ensure_ascii=False, indent=2) + "\n")
	print(f"relu {os.path.relpath(source, RACINE)}")
	print(f"{len(docs)} docs → {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
	main(sys.argv)
