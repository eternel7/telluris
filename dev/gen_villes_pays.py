"""Chaque cité posée sur la carte de SON pays, la frontière Égypte ↔ Afrique du Nord, et les
lieux d'Atlantis et de Mu.

POURQUOI : une cité sans connexion n'est atteignable de nulle part. Les liens pays ↔ cité qui
existaient (France, Italie, plaine européenne, Roumanie, Afrique du Nord) laissaient isolées les
cités dont le pays a pourtant sa carte. Ce générateur les y pose, sur le schéma de
`gen_france_espagne_italie.connexions_rome` :

  · sur la carte du pays, la case de la cité DESSINÉE (`CITES[...]["position"]`) et ses
    voisines — un lien par sortie (`cases_autour`, le schéma de Reims ↔ France) ;
  · dans la cité, une sortie par route qui quitte la carte, ramenée à la case la plus proche
    dans la zone visée (`zone_de` + ancre : sans ancre la plus grande zone ; une ancre vise un
    quartier que la grande zone ne joint pas — rive est de Lyon) ;
  · nœud de la cité libellé « <cité> — par l'ouest » ; `_id` `link:<pays>_to_<cité>_<sortie>`.
  · la cité reçoit `lieu_parent` = son pays si elle n'en a pas (un parent déjà posé n'est
    jamais réécrit : Alexandrie et Le Caire, aussi reliées à l'Afrique du Nord, prennent
    l'Égypte).

LYON — GRILLE REFAITE (`GRILLES_REFAITES`) : la première passe faisait de la rive gauche du
Rhône, des collines de l'ouest et du faubourg sud-ouest trois zones isolées (une « enceinte »
lue à tort au bord du Rhône). Nouvelle proposition SANS enceinte, nav repartant de VIDE
(`--nav-vide --sans-enceinte`), puis les PONTS dessinés ouverts (`1`) : la proposition les
lit comme de l'eau. ⚠️ Refaite UNE fois : si tous les ponts sont déjà à 1 en base, le doc
relu est gardé tel quel (une retouche faite depuis dans l'éditeur survit au rejeu).

ÉGYPTE ↔ AFRIQUE DU NORD : `gen_egypte_afrique_du_nord.construire` (le détail y est) — même
règle que France ↔ plaine européenne ; les cités d'Égypte sont posées sur la carte d'Égypte
TELLE QU'ELLE SERA ÉCRITE.

ABOU SIMBEL : `lieu:abou_simbel` créé depuis `towns/abou_simbel_capital.jpg` (même voie
qu'Atlantis), mais sa grille est DESSINÉE (`GRILLES_DESSINEES`, `dev/grille_abou_simbel.py` :
la vue cavalière trompe la proposition, dont seule l'eau est reprise), puis posé sur la carte
d'Afrique du Nord — le temple sur le Nil, au sud de l'Égypte —, sortie par le pont.

ATLANTIS ET MU : `lieu:*` minimaux depuis `towns/atlantis_capital.jpg` et `towns/mu_capital.jpg`
(`gen_villes_images.villes_a_creer`, grille de `gen_grille_image.proposer_pour_image`), SANS
connexion : aucune carte de pays ne les montre, et le lore n'y mène que par la mer (Atlantis,
dès le rang A) ou par le portail de Notre-Dame (Mu) — c'est à l'Auteur de les relier.

ÉMIS = ce qui DIFFÈRE DU DUMP (`gen_voisins_france.a_emettre`) : rejeu sur un dump à jour ⇒
AUCUN fichier. ⚠️ Import = PUT COMPLET (CLAUDE.md §11) : une cité qui reçoit son parent ou sa
grille, `lieu:egypte` et `lieu:afrique_du_nord` partent ENTIERS depuis le dump — dump frais
exigé.

Usage :
  python dev/gen_villes_pays.py [--dump jsons/telluris-dump-….json] [--sans-apercu]

Sortie : jsons/villes_pays_a_importer.json (+ jsons/<slug>_grille_apercu.png par lieu créé)
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_egypte_afrique_du_nord as egypte  # noqa: E402
from dev import gen_grille_image as ggi  # noqa: E402
from dev import grille_abou_simbel  # noqa: E402
from dev.gen_plaine_europeenne import (  # noqa: E402
	case_proche, cases_autour, connexion, libelle_sortie, libelles_de, sans_rev, zone_de)
from dev.gen_villes_images import _taille_image, poser_grille, villes_a_creer  # noqa: E402
from dev.gen_voisins_france import a_emettre  # noqa: E402

RACINE = ggi.RACINE
SORTIE = os.path.join(ggi.DOSSIER_JSONS, "villes_pays_a_importer.json")

# Cartes de cité sans lieu à créer (Atlantis et Mu sans connexion, cf. docstring).
IMAGES_NOUVELLES = ("abou_simbel_capital.jpg", "atlantis_capital.jpg", "mu_capital.jpg")

# Cités NEUVES dont la grille est dessinée : `fn(cells proposées) -> (cells, nav)`.
GRILLES_DESSINEES = {"lieu:abou_simbel": grille_abou_simbel.grille}

# Un point de TERRE par carte de pays : la zone qui le contient est celle où l'on marche.
ANCRES_PAYS = {
	"lieu:france": (45, 25),      # Massif central
	"lieu:angleterre": (68, 33),  # Midlands
	"lieu:islande": (45, 32),     # hautes terres
	"lieu:australie": (40, 25),   # Regio Deserta
	"lieu:egypte": (40, 30),      # désert occidental
	"lieu:afrique_du_nord": (40, 30),  # Sahara, sous le Hoggar
}

# Cités dont la grille est refaite : options de `gen_grille_image.proposer_pour_image` et
# ponts ouverts après coup — ((x, y) de départ, (x, y) d'arrivée), tracés case à case (lus sur
# l'image, de rive à rive).
GRILLES_REFAITES = {
	"lieu:lyon": {
		"options": frozenset({"--nav-vide", "--sans-enceinte"}),
		"ponts": (
			((15, 15), (18, 15)),   # Saône, au pied des Monts d'Or
			((12, 26), (17, 25)),   # Saône, vers Saint-Paul
			((21, 40), (28, 37)),   # Saône, vers la presqu'île
			((63, 27), (72, 28)),   # Rhône, pont du nord
			((57, 34), (68, 36)),   # Rhône, pont du sud
		),
	},
}

# Cité → son pays, sa place SUR LA CARTE DU PAYS (lue sur l'image) et ses sorties :
# nom → (point visé dans la cité, ancre de la zone visée ou None = la plus grande zone).
# Les sorties visent une route qui quitte la carte de la cité ; leur nombre = le nombre de
# cases prises autour de `position` sur le pays.
CITES = {
	# Lyon — au confluent du Rhône et de la Saône, au pied du Jura.
	"lieu:lyon": {"pays": "lieu:france", "position": (57, 28), "sorties": {
		"nord": ((30, 3), None), "ouest": ((2, 27), None),
		"est": ((86, 22), None), "sud": ((75, 45), None)}},
	# Orléans — le château au sommet de la boucle de la Loire.
	"lieu:orleans": {"pays": "lieu:france", "position": (43, 17), "sorties": {
		"nord": ((17, 1), None), "est": ((80, 1), None), "ouest": ((1, 36), None),
		"sud": ((55, 46), None)}},
	# Londres — Caer-Ondin, sur la Tamise.
	"lieu:london": {"pays": "lieu:angleterre", "position": (72, 35), "sorties": {
		"nord": ((30, 5), None), "ouest": ((5, 22), None), "est": ((80, 24), None),
		"sud": ((14, 43), None)}},
	# Reykjavík — la citadelle dessinée au sud-ouest de l'île.
	"lieu:reykjavik": {"pays": "lieu:islande", "position": (31, 35), "sorties": {
		"nord": ((55, 3), None), "est": ((86, 22), None), "sud": ((50, 44), None)}},
	# Akureyri — au fond de l'Eyjafjörður, sur la côte nord.
	"lieu:akureyri": {"pays": "lieu:islande", "position": (48, 20), "sorties": {
		"ouest": ((2, 12), None), "est": ((62, 14), None), "sud": ((32, 62), None)}},
	# Sydney — Castrum Sydnia, sur la côte est.
	"lieu:sydney": {"pays": "lieu:australie", "position": (66, 34), "sorties": {
		"ouest": ((1, 18), None), "nord": ((35, 1), None), "sud": ((25, 46), None)}},
	# Melbourne — Castrum Melbornia, sur la côte sud.
	"lieu:melbourne": {"pays": "lieu:australie", "position": (54, 37), "sorties": {
		"nord": ((45, 6), None), "ouest": ((8, 25), None), "est": ((79, 25), None)}},
	# Alexandrie — sur la côte, à l'ouest du delta ; sorties hors des remparts.
	"lieu:alexandrie": {"pays": "lieu:egypte", "position": (42, 9), "sorties": {
		"ouest": ((2, 22), None), "est": ((86, 22), None), "sud": ((40, 37), None)}},
	# Le Caire — à la pointe du delta.
	"lieu:cairo": {"pays": "lieu:egypte", "position": (53, 16), "sorties": {
		"nord": ((60, 4), None), "est": ((86, 20), None), "sud": ((75, 44), None)}},
	# Abou Simbel — le temple dessiné sur le Nil, au sud de l'Égypte (case relue dans
	# `gen_egypte_afrique_du_nord`) ; seule sortie : le pont, puis la route murée de la rive.
	"lieu:abou_simbel": {"pays": "lieu:afrique_du_nord", "position": egypte.ABOU_SIMBEL_AFRIQUE, "sorties": {
		"sud": ((48, 80), None)}},
}


def slug(_id):
	return _id.split(":", 1)[1]


def connexions_cite(cite_id, cite, zone_pays, cite_label):
	"""(docs, refus) des liens pays ↔ cité ; le nœud de la cité libellé par sa sortie."""
	spec = CITES[cite_id]
	pays, sorties = spec["pays"], spec["sorties"]
	centre = case_proche(zone_pays, spec["position"])
	cases = cases_autour(zone_pays, centre, len(sorties)) if centre else None
	if not cases:
		return [], [f"{pays} : pas {len(sorties)} cases de terre autour de "
			f"{list(spec['position'])} pour {cite_id}"]
	docs, refus = [], []
	for (nom, (cible, ancre)), pos_pays in zip(sorties.items(), cases):
		pos = case_proche(zone_de(cite["cells"], cite.get("nav") or {}, ancre), cible)
		if pos is None:
			refus.append(f"{cite_id} : aucune case de la zone {list(ancre) if ancre else 'principale'}"
				f" pour la sortie {nom}")
			continue
		doc = connexion(f"link:{slug(pays)}_to_{slug(cite_id)}_{nom}", pays, pos_pays, cite_id, pos)
		doc["nodes"][1]["label"] = libelle_sortie(cite_label, nom)
		docs.append(doc)
	return docs, refus


def trace(a, b):
	"""Cases de `a` à `b`, chaque pas ORTHOGONAL (un pont se traverse sans diagonale)."""
	(x0, y0), (x1, y1) = a, b
	n = max(abs(x1 - x0), abs(y1 - y0))
	cases = [a]
	for i in range(1, n + 1):
		x, y = round(x0 + (x1 - x0) * i / n), round(y0 + (y1 - y0) * i / n)
		px, py = cases[-1]
		if x != px and y != py:
			cases.append((x, py))
		cases.append((x, y))
	return cases


def cases_des_ponts(ponts):
	return [c for a, b in ponts for c in trace(a, b)]


def grille_refaite(doc, proposer_fn):
	"""(doc, proposition | None) : le doc relu (`_rev` retiré) avec sa grille REFAITE, ou tel
	quel si tous ses ponts sont déjà à 1 (refaite une fois)."""
	spec = GRILLES_REFAITES[doc["_id"]]
	doc = sans_rev(doc)
	ponts = cases_des_ponts(spec["ponts"])
	if all(doc["cells"][y][x] == 1 for x, y in ponts):
		return doc, None
	proposition = proposer_fn(doc, spec["options"])
	cells = [list(ligne) for ligne in proposition["cells"]]
	for x, y in ponts:
		cells[y][x] = 1
	doc["cells"], doc["nav"] = cells, dict(proposition["nav"])
	return doc, proposition


def rattachee(cite_doc, pays):
	"""Le doc de la cité relu, `_rev` retiré, `lieu_parent` posé s'il manque."""
	doc = sans_rev(cite_doc)
	if not doc.get("lieu_parent"):
		doc["lieu_parent"] = pays
	return doc


