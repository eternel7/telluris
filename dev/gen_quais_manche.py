"""Quais de Calais et de Douvres : trois zones de quai par port, un capitaine par zone.

Chaque port n'avait qu'UN accès aux quais (`link:quai01_to_*`) et qu'un capitaine : on
longeait les bassins sans le trouver. Le pourtour de chaque bassin est découpé en trois
ZONES de cases qui se suivent ; une zone = un lieu de quai, son capitaine, sa route de
traversée, et une connexion par case :

  · zone d'origine : `lieu:<cité>_quais`, son capitaine et sa route existants — seul le
    portrait du capitaine change (`PORTRAITS`), dans le PNJ et dans l'entrée `pnj` du lieu ;
  · zones neuves : `lieu:<cité>_quais_<zone>` (forme du quai d'origine), `pnj:capitaine_
    <cité>_<zone>` (services et dialogue de traversée), `traversee:<cité>_<zone>_<arrivée>`
    = la route d'origine dont seul le DÉPART change — un capitaine ne vend que la route qui
    part de son lieu (`routers/pnj._offre_traversee`). L'arrivée reste le quai d'origine
    d'en face.

Connexions : forme de `quai01` (pas de label : le bouton reprend celui du lieu), `_id`
`link:quaiNN_to_<cité>` — un numéro reste attaché à sa case d'un rejeu à l'autre.

Refus avant toute écriture : case ≠ 1, case que les rues ne relient pas à `quai01`, case
prise par une autre connexion de la cité, `_id` d'une autre connexion, doc d'origine absent.

Usage :
  python dev/gen_quais_manche.py [--dump jsons/telluris-dump-….json]

Sortie : jsons/quais_manche_a_importer.json (ÉMIS = ce qui diffère du dump : un rejeu sur un
dump à jour n'écrit rien). ⚠️ Import = PUT COMPLET (CLAUDE.md §11).
"""

import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_grille_image as ggi  # noqa: E402
from dev.gen_calais_remparts import atteint  # noqa: E402
from dev.gen_plaine_europeenne import sans_rev  # noqa: E402
from dev.gen_voisins_france import a_emettre  # noqa: E402

SORTIE = os.path.join(ggi.DOSSIER_JSONS, "quais_manche_a_importer.json")

META = {"type": "quai", "status": "ouvert"}

# Portraits des capitaines d'origine (fichiers de templates/resources/pnj/).
PORTRAITS = {"pnj:capitaine_calais": "capitaine_humain_f_calais01.jpg",
			 "pnj:capitaine_douvres": "capitaine_ogre_m_douvres01.jpg"}


def _dialogue(accueil, danger, a_bord):
	"""Arbre de traversée (forme des capitaines d'origine) : accueil, danger, à bord, pauvre."""
	fin = {"id": "fin", "label": "Une autre fois.", "next": "fin"}
	return {"noeud_depart": "accueil", "noeuds": {
		"accueil": {"texte": accueil, "choix": [
			{"id": "embarquer", "label": "Payer {tarif} et monter à bord.",
			 "action": {"service": "traversee", "op": "embarquer"}},
			{"id": "danger", "label": "Qu'est-ce qui rôde au large ?", "next": "danger"},
			fin]},
		"danger": {"texte": danger, "choix": [
			{"id": "retour", "label": "Revenir au passage.", "next": "accueil"}, fin]},
		"a_bord": {"texte": a_bord, "choix": [
			{"id": "fin", "label": "Monter à bord.", "next": "fin"}]},
		"pauvre": {"texte": "{pnj} compte vos pièces et secoue la tête. « Ça ne paie pas "
							"la place. Revenez avec {tarif}, et on lève l'ancre. »",
				   "choix": [{"id": "fin", "label": "Repartir.", "next": "fin"}]},
	}}


