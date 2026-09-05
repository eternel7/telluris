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
# Usage : python dev/gen_progeniture.py
# Sortie (à coller dans /admin -> Import en masse) :
#   jsons/progeniture_a_importer.json

import json
import os

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SOURCE UNIQUE : le dump complet de la base. Figé explicitement (et non « le glob le plus
# récent ») pour que régénérer donne toujours le même résultat ; à mettre à jour à la main
# après un nouveau dump.
SRC_DUMP = "jsons/telluris-dump-20260905-041008.json"
SORTIE = "jsons/progeniture_a_importer.json"

# Les familles. Le `nom` reprend celui du tenancier tel que son lieu le nomme, et la `race`
# celle que trahit son portrait — un enfant ressemble à ses parents.
#
# ⚠️ Les portraits d'enfants sont pris dans `templates/resources/characters` : il n'existe pas
# de planche « civil », on emprunte donc aux vocations qui en ont l'allure (druide, ménestrel,
# forestier, lettré). Le fichier DOIT exister et son couple race/sexe correspondre, sinon le
# jeton de combat et la carte du protégé s'afficheraient vides.
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
	with open(os.path.join(RACINE, chemin), encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


def main() -> None:
	base = {d["_id"]: d for d in charger(SRC_DUMP)
			if isinstance(d, dict) and d.get("_id")}
	docs = []
	for lieu_id, famille in FAMILLES.items():
		doc = base.get(lieu_id)
		if doc is None:
			# Sortie en erreur plutôt qu'un doc inventé : un import écraserait la boutique
			# par une version reconstruite de toutes pièces.
			raise SystemExit(f"{lieu_id} absent de {SRC_DUMP} — dump périmé ?")
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


if __name__ == "__main__":
	main()