def construire(docs, taille_fn, proposer_fn):
	"""(lieux, liens, refus, propositions, avertissements). `proposer_fn(doc, options) -> {cells,
	nav, rapport}` : grille d'une cité NEUVE ou REFAITE (Pillow côté CLI). `lieux` = docs complets, émis par
	l'appelant s'ils diffèrent du dump."""
	par_id = {d.get("_id"): d for d in docs}
	nouvelles, refus = villes_a_creer(IMAGES_NOUVELLES, docs, taille_fn)
	ids_neufs = {d["_id"] for d in nouvelles}
	manquants = [i for i in sorted(set(ANCRES_PAYS) | set(CITES))
		if i not in ids_neufs and not (par_id.get(i) or {}).get("cells")]
	if manquants:
		return [], [], [f"absent(s) du dump ou sans grille : {', '.join(manquants)}"], {}, []
	if refus:
		return [], [], refus, {}, []
	libelles = libelles_de(docs, nouvelles)
	lieux, liens, refus, avert = egypte.construire(docs, libelles)
	# Les cités d'Égypte se posent sur la carte TELLE QU'ELLE SERA ÉCRITE.
	par_id.update({d["_id"]: d for d in lieux})
	propositions = {}
	for doc in nouvelles:
		proposition = proposer_fn(doc, frozenset())
		if doc["_id"] in GRILLES_DESSINEES:
			cells, nav = GRILLES_DESSINEES[doc["_id"]](proposition["cells"])
			proposition = {**proposition, "cells": cells, "nav": nav, "dessinee": True}
		propositions[doc["_id"]] = proposition
		doc = poser_grille(doc, proposition)
		if doc["_id"] in CITES:
			par_id[doc["_id"]] = doc  # émise par la boucle des cités, parent posé
		else:
			lieux.append(doc)
	for cite_id in sorted(GRILLES_REFAITES):
		doc, proposition = grille_refaite(par_id[cite_id], proposer_fn)
		par_id[cite_id] = doc
		if proposition:
			propositions[cite_id] = proposition

	zones_pays = {p: zone_de(par_id[p]["cells"], par_id[p].get("nav") or {}, a)
		for p, a in ANCRES_PAYS.items()}
	for cite_id in sorted(CITES):
		pays = CITES[cite_id]["pays"]
		d, r = connexions_cite(cite_id, par_id[cite_id], zones_pays[pays], libelles[cite_id])
		liens += d
		refus += r
		lieux.append(rattachee(par_id[cite_id], pays))
	return lieux, liens, refus, propositions, avert


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

	def proposer(doc, options):
		dim = doc["dimensions"]
		return ggi.proposer_pour_image(ggi.trouver_image(doc["image"]), dim["x"], dim["y"], doc,
			options=options)

	lieux, liens, refus, propositions, avert = construire(docs, _taille_image, proposer)
	for a in avert:
		print(f"⚠ {a}")
	deja = {d.get("_id") for d in docs}
	emis, r = a_emettre(docs, lieux + liens)
	refus += r
	for r in refus:
		print(f"✗ {r}")
	if refus:
		print("✗ lot refusé : rien n'est écrit.")
		return 1
	if not emis:
		print("Tout est déjà en base : rien à écrire.")
		return 0

	for doc in emis:
		if doc.get("type") == "connection":
			a, b = doc["nodes"]
			print(f"  🔗 {doc['_id']} : {a['lieu']} {a['pos']} ↔ {b['lieu']} {b['pos']}")
			continue
		neuf = doc["_id"] in propositions
		cree = doc["_id"] not in deja
		print(f"  {'✚' if cree else '✎'} {doc['_id']} — {doc.get('label')}"
			f"{' · grille refaite' if neuf and not cree else ''}"
			f"{' · parent ' + doc['lieu_parent'] if doc.get('lieu_parent') else ''}")
		if neuf:
			chemin = ggi.trouver_image(doc["image"])
			proposition = propositions[doc["_id"]]
			if proposition.get("dessinee"):
				comptes = ggi.grille_image.comptes(doc["cells"])
				print("    grille dessinée : " + " · ".join(f"{v} × {n}" for v, n in sorted(comptes.items()))
					+ f" · {len(doc['nav'])} case(s) nav")
			else:
				ggi.imprimer_resume(chemin, proposition)
			if "--sans-apercu" not in args:
				apercu = os.path.join(ggi.DOSSIER_JSONS, f"{slug(doc['_id'])}_grille_apercu.png")
				ggi.ecrire_apercu(chemin, doc["cells"], apercu, doc.get("nav"),
					None if proposition.get("dessinee") else proposition["rapport"])
				print(f"    aperçu : {os.path.relpath(apercu, RACINE)}")

	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(emis, f, ensure_ascii=False, indent=2)
		f.write("\n")
	n_liens = sum(1 for d in emis if d.get("type") == "connection")
	print(f"\n✎ {os.path.relpath(SORTIE, RACINE)} — {len(emis) - n_liens} lieu(x), {n_liens} connexion(s)")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