# Cases de quai lues sur l'image de la cité (grille 88×48), dans l'ordre du pourtour du
# bassin ; `NN` = numéro de la connexion `link:quaiNN_to_<cité>` (01 = l'existante).
PORTS = (
	{"cite": "lieu:calais", "existant": (36, 19), "route": "traversee:calais_douvres",
	 "zones": (
		{"zone": "nord", "label": "Les quais nord de Calais",
		 "cases": {7: (28, 17), 2: (30, 17), 8: (32, 17)},
		 "capitaine": {"nom": "Aubin Cordemâle", "race": "nain", "sexe": "m",
					   "description": "Patron d'un navire trapu qui fait la traversée du Pas "
									  "vers Douvres depuis le bassin nord.",
					   "dialogue": _dialogue(
						   "{pnj} tape du plat de la main sur la coque de son navire, large "
						   "et bas sur l'eau. « Il ne gagne pas de courses, mais il arrive. "
						   "Douvres, c'est ça ? Places à bord : {passagers}. Ce sera {tarif}. »",
						   "« Des tritons qui tirent sur les filins, des sirènes qui chantent "
						   "aux matelots trop jeunes. » {pnj} montre la hache passée au mât. "
						   "« Et quand un bras de kraken monte sur le pont, on coupe. On ne "
						   "discute pas avec un kraken. »",
						   "« Larguez ! » Le navire du bassin nord quitte le quai à la rame "
						   "puis prend le vent. Cap sur Douvres.")}},
		{"zone": None,      # zone d'origine : lieu:calais_quais, pnj:capitaine_calais
		 "cases": {3: (37, 17), 1: (36, 19), 4: (36, 21)}},
		{"zone": "sud", "label": "Les quais sud de Calais",
		 "cases": {9: (35, 23), 5: (33, 25), 6: (30, 25)},
		 "capitaine": {"nom": "Ysolde Marbrise", "race": "elfe", "sexe": "f",
					   "description": "Patronne d'un navire effilé qui fait la traversée du "
									  "Pas vers Douvres depuis le bassin sud.",
					   "dialogue": _dialogue(
						   "{pnj} lève les yeux de ses cartes marines, couvertes de courants "
						   "tracés à l'encre fine. « Douvres ? Le vent tourne à la marée "
						   "haute, nous serons partis avant lui. Places à bord : {passagers}. "
						   "Le passage coûte {tarif}. »",
						   "« J'ai fait cette traversée plus de fois que vous n'avez vu de "
						   "printemps. » {pnj} replie une carte. « Les serpents suivent les "
						   "sillages, les sirènes guettent les récifs. Mon navire est rapide : "
						   "nous ne nous battons que quand ils sont plus rapides que lui. »",
						   "« Larguez les amarres ! » Le navire effilé glisse hors du bassin "
						   "sud et prend le vent. Cap sur Douvres.")}},
	 )},
	{"cite": "lieu:douvres", "existant": (60, 24), "route": "traversee:douvres_calais",
	 "zones": (
		{"zone": "ouest", "label": "Les quais ouest de Douvres",
		 "cases": {3: (56, 22), 7: (54, 25), 2: (50, 27)},
		 "capitaine": {"nom": "Tamsin Brockwell", "race": "hobbit", "sexe": "f",
					   "description": "Patronne d'un petit navire vif qui fait la traversée "
									  "du Pas vers Calais depuis le quai ouest.",
					   "dialogue": _dialogue(
						   "{pnj} grimpe sur une caisse pour vous regarder dans les yeux. "
						   "« Calais ? Le plus petit navire du port, et le plus rapide à "
						   "virer. Places à bord : {passagers}. Ce sera {tarif}. »",
						   "« Les grands navires, les serpents les voient de loin. Le mien, "
						   "ils le prennent pour une planche qui flotte. » {pnj} sourit. "
						   "« Ça ne marche pas toujours. Les sirènes, elles, chantent pour "
						   "tout le monde : on se bouche les oreilles à la cire, et on "
						   "rame. »",
						   "« Larguez ! » Le petit navire file hors du quai ouest et prend "
						   "le vent. Cap sur Calais.")}},
		{"zone": None,      # zone d'origine : lieu:douvres_quais, pnj:capitaine_douvres
		 "cases": {1: (60, 24), 8: (63, 22), 4: (66, 22), 5: (70, 26)}},
		{"zone": "sud", "label": "Les quais sud de Douvres",
		 "cases": {9: (52, 32), 6: (56, 33), 10: (59, 33), 11: (61, 33)},
		 "capitaine": {"nom": "Osric Fenwick", "race": "humain", "sexe": "m",
					   "description": "Patron d'un navire de charge qui fait la traversée "
									  "du Pas vers Calais depuis le quai sud.",
					   "dialogue": _dialogue(
						   "{pnj} surveille le chargement de ses tonneaux sans lâcher son "
						   "registre. « Calais, avec la cargaison de laine. Il reste de la "
						   "place entre les ballots. Places à bord : {passagers}. Le passage "
						   "coûte {tarif}. »",
						   "« Un navire lourd, ça n'esquive rien. » {pnj} montre les "
						   "harpons rangés le long du bastingage. « Alors on se prépare : "
						   "harpons pour les serpents, torches pour les tritons, et le cap "
						   "droit sur Calais. Les sirènes, on les laisse chanter. »",
						   "« Larguez les amarres ! » Le navire chargé s'écarte lourdement "
						   "du quai sud et prend le vent. Cap sur Calais.")}},
	 )},
)


