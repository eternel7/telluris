#!/usr/bin/env python
# dev/gen_architecte_contenants.py
# L'Architecte de l'institut qui vend les trois copies de contenants (Auteur, 02/11 : « copies
# vendues à prix fixe par un PNJ Architecte de l'institut » ; 08/11 : à la Cour des Arches,
# avec Aélis).
#
#   Maître Villard de Honnecourt — nain, maître d'œuvre de l'Institut des Architectes de
#   Lutecia (adapté du maître d'œuvre picard et de son carnet de croquis). Toujours présent à
#   la Cour des Arches. Service `vente` (utils/pnj.article_en_vente) : Besace profonde, Urne
#   intérieure, Coffre de retrait, au prix FIXE de leur `valeur` (min = max), sans stock, sans
#   fabrication, sans condition de rang (Auteur, 02/11).
#   Le doute (règle de l'Auteur) : les sacs des légendes ont-ils inspiré les copies, ou n'ont-ils
#   jamais été pliés par des Anthropes ? Il ne tranche pas.
#
# Prix, noms, poids et contenances : les docs item de `dev/gen_contenants.py` (leur source) ;
# les articles et les libellés du catalogue en sont dérivés. Prix des copies ×5 (Auteur, 08/11).
#
# ⚠️ UN SEUL FICHIER À IMPORTER (CLAUDE.md §18) : jsons/architecte_contenants_a_importer.json —
# `lieu:la_cour_des_arches` RELU du dernier dump (seule l'entrée `pnj` de l'Architecte s'y
# ajoute : régénération idempotente) + `pnj:villard_de_honnecourt` + les copies dont le doc
# diffère du dump (prix), chacun COMPLET (PUT, §11).
#
# Usage : python dev/gen_architecte_contenants.py [jsons/telluris-dump-….json]

import copy
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from utils.traversee import texte_bourse  # noqa: E402
from dev import gen_contenants  # noqa: E402

SORTIE = os.path.join(RACINE, "jsons", "architecte_contenants_a_importer.json")

PNJ_ID = "pnj:villard_de_honnecourt"
LIEU_ID = "lieu:la_cour_des_arches"
PORTRAIT = "architecte_nain_m_cour02.jpg"  # cour01 garde le maître architecte des missions B-A

# Les trois copies d'Architectes, du plus petit au plus grand (docs/conception_contenants.md).
COPIES = ("item:besace_profonde", "item:urne_interieure", "item:coffre_de_retrait")
# Les sacs à dos à TROPHÉE (Auteur, 08/11) → le morceau de monstre laissé à l'Architecte, en plus
# du prix. Dragon : rencontré en France ; Mimique : gardienne du coffre des catacombes de Lutecia.
SACS_A_DOS = {
	"item:sac_de_grendel": "item:dragon_aile",
	"item:havresac_de_mimique": "item:mimique",
}
ARTICLES = COPIES + tuple(SACS_A_DOS)

ENTREE_LIEU = {
	"character": PNJ_ID,
	"nom": "Maître Villard",
	"portrait": PORTRAIT,
	"probabilite": 1,
	"description": "Un nain à la barbe tressée de fil de cuivre, penché sur un établi chargé "
				   "de besaces, d'urnes et d'un petit coffre ferré.",
}


def _kg(valeur) -> str:
	"""« 0,5 kg », « 1 000 kg » : virgule décimale, espace insécable des milliers."""
	v = float(valeur)
	texte = f"{v:,.1f}" if v != int(v) else f"{int(v):,}"
	return texte.replace(",", " ").replace(".", ",") + " kg"


def article(item_doc: dict) -> dict:
	"""Article du service `vente` : prix fixe = `valeur` du doc item (min = max), et le trophée
	exigé pour un sac à dos."""
	valeur = item_doc.get("valeur") or []
	prix = {int((v or {}).get("cu", 0)) for v in valeur}
	if len(prix) != 1 or min(prix) <= 0:
		sys.exit(f"{item_doc['_id']} : `valeur` doit être un prix fixe (min = max > 0), reçu {valeur!r}.")
	art = {"item": item_doc["_id"], "cout_cuivre": prix.pop()}
	if item_doc["_id"] in SACS_A_DOS:
		art["trophee"] = SACS_A_DOS[item_doc["_id"]]
	return art


def choix_achat(item_doc: dict, art: dict, noms_trophees: dict) -> dict:
	slug = item_doc["_id"].split(":", 1)[1]
	contre = f" + {noms_trophees[art['trophee']]}" if art.get("trophee") else ""
	return {
		"id": f"acheter_{slug}",
		"label": f"Acheter : {item_doc.get('icon', '')} {item_doc['nom']} — contient "
				 f"{_kg(item_doc['contenant']['capacite_kg'])}, pèse {_kg(item_doc['poids'])} — "
				 f"{texte_bourse(art['cout_cuivre'])}{contre}",
		"action": {"service": "vente", "op": "acheter", "item": item_doc["_id"]},
	}


