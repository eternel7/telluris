#!/usr/bin/env python
"""Rayon / Lance de lumière — la défense anti-aérienne des cités, et ses quatre maîtres."""
# dev/gen_lumiere_paladine.py
#
# Deux sorts Saints de niveau 10, en LIGNE (rectangle 1×20 ancré sur le lanceur) qui PERCE les
# murs (`zone.perce`) et touche AUSSI les alliés (`zone.tir_ami`, seul tir ami au lancement) :
#   • Rayon de lumière — forme simple : grimoire unique + recette de scriptorium ;
#   • Lance de lumière — forme paladine (lore : 04_institutions.md, perfectionnée à Montmartre) :
#     `enseignement` (aucun grimoire, refusée par /api/apprendre_sort) et `ameliore` (exige le
#     Rayon et le REMPLACE). Seul un MAÎTRE la transmet (service PNJ `enseignement`), après une
#     épreuve (service `apport` : rapporter des trophées de volants abattus).
#
# Calibrage (Dragon Empereur : 380 à 560 PV, sorts sans armure) : Lance 50+5D10 (55-100) ⇒ dix
# lances tuent un Empereur au plus fort ; la part variable double la base au jet maximal.
#
# Quatre maîtres, un par cité de défense aérienne : Lutecia–Montmartre (le Sacré-Cœur), Bruges
# (le Beffroi), Aix-la-Chapelle (le Granusturm), Reykjavik (Hallgrímskirkja). Ni Beffroi, ni
# Granusturm, ni Hallgrímskirkja n'ont de lieu propre en base : le maître se tient dans le lieu
# de la CITÉ, et son texte dit d'où il descend.
#
# IDEMPOTENT : un doc déjà en base à l'identique n'est pas réémis ; un `_id` pris par un doc
# différent fait REFUSER tout le lot (l'import est un PUT complet). Les docs de LIEU sont relus
# dans le dump et ne gagnent que l'entrée `pnj` du maître (fusion, CLAUDE.md § 11).
#
# Usage : python dev/gen_lumiere_paladine.py [--dump chemin] [--sortie chemin]
# Sortie : jsons/lumiere_paladine_a_importer.json (📥 Importer depuis /admin)

import argparse
import copy
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
DOSSIER_JSONS = os.path.join(RACINE, "jsons")
SORTIE = os.path.join(DOSSIER_JSONS, "lumiere_paladine_a_importer.json")

from utils import grimoires  # noqa: E402

RAYON_ID = "sort:rayon_de_lumiere"
LANCE_ID = "sort:lance_de_lumiere"

# Ligne droite : part de la case VOISINE du lanceur (decalage 1, il n'est jamais touché),
# traverse la cible et continue jusqu'à 20 cases. Axe arrondi au huitième de tour.
ZONE_RAYON = {"forme": "rectangle", "origine": "lanceur", "orientation": "cible",
			  "longueur": 20, "largeur": 1, "decalage": 1, "perce": True, "tir_ami": True}

