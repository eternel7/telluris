"""Pierres et terres de construction + leur place dans les défauts des zones d'influence (Auteur, 16/11).

- Treize objets `item:*`, `categorie:"composant"`, `sous_categorie:"pierre"` : ils entrent dans le
  stock « Matériaux » d'une implantation (`colonisation.DEFAUTS["depots"]`), relèvent l'axe matériaux
  de la fiche de site (`site.ressources_axes`) et rejoignent les ventes du carrier — sans toucher à
  `rules:colonisation`.
- `defauts_ressources` des zones naturelles, toutes régions confondues : ADDITIF, relu du dump
  (un défaut déjà présent est gardé tel quel, rien n'est retiré).

DELTA seul contre le dump : un objet déjà en base n'est pas réémis ; seules les zones qui gagnent une
entrée le sont. Régénération idempotente.

    python dev/gen_materiaux_construction.py [--dump jsons/telluris-dump-….json] [--sortie …]
"""

import argparse
import copy
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from utils import zones  # noqa: E402

SORTIE = os.path.join(RACINE, "jsons", "materiaux_construction_a_importer.json")

# id (sans « item: ») → (nom, icône, rareté, poids kg, valeur cu, description)
OBJETS = {
	"calcaire": ("Calcaire de taille", "🪨", "commun", 1.0, 4,
				 "Bloc de pierre blonde et tendre, qui se scie au sortir de la carrière et durcit à l'air. "
				 "La pierre des remparts et des maisons de rapport."),
	"gres": ("Grès", "🪨", "commun", 1.0, 4,
			 "Pierre de sable soudé, rose ou ocre, rugueuse sous la main. On en dalle les cours et l'on "
			 "en taille les meules."),
	"argile": ("Argile", "🟫", "commun", 1.0, 2,
			   "Terre grasse tirée des berges, qui se moule en briques et en tuiles et se cuit au four."),
	"silex": ("Silex", "🪨", "commun", 0.5, 5,
			  "Rognon de pierre dure arraché à la craie. Il donne l'étincelle, et taillé en moellons il "
			  "tient un mur des siècles."),
	"ardoise": ("Ardoise", "⬛", "commun", 1.0, 5,
				"Pierre grise qui se fend en feuilles minces : les toits qui en sont couverts ne craignent "
				"ni la pluie ni les braises."),
	"tuf_volcanique": ("Tuf volcanique", "🪨", "commun", 0.8, 3,
					   "Cendre de volcan prise en pierre, légère et poreuse. Elle se taille au couteau et "
					   "garde la fraîcheur des caves."),
	"basalte": ("Basalte", "⬛", "commun", 1.2, 5,
				"Roche noire et lourde des coulées refroidies, qui se brise en colonnes. Les seuils et les "
				"bornes qui en sont faits ne s'usent pas."),
	"granit": ("Granit", "🪨", "commun", 1.2, 6,
			   "Pierre grenue, mouchetée de gris et de rose, la plus dure à tailler et la plus longue à "
			   "mourir. Les fondations des tours en sont faites."),
	"travertin": ("Travertin", "🪨", "peu_commun", 1.0, 10,
				  "Pierre crème piquée de petits trous, que l'eau des sources chaudes dépose couche après "
				  "couche. On en pave les thermes et les grandes salles."),
	"marbre": ("Marbre", "⬜", "peu_commun", 1.0, 12,
			   "Bloc de pierre blanche veinée, qui prend le poli comme un miroir. Les cités en parent "
			   "leurs temples et les puissants leurs escaliers."),
	"albatre": ("Albâtre", "⬜", "peu_commun", 0.8, 15,
				"Pierre laiteuse qui laisse passer la lumière quand on l'amincit : on en fait des vasques, "
				"des lampes et des fenêtres sans verre."),
	"porphyre": ("Porphyre", "🟥", "peu_commun", 1.2, 25,
				 "Roche pourpre semée de cristaux clairs, si dure qu'il faut des semaines pour en polir une "
				 "colonne. Elle était, dit-on, réservée aux souverains."),
	"obsidienne": ("Obsidienne", "⬛", "rare", 0.5, 30,
				   "Verre noir né du feu des volcans, tranchant à la cassure. On en incruste les seuils "
				   "et les autels ; certains y lisent l'avenir."),
}

