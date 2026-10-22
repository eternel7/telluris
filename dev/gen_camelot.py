"""Camelot en jeu : le doc `lieu:camelot` et ses trois connexions à la carte d'Angleterre.

Lore : docs/lore/cites/20261021_camelot_winchester.md (cité fondée par Arthur, Winchester
bourg voisin au sud, accès tôt par Douvres). Image : towns/camelot_capital.jpg.

- Le doc est celui de `gen_villes_images.villes_a_creer` (forme de `lieu:rhemi`, cases de la
  taille de celles des villes en base), avec la PREMIÈRE PASSE de grille de
  `gen_grille_image.proposer_pour_image` — à retoucher dans l'éditeur. `sous_categorie`
  « ville » et non « capitale » : Londres reste la capitale de l'île (champ sans effet en jeu).
- Sur la carte d'Angleterre, Camelot est posée là où est Winchester : coordonnées réelles
  recalées sur Londres et Glastonbury, puis remontées dans les terres (la case brute tombe
  dans l'estuaire de Southampton).
- ⚠️ La grille sépare la campagne du dedans (enceinte fermée par nav, portes de rempart à poser
  à l'éditeur) : les trois entrées sont donc posées dans la zone de la VILLE et de son bourg
  (porte ouest côté intérieur, bourg de Winchester, est du bourg). Le script refuse d'écrire si
  une entrée tombe hors de la zone praticable qui contient le parvis.

Usage : python dev/gen_camelot.py [--dump jsons/telluris-dump-….json] [--sans-apercu]
Sortie : jsons/camelot_a_importer.json (+ jsons/camelot_grille_apercu.png)
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_grille_image as ggi  # noqa: E402
from dev import gen_villes_images as gvi  # noqa: E402
from utils.lieux import nav_allows  # noqa: E402

IMAGE = "camelot_capital.jpg"
PAYS = "lieu:angleterre"
SORTIE = os.path.join(ggi.DOSSIER_JSONS, "camelot_a_importer.json")

# Case du parvis de la cathédrale : la zone praticable qui la contient est « la ville ».
PARVIS = (45, 23)
# (suffixe d'_id, libellé, case sur la carte d'Angleterre, case dans Camelot)
ENTREES = (
	("ouest", "Camelot — par la porte ouest", (63, 38), (22, 28)),
	("sud", "Camelot — par le bourg de Winchester", (64, 39), (50, 42)),
	("est", "Camelot — par l'est", (65, 38), (72, 40)),
)


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


def connexion(suffixe: str, label: str, case_pays, case_ville) -> dict:
	return {
		"_id": f"link:angleterre_to_camelot_{suffixe}",
		"type": "connection",
		"nodes": [
			{"lieu": PAYS, "pos": list(case_pays)},
			{"lieu": "lieu:camelot", "pos": list(case_ville), "label": label},
		],
		"metadata": {"type": "chemin", "status": "ouvert"},
	}


def main() -> int:
	args = sys.argv[1:]
	chemin_dump = args[args.index("--dump") + 1] if "--dump" in args else None
	docs = ggi.charger_dump(chemin_dump)
	par_id = {d.get("_id"): d for d in docs}
	if PAYS not in par_id:
		print(f"✗ {PAYS} absent du dump.")
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
	doc = gvi.poser_grille(doc, proposition)

	ville = zone_de(doc["cells"], doc["nav"], PARVIS)
	pays = par_id[PAYS]
	erreurs = [f"entrée {s} : case {c} hors de la zone de la ville"
		for s, _l, _p, c in ENTREES if tuple(c) not in ville]
	erreurs += [f"entrée {s} : case {p} non praticable sur {PAYS}"
		for s, _l, p, _c in ENTREES if pays["cells"][p[1]][p[0]] != 1]
	sortie = [doc] + [connexion(*e) for e in ENTREES]
	erreurs += [f"{d['_id']} déjà en base" for d in sortie if d["_id"] in par_id]
	if erreurs:
		print("✗ " + "\n✗ ".join(erreurs))
		return 1

	if "--sans-apercu" not in args:
		ggi.ecrire_apercu(chemin, doc["cells"], os.path.join(ggi.DOSSIER_JSONS, "camelot_grille_apercu.png"),
			doc["nav"], proposition["rapport"])
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"{doc['_id']} {cols}×{rows} · zone de la ville {len(ville)} cases · "
		f"{len(sortie)} doc(s) → {os.path.relpath(SORTIE, ggi.RACINE)}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
