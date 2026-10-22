"""Camelot en jeu, et Londres recalée sur sa forteresse : UN fichier à importer.

Lore : docs/lore/cites/20261021_camelot_winchester.md (cité fondée par Arthur, Winchester
bourg voisin au sud, accès tôt par Douvres). Image : towns/camelot_capital.jpg.

Camelot
- Le doc est celui de `gen_villes_images.villes_a_creer` (forme de `lieu:rhemi`, cases de la
  taille de celles des villes en base), avec la PREMIÈRE PASSE de grille de
  `gen_grille_image.proposer_pour_image`, puis trois RETOUCHES (ci-dessous). `sous_categorie`
  « ville » et non « capitale » : Londres reste la capitale de l'île (champ sans effet en jeu).
- Retouches de la grille :
  1. `COUPE_REMPART` → 0 : la lecture des rues a pris le chemin de ronde du rempart sud pour
     une rue, et l'on passait de la ville au bourg PAR-DESSUS le mur. Coupe minimale entre le
     parvis et le bourg, restreinte aux lignes du rempart (33-36), calculée une fois et
     recopiée ici.
  2. `PONT_OUEST` : le pont devant la porte ouest était fermé (murs nav, tablier rattaché à la
     tour). Son tablier est rouvert vers la rive et le pré, et fermé côté ville.
  3. Le bourg de Winchester n'a pas d'enceinte : les murs nav qui le séparaient de la
     campagne sont effacés (entre cases praticables seulement).
  Résultat : deux zones, le DEDANS (zone du parvis) et le DEHORS (campagne + bourg), reliées
  par les seules portes de rempart. Le script refuse d'écrire si ce n'est plus vrai.
- Portes de rempart (forme de l'éditeur, `_ptDocs`, cinq docs par porte) : porte ouest (sur
  le pont) et porte de Winchester (vers le bourg), chaque case au plus près de son arche.
  Images réutilisées : toutes les `porte_de_ville_*` servent déjà (Calais et Bucarest en
  partagent avec Auxerre).
- Sur la carte d'Angleterre, Camelot est là où est Winchester : coordonnées réelles recalées
  sur Londres et Glastonbury, puis remontées dans les terres (la case brute tombe dans
  l'estuaire de Southampton). Ses trois entrées arrivent DEHORS.

Londres (demande de l'Auteur, 22/10/2026)
- Ses connexions descendent sur le corps de la forteresse dessinée (cases `LONDRES_PAYS`),
  jusqu'à l'entrée du fleuve au coin sud-ouest, et la COUVRENT : une connexion par case.
  Les quatre liens existants gardent leur `_id` (relus du dump, seul leur nœud Angleterre
  bouge) ; les autres sont neufs. Chaque connexion a sa PROPRE case d'arrivée dans Londres :
  partagée, cette case porterait plusieurs boutons « Angleterre » menant ailleurs.

Usage : python dev/gen_camelot.py [--dump jsons/telluris-dump-….json] [--sans-apercu]
Sortie : jsons/camelot_a_importer.json (+ jsons/camelot_grille_apercu.png)
"""

import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_grille_image as ggi  # noqa: E402
from dev import gen_villes_images as gvi  # noqa: E402
from utils.lieux import VALID_MOVES, nav_allows  # noqa: E402

IMAGE = "camelot_capital.jpg"
CITE = "lieu:camelot"
PAYS = "lieu:angleterre"
LONDRES = "lieu:london"
SORTIE = os.path.join(ggi.DOSSIER_JSONS, "camelot_a_importer.json")

# Repères de zone : le parvis de la cathédrale (DEDANS), le bourg et la campagne (DEHORS).
PARVIS = (45, 23)
BOURG = (50, 42)
CAMPAGNE = (10, 40)

COUPE_REMPART = ((38, 33), (41, 33), (47, 34))
# Tablier du pont ouest, de la porte vers la rive opposée ; ses deux bouts DEHORS.
PONT_OUEST = ((20, 32), (19, 33), (18, 33))
PONT_BOUTS = ((21, 32), (17, 34))