# zone (sans « zone: ») → pierres (sans « item: ») ajoutées à ses `defauts_ressources`.
TABLE = {
	"carriere": ["marbre", "calcaire", "granit", "ardoise"],
	"montagne": ["marbre", "granit"],
	"haute_montagne": ["granit", "porphyre"],
	"contreforts": ["marbre", "granit", "ardoise"],
	"contreforts_arides": ["gres"],
	"karst": ["marbre", "calcaire", "travertin"],
	"plateau": ["calcaire", "silex"],
	"collines": ["calcaire", "silex"],
	"falaise_cotiere": ["granit", "calcaire", "basalte", "silex"],
	"fjord": ["granit", "ardoise"],
	"gorge": ["ardoise"],
	"lande": ["ardoise"],
	"canyon": ["gres", "porphyre"],
	"desert": ["gres"],
	"hamada": ["gres"],
	"volcan": ["basalte", "tuf_volcanique", "obsidienne"],
	"source_thermale": ["tuf_volcanique", "travertin"],
	"cascade": ["travertin"],
	"haut_plateau_froid": ["basalte"],
	"grotte": ["albatre"],
	"gouffre": ["albatre"],
	"desert_sel": ["albatre"],
	"riviere": ["argile"],
	"delta": ["argile"],
	"marais": ["argile"],
	"estuaire": ["argile"],
}


def dernier_dump() -> str:
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		sys.exit("Aucun dump dans jsons/.")
	return dumps[-1]


def doc_objet(ident: str) -> dict:
	nom, icone, rarete, poids, cu, description = OBJETS[ident]
	return {"_id": f"item:{ident}", "type": "item", "nom": nom, "icon": icone, "description": description,
			"rarete": rarete, "categorie": "composant", "sous_categorie": "pierre", "slots": [], "tags": [],
			"poids": poids, "valeur": [{"cu": cu}]}


def generer(docs: list) -> list:
	par_id = {d["_id"]: d for d in docs}
	inconnus = sorted({p for ps in TABLE.values() for p in ps} - set(OBJETS))
	if inconnus:
		sys.exit(f"Pierres de TABLE absentes d'OBJETS : {inconnus}")
	sortie = []
	for ident in OBJETS:
		existant = par_id.get(f"item:{ident}")
		if existant is None:
			sortie.append(doc_objet(ident))
		elif existant.get("sous_categorie") != "pierre" or existant.get("type") != "item":
			sys.exit(f"Collision d'_id : item:{ident} existe déjà sous une autre forme.")
	for zone, pierres in TABLE.items():
		zid = f"zone:{zone}"
		doc = par_id.get(zid)
		if doc is None:
			sys.exit(f"Zone absente du dump : {zid}")
		defauts = list(doc.get("defauts_ressources") or [])
		presents = {(e or {}).get("ressource") for e in defauts}
		ajouts = [{"ressource": f"item:{p}"} for p in pierres if f"item:{p}" not in presents]
		if not ajouts:
			continue
		neuf = copy.deepcopy(doc)
		neuf.pop("_rev", None)
		neuf["defauts_ressources"] = zones.normaliser_defauts(defauts + ajouts, "ressource")
		sortie.append(neuf)
	return sortie


def main():
	ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	ap.add_argument("--dump", default=None)
	ap.add_argument("--sortie", default=SORTIE)
	args = ap.parse_args()
	chemin = args.dump or dernier_dump()
	with open(chemin, encoding="utf-8") as f:
		docs = json.load(f)["docs"]
	sortie = generer(docs)
	ids = [d["_id"] for d in sortie]
	assert len(ids) == len(set(ids)), "doublon d'_id dans la sortie"
	with open(args.sortie, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=1)
		f.write("\n")
	n_obj = sum(1 for i in ids if i.startswith("item:"))
	print(f"{os.path.basename(chemin)} → {os.path.relpath(args.sortie, RACINE)} : "
		  f"{n_obj} objets, {len(ids) - n_obj} zones")


if __name__ == "__main__":
	main()