SORTS = [
	{
		"_id": RAYON_ID,
		"type": "sort",
		"nom": "Rayon de lumière",
		"icon": "🔆",
		"description": "Un trait de lumière droit comme une corde tendue. Il traverse ce qu'il "
					   "touche, la pierre comme la chair, et ne fait aucune différence entre "
					   "l'ennemi et l'allié qui se tient sur sa ligne. On l'enseigne dans les "
					   "livres ; les paladins des tours de guet savent qu'il n'en est que l'ébauche.",
		"magie": "Sainte",
		"niveau": 10,
		"cout_pm": 55,
		"incantation": 3,
		"cible": "ennemi",
		"jet": "magique",
		"portee": 20,
		"effets": {"degats": "25+3D8"},
		# Catalyseur AVANT le consommé (ordre de la base) ; le catalyseur pèse moins.
		"composants": [
			{"item": "item:relique", "consomme": False, "bonus": {"degats": "3"}},
			{"item": "item:Eau_benite", "consomme": True, "bonus": {"degats": "2D6"}},
		],
		"animation": "animation:capa_lumiere",
		"animation_zone": "animation:capa_lumiere_zone",
		"zone": dict(ZONE_RAYON),
	},
	{
		"_id": LANCE_ID,
		"type": "sort",
		"nom": "Lance de lumière",
		"icon": "☀️",
		"description": "Le Rayon tel que les paladins le portent sur les terrasses de guet : un "
					   "trait à la vitesse de la lumière, qui perce tout ce qu'il rencontre "
					   "jusqu'au bout de sa course. Il faut savoir où il finira avant de le lancer. "
					   "Aucun livre ne l'enseigne : un maître le transmet, à qui a fait ses preuves "
					   "contre le ciel.",
		"magie": "Sainte",
		"niveau": 10,
		"cout_pm": 80,
		# 6 PA sous Vol 40, 5 à Vol 40, 4 à Vol 80 : la maîtrise raccourcit la Lance.
		"incantation": "6-{Vol/40}",
		"cible": "ennemi",
		"jet": "magique",
		"portee": 20,
		"effets": {"degats": "50+5D10"},
		"composants": [
			{"item": "item:relique", "consomme": False, "bonus": {"degats": "5"}},
			{"item": "item:Eau_benite", "consomme": True, "bonus": {"degats": "3D8"}},
		],
		"animation": "animation:capa_lumiere",
		"animation_zone": "animation:capa_lumiere_zone",
		"zone": dict(ZONE_RAYON),
		"enseignement": True,
		"ameliore": RAYON_ID,
	},
]


# ── Les maîtres ───────────────────────────────────────────────────────────────────
# Une ligne par maître : identité, lieu, épreuve (trophée de volant abattu près de SA cité),
# et les textes propres. Le squelette du dialogue est commun (`_dialogue`).