def slug_cite(cite_id):
	return cite_id.split(":", 1)[1]


def portrait_de(cap, cite_id):
	"""Fichier attendu dans templates/resources/pnj/ pour un capitaine neuf."""
	return f"capitaine_{cap['race']}_{cap['sexe']}_{slug_cite(cite_id)}01.jpg"


def ids_zone(cite_id, zone):
	"""(lieu, pnj) d'une zone ; None ⇒ zone d'origine."""
	s = slug_cite(cite_id)
	if zone is None:
		return f"lieu:{s}_quais", f"pnj:capitaine_{s}"
	return f"lieu:{s}_quais_{zone}", f"pnj:capitaine_{s}_{zone}"


def construire(docs):
	"""(sortants, refus) — lieux, capitaines, routes et connexions des trois zones."""
	par_id = {d.get("_id"): d for d in docs}
	sortants, refus = [], []
	for port in PORTS:
		cite_id, s = port["cite"], slug_cite(port["cite"])
		cite, route0 = par_id.get(cite_id), par_id.get(port["route"])
		quai0, pnj0 = par_id.get(f"lieu:{s}_quais"), par_id.get(f"pnj:capitaine_{s}")
		manquants = [i for i, d in ((cite_id, cite), (port["route"], route0),
									 (f"lieu:{s}_quais", quai0), (f"pnj:capitaine_{s}", pnj0))
					 if not d]
		if manquants:
			refus += [f"{i} : absent du dump" for i in manquants]
			continue
		cells, nav = cite["cells"], cite.get("nav") or {}
		joint = atteint(cells, nav, port["existant"])
		prises = {tuple(n["pos"]): d["_id"] for d in docs if d.get("type") == "connection"
				  for n in d.get("nodes", []) if n.get("lieu") == cite_id}
		quais_du_port = {f"lieu:{s}_quais"} | {f"lieu:{s}_quais_{z['zone']}"
											   for z in port["zones"] if z["zone"]}
		for z in port["zones"]:
			lieu_id, pnj_id = ids_zone(cite_id, z["zone"])
			if z["zone"] is None:
				portrait = PORTRAITS[pnj_id]
				pnj_doc = sans_rev(copy.deepcopy(pnj0))
				pnj_doc["portrait"] = portrait
				lieu_doc = sans_rev(copy.deepcopy(quai0))
				for e in lieu_doc.get("pnj") or []:
					if e.get("character") == pnj_id:
						e["portrait"] = portrait
				sortants += [lieu_doc, pnj_doc]
			else:
				cap = z["capitaine"]
				portrait = portrait_de(cap, cite_id)
				route_id = f"traversee:{s}_{z['zone']}_" + port["route"].split("_", 1)[1]
				route = sans_rev(copy.deepcopy(route0))
				route["_id"], route["depart"] = route_id, {"lieu": lieu_id}
				conf = copy.deepcopy(pnj0["services"]["traversee"])
				conf["route"] = route_id
				sortants += [
					{"_id": lieu_id, "type": "lieu", "label": z["label"],
					 "image": quai0.get("image"), "categorie": quai0.get("categorie"),
					 "lieu_parent": cite_id,
					 "pnj": [{"character": pnj_id, "nom": cap["nom"], "portrait": portrait,
							  "probabilite": 1}]},
					{"_id": pnj_id, "type": "pnj", "nom": cap["nom"], "race": cap["race"],
					 "portrait": portrait, "vocation": pnj0.get("vocation", "guerrier"),
					 "description": cap["description"], "services": {"traversee": conf},
					 "dialogue": cap["dialogue"]},
					route,
				]
			for nn, (x, y) in z["cases"].items():
				_id = f"link:quai{nn:02d}_to_{s}"
				if cells[y][x] != 1:
					refus.append(f"{_id} : case {[x, y]} = {cells[y][x]}, pas 1")
				elif (x, y) not in joint:
					refus.append(f"{_id} : case {[x, y]} non reliée par les rues à "
								 f"{list(port['existant'])}")
				if (x, y) in prises and prises[(x, y)] != _id:
					refus.append(f"{_id} : case {[x, y]} déjà prise par {prises[(x, y)]}")
				ancien = par_id.get(_id)
				if ancien and not any(n.get("lieu") in quais_du_port
									  for n in ancien.get("nodes", [])):
					refus.append(f"{_id} : _id déjà pris par une autre connexion")
				if ancien and nn == 1:
					lien = sans_rev(copy.deepcopy(ancien))   # quai01 : seul le quai peut changer
					for n in lien["nodes"]:
						if n.get("lieu") in quais_du_port:
							n["lieu"] = lieu_id
					sortants.append(lien)
					continue
				sortants.append({"_id": _id, "type": "connection",
								 "nodes": [{"lieu": cite_id, "pos": [x, y]},
										   {"lieu": lieu_id, "pos": [0, 0]}],
								 "metadata": dict(META)})
	return sortants, refus


