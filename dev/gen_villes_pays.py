"""Chaque cité posée sur la carte de SON pays, et les lieux d'Atlantis et de Mu.

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

ATLANTIS ET MU : `lieu:*` minimaux depuis `towns/atlantis_capital.jpg` et `towns/mu_capital.jpg`
(`gen_villes_images.villes_a_creer`, grille de `gen_grille_image.proposer_pour_image`), SANS
connexion : aucune carte de pays ne les montre, et le lore n'y mène que par la mer (Atlantis,
dès le rang A) ou par le portail de Notre-Dame (Mu) — c'est à l'Auteur de les relier.

ÉMIS = ce qui DIFFÈRE DU DUMP (`gen_voisins_france.a_emettre`) : rejeu sur un dump à jour ⇒
AUCUN fichier. ⚠️ Import = PUT COMPLET (CLAUDE.md §11) : une cité qui reçoit son parent part
ENTIÈRE depuis le dump — dump frais exigé.

Usage :
  python dev/gen_villes_pays.py [--dump jsons/telluris-dump-….json] [--sans-apercu]

Sortie : jsons/villes_pays_a_importer.json (+ jsons/<slug>_grille_apercu.png par lieu créé)
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_grille_image as ggi  # noqa: E402
from dev.gen_plaine_europeenne import (  # noqa: E402
	case_proche, cases_autour, connexion, libelle_sortie, libelles_de, sans_rev, zone_de)
from dev.gen_villes_images import _taille_image, poser_grille, villes_a_creer  # noqa: E402
from dev.gen_voisins_france import a_emettre  # noqa: E402

RACINE = ggi.RACINE
SORTIE = os.path.join(ggi.DOSSIER_JSONS, "villes_pays_a_importer.json")

# Cartes de cité sans lieu à créer (sans connexion, cf. docstring).
IMAGES_NOUVELLES = ("atlantis_capital.jpg", "mu_capital.jpg")

# Un point de TERRE par carte de pays : la zone qui le contient est celle où l'on marche.
ANCRES_PAYS = {
	"lieu:france": (45, 25),      # Massif central
	"lieu:angleterre": (68, 33),  # Midlands
	"lieu:islande": (45, 32),     # hautes terres
	"lieu:australie": (40, 25),   # Regio Deserta
	"lieu:egypte": (40, 30),      # désert occidental
}

# Cité → son pays, sa place SUR LA CARTE DU PAYS (lue sur l'image) et ses sorties :
# nom → (point visé dans la cité, ancre de la zone visée ou None = la plus grande zone).
# Les sorties visent une route qui quitte la carte de la cité ; leur nombre = le nombre de
# cases prises autour de `position` sur le pays.
CITES = {
	# Lyon — au confluent du Rhône et de la Saône, au pied du Jura ; la rive gauche du Rhône
	# est une zone à part de la grille (aucun pont n'y passe) : est et sud y mènent.
	"lieu:lyon": {"pays": "lieu:france", "position": (57, 28), "sorties": {
		"nord": ((30, 3), None), "ouest": ((2, 27), None),
		"est": ((86, 22), (80, 25)), "sud": ((75, 45), (80, 25))}},
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


def rattachee(cite_doc, pays):
	"""Le doc de la cité relu, `_rev` retiré, `lieu_parent` posé s'il manque."""
	doc = sans_rev(cite_doc)
	if not doc.get("lieu_parent"):
		doc["lieu_parent"] = pays
	return doc


def construire(docs, taille_fn, proposer_fn):
	"""(lieux, liens, refus, propositions). `proposer_fn(doc) -> {cells, nav, rapport}` : grille
	d'une cité NEUVE (Pillow côté CLI). `lieux` = docs complets, émis par l'appelant s'ils
	diffèrent du dump."""
	par_id = {d.get("_id"): d for d in docs}
	manquants = [i for i in sorted(set(ANCRES_PAYS) | set(CITES)) if not (par_id.get(i) or {}).get("cells")]
	if manquants:
		return [], [], [f"absent(s) du dump ou sans grille : {', '.join(manquants)}"], {}
	nouvelles, refus = villes_a_creer(IMAGES_NOUVELLES, docs, taille_fn)
	if refus:
		return [], [], refus, {}
	propositions, lieux = {}, []
	for doc in nouvelles:
		propositions[doc["_id"]] = proposer_fn(doc)
		lieux.append(poser_grille(doc, propositions[doc["_id"]]))

	zones_pays = {p: zone_de(par_id[p]["cells"], par_id[p].get("nav") or {}, a)
		for p, a in ANCRES_PAYS.items()}
	libelles = libelles_de(docs)
	liens = []
	for cite_id in sorted(CITES):
		pays = CITES[cite_id]["pays"]
		d, r = connexions_cite(cite_id, par_id[cite_id], zones_pays[pays], libelles[cite_id])
		liens += d
		refus += r
		lieux.append(rattachee(par_id[cite_id], pays))
	return lieux, liens, refus, propositions


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

	def proposer(doc):
		dim = doc["dimensions"]
		return ggi.proposer_pour_image(ggi.trouver_image(doc["image"]), dim["x"], dim["y"], doc)

	lieux, liens, refus, propositions = construire(docs, _taille_image, proposer)
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
		print(f"  {'✚' if neuf else '✎'} {doc['_id']} — {doc.get('label')}"
			f"{' · parent ' + doc['lieu_parent'] if doc.get('lieu_parent') else ''}")
		if neuf:
			chemin = ggi.trouver_image(doc["image"])
			ggi.imprimer_resume(chemin, propositions[doc["_id"]])
			if "--sans-apercu" not in args:
				apercu = os.path.join(ggi.DOSSIER_JSONS, f"{slug(doc['_id'])}_grille_apercu.png")
				ggi.ecrire_apercu(chemin, doc["cells"], apercu, doc.get("nav"),
					propositions[doc["_id"]]["rapport"])
				print(f"    aperçu : {os.path.relpath(apercu, RACINE)}")

	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(emis, f, ensure_ascii=False, indent=2)
		f.write("\n")
	n_liens = sum(1 for d in emis if d.get("type") == "connection")
	print(f"\n✎ {os.path.relpath(SORTIE, RACINE)} — {len(emis) - n_liens} lieu(x), {n_liens} connexion(s)")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