MAITRES = [
	{
		"slug": "genevieve_du_sacre_coeur",
		"lieu": "lieu:montmartre",
		"nom": "Dame Geneviève",
		"race": "humain",
		"portrait": "race_paladin_f_humain01.jpg",
		"presence": "Une paladine aux cheveux gris coupés court, descendue des terrasses de la "
					"basilique, qui regarde le ciel plus souvent que les convois.",
		"description": "Maîtresse de guet du Sacré-Cœur. Les vieux de Lutecia disent qu'une "
					   "Geneviève a déjà gardé la ville quand tout le monde fuyait ; elle répond "
					   "que c'était une autre, et qu'on raconte n'importe quoi.",
		"epreuve": {
			"id": "quete:epreuve_lance_montmartre",
			"titre": "Les griffons de la Butte",
			"item": "item:griffon_tete", "quantite": 3,
			"description": "Des griffons sauvages chassent au-dessus des faubourgs nord de "
						   "Lutecia. Dame Geneviève veut trois têtes de griffon, rapportées à "
						   "Montmartre, avant de vous parler de la Lance.",
			"recompenses": {"xp": 300, "cuivre": 2500},
		},
		"accueil": "Dame Geneviève ne quitte pas des yeux le ciel au-dessus des toits. « Les "
				   "convois, c'est en bas. Ici, on regarde en l'air. »",
		"lance": "« La Lance ? C'est le Rayon, en vrai. Le livre vous apprend à tirer. Ici, on "
				 "apprend à tirer sans toucher les toits de Lutecia, ni le paladin qui se tient "
				 "devant vous. »",
		"lance_suite": "« Seule, elle n'abat pas un grand dragon. Dix paladins sur dix terrasses, "
					   "l'un après l'autre, oui. C'est pour ça que je ne l'apprends pas à n'importe "
					   "qui. »",
		"propose": "« Les griffons chassent sur les faubourgs du nord. Rapportez-m'en trois "
				   "têtes. Je verrai comment vous visez. »",
	},
	{
		"slug": "soeur_marguerite_du_beffroi",
		"lieu": "lieu:bruges",
		"nom": "Sœur Marguerite",
		"race": "elfe",
		"portrait": "paladin_elfe_f01.jpg",
		"presence": "Une sœur de Bataille du Béguinage, en manteau gris, descendue du Beffroi. "
					"Elle compte les coups de cloche sans y penser.",
		"description": "Sœur de Bataille du Béguinage de Bruges, maîtresse de tir du Beffroi. "
					   "Elle a été sœur du Calvaire avant de passer à l'autre ordre, et soigne "
					   "encore ceux qu'elle a dû toucher avec le reste.",
		"epreuve": {
			"id": "quete:epreuve_lance_bruges",
			"titre": "Les wyvernes du Zwin",
			"item": "item:wyvern_tete", "quantite": 2,
			"description": "Des wyvernes suivent les navires qui remontent le Zwin jusqu'aux "
						   "canaux de Bruges. Sœur Marguerite attend deux têtes de wyverne "
						   "avant de vous enseigner la Lance.",
			"recompenses": {"xp": 300, "cuivre": 2500},
		},
		"accueil": "Au-dessus de la place, les cloches du Beffroi sonnent l'heure. Sœur "
				   "Marguerite lève les yeux, compte, puis revient à vous. « Ce n'était que "
				   "l'heure. »",
		"lance": "« Au Beffroi, on sonne d'abord, on tire ensuite. La Lance part du haut de la "
				 "tour, au-dessus des toits et des mâts. En bas, elle traverserait le marché. »",
		"lance_suite": "« Elle ne choisit pas ce qu'elle touche. Celui qui la lance, si. Je "
					   "l'apprends à ceux qui savent se retenir. »",
		"propose": "« Les wyvernes suivent les navires du Zwin. Rapportez-moi deux têtes. »",
	},
	{
		"slug": "turpin_du_granusturm",
		"lieu": "lieu:aix_la_chapelle",
		"nom": "Turpin",
		"race": "ogre",
		"portrait": "paladin_ogre_m_rhemi01.png",
		"presence": "Un paladin ogre d'un âge indéfinissable, descendu du Granusturm, le "
					"manteau rapiécé aux épaules.",
		"description": "Maître de guet du Granusturm. Il se dit l'un des pairs de la cour de "
					   "Charlemagne ; les chroniqueurs d'Aix ne sont pas d'accord entre eux sur "
					   "le nombre de Turpin qu'il y a eu.",
		"epreuve": {
			"id": "quete:epreuve_lance_aix",
			"titre": "Les gargouilles du double rempart",
			"item": "item:gargouille_tete", "quantite": 3,
			"description": "Des gargouilles se posent la nuit sur le double rempart d'Aix-la-"
						   "Chapelle. Turpin veut trois têtes de gargouille avant de vous "
						   "montrer la Lance.",
			"recompenses": {"xp": 300, "cuivre": 2500},
		},
		"accueil": "Turpin s'appuie au mur, les bras croisés. X",
		"lance": "« Du haut du Granusturm, la Lance passe au-dessus des deux remparts. On l'a "
				 "toujours tirée en rang, une tour après l'autre. Un seul tireur ne fait que "
				 "mettre la bête en colère. »",
		"lance_suite": "« Je l'enseigne à qui me prouve qu'il sait voir dans la nuit ce qui "
					   "bouge sur une pierre. »",
		"propose": "« Les gargouilles se posent sur le double rempart, la nuit. Trois têtes. »",
	},
	{
		"slug": "audr_de_hallgrimskirkja",
		"lieu": "lieu:reykjavik",
		"nom": "Auðr",
		"race": "elfe",
		"portrait": "paladin_elfe_f02.jpg",
		"presence": "Une paladine elfe au manteau doublé de fourrure, descendue de "
					"Hallgrímskirkja, qui garde les yeux sur les montagnes.",
		"description": "Paladine de Hallgrímskirkja, sur les voies terrestres de l'Islande. Les "
					   "Islandais lui prêtent le nom d'une fondatrice venue par la mer ; elle ne "
					   "dit ni oui ni non.",
		"epreuve": {
			"id": "quete:epreuve_lance_reykjavik",
			"titre": "Le dragon blanc des glaciers",
			"item": "item:dragon_blanc_tete", "quantite": 1,
			"description": "Un dragon blanc descend des glaciers sur les fermes autour de "
						   "Reykjavik. Auðr veut sa tête avant de vous enseigner la Lance.",
			"recompenses": {"xp": 500, "cuivre": 4000},
		},
		"accueil": "Auðr regarde les montagnes, au-delà des toits. « Ici, ce qui vole est plus "
				   "grand qu'ailleurs. »",
		"lance": "« La Lance ne tue pas un dragon. Elle le blesse. Dix lances le tuent, si les "
				 "dix tireurs tiennent. »",
		"lance_suite": "« On dit que certains dragons ne sont pas nos ennemis. Je n'en sais "
					   "rien. Je ne tire que sur ceux qui descendent sur les fermes. »",
		"propose": "« Un dragon blanc descend des glaciers sur les fermes. Rapportez-moi sa "
				   "tête. »",
	},
]


