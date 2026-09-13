#!/usr/bin/env python
# dev/gen_progeniture.py
# Donne une FAMILLE à une poignée de tenanciers d'Auxerre : c'est le contenu qui allume les
# escortes de progéniture (moteur : `utils/escorte.py`, section PROGÉNITURE).
#
# ⚠️ LE BLOC VIT SUR L'ENTRÉE `pnj` DU DOC LIEU, jamais sur le doc PNJ. Un
# `pnj:marchand_<categorie>` est GÉNÉRIQUE — L'Athanor et Le Chaudron des Brumes partagent
# `pnj:marchand_laboratoire_d_alchimie` — et ils ne peuvent pas avoir le même enfant. C'est
# la même entrée qui rebaptise déjà le tenancier (`nom`), donc le même endroit décrit toute
# la maisonnée. `escorte.progeniture_de` lit l'entrée d'abord, le doc en repli.
#
# ⚠️ SEULES LES BOUTIQUES CITÉES ICI offrent des escortes, et le comptoir de la guilde ne
# recense qu'elles : c'est exactement la règle demandée. Les cinquante autres restent muettes
# tant qu'on ne leur écrit rien — ajouter une famille se fait ici, sans une ligne de code.
#
# ⚠️ POURQUOI UN SCRIPT ET PAS UN JSON À LA MAIN : `admin_import_bulk` fait un PUT COMPLET,
# jamais un merge. On RELIT donc chaque doc lieu depuis le dump et on n'injecte que le champ
# `progeniture` dans son entrée `pnj` : régénérer est idempotent, et tout ce que la base a de
# particulier (image, `acces`, `zone_influences`, `cells`…) survit intact.
#
# ⚠️ ALINE VARNEPIERRE EST DANS LES DEUX CANAUX, ET C'EST VOULU. Elle est aussi la disparue
# de `services.escorte.offre` du révérend Malakor (une mission ÉCRITE, dialogue authoré,
# `rang_min` E). Ce n'est PAS un doublon : les deux offres portent le MÊME id de quête —
# celui que rend `escorte.id_enfant`, c'est-à-dire
# `quete:escorte_progeniture_l_athanor_de_saint_germain_aline`, et le doc de Malakor le
# reprend tel quel. Ramener Aline par l'un des canaux la retire donc de l'AUTRE
# (`deja_reussie` compare des ids) : une seule disparition, deux façons d'en entendre parler.
#
# ⚠️ L'ID DE MALAKOR EST DONC DÉRIVÉ DE CETTE DONNÉE — slug du `_id` du magasin + slug du
# prénom. Renommer `lieu:l_athanor_de_saint_germain` ou corriger « Aline » ici fait DIVERGER
# les deux ids EN SILENCE, et la même enfant redevient sauvable deux fois, sans le moindre
# symptôme. Les deux se retouchent ensemble, jamais l'un sans l'autre :
# `jsons/escorte_aline_varnepierre_a_importer.json`.
#
# ⚠️ Portrait et description sont ALIGNÉS sur ceux de la mission écrite : c'est la même
# enfant, elle doit avoir le même visage quel que soit le canal qui la confie.
#
# Usage : python dev/gen_progeniture.py                       # familles ÉCRITES d'Auxerre
#         python dev/gen_progeniture.py --dump <d> --lieux lieu:a,lieu:b   # GÉNÉRIQUE (cf. plus bas)
# Sorties (à coller dans /admin -> Import en masse, ou 📥 sur /admin/lieux) :
#   jsons/progeniture_a_importer.json         (familles écrites)
#   jsons/progeniture_lieux_a_importer.json   (--lieux)