def doc_pnj(items: list, noms_trophees: dict) -> dict:
	"""`noms_trophees` : id → nom de chaque morceau de monstre exigé (relu du dump)."""
	articles = [article(d) for d in items]
	return {
		"_id": PNJ_ID,
		"type": "pnj",
		"nom": "Villard de Honnecourt",
		"race": "nain",
		"vocation": "lettre",
		"portrait": PORTRAIT,
		"description": "Maître d'œuvre venu de Honnecourt, sur l'Escaut, l'un des rares Architectes "
					   "de l'Institut à savoir plier un espace dans une enveloppe : besaces, urnes, "
					   "coffres. Son carnet de croquis ne le quitte jamais. Il vend ses copies à la "
					   "Cour des Arches, au prix du travail, sans marchander.",
		"services": {
			"vente": {
				"articles": articles,
				"noeuds": {"fait": "vendu", "sans_fonds": "sans_fonds", "trop_charge": "trop_charge",
						   "sans_trophee": "sans_trophee"},
			},
		},
		"dialogue": {
			"noeud_depart": "etabli",
			"noeuds": {
				"etabli": {
					"texte": "Sous l'une des arches, un établi encombré de besaces de cuir, d'urnes "
							 "cerclées de bronze et d'un petit coffre ferré. Un nain à la barbe tressée "
							 "de fil de cuivre y trace des cercles au compas sur une toile tendue, un "
							 "carnet de croquis ouvert près du coude.",
					"choix": [
						{"id": "a_vendre", "label": "Ces besaces sont-elles à vendre ?", "next": "catalogue"},
						{"id": "art", "label": "Que faites-vous, au juste ?", "next": "art_01"},
						{"id": "fin", "label": "(Passer votre chemin.)", "next": "fin"},
					],
				},
				"art_01": {
					"texte": "Le nain lève enfin les yeux. « Je plie. Un portail a deux bouts, n'est-ce "
							 "pas ? Il relie un lieu à un autre. Moi, j'en fais qui n'ont qu'une ouverture : "
							 "ce qu'on y range part dans un espace qui n'est nulle part ailleurs. Villard "
							 "de Honnecourt, maître d'œuvre de l'Institut. »",
					"choix": [
						{"id": "poids", "label": "Et ce qu'on y range ne pèse rien ?", "next": "art_02"},
					],
				},
				"art_02": {
					"texte": "« Pour votre épaule, rien. Pour votre magie non plus : ce qui est rangé ne "
							 "gêne pas un mage. Seule l'enveloppe pèse. Deux règles, et je n'y déroge pas : "
							 "rien de vivant dedans, et jamais un de ces objets dans un autre. Ceux qui ont "
							 "essayé n'ont jamais su dire où était passé le second. »",
					"choix": [
						{"id": "legendes", "label": "On parle de sacs des légendes, plus vastes encore…",
						 "next": "legendes"},
						{"id": "voir", "label": "Montrez-moi ce que vous vendez.", "next": "catalogue"},
					],
				},
				"legendes": {
					"texte": "« Le sac de Manannán, celui de Rhiannon… Je les ai cherchés dans les "
							 "relevés de l'Institut, et je ne les ai jamais vus. Certains ici disent que "
							 "nos copies en descendent, qu'un ancien maître en aurait ouvert un pour "
							 "comprendre comment il était plié. D'autres jurent que ces sacs-là ne furent "
							 "jamais l'œuvre de mains d'Anthropes. Je n'ai pas tranché. Mes copies, elles, "
							 "je sais comment elles sont faites. »",
					"choix": [
						{"id": "voir", "label": "Montrez-moi ce que vous vendez.", "next": "catalogue"},
						{"id": "fin", "label": "Merci, maître.", "next": "fin"},
					],
				},
				"catalogue": {
					"texte": "« Trois tailles, trois prix, et je ne marchande pas : le prix est celui du "
							 "travail. La besace pour l'aventurier, l'urne pour qui transporte minerais et "
							 "marchandises, le coffre pour qui veut emporter une salle entière. Et deux "
							 "sacs à dos, si vous m'apportez de quoi les tailler. »",
					"choix": [
						*(choix_achat(d, a, noms_trophees) for d, a in zip(items, articles)),
						{"id": "peaux", "label": "Tailler un sac dans un monstre ?", "next": "peaux_01"},
						{"id": "art", "label": "Que faites-vous, au juste ?", "next": "art_01"},
						{"id": "fin", "label": "Une autre fois.", "next": "fin"},
					],
				},
				"peaux_01": {
					"texte": "« Certaines bêtes savent déjà tenir plus qu'elles ne montrent. Je ne fais "
							 "que les y aider. Les récits du Nord parlent d'un monstre, Grendel, qui "
							 "portait une poche immense, cousue de peaux de dragon : la membrane d'une aile "
							 "se plie mieux que n'importe quelle toile. Et la mimique, ce coffre qui mord : "
							 "vivante, elle était plus vaste dedans que dehors. Sa panse s'en souvient. »",
					"choix": [
						{"id": "lustig", "label": "Un sac à dos qui avale tout, ça existe ?", "next": "peaux_02"},
						{"id": "voir", "label": "Montrez-moi ce que vous vendez.", "next": "catalogue"},
					],
				},
				"peaux_02": {
					"texte": "« On raconte l'histoire d'un soldat congédié, Frère Lustig, dont le havresac "
							 "avalait tout ce qu'il lui ordonnait d'y entrer, jusqu'à des diables. Un autre "
							 "conte, plus à l'est, prête la même besace à un soldat qui y enferma la Mort. "
							 "Des diables, je n'en mets pas : rien de vivant n'entre dans mes sacs. Quant à "
							 "savoir d'où ces soldats tenaient le leur… certains ici disent d'un Architecte, "
							 "d'autres d'un saint. Je n'ai pas tranché. Rapportez-moi la peau, je "
							 "m'occupe du reste. »",
					"choix": [
						{"id": "voir", "label": "Montrez-moi ce que vous vendez.", "next": "catalogue"},
						{"id": "fin", "label": "Merci, maître.", "next": "fin"},
					],
				},
				"sans_trophee": {
					"texte": "« Sans {trophee}, je n'ai rien à plier : la peau fait la moitié du travail. "
							 "Revenez avec, votre bourse fera le reste. »",
					"choix": [
						{"id": "encore", "label": "Voir les autres.", "next": "catalogue"},
						{"id": "fin", "label": "Une autre fois.", "next": "fin"},
					],
				},
				"vendu": {
					"texte": "« Marché conclu : {objet}, pour {prix}. La première fois, ouvrez doucement : "
							 "l'espace a besoin d'un instant pour se déplier. »",
					"choix": [
						{"id": "encore", "label": "Autre chose…", "next": "catalogue"},
						{"id": "fin", "label": "Merci, maître.", "next": "fin"},
					],
				},
				"sans_fonds": {
					"texte": "« {objet} coûte {prix}, et votre bourse n'y est pas. Je ne fais ni crédit "
							 "ni rabais : revenez quand elle sera plus lourde. »",
					"choix": [
						{"id": "encore", "label": "Voir les autres.", "next": "catalogue"},
						{"id": "fin", "label": "Une autre fois.", "next": "fin"},
					],
				},
				"trop_charge": {
					"texte": "« Vous portez déjà tout ce que vous pouvez : {objet} ne tiendrait pas sur "
							 "votre dos. Allégez-vous, puis revenez. »",
					"choix": [
						{"id": "encore", "label": "Voir les autres.", "next": "catalogue"},
						{"id": "fin", "label": "Une autre fois.", "next": "fin"},
					],
				},
			},
		},
	}