# (nom, slug, (case dehors, case dedans), image extérieure, image intérieure)
PORTES = (
	("Porte ouest", "ouest", ((21, 32), (22, 28)),
	 "porte_de_ville_pont_exterieur04.png", "porte_de_ville_pont_interieur04.png"),
	("Porte de Winchester", "de_winchester", ((56, 35), (56, 32)),
	 "porte_de_ville_exterieure08.jpg", "porte_de_ville_interieur16.png"),
)
PORTE_TYPE = "poste de garde"
PORTE_LABEL_DEHORS = "au-delà des remparts"

# (suffixe d'_id, libellé, case sur la carte d'Angleterre, case dans Camelot — DEHORS)
ENTREES = (
	("ouest", "Camelot — par le pont de l'ouest", (63, 38), (16, 34)),
	("sud", "Camelot — par le bourg de Winchester", (64, 39), (50, 42)),
	("est", "Camelot — par l'est", (65, 38), (78, 27)),
)

# Londres : le corps de la forteresse sur la carte d'Angleterre ([68, 37] est une case
# enclavée par les murs du fleuve, exclue), groupé par côté. Chaque groupe arrive dans Londres
# le long de sa case d'origine : cases voisines, une par connexion.
#   côté : (libellé, cases Angleterre, case d'arrivée de référence dans Londres, pas)
LONDRES_COTES = {
	"ouest": ("Londres — par l'ouest", ((68, 35), (68, 36), (69, 35), (69, 36)), (5, 22), (0, 1)),
	"fleuve": ("Londres — par le fleuve", ((69, 37), (70, 37)), (38, 34), (1, 0)),
	"sud": ("Londres — par le sud", ((71, 37), (72, 37), (73, 37)), (14, 43), (1, 0)),
	"nord": ("Londres — par le nord", ((70, 35), (71, 35), (72, 35), (73, 35)), (30, 5), (1, 0)),
	"pont": ("Londres — par le pont", ((70, 36), (71, 36)), (52, 30), (1, 0)),
	"est": ("Londres — par l'est", ((72, 36), (73, 36)), (79, 24), (0, 1)),
}
# Les quatre liens existants : leur `_id` et leur nœud Londres restent, la case Angleterre
# devient celle-ci.
LONDRES_EXISTANTS = {
	"link:angleterre_to_london_ouest": (68, 36),
	"link:angleterre_to_london_nord": (71, 35),
	"link:angleterre_to_london_sud": (72, 37),
	"link:angleterre_to_london_est": (73, 36),
}


def zone_de(cells, nav, depart) -> set:
	"""Cases praticables (valeur 1, murs nav respectés) jointes à `depart`."""
	hauteur, largeur = len(cells), len(cells[0])
	x0, y0 = depart
	if cells[y0][x0] != 1:
		return set()
	vues, pile = {depart}, [depart]
	while pile:
		x, y = pile.pop()
		for dx in (-1, 0, 1):
			for dy in (-1, 0, 1):
				nx, ny = x + dx, y + dy
				if ((dx or dy) and 0 <= nx < largeur and 0 <= ny < hauteur
						and (nx, ny) not in vues and cells[ny][nx] == 1
						and nav_allows(nav, x, y, dx, dy)):
					vues.add((nx, ny))
					pile.append((nx, ny))
	return vues


def _bit(dx, dy) -> int:
	return next(b for b, ddx, ddy, _op in VALID_MOVES if (ddx, ddy) == (dx, dy))


def _poser(nav, a, b, ferme: bool) -> None:
	"""Ferme ou ouvre le pas a ↔ b, des DEUX côtés (le pas est vérifié des deux)."""
	for (x, y), (nx, ny) in ((a, b), (b, a)):
		cle, bit = f"{x},{y}", _bit(nx - x, ny - y)
		valeur = (nav.get(cle, 0) | bit) if ferme else (nav.get(cle, 0) & ~bit)
		if valeur:
			nav[cle] = valeur
		else:
			nav.pop(cle, None)


