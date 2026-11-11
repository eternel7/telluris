"""Aménagements de propriété : stockage relevé + une description pour chacun.

# Rangement d'un bien = base du type + Σ `capacite.stockage_kg` des aménagements installés
# (`proprietes.capacites`). Les bases des types ont été relevées (chambre 200 kg … domaine
# 4000) ; les aménagements de rangement suivent, à l'échelle des pièces qu'ils représentent.
# Chaque aménagement reçoit aussi une `description` (le chiffre, lui, reste dans la ligne
# « ✨ » générée par `proprietes.textes_effets` : la prose ne le recopie jamais).
#
# ⚠️ POURQUOI UN SCRIPT : `admin_import_bulk` fait un PUT COMPLET. On relit `rules:proprietes`
# dans le dump le plus récent et on n'y change QUE `capacite.stockage_kg` des ids de STOCKAGE
# et la `description` des aménagements qui n'en ont pas (une description déjà écrite en base
# n'est JAMAIS réécrite) : régénérer est idempotent — relancer sur un dump FRAIS.
#
# Usage : python dev/gen_amenagements_stockage_descriptions.py [--dump chemin]
# Sortie : jsons/amenagements_stockage_descriptions_a_importer.json
"""

import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = "jsons/amenagements_stockage_descriptions_a_importer.json"
DOC_ID = "rules:proprietes"

# id → kg ajoutés au rangement du bien.
STOCKAGE = {
	"etagere": 25,
	"rangement": 50,
	"petit_coffre": 75,
	"reserve": 300,
	"cave": 600,
	"archives": 800,
	"dependances": 1500,
	"grange": 3000,
}

