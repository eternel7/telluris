"""Les contenants : objets à poids fixe qui contiennent plus qu'ils ne pèsent.

	python dev/gen_contenants.py

Sortie :
	jsons/contenants_a_importer.json   (à coller dans la carte d'import de /admin)

Mécanique : utils/contenants.py, docs/conception_contenants.md (bloc `contenant` du doc item,
contenu porté par la RÉFÉRENCE d'inventaire). Chiffres arbitrés par l'Auteur le 02/11/2026 :
docs/lore/monde/20261102_sacs_des_legendes.md (tableau « Ce qui est retenu »).

- Trois COPIES d'Architectes, à prix fixe (`valeur` min = max).
- Quatre RELIQUES (tag `relique` : une par personnage, règle à appliquer à l'obtention).
- Les pots d'Anansi (plusieurs exemplaires) et les cinq objets du lore : ni tag `relique`, ni
  `valeur` (non arbitrés) — prix dérivé du poids, seul un négociant les rachète.
- Tous : catégorie `outil`, sous-catégorie `contenant`, aucun slot (jamais équipés), tag
  `non_personnalisable` (une variante sur mesure changerait d'`_id`).

Docs NEUFS : refus d'écrire si un `_id` existe déjà dans le dump le plus récent avec un autre
contenu (le PUT complet de l'import l'écraserait en silence) ; identique = déjà importé. Relancer régénère le fichier à l'identique."""

import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "contenants_a_importer.json")

TAGS = ["contenant", "non_personnalisable"]


def _prix(cuivre: int) -> list:
	return [{"cu": cuivre}, {"cu": cuivre}]


def _doc(slug, nom, icon, poids, capacite, rarete, description, *, tags=(), valeur=None, maree=False):
	bloc = {"capacite_kg": capacite}
	if maree:
		bloc["maree"] = True
	doc = {
		"_id": f"item:{slug}",
		"type": "item",
		"nom": nom,
		"icon": icon,
		"categorie": "outil",
		"sous_categorie": "contenant",
		"slots": [],
		"tags": [*TAGS, *tags],
		"rarete": rarete,
		"poids": poids,
		"contenant": bloc,
		"description": description,
	}
	if valeur is not None:
		doc["valeur"] = _prix(valeur)
	return doc