def _dialogue(m: dict) -> dict:
	"""Arbre commun : l'épreuve (service `apport`), puis l'enseignement (service `enseignement`)
	réservé à qui l'a réussie. Les refus sont PARLÉS : le maître dit ce qui manque."""
	qid = m["epreuve"]["id"]
	reussie = {"quete_reussie": {"id": qid}}
	return {
		"noeud_depart": "accueil",
		"noeuds": {
			"accueil": {
				"texte": m["accueil"],
				"choix": [
					{"id": "lance", "label": "« On parle d'une Lance de lumière. »", "next": "lance_01"},
					{"id": "epreuve", "label": "« Que faut-il pour l'apprendre ? »",
					 "condition": {"apport_offert": True}, "next": "epreuve_propose"},
					{"id": "remettre", "label": "(Montrer les trophées.)",
					 "condition": {"apport_possible": True},
					 "action": {"service": "apport", "op": "remettre"}},
					{"id": "apprendre", "label": "« Je viens recevoir la Lance. »",
					 "condition": {**reussie, "enseignement_possible": True},
					 "action": {"service": "enseignement", "op": "apprendre"}},
					{"id": "rayon", "label": "« Je viens recevoir la Lance. »",
					 "condition": {**reussie, "enseignement_connu": False,
								   "enseignement_prerequis_manquant": True},
					 "next": "pas_pret_rayon"},
					{"id": "niveau", "label": "« Je viens recevoir la Lance. »",
					 "condition": {**reussie, "enseignement_connu": False,
								   "enseignement_prerequis_manquant": False,
								   "enseignement_niveau_insuffisant": True},
					 "next": "pas_pret_niveau"},
					{"id": "points", "label": "« Je viens recevoir la Lance. »",
					 "condition": {**reussie, "enseignement_connu": False,
								   "enseignement_prerequis_manquant": False,
								   "enseignement_niveau_insuffisant": False,
								   "enseignement_points_insuffisants": True},
					 "next": "pas_pret_points"},
					{"id": "deja", "label": "« Une question sur la Lance. »",
					 "condition": {"enseignement_connu": True}, "next": "deja"},
					{"id": "fin", "label": "(Prendre congé.)", "next": "fin"},
				],
			},
			"lance_01": {"texte": m["lance"],
						 "choix": [{"id": "suite", "label": "« Et contre un dragon ? »", "next": "lance_02"}]},
			"lance_02": {"texte": m["lance_suite"],
						 "choix": [{"id": "retour", "label": "(Revenir à la conversation.)", "next": "accueil"},
								   {"id": "fin", "label": "(Prendre congé.)", "next": "fin"}]},
			"epreuve_propose": {
				"texte": m["propose"] + " (Récompense : {xp} XP, {prime}.)",
				"choix": [{"id": "accepter", "label": "« J'y vais. »",
						   "action": {"service": "apport", "op": "accepter"}},
						  {"id": "plus_tard", "label": "« Pas encore. »", "next": "fin"}],
			},
			"epreuve_accepte": {
				"texte": "« {quantite} × {objet}. Je serai là. »",
				"choix": [{"id": "fin", "label": "(Partir.)", "next": "fin"}],
			},
			"epreuve_partiel": {
				"texte": "{pnj} examine les trophées et les pose de côté. « Il en manque encore "
						 "{reste}. »",
				"choix": [{"id": "fin", "label": "(Repartir chasser.)", "next": "fin"}],
			},
			"epreuve_remis": {
				"texte": "{pnj} regarde longtemps les trophées. « Bien. Si le Rayon vous obéit "
						 "déjà, je vous montrerai la Lance. »",
				"choix": [{"id": "retour", "label": "(Revenir à la conversation.)", "next": "accueil"},
						  {"id": "fin", "label": "(Prendre congé.)", "next": "fin"}],
			},
			"appris": {
				"texte": "La leçon dure jusqu'au soir. Quand elle finit, {pnj} montre le ciel "
						 "vide. « Maintenant, vous savez où elle s'arrête. C'est le plus "
						 "important. »",
				"choix": [{"id": "fin", "label": "(Prendre congé.)", "next": "fin"}],
			},
			"refus": {
				"texte": "{pnj} secoue la tête. « Pas aujourd'hui. Revenez plus tard. »",
				"choix": [{"id": "fin", "label": "(Prendre congé.)", "next": "fin"}],
			},
			"pas_pret_rayon": {
				"texte": "« La Lance part du Rayon. Apprenez d'abord le Rayon de lumière, dans "
						 "un grimoire. Ensuite, revenez. »",
				"choix": [{"id": "fin", "label": "(Prendre congé.)", "next": "fin"}],
			},
			"pas_pret_niveau": {
				"texte": "« Votre magie sainte n'est pas encore assez sûre pour ça. Revenez "
						 "plus tard. »",
				"choix": [{"id": "fin", "label": "(Prendre congé.)", "next": "fin"}],
			},
			"pas_pret_points": {
				"texte": "« Il vous faudra {cout} points pour la retenir. Vous ne les avez "
						 "pas encore. »",
				"choix": [{"id": "fin", "label": "(Prendre congé.)", "next": "fin"}],
			},
			"deja": {
				"texte": "« Vous l'avez. Tirez haut, et regardez qui se tient sur la ligne. »",
				"choix": [{"id": "fin", "label": "(Prendre congé.)", "next": "fin"}],
			},
		},
	}