DESCRIPTIONS = {
	"lit_ameliore": "Un vrai sommier, une paillasse de laine et des draps épais : on s'y relève reposé, les plaies déjà moins vives.",
	"petit_coffre": "Un coffre de chêne ferré, glissé au pied du lit : bien plus de place que ce qu'on porte sur le dos.",
	"rangement": "Un placard dans le mur et de la place sous le lit : vos affaires cessent de traîner par terre.",
	"bureau": "Une table solide, un encrier et un registre : d'ici, vous tenez les comptes de vos biens dans la cité et en relevez les caisses.",
	"etagere": "Quelques planches fixées au mur, pour poser ce qui encombre.",
	"eclairage": "Chandelles de suif et lampe à huile : on lit tard, et l'esprit se repose mieux qu'à la nuit noire.",
	"decoration": "Tentures, tapis, vaisselle peinte : le lieu prend du caractère, et trouve plus aisément preneur à la revente.",
	"chambre_amelioree": "Volets épais, murs qui étouffent le bruit de la rue : un sommeil profond, dont on sort la volonté affermie.",
	"reserve": "Une pièce fermée à clef, ses caisses et ses tonneaux : ce qui n'a pas sa place ailleurs y trouve la sienne.",
	"petite_cuisine": "Un âtre et une table de travail : un cuisinier y prépare des plats qu'il vend, et qui nourrissent la maisonnée.",
	"petite_salle_a_manger": "Une table où prendre de vrais repas. Quand un cuisinier tient la cuisine, on s'en relève plus résistant.",
	"petite_bibliotheque": "Quelques rayonnages et un pupitre. Les grimoires rangés ici servent à apprendre ; avec un bibliothécaire, on y écrit comme au scriptorium.",
	"espace_medical": "Un lit de soins, des bandes et des simples. Avec un médecin à demeure, la nuit chasse les maux passagers des dormeurs.",
	"lit_supplementaire": "Un second couchage : une personne de plus peut vivre sous votre toit.",
	"coin_resident": "Un réduit aménagé pour un domestique à demeure. Un compagnon bien servi ne songe pas à quitter le groupe.",
	"chambres_multiples": "Plusieurs chambres à l'étage : la maison accueille davantage de monde.",
	"grande_cuisine": "Grands fourneaux, four à pain et garde-manger : le cuisinier y travaille en grand et vend ses plats comme son pain.",
	"salle_a_manger": "Une vraie salle pour les repas de la maisonnée. Quand un cuisinier tient la cuisine, on s'en relève plus résistant.",
	"salon": "Fauteuils, cheminée, conversation au coin du feu : l'esprit s'y repose et la volonté s'y affermit.",
	"bibliotheque": "Une pièce entière de livres. Les grimoires rangés ici servent à apprendre ; avec un bibliothécaire, on y écrit comme au scriptorium.",
	"cave": "Un niveau voûté sous la maison : tonneaux, caisses et tout ce qui ne doit pas encombrer les pièces.",
	"salle_de_soins": "Lits, onguents et instruments. Avec un médecin, la nuit chasse les maux passagers et les dormeurs se relèvent mieux remis.",
	"salle_etude": "Pupitres, encre et parchemin : un érudit y copie et rédige, et vend ses écrits comme un scriptorium.",
	"salle_entrainement": "Mannequins, poids et râteliers : la routine du matin laisse le bras plus fort pour la journée.",
	"petit_laboratoire": "Alambics, cornues et fourneau : un alchimiste y prépare ses mixtures et les vend.",
	"petit_atelier": "Un établi, des outils, une réserve de matières : un artisan y façonne des pièces qu'il vend.",
	"bureau_professionnel": "Un comptoir et des registres : un marchand y achète et revend pour votre compte.",
	"chambre_domestique": "Une chambre pour un domestique à demeure. Un compagnon bien servi ne songe pas à quitter le groupe.",
	"cour_interieure": "Une cour pavée derrière la porte cochère : une monture peut y loger.",
	"petit_jardin": "Quelques plates-bandes au soleil : chaque jour, de quoi cueillir.",
	"quartiers_personnel": "Un logement pour toute une domesticité. Des compagnons bien servis ne songent pas à quitter le groupe.",
	"appartement_invites": "Un appartement à part pour vos hôtes : la demeure accueille davantage de monde.",
	"salle_reunion": "Une grande table pour tenir conseil : on en sort avec le sentiment que la chance tourne.",
	"archives": "Rayonnages du sol au plafond, coffres à documents, tiroirs étiquetés : une pièce entière pour ranger.",
	"salon_reception": "Lustres, tapisseries et sièges d'apparat : recevoir ici forge l'aisance en société.",
	"salle_medicale": "Une pièce de soins bien pourvue. Avec un médecin, la nuit chasse les maux passagers et les dormeurs retrouvent leur mana plus vite.",
	"infirmerie": "Plusieurs lits, une pharmacie, un enclos de soins. Avec un médecin, personnes et montures se remettent pendant la nuit.",
	"laboratoire_alchimie": "Un laboratoire complet : un alchimiste y mène les préparations les plus fines et les vend.",
	"atelier_artisan": "Un atelier spacieux et bien outillé : un artisan y façonne des pièces de qualité et les vend.",
	"cabinet_medecin": "Un cabinet où un médecin reçoit, prépare remèdes et onguents, et les vend.",
	"cabinet_apothicaire": "Bocaux, mortiers et balances : un apothicaire y prépare ses remèdes et les vend.",
	"bureau_marchand": "Un bureau de négoce avec ses commis et ses registres : un marchand y achète et revend pour votre compte.",
	"salle_recherche": "Une salle d'étude agrandie, ses cartes et ses archives : un érudit y poursuit ses travaux et vend ses écrits.",
	"salle_armes": "Râteliers, mannequins et parquet de duel : à force d'exercice, le pas d'esquive devient un réflexe.",
	"cour_entrainement": "Une cour où les gardes s'exercent. Un garde au poste protège vos biens du vol.",
	"jardin": "Allées, massifs et serre : un jardinier les entretient et vend plants et cueillettes.",
	"cour": "Une cour fermée devant la demeure : une monture peut y loger.",
	"ecurie_limitee": "Quelques stalles et une sellerie. Un palefrenier y soigne les bêtes, qui repartent plus vaillantes.",
	"nombreuses_chambres": "Une aile entière de chambres : le domaine loge beaucoup de monde.",
	"appartements_invites": "Plusieurs appartements pour vos hôtes : le domaine accueille davantage de monde.",
	"bureau_administratif": "Le cabinet de l'intendant. Avec lui, la caisse de vos ateliers est relevée dès votre arrivée.",
	"grande_bibliotheque": "Une bibliothèque digne d'une institution. Les grimoires rangés ici servent à apprendre ; avec des bibliothécaires, on y écrit comme au scriptorium.",
	"salle_gestion": "Registres, cartes des terres et comptes de la maison : un intendant y attire davantage de candidats à chaque embauche.",
	"grande_salle_a_manger": "Une salle de banquet. Quand un cuisinier tient la cuisine, on se relève de table bien plus résistant.",
	"buanderie": "Cuves, lessiveuses et étendoirs : avec des domestiques, chacun s'éveille en habits propres, et cela se remarque.",
	"apothicairerie": "Une officine complète : des apothicaires y préparent remèdes courants et rares, et les vendent.",
	"ateliers_specialises": "Plusieurs ateliers côte à côte, chacun pour son art : des artisans y travaillent et vendent leurs pièces.",
	"cabinets_specialistes": "Des cabinets de curiosités et de spécimens : des érudits y préparent, naturalisent et vendent.",
	"poste_de_garde": "Une guérite et une salle de garde à l'entrée du domaine. Des gardes au poste protègent vos biens du vol.",
	"quartiers_gardes": "Dortoirs, armurerie et réfectoire pour une garde permanente : vos biens sont protégés du vol.",
	"potager": "Des carrés de légumes et d'herbes : un jardinier les cultive et vend ses récoltes.",
	"verger": "Des rangs d'arbres fruitiers : un jardinier les soigne et vend ses fruits.",
	"ecuries": "De vraies écuries, stalles, sellerie et fourrage. Des palefreniers y soignent les bêtes, qui repartent plus vaillantes.",
	"grange": "Un grand bâtiment de bois et de pierre, de la terre battue jusqu'aux combles : la plus vaste réserve qui soit.",
	"dependances": "Remises, appentis et logis annexes autour de la demeure : de la place pour ranger, et pour loger du monde.",
	"terrain_prive": "Des terres closes autour du domaine : chaque jour, de quoi récolter.",
}


