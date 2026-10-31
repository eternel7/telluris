"""Le catalogue des guides locaux d'auberge : `rules:guides` (cf. utils/guides.py).

	python dev/gen_guides.py

Sortie :
	jsons/guides_a_importer.json   (à coller dans la carte d'import de /admin)

Doc NEUF : refus d'écrire s'il existe déjà dans le dump le plus récent avec un contenu
différent (le PUT complet de l'import écraserait en silence un réglage fait en base).
Relancer régénère le fichier à l'identique."""

import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "guides_a_importer.json")
ID = "rules:guides"

DOC = {
	"_id": ID,
	"type": "rules",
	"tableau_nb": 3,
	"duree_offre_secondes": 21600,
	"seuil_alerte_tours": 10,
	"repliques": {
		"accueil": "Dites-moi ce que vous cherchez, je vous dirai si je connais.",
		"accepte": "Oui, je vois. Pour {lieu}, suivez-moi, je vous indique la direction.",
		"ici": "Nous y sommes : {lieu}. À vous d'ouvrir l'œil, maintenant.",
		"inconnu": "« {quete} »… Non, ça ne me dit rien. Je ne vous enverrai pas au hasard.",
		"proche": "« {recherche} » ? Je ne connais pas ce nom. Vous pensez à l'un de ceux-là ?",
		"sans_chemin": "{lieu}, je connais le nom, mais je ne sais pas par où on y passe d'ici.",
		"epuise": "Vous m'avez payé jusqu'ici, et ici nous sommes. Je reste avec vous, mais pour la route, il faudra un nouveau forfait.",
		"renouvele": "Le compte est bon. Où allons-nous ?",
	},
	"metiers": {
		"ancien_aventurier": {
			"label": "Ancien aventurier",
			"forfait_cuivre": 100, "forfait_tours": 100,
			"offre": {"partout": True},
			"savoir": {"categories": ["guilde_aventurier_exterieur"]},
			"portrait_voc": "guerrier",
			"equipement": {"main_droite": "item:Epee_courte", "torse": "item:Armure_de_cuir_cloutee", "tete": "item:Casque_de_cuir_bouilli", "pieds": "item:Bottes_de_voyage"},
			"repliques": {
				"presentation": "Carte de la Guilde rendue, souvenirs gardés : où mène chaque contrat, où se tient chaque maison, tout est encore là.",
				"accueil": "J'ai fait ce métier assez longtemps. Quel contrat vous occupe ?",
			},
		},
		"guide_des_routes": {
			"label": "Guide des routes",
			"forfait_cuivre": 50, "forfait_tours": 100,
			"offre": {"partout": True},
			"savoir": {},
			"portrait": "routes",
			"portrait_voc": "forestier",
			"equipement": {"main_droite": "item:Canne_ferree", "torse": "item:Veste_cuir_souple", "epaules": "item:Manteau_de_ratine", "pieds": "item:Bottes_de_voyage"},
			"repliques": {
				"presentation": "Loue ses jambes d'un relais à l'autre et connaît le pays borne par borne. Rien au-delà, mais c'est le moins cher.",
				"accueil": "Le pays, je le connais jusqu'à ses ornières. Où voulez-vous aller ?",
			},
		},
		"survivant_de_donjon": {
			"label": "Survivant d'un donjon",
			"forfait_cuivre": 150, "forfait_tours": 100,
			"offre": {"traits": ["donjon"]},
			"savoir": {"tags": ["donjon"]},
			"portrait": "survivant",
			"portrait_voc": "barbare",
			"equipement": {"main_droite": "item:Hache_de_guerre", "torse": "item:Armure_de_peau", "pieds": "item:Bottes_noires"},
			"repliques": {
				"presentation": "Ses compagnons ne sont pas remontés. Depuis, boit à la porte du temple et raconte à qui paie ce qui s'y trouve, et où.",
				"accueil": "Moi, j'ai revu le jour. Demandez, tant que je m'en souviens.",
			},
		},
		"contrebandier": {
			"label": "Contrebandier",
			"forfait_cuivre": 150, "forfait_tours": 100,
			"offre": {"traits": ["port", "contrebande"]},
			"savoir": {"categories": ["quai"], "tags": ["contrebande"]},
			"portrait_voc": "voleur",
			"equipement": {"main_droite": "item:Dague", "main_gauche": "item:Dague_de_parade", "torse": "item:Cuirasse_cuir_noir", "tete": "item:Capuche_noire", "pieds": "item:Bottes_silencieuses"},
			"repliques": {
				"presentation": "Nul ne sait quelle marchandise passe par ces mains, mais ces mains savent par où : les quais, et les chemins qui évitent les octrois.",
				"accueil": "Parlez bas. Où faut-il passer sans qu'on vous voie ?",
			},
		},
		"interprete": {
			"label": "Interprète",
			"forfait_cuivre": 150, "forfait_tours": 100,
			"offre": {"traits": ["port"], "sous_categories": ["capitale"]},
			"savoir": {"categories": ["ville"]},
			"portrait_voc": "lettre",
			"equipement": {"main_droite": "item:Couteau", "torse": "item:Manteau_de_cour_double", "pieds": "item:Souliers_cuir"},
			"repliques": {
				"presentation": "A suivi les caravanes de cité en cité et parle assez de langues pour savoir où chacune se trouve.",
				"accueil": "Chaque cité a son nom pour tout. Laquelle cherchez-vous ?",
			},
		},
		"montagnard": {
			"label": "Montagnard",
			"forfait_cuivre": 100, "forfait_tours": 100,
			"offre": {"traits": ["montagne"]},
			"savoir": {"tags": ["montagne"]},
			"portrait_voc": "barbare",
			"equipement": {"main_droite": "item:Hachette", "torse": "item:Armure_de_peau", "epaules": "item:Cape_de_fourrure", "jambes": "item:Braies_fourrure", "pieds": "item:Bottes_de_chasse"},
			"repliques": {
				"presentation": "Vend ses fromages en ville et remonte demain. Les cols, les passes et ce qui y rôde n'ont pas de secret pour qui vit là-haut.",
				"accueil": "Là-haut, on ne se trompe qu'une fois. Où montons-nous ?",
			},
		},
		"marin": {
			"label": "Marin",
			"forfait_cuivre": 100, "forfait_tours": 100,
			"offre": {"traits": ["port"]},
			"savoir": {"categories": ["quai"]},
			"portrait_voc": "duelliste",
			"equipement": {"main_droite": "item:Rapiere", "torse": "item:Jaque_de_crin", "tete": "item:Bandeau_de_cuir", "pieds": "item:Bottes_lacees"},
			"repliques": {
				"presentation": "Entre deux traversées, connaît chaque quai où l'on peut encore accoster, et ceux que les bêtes de la mer ont rendus mauvais.",
				"accueil": "À terre, je m'ennuie. Quel port vous faut-il ?",
			},
		},
	},
}