import argparse
import json
import os
import random
import re
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SOURCE UNIQUE : le dump complet de la base. Figé explicitement (et non « le glob le plus
# récent ») pour que régénérer donne toujours le même résultat ; à mettre à jour à la main
# après un nouveau dump.
SRC_DUMP = "jsons/telluris-dump-20260905-041008.json"
SORTIE = "jsons/progeniture_a_importer.json"

# Les familles. Le `nom` reprend celui du tenancier tel que son lieu le nomme, et la `race`
# celle que trahit son portrait — un enfant ressemble à ses parents.
#
# ⚠️ Les portraits d'enfants sont pris dans `templates/resources/characters`, DERNIER RESSORT
# de `escorte.image_protege` (qui cherche d'abord dans `pnj/`) : il n'existe pas de planche
# « civil », on emprunte donc aux vocations qui en ont l'allure (druide, ménestrel, forestier,
# lettré). Un fichier de même nom posé dans `pnj/` prendrait la main. Le fichier DOIT exister
# et son couple race/sexe correspondre, sinon le jeton de combat et la carte du protégé
# s'afficheraient vides.
FAMILLES = {
	"lieu:l_athanor_de_saint_germain": {          # Clément Varnepierre, alchimiste
		"nom": "Varnepierre",
		"race": "humain",
		"enfants": [
			{"prenom": "Girard", "sex": "M", "image": "druide_m_humain01.jpg",
			 "description": "Le cadet de l'alchimiste. Il connaît les mélanges de son père "
							"par cœur et le bois pas du tout.",
			 "inventaire": [{"item": "item:Herbes_medicinales", "poids": 0.1}]},
			# ⚠️ La disparue de la mission ÉCRITE du révérend Malakor — même id de quête,
			# donc même enfant. Portrait et description RECOPIÉS de sa spec : la ramener
			# par le père ou par le révérend doit montrer le même visage.
			{"prenom": "Aline", "sex": "F", "image": "druide_f_humain03.jpg",
			 "description": "La fille de l'apothicaire d'Auxerre. Elle connaît les herbes "
							"mieux que personne — et les loups bien moins qu'elle ne le "
							"croyait.",
			 "inventaire": [{"item": "item:Herbes_medicinales", "poids": 0.1}]},
		],
	},
	"lieu:fumee_de_l_yonne": {                    # Hermine Valcorbe, fumoir de la Guilde
		"nom": "Valcorbe",
		"race": "humain",
		"enfants": [
			{"prenom": "Perrote", "sex": "F", "image": "druide_f_humain04.jpg",
			 "description": "Elle porte le bois au hâloir depuis qu'elle sait marcher, et "
							"s'éloigne un peu plus loin chaque jour."},
		],
	},
	"lieu:l_enclume_du_rempart": {                # George Dubois, armurier
		"nom": "Dubois",
		"race": "humain",
		"enfants": [
			{"prenom": "Colin", "sex": "M", "image": "menestrel_m_humain01.jpg",
			 "description": "L'aîné de l'armurier, qui préfère les chansons à l'enclume — et "
							"les chemins de traverse à la forge."},
		],
	},
	"lieu:le_chanvre_tresse": {                   # Géraud des Vignes, cordier
		"nom": "des Vignes",
		"race": "humain",
		"enfants": [
			{"prenom": "Jehanne", "sex": "F", "image": "druide_f_humain05.jpg",
			 "description": "Elle va couper le chanvre sauvage au bord de l'eau, seule, et "
							"revient toujours plus tard qu'annoncé."},
		],
	},
	"lieu:la_navette_d_auxerre": {                # Alix Vaugrenière, tisserande elfe
		"nom": "Vaugrenière",
		"race": "elfe",
		"enfants": [
			{"prenom": "Sylvain", "sex": "M", "image": "druide_m_elfe01.jpg",
			 "description": "Il cueille les plantes à teindre lui-même et jure que la forêt "
							"ne fera jamais de mal à un elfe."},
		],
	},
	"lieu:le_clos_des_simples": {                 # Héva du Serein, jardinière
		"nom": "du Serein",
		"race": "humain",
		"enfants": [
			{"prenom": "Ysabel", "sex": "F", "image": "druide_f_humain06.jpg",
			 "description": "Elle rapporte des boutures que personne n'a jamais vues, et ne "
							"dit jamais d'où elles viennent."},
		],
	},
	"lieu:la_semelle_du_pelerin": {               # Damien de Cravant, cordonnier nain
		"nom": "de Cravant",
		"race": "nain",
		"enfants": [
			{"prenom": "Durand", "sex": "M", "image": "forestier_m_nain01.jpg",
			 "description": "Il suit les pèlerins sur la route pour leur vendre des semelles, "
							"et pousse chaque fois un peu plus loin."},
		],
	},
	"lieu:le_duvet_d_oie": {                      # Jacquette Lormière, plumassière hobbit
		"nom": "Lormière",
		"race": "hobbit",
		"enfants": [
			{"prenom": "Alison", "sex": "F", "image": "druide_f_hobbit01.jpg",
			 "description": "Elle ramasse les plumes tombées sous les arbres à oiseaux, là où "
							"nul hobbit sensé ne s'aventure."},
		],
	},
	"lieu:la_marmite_du_guet": {                  # Lalie Chantepie, cuisinière hobbit
		"nom": "Chantepie",
		"race": "hobbit",
		"enfants": [
			{"prenom": "Robinet", "sex": "M", "image": "druide_m_hobbit01.jpg",
			 "description": "Il cherche des champignons pour la marmite et ne sait pas encore "
							"lesquels cherchent le promeneur."},
		],
	},
	# Deux enfants : la maison peut donc confier DEUX escortes, l'une après l'autre, et
	# rapporter deux points de réputation — jamais plus.
	"lieu:les_etalages_d_autessiodurum": {        # Aelis de Bourgogne, bouchère
		"nom": "de Bourgogne",
		"race": "humain",
		"enfants": [
			{"prenom": "Marguet", "sex": "F", "image": "druide_f_humain07.jpg",
			 "description": "L'aînée de la bouchère. Elle mène les bêtes au pré et ne compte "
							"plus les heures."},
			{"prenom": "Guyot", "sex": "M", "image": "menestrel_m_humain02.jpg",
			 "description": "Le cadet, qui suit sa sœur partout et rentre rarement avec elle."},
		],
	},
}


def charger(chemin: str) -> list:
	"""Docs d'un export admin ou d'un dump : tableau nu, ou {"docs": [...]}."""
	absolu = chemin if os.path.isabs(chemin) else os.path.join(RACINE, chemin)
	with open(absolu, encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


def main_authore(src_dump: str) -> None:
	"""Les familles ÉCRITES d'Auxerre (`FAMILLES`) — le comportement d'origine du script."""
	base = {d["_id"]: d for d in charger(src_dump)
			if isinstance(d, dict) and d.get("_id")}
	docs = []
	for lieu_id, famille in FAMILLES.items():
		doc = base.get(lieu_id)
		if doc is None:
			# Sortie en erreur plutôt qu'un doc inventé : un import écraserait la boutique
			# par une version reconstruite de toutes pièces.
			raise SystemExit(f"{lieu_id} absent de {src_dump} — dump périmé ?")
		doc = json.loads(json.dumps(doc))        # copie profonde : on ne mute pas le dump
		entrees = doc.get("pnj") or []
		if not entrees:
			raise SystemExit(f"{lieu_id} n'a aucune entrée `pnj` — pas de tenancier à qui "
							 f"donner une famille.")
		# La PREMIÈRE entrée : c'est celle que `pnj.nom_pnj_du_lieu` nomme, et celle que le
		# tirage de présence retient d'abord (les entrées suivantes sont des variantes).
		entrees[0]["progeniture"] = json.loads(json.dumps(famille))
		doc["pnj"] = entrees
		docs.append(doc)
	chemin = os.path.join(RACINE, SORTIE)
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
	enfants = sum(len(f["enfants"]) for f in FAMILLES.values())
	print(f"{len(docs)} boutiques, {enfants} enfants -> {SORTIE}")


# ══ GÉNÉRATION GÉNÉRIQUE : `--lieux` (outil « 👪 Progéniture » de /admin/lieux) ══════
# Donne une famille aux boutiques CHOISIES (les lignes affichées du tableau d'une ville)
# plutôt qu'à la liste figée ci-dessus.
#
# ⚠️ JAMAIS RÉÉCRIRE UNE FAMILLE : une maison dont la 1re entrée porte déjà une progéniture
# (ou dont le doc PNJ en porte une, repli d'`escorte.progeniture_de`) est SAUTÉE. Le prénom
# fait l'id de la quête (`escorte.id_enfant`) : renommer un enfant déjà ramené le rendrait
# sauvable une seconde fois.
# ⚠️ DÉTERMINISTE : un `random.Random(<lieu_id>)` par maison. Relancer sur le même dump rend
# le même fichier, octet pour octet — et une maison ajoutée ne rebat pas les autres.
# ⚠️ `FAMILLES` garde la priorité : une maison écrite à la main n'est jamais tirée au sort.
# ⚠️ Seules les boutiques dont la 1re entrée `pnj` est un `pnj:marchand_*` EXPLICITE sont
# servies. Un tenancier implicite (boutique sans `pnj`, cf. `transport.entree_marchand`)
# n'a pas d'entrée où poser le bloc : on le dit, on n'invente pas l'entrée.

SORTIE_LIEUX = "jsons/progeniture_lieux_a_importer.json"
DOSSIER_PORTRAITS = os.path.join(RACINE, "templates", "resources", "characters")
# Même emprunt que `FAMILLES` : il n'existe pas de planche « civil ».
VOCATIONS_CIVILES = ("druide", "menestrel", "forestier", "lettre")
PROBA_DEUX_ENFANTS = 0.2
PORTRAIT_MARCHAND = re.compile(r"^marchand_([a-z]+)_([mf])_")

# `{Il}`/`{il}` suivent le sexe de l'enfant, `{maison}` le label de la boutique.
DESCRIPTIONS = {
	"boucherie": "{Il} mène les bêtes au pré pour la boutique et ne compte plus les heures.",
	"boulangerie": "{Il} part avant l'aube chercher le bois du four, et revient chaque jour un peu plus tard.",
	"cuisine": "{Il} cherche des champignons pour la marmite et ne sait pas encore lesquels cherchent le promeneur.",
	"tannerie": "{Il} rince les peaux à la rivière, loin en amont, là où l'eau est claire et les rives désertes.",
	"jardinier": "{Il} rapporte des boutures que personne n'a jamais vues, et ne dit jamais d'où elles viennent.",
	"apothicairerie": "{Il} connaît les simples mieux que personne — et les loups bien moins qu'{il} ne le croit.",
	"laboratoire_d_alchimie": "{Il} connaît les mélanges de la maison par cœur et le bois pas du tout.",
	"armurerie": "{Il} préfère les chansons à l'enclume — et les chemins de traverse à la forge.",
	"corderie": "{Il} va couper le chanvre sauvage au bord de l'eau, seul{e}, et revient toujours plus tard qu'annoncé.",
	"tissage": "{Il} cueille les plantes à teindre et jure que la forêt ne {lui} fera jamais de mal.",
	"plumasserie": "{Il} ramasse les plumes tombées sous les arbres à oiseaux, là où nul enfant sensé ne s'aventure.",
	"cordonnerie": "{Il} suit les pèlerins sur la route pour leur vendre des semelles, et pousse chaque fois un peu plus loin.",
	"etable": "{Il} mène les bêtes boire hors les murs et s'attarde toujours près des bois.",
}
DESCRIPTION_DEFAUT = ("{Il} connaît chaque recoin de « {maison} », et bien moins les chemins "
					  "hors les murs.")


def _texte(gabarit: str, sex: str, maison: str) -> str:
	f = sex == "F"
	return gabarit.format(Il="Elle" if f else "Il", il="elle" if f else "il",
						  e="e" if f else "", lui="lui", maison=maison)


def _race_du_parent(entree: dict, pnj_doc: dict | None, races: set) -> str:
	"""Race lue sur le portrait générique `marchand_<race>_<sexe>_…`, puis sur le doc PNJ."""
	m = PORTRAIT_MARCHAND.match(str((entree or {}).get("portrait") or ""))
	if m and m.group(1) in races:
		return m.group(1)
	race = str((pnj_doc or {}).get("race") or "")
	return race if race in races else "humain"


def _images_prises(base: dict) -> set:
	"""Portraits déjà donnés à un enfant, ailleurs en base : on évite de les redistribuer."""
	prises = set()
	for d in base.values():
		for e in (d.get("pnj") or []) if isinstance(d.get("pnj"), list) else []:
			for enfant in ((e or {}).get("progeniture") or {}).get("enfants") or []:
				if isinstance(enfant, dict) and enfant.get("image"):
					prises.add(enfant["image"])
	return prises


def familles_generees(base: dict, lieux: list, portraits: list) -> tuple:
	"""PURE (dump et fichiers de portraits injectés). Rend (docs à importer, lignes du rapport)."""
	from utils.escorte import progeniture_de
	from utils.recrutement import NOMS, PRENOMS

	races = {r for r in PRENOMS if r != "defaut"}
	prises = _images_prises(base)
	docs, rapport = [], []
	for lieu_id in lieux:
		doc = base.get(lieu_id)
		if not doc or doc.get("type") != "lieu":
			rapport.append(f"  · {lieu_id} — absent du dump, sauté")
			continue
		entrees = doc.get("pnj") if isinstance(doc.get("pnj"), list) else []
		e0 = entrees[0] if entrees and isinstance(entrees[0], dict) else None
		if not e0:
			rapport.append(f"  · {lieu_id} — aucune entrée `pnj` (tenancier implicite ?) : "
						   "ajoutez-la par ✏️ Lieu, puis relancez")
			continue
		character = str(e0.get("character") or "")
		if not character.startswith("pnj:marchand_"):
			rapport.append(f"  · {lieu_id} — la 1re entrée n'est pas un tenancier ({character or '?'}), sauté")
			continue
		if progeniture_de(e0, base.get(character)):
			rapport.append(f"  · {lieu_id} — famille déjà écrite, jamais réécrite")
			continue

		if lieu_id in FAMILLES:
			famille = json.loads(json.dumps(FAMILLES[lieu_id]))
			origine = "écrite (FAMILLES)"
		else:
			rng = random.Random(lieu_id)
			race = _race_du_parent(e0, base.get(character), races)
			mots = str(e0.get("nom") or "").split()
			nom = " ".join(mots[1:]) if len(mots) >= 2 else rng.choice(NOMS.get(race) or NOMS["defaut"])
			enfants = []
			for _ in range(2 if rng.random() < PROBA_DEUX_ENFANTS else 1):
				sex = rng.choice(("M", "F"))
				pool = (PRENOMS.get(race) or PRENOMS["defaut"]).get(sex) or PRENOMS["defaut"][sex]
				libres = [p for p in pool if p not in {e["prenom"] for e in enfants}] or pool
				prenom = rng.choice(sorted(libres))
				motif = re.compile(r"^(%s)_%s_%s\d*\.(jpe?g|png)$"
								   % ("|".join(VOCATIONS_CIVILES), sex.lower(), race))
				candidats = sorted(p for p in portraits if motif.match(p))
				neufs = [p for p in candidats if p not in prises] or candidats
				image = rng.choice(neufs) if neufs else ""
				if image:
					prises.add(image)
				gabarit = DESCRIPTIONS.get(doc.get("categorie") or "", DESCRIPTION_DEFAUT)
				enfant = {"prenom": prenom, "sex": sex, "image": image,
						  "description": _texte(gabarit, sex, doc.get("label") or lieu_id)}
				enfants.append(enfant)
			famille = {"nom": nom, "race": race, "enfants": enfants}
			origine = "tirée"
		copie = json.loads(json.dumps(doc))      # on ne mute pas le dump
		copie["pnj"][0]["progeniture"] = famille
		docs.append(copie)
		noms = ", ".join(f"{e['prenom']} ({e['sex']})" + ("" if e.get("image") else " ⚠ sans portrait")
						 for e in famille["enfants"])
		rapport.append(f"  + {lieu_id} — famille {origine} « {famille['nom']} » ({famille.get('race', '?')}) : {noms}")
	return docs, rapport


def main(argv=None) -> int:
	# Console Windows en cp1252 : sans cela, un accent fait planter le rapport.
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	p = argparse.ArgumentParser(description="Familles des tenanciers (escortes de progéniture).")
	p.add_argument("--dump", default=SRC_DUMP, help="dump source (défaut : le dump figé d'Auxerre)")
	p.add_argument("--lieux", default="", help="lieu:a,lieu:b — génération générique sur ces boutiques")
	args = p.parse_args(argv)
	if not args.lieux:
		main_authore(args.dump)
		return 0

	if RACINE not in sys.path:
		sys.path.insert(0, RACINE)
	lieux = list(dict.fromkeys(x.strip() for x in args.lieux.split(",") if x.strip()))
	base = {d["_id"]: d for d in charger(args.dump) if isinstance(d, dict) and d.get("_id")}
	portraits = os.listdir(DOSSIER_PORTRAITS) if os.path.isdir(DOSSIER_PORTRAITS) else []
	docs, rapport = familles_generees(base, lieux, portraits)
	print(f"dump : {args.dump}")
	print(f"{len(lieux)} lieu(x) demandé(s), {len(docs)} famille(s) générée(s)")
	print()
	for ligne in rapport:
		print(ligne)
	print()
	if not docs:
		# Aucun fichier : un import vide serait refusé, et un fichier ancien laissé en place
		# ne doit pas passer pour le produit de ce run (/admin/lieux compare les dates).
		print("Rien à écrire.")
		return 0
	with open(os.path.join(RACINE, SORTIE_LIEUX), "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
	print(f"→ {SORTIE_LIEUX}")
	print("⚠ Sans les nœuds d'escorte sur le doc `pnj:marchand_*` (gen_escorte_marchands), "
		  "la famille existe mais aucun dialogue ne la propose.")
	return 0


if __name__ == "__main__":
	sys.exit(main())