def _dump_le_plus_recent() -> str:
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		sys.exit("ERREUR : aucun jsons/telluris-dump-*.json")
	return dumps[-1]


def generer(docs: list) -> tuple[dict, list]:
	"""→ (doc `rules:proprietes` à importer, [changements lisibles])."""
	doc = next((d for d in docs if d.get("_id") == DOC_ID), None)
	if doc is None:
		sys.exit(f"ERREUR : {DOC_ID} absent du dump")
	doc = json.loads(json.dumps(doc))
	doc.pop("_rev", None)
	ams = {a["id"]: a for a in doc["value"]["amenagements"]}
	inconnus = sorted((set(STOCKAGE) | set(DESCRIPTIONS)) - set(ams))
	if inconnus:
		sys.exit("ERREUR : aménagements absents du dump : " + ", ".join(inconnus))
	changes = []
	for am_id, kg in STOCKAGE.items():
		cap = ams[am_id].setdefault("capacite", {})
		if cap.get("stockage_kg") != kg:
			changes.append(f"{am_id}: stockage {cap.get('stockage_kg')} → {kg}")
			cap["stockage_kg"] = kg
	for am_id, texte in DESCRIPTIONS.items():
		if not (ams[am_id].get("description") or "").strip():
			ams[am_id]["description"] = texte
			changes.append(f"{am_id}: description")
	sans = sorted(i for i, a in ams.items() if not (a.get("description") or "").strip())
	if sans:
		print("⚠️ Aménagements toujours sans description : " + ", ".join(sans))
	return doc, changes


def main() -> None:
	args = sys.argv[1:]
	source = args[args.index("--dump") + 1] if "--dump" in args else _dump_le_plus_recent()
	with open(source, encoding="utf-8") as f:
		docs = json.load(f)["docs"]
	doc, changes = generer(docs)
	print(f"relu {os.path.relpath(source, RACINE)} — {len(changes)} changement(s)")
	for c in changes:
		print("   " + c)
	if not changes:
		print("Rien à importer : le dump est déjà à jour.")
		return
	with open(os.path.join(RACINE, SORTIE), "w", encoding="utf-8") as f:
		json.dump({"docs": [doc]}, f, ensure_ascii=False, indent=2)
	print(f"→ {SORTIE}")


if __name__ == "__main__":
	main()