def lieu_avec_architecte(lieu_doc: dict) -> dict:
	"""La Cour des Arches relue, avec l'entrée de l'Architecte (remplacée si déjà là)."""
	doc = copy.deepcopy(lieu_doc)
	doc.pop("_rev", None)
	doc["pnj"] = [e for e in doc.get("pnj") or [] if e.get("character") != PNJ_ID] + [dict(ENTREE_LIEU)]
	return doc


def _dernier_dump() -> str:
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		sys.exit("Aucun dump jsons/telluris-dump-*.json.")
	return dumps[-1]


def copies() -> list:
	"""Les articles (copies puis sacs à dos) tels que `gen_contenants` les écrit (source des prix)."""
	par_id = {d["_id"]: d for d in gen_contenants.DOCS}
	return [copy.deepcopy(par_id[i]) for i in ARTICLES]


def copies_a_importer(docs_dump: dict) -> list:
	"""Les articles dont le doc diffère du dump ou y manque (`_rev` ignoré) : le delta."""
	return [d for d in copies()
			if {k: v for k, v in (docs_dump.get(d["_id"]) or {}).items() if k != "_rev"} != d]


def generer(docs_dump: dict) -> list:
	manquants = [i for i in (LIEU_ID, *SACS_A_DOS.values()) if i not in docs_dump]
	if manquants:
		sys.exit(f"Absents du dump : {', '.join(manquants)}")
	noms_trophees = {t: docs_dump[t]["nom"] for t in SACS_A_DOS.values()}
	# `pnj:villard_de_honnecourt` n'appartient qu'à ce générateur : déjà en base, c'est son
	# import précédent, que le PUT remplace. Un autre type sous cet _id serait une collision.
	if docs_dump.get(PNJ_ID, {}).get("type", "pnj") != "pnj":
		sys.exit(f"Refus : {PNJ_ID} existe déjà dans le dump sous un autre type.")
	return [doc_pnj(copies(), noms_trophees), lieu_avec_architecte(docs_dump[LIEU_ID]), *copies_a_importer(docs_dump)]


def main() -> None:
	dump = sys.argv[1] if len(sys.argv) > 1 else _dernier_dump()
	with open(dump, encoding="utf-8") as f:
		docs_dump = {d.get("_id"): d for d in json.load(f).get("docs", [])}
	docs = generer(docs_dump)
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump({"docs": docs}, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"{len(docs)} docs → {os.path.relpath(SORTIE, RACINE)} (dump : {os.path.basename(dump)})")


if __name__ == "__main__":
	main()