def _voisins(case):
	x, y = case
	return [(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]


def retoucher(doc: dict) -> dict:
	"""Les trois retouches de la première passe (cf. docstring du module)."""
	cells, nav = doc["cells"], doc["nav"]
	for x, y in COUPE_REMPART:
		cells[y][x] = 0

	dedans = zone_de(cells, nav, PARVIS)
	tablier = set(PONT_OUEST)
	for x, y in PONT_OUEST:
		cells[y][x] = 1
	for case in PONT_OUEST:
		for n in _voisins(case):
			if n in tablier or n in PONT_BOUTS:
				_poser(nav, case, n, ferme=False)
			elif n in dedans:
				_poser(nav, case, n, ferme=True)

	bourg = zone_de(cells, nav, BOURG)
	campagne = zone_de(cells, nav, CAMPAGNE)
	for case in sorted(bourg):
		for n in _voisins(case):
			if n in campagne:
				_poser(nav, case, n, ferme=False)
	return doc


def portes(cite: str) -> list:
	"""Les cinq docs de chaque porte, forme de `_ptDocs` (admin_map_editor.html)."""
	base_cite = cite.split(":", 1)[1]
	sortie = []
	for nom, slug, (dehors, dedans), img_ext, img_int in PORTES:
		base = f"{base_cite}_porte_{slug}"
		ext, int_ = f"lieu:{base}_exterieur", f"lieu:{base}_interieur"
		meta = {"type": PORTE_TYPE, "status": "ouvert"}
		sortie += [
			{"_id": ext, "type": "lieu", "label": f"{nom} — extérieur", "image": img_ext,
			 "categorie": "Porte de rempart", "lieu_parent": cite},
			{"_id": int_, "type": "lieu", "label": f"{nom} — intérieur", "image": img_int,
			 "categorie": "Porte de rempart", "lieu_parent": cite},
			{"_id": f"link:{base}_carte_exterieur", "type": "connection",
			 "nodes": [{"lieu": cite, "pos": list(dehors), "label": PORTE_LABEL_DEHORS},
					   {"lieu": ext, "pos": [0, 0]}], "metadata": dict(meta)},
			{"_id": f"link:{base}_carte_interieur", "type": "connection",
			 "nodes": [{"lieu": cite, "pos": list(dedans)}, {"lieu": int_, "pos": [0, 0]}],
			 "metadata": dict(meta)},
			{"_id": f"link:{base}_passage", "type": "connection",
			 "nodes": [{"lieu": ext, "pos": [0, 0]}, {"lieu": int_, "pos": [0, 0]}],
			 "metadata": dict(meta)},
		]
	return sortie


def connexion_camelot(suffixe: str, label: str, case_pays, case_ville) -> dict:
	return {
		"_id": f"link:angleterre_to_camelot_{suffixe}",
		"type": "connection",
		"nodes": [
			{"lieu": PAYS, "pos": list(case_pays)},
			{"lieu": CITE, "pos": list(case_ville), "label": label},
		],
		"metadata": {"type": "chemin", "status": "ouvert"},
	}


def _arrivee(zone: set, depart, pas, prises: set):
	"""Première case de `zone` libre, en partant de `depart` dans la direction `pas`, puis
	dans l'autre sens."""
	for k in range(0, 40):
		for signe in (1, -1):
			case = (depart[0] + signe * k * pas[0], depart[1] + signe * k * pas[1])
			if case in zone and case not in prises:
				return case
	return None


def connexions_londres(par_id: dict, erreurs: list) -> list:
	londres = par_id[LONDRES]
	zone = zone_de(londres["cells"], londres.get("nav") or {}, (5, 22))
	existants = {}
	for lid, case_pays in LONDRES_EXISTANTS.items():
		doc = copy.deepcopy(par_id[lid])
		doc.pop("_rev", None)
		noeud = next(n for n in doc["nodes"] if n["lieu"] == PAYS)
		noeud["pos"] = list(case_pays)
		existants[tuple(case_pays)] = doc
	prises = {tuple(next(n["pos"] for n in d["nodes"] if n["lieu"] == LONDRES))
		for d in existants.values()}
	sortie = list(existants.values())
	for cote, (label, cases, depart, pas) in LONDRES_COTES.items():
		neuves = [c for c in cases if tuple(c) not in existants]
		for i, case_pays in enumerate(neuves, 1):
			arrivee = _arrivee(zone, depart, pas, prises)
			if arrivee is None:
				erreurs.append(f"Londres {cote} : aucune case d'arrivée libre")
				continue
			prises.add(arrivee)
			sortie.append({
				"_id": f"link:angleterre_to_london_{cote}_{i:02d}",
				"type": "connection",
				"nodes": [
					{"lieu": PAYS, "pos": list(case_pays)},
					{"lieu": LONDRES, "pos": list(arrivee), "label": label},
				],
				"metadata": {"type": "chemin", "status": "ouvert"},
			})
	return sortie


def main() -> int:
	args = sys.argv[1:]
	chemin_dump = args[args.index("--dump") + 1] if "--dump" in args else None
	docs = ggi.charger_dump(chemin_dump)
	par_id = {d.get("_id"): d for d in docs}
	manquants = [i for i in (PAYS, LONDRES, *LONDRES_EXISTANTS) if i not in par_id]
	if manquants:
		print("✗ absents du dump : " + ", ".join(manquants))
		return 1

	a_creer, refus = gvi.villes_a_creer([IMAGE], docs, gvi._taille_image)
	if refus or not a_creer:
		print("✗ " + ("; ".join(refus) or f"{IMAGE} est déjà citée par un lieu : rien à créer."))
		return 1
	doc = a_creer[0]
	doc.update({"label": "Camelot", "sous_categorie": "ville", "lieu_parent": PAYS})
	cols, rows = doc["dimensions"]["x"], doc["dimensions"]["y"]
	chemin = ggi.trouver_image(IMAGE)
	proposition = ggi.proposer_pour_image(chemin, cols, rows, doc, frozenset(), "ville")
	doc = retoucher(gvi.poser_grille(doc, proposition))

	cells, nav = doc["cells"], doc["nav"]
	dedans, dehors = zone_de(cells, nav, PARVIS), zone_de(cells, nav, CAMPAGNE)
	erreurs = []
	if dedans & dehors:
		erreurs.append("le dedans et le dehors communiquent sans porte")
	for nom, _slug, (c_dehors, c_dedans), _ie, _ii in PORTES:
		if c_dehors not in dehors:
			erreurs.append(f"{nom} : case {c_dehors} hors du dehors")
		if c_dedans not in dedans:
			erreurs.append(f"{nom} : case {c_dedans} hors du dedans")
	if BOURG not in dehors or PONT_BOUTS[1] not in dehors:
		erreurs.append("le bourg ou la rive du pont n'est pas dehors")

	pays = par_id[PAYS]
	zone_pays = zone_de(pays["cells"], pays.get("nav") or {}, (78, 38))  # depuis Douvres
	for s, _l, p, c in ENTREES:
		if tuple(c) not in dehors:
			erreurs.append(f"entrée {s} : case {c} hors du dehors")
		if tuple(p) not in zone_pays:
			erreurs.append(f"entrée {s} : case {p} injoignable depuis Douvres")
	for _label, cases, _d, _p in LONDRES_COTES.values():
		erreurs += [f"Londres : case {c} injoignable depuis Douvres"
			for c in cases if tuple(c) not in zone_pays]
	tous = [c for _l, cases, _d, _p in LONDRES_COTES.values() for c in cases]
	if sorted(LONDRES_EXISTANTS.values()) != sorted(c for c in tous if c in LONDRES_EXISTANTS.values()):
		erreurs.append("un lien existant de Londres n'a pas de case dans LONDRES_COTES")

	neufs = [doc] + portes(CITE) + [connexion_camelot(*e) for e in ENTREES]
	erreurs += [f"{d['_id']} déjà en base" for d in neufs if d["_id"] in par_id]
	londres = connexions_londres(par_id, erreurs)
	erreurs += [f"{d['_id']} déjà en base" for d in londres
		if d["_id"] in par_id and d["_id"] not in LONDRES_EXISTANTS]
	if erreurs:
		print("✗ " + "\n✗ ".join(erreurs))
		return 1

	sortie = neufs + londres
	if "--sans-apercu" not in args:
		ggi.ecrire_apercu(chemin, cells, os.path.join(ggi.DOSSIER_JSONS, "camelot_grille_apercu.png"),
			nav, proposition["rapport"])
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"{CITE} {cols}×{rows} · dedans {len(dedans)} cases · dehors {len(dehors)} cases · "
		f"{len(PORTES)} porte(s) · Londres {len(londres)} connexion(s) · "
		f"{len(sortie)} doc(s) → {os.path.relpath(SORTIE, ggi.RACINE)}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