def pnj_doc(m: dict) -> dict:
	e = m["epreuve"]
	return {
		"_id": "pnj:" + m["slug"],
		"type": "pnj",
		"nom": m["nom"],
		"race": m["race"],
		"vocation": "paladin",
		"portrait": m["portrait"],
		"description": m["description"],
		"services": {
			"apport": {
				"offre": {"id": e["id"], "titre": e["titre"], "description": e["description"],
						  "item": e["item"], "quantite": e["quantite"], "unique": True,
						  "recompenses": dict(e["recompenses"])},
				"noeuds": {"accepte": "epreuve_accepte", "partiel": "epreuve_partiel",
						   "remis": "epreuve_remis"},
			},
			"enseignement": {"sort": LANCE_ID, "noeuds": {"appris": "appris", "refus": "refus"}},
		},
		"dialogue": _dialogue(m),
	}


def entree_presence(m: dict) -> dict:
	return {"character": "pnj:" + m["slug"], "nom": m["nom"], "portrait": m["portrait"],
			"probabilite": 1, "description": m["presence"]}


def dernier_dump() -> str:
	dumps = sorted(glob.glob(os.path.join(DOSSIER_JSONS, "telluris-dump-*.json")))
	if not dumps:
		raise SystemExit("Aucun telluris-dump-*.json dans jsons/ — passez --dump.")
	return dumps[-1]