def portraits_manquants(sortants):
	"""Portraits référencés par les PNJ émis et absents de templates/resources/pnj/."""
	dossier = os.path.join(ggi.RACINE, "templates", "resources", "pnj")
	return sorted({d["portrait"] for d in sortants if d.get("type") == "pnj"
				   and not os.path.exists(os.path.join(dossier, d["portrait"]))})


def main() -> int:
	args = sys.argv[1:]
	chemin_dump = None
	if "--dump" in args:
		i = args.index("--dump")
		if i + 1 >= len(args):
			print("✗ --dump attend un chemin.")
			return 2
		chemin_dump = args[i + 1]
	docs = ggi.charger_dump(chemin_dump)
	if not docs:
		print("✗ aucun dump : passer --dump ou exporter un telluris-dump-*.json dans jsons/.")
		return 1
	sortants, refus = construire(docs)
	emis, refus_emis = a_emettre(docs, sortants)
	for r in refus + refus_emis:
		print(f"✗ {r}")
	if refus or refus_emis:
		print("✗ lot refusé : rien n'est écrit.")
		return 1
	if not emis:
		print("Rien à importer : le dump contient déjà tout.")
		return 0
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(emis, f, ensure_ascii=False, indent=2)
		f.write("\n")
	for d in emis:
		quoi = d["nodes"][0]["pos"] if d.get("type") == "connection" else d.get("label") or d.get("nom", "")
		print(f"  {d['_id']} : {quoi}")
	for p in portraits_manquants(sortants):
		print(f"  ⚠ portrait à déposer avant l'import : templates/resources/pnj/{p}")
	print(f"✎ {os.path.relpath(SORTIE, ggi.RACINE)} — {len(emis)} doc(s) à importer")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