# Types propres à un pays : le nom et l'image changent, le service reste celui de leur modèle.
# (id, modèle, pays, label, présentation, accueil) — présentation SANS pronom : le guide peut
# être une femme comme un homme.
TYPES_PAR_PAYS = [
	("compagnon", "guide_des_routes", "lieu:france", "Compagnon du Tour",
	 "Fait son Tour de ville en ville, un chantier après l'autre. Les routes de France n'ont plus de secret, ni leurs auberges.",
	 "Je connais un toit à chaque étape. Où allons-nous ?"),
	("ecuyer", "ancien_aventurier", "lieu:angleterre", "Écuyer errant",
	 "Sans chevalier à servir pour l'heure, parcourt l'île de maison en maison de la Guilde et sait ce que la Table ronde ne dit pas.",
	 "Ni heaume ni éperons, mais je connais l'île. Quel contrat vous occupe ?"),
	("peau_de_loup", "montagnard", "lieu:islande", "Chasseur en peau de loup",
	 "Chasse pour Reykjavik et Akureyri, une peau de loup sur les épaules, et rentre toujours avant que le froid ne décide.",
	 "Ici, le froid tue avant les bêtes. Où montons-nous ?"),
	("cicerone", "interprete", "lieu:italie", "Cicerone",
	 "Fait parler les pierres de Rome pour qui paie, et assez de langues pour savoir où se trouve chaque cité.",
	 "Chaque pierre a son histoire, chaque cité son nom. Laquelle cherchez-vous ?"),
	("passeur_nil", "marin", "lieu:egypte", "Passeur du Nil",
	 "Vit sur le fleuve, d'Alexandrie au Caire : chaque rive, chaque crue, et ce qui guette sous l'eau.",
	 "Le fleuve décide, je traduis. Quelle rive vous faut-il ?"),
	("caravanier", "guide_des_routes", "lieu:levant", "Caravanier nabatéen",
	 "Mène les bêtes de bât de citerne en citerne et ne passe jamais où l'eau manque, car à Petra, c'est l'eau qui commande.",
	 "Une piste, c'est de l'eau à chaque étape. Où allons-nous ?"),
	("mehariste", "guide_des_routes", "lieu:afrique_du_nord", "Méhariste",
	 "Traverse le désert à dos de dromadaire, d'un puits à l'autre, et lit la route dans les étoiles quand le vent a effacé les traces.",
	 "Au désert, on arrive ou on n'arrive pas. Où voulez-vous aller ?"),
	("pisteur", "guide_des_routes", "lieu:australie", "Pisteur aborigène",
	 "Lit le pays à une empreinte près et chante le chemin comme l'ont appris ceux d'avant les portails.",
	 "La piste parle à qui sait l'écouter. Que cherchez-vous ?"),
	("coureur_des_bois", "guide_des_routes", "lieu:amerique_du_nord", "Coureur des bois",
	 "Vit de peaux et de portages, loin de tout rempart, et passe en canot là où aucune route n'existe.",
	 "La forêt n'a pas de route, mais j'y passe. Où allons-nous ?"),
]

for _id, _modele, _pays, _label, _presentation, _accueil in TYPES_PAR_PAYS:
	DOC["metiers"][_id] = {
		**DOC["metiers"][_modele],
		"label": _label,
		"offre": {"pays": [_pays]},
		"portrait": _id,
		"repliques": {"presentation": _presentation, "accueil": _accueil},
	}


def _dump_recent() -> dict | None:
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		return None
	with open(dumps[-1], encoding="utf-8") as f:
		return json.load(f)


def main() -> int:
	dump = _dump_recent() or {"docs": []}
	existant = next((d for d in dump["docs"] if d.get("_id") == ID), None)
	if existant:
		sans_rev = {k: v for k, v in existant.items() if k != "_rev"}
		if sans_rev != DOC:
			print(f"REFUS : {ID} existe déjà dans le dump avec un autre contenu.")
			return 1
	with open(SORTIE, "w", encoding="utf-8", newline="\n") as f:
		json.dump([DOC], f, ensure_ascii=False, indent="\t")
		f.write("\n")
	print(f"{SORTIE} : 1 doc ({len(DOC['metiers'])} métiers).")
	return 0


if __name__ == "__main__":
	sys.exit(main())