def deja_importe(genere: dict, existant: dict) -> bool:
	"""Chaque champ produit se retrouve à l'identique (la base peut ENRICHIR un doc importé)."""
	return all((existant or {}).get(k) == v for k, v in (genere or {}).items())


def _sans_rev(doc: dict) -> dict:
	return {k: v for k, v in doc.items() if k != "_rev"}


def construire(base: dict) -> tuple:
	"""`(docs, erreurs)` : sorts, grimoire + recette du Rayon, maîtres, lieux enrichis."""
	docs, erreurs = [], []

	def _neuf(doc):
		existant = base.get(doc["_id"])
		if existant is None:
			docs.append(doc)
		elif not deja_importe(doc, existant):
			erreurs.append(f"{doc['_id']} : `_id` déjà pris par un doc différent")

	for item in ("item:relique", "item:Eau_benite", "item:griffon_tete", "item:wyvern_tete",
				 "item:gargouille_tete", "item:dragon_blanc_tete"):
		if item not in base:
			erreurs.append(f"{item} absent du dump")
	for doc in SORTS:
		_neuf(doc)
	neufs_sorts = [d for d in docs if d["type"] == "sort"]
	grim_docs, _lignes, grim_erreurs = grimoires.grimoires_manquants(base, neufs_sorts)
	# Seulement le grimoire du RAYON (la Lance n'en a pas, par décision) : `grimoires_manquants`
	# rend aussi ceux de tout autre sort orphelin de la base.
	nos = ("item:grimoire_rayon_de_lumiere", "recette:grimoire_rayon_de_lumiere")
	docs += [d for d in grim_docs if d["_id"] in nos
			 or d.get("objet_final") == "grimoire_rayon_de_lumiere"]
	erreurs += [e for e in grim_erreurs if "rayon_de_lumiere" in e or "aucune recette" in e]
	for m in MAITRES:
		_neuf(pnj_doc(m))
		lieu = base.get(m["lieu"])
		if lieu is None:
			erreurs.append(f"{m['lieu']} absent du dump")
			continue
		presence = list(lieu.get("pnj") or [])
		if any((p or {}).get("character") == "pnj:" + m["slug"] for p in presence):
			continue
		lieu = copy.deepcopy(_sans_rev(lieu))
		lieu["pnj"] = presence + [entree_presence(m)]
		docs.append(lieu)
	return docs, erreurs


def _affiche(chemin) -> str:
	try:
		return os.path.relpath(chemin, RACINE)
	except ValueError:
		return os.path.abspath(chemin)


def main(argv=None) -> int:
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	ap.add_argument("--dump", default=None)
	ap.add_argument("--sortie", default=SORTIE)
	args = ap.parse_args(argv)
	chemin = args.dump or dernier_dump()
	base = {d["_id"]: d for d in json.load(open(chemin, encoding="utf-8"))["docs"]
			if isinstance(d, dict) and d.get("_id")}
	docs, erreurs = construire(base)
	if erreurs:
		print(f"REFUS — {len(erreurs)} erreur(s), rien n'est écrit :")
		for e in erreurs:
			print("  · " + e)
		return 1
	with open(args.sortie, "w", encoding="utf-8", newline="\n") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
		f.write("\n")
	compte = {}
	for d in docs:
		compte[d["type"]] = compte.get(d["type"], 0) + 1
	print(f"{len(docs)} doc(s) écrits dans {_affiche(args.sortie)} — "
		  + ", ".join(f"{n} {t}" for t, n in sorted(compte.items())) + ".")
	return 0


if __name__ == "__main__":
	sys.exit(main())