DOCS = [
	# ── Copies d'Architectes (vendues à prix fixe : service `vente`, à venir) ──
	_doc("besace_profonde", "Besace profonde", "👜", 0.5, 100, "rare",
		 "Une besace de cuir souple, ordinaire à l'œil. Les Architectes y ont plié un espace "
		 "bien plus vaste que sa toile : on y range de quoi charger une mule, et l'épaule n'en "
		 "sent rien.", valeur=10000),
	_doc("urne_interieure", "Urne intérieure", "🏺", 8, 300, "tres_rare",
		 "Une urne de terre cuite au col étroit, cerclée de bronze. Son ventre ouvre sur une "
		 "réserve où tiennent minerais, matériaux et marchandises ; son poids ne change jamais, "
		 "qu'elle soit vide ou pleine.", valeur=40000),
	_doc("coffre_de_retrait", "Coffre de retrait", "🗃️", 20, 1000, "tres_rare",
		 "Un petit coffre ferré qu'un homme seul porte sur le dos. Le couvercle soulevé, on "
		 "devine une salle entière derrière ses planches. Les Architectes qui savent en bâtir se "
		 "comptent sur les doigts d'une main.", valeur=150000),

	# ── Reliques (une par personnage) ──
	_doc("sac_de_manannan", "Sac de Manannán", "🌊", 0.5, 500, "legendaire",
		 "Un sac en peau de grue, qui fut une femme selon les marins d'Irlande. Le dieu de la "
		 "mer y gardait ses trésors. À marée haute, son contenu apparaît en son milieu ; quand "
		 "la mer se retire, le sac semble vide.", tags=("relique",), maree=True),
	_doc("sac_de_rhiannon", "Sac de Rhiannon", "👝", 0.5, 1000, "legendaire",
		 "Un petit sac qu'on dit venu d'Annwn. On y verse et on y verse encore : il ne se "
		 "remplit jamais. Les conteurs gallois prétendent qu'un homme y fut pris pour avoir "
		 "voulu en tasser le contenu de ses pieds.", tags=("relique",)),
	_doc("carquois_d_arjuna", "Carquois d'Arjuna", "🏹", 1, 300, "legendaire",
		 "Un carquois qu'un héros lointain reçut, dit-on, du dieu des eaux, et qu'il rendit à la "
		 "mer. On croyait qu'il ne se vidait jamais ; en vérité, il contient bien plus qu'il "
		 "ne pèse.", tags=("relique",)),
	_doc("coquille_d_oduduwa", "Coquille d'Oduduwa", "🐚", 0.1, 2000, "legendaire",
		 "Une coquille d'escargot qui tient dans le creux de la main. Les récits du Sud disent "
		 "qu'un dieu en versa toute la terre ferme sur les eaux du commencement. De tous les "
		 "contenants connus, c'est le plus vaste.", tags=("relique",)),

	# ── Plusieurs exemplaires ──
	_doc("pot_d_anansi", "Pot d'Anansi", "🕷️", 3, 300, "legendaire",
		 "Un pot de terre ventru, fait à l'image de celui où l'araignée Anansi enferma toute la "
		 "sagesse du monde avant de le briser. Les conteurs akan en façonnent encore, et ceux-là "
		 "contiennent bien davantage que leur panse."),

	# ── Objets du lore (unicité, lieu et rang non arbitrés) ──
	_doc("coffres_de_thot", "Coffres du Livre de Thot", "🗝️", 30, 1000, "legendaire",
		 "Six coffres emboîtés — fer, bronze, bois, ivoire et ébène, argent, or — que les récits "
		 "d'Égypte placent au fond du Nil, gardés par des serpents. On n'en ouvre qu'un à la "
		 "fois, et le dernier est toujours plus vaste que le premier."),
	_doc("tente_de_pari_banou", "Tente de Pari Banou", "⛺", 2, 1500, "legendaire",
		 "Une toile pliée qui tient dans une main. Dépliée, elle abriterait les ballots d'une "
		 "caravane entière ; repliée, tout ce qu'on y a laissé voyage avec elle."),
	_doc("outre_d_eole", "Outre d'Éole", "💨", 1.5, 300, "legendaire",
		 "Une outre de cuir cousue d'un fil d'argent. Les marins disent qu'elle enferma tous les "
		 "vents sauf un, et qu'un équipage curieux l'ouvrit trop tôt. Elle garde aujourd'hui des "
		 "choses plus sages."),
	_doc("gourde_de_li_tieguai", "Gourde de Li Tieguai", "🍶", 1, 200, "legendaire",
		 "Une calebasse laquée, attachée à une cordelette. Celle de l'Immortel à la béquille de "
		 "fer portait élixirs et remèdes ; son col étroit ouvre sur une panse bien plus grande "
		 "que lui."),
	_doc("kibisis", "Kibisis de Persée", "🎒", 0.5, 100, "legendaire",
		 "La besace que Persée porta en revenant d'avoir tranché la tête de la Gorgone : rien de "
		 "ce qu'elle renferme ne peut nuire à qui la porte. Sa toile est usée, son fermoir "
		 "toujours sûr."),
]


def _dernier_dump() -> str:
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		sys.exit("Aucun dump jsons/telluris-dump-*.json : impossible de vérifier les collisions d'_id.")
	return dumps[-1]


def collisions(docs: list, existants: dict) -> list:
	"""`_id` déjà en base avec un AUTRE contenu (`_rev` ignoré) : le PUT complet l'écraserait.
	Un doc identique est l'import déjà fait — le rejouer ne change rien."""
	def _sans_rev(doc):
		return {k: v for k, v in doc.items() if k != "_rev"}
	return sorted(d["_id"] for d in docs if d["_id"] in existants and _sans_rev(existants[d["_id"]]) != d)


def main() -> None:
	dump = _dernier_dump()
	with open(dump, encoding="utf-8") as f:
		existants = {d.get("_id"): d for d in json.load(f).get("docs", [])}
	pris = collisions(DOCS, existants)
	if pris:
		sys.exit(f"Refus : _id déjà en base ({os.path.basename(dump)}) : {', '.join(pris)}")
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump({"docs": DOCS}, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"{len(DOCS)} contenants → {os.path.relpath(SORTIE, RACINE)} (dump : {os.path.basename(dump)})")


if __name__ == "__main__":
	main()
