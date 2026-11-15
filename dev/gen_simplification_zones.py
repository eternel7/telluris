#!/usr/bin/env python
"""Simplification des zones d'influence de la France et de l'Afrique du Nord (Auteur, 15/11).

Écrit UN fichier `jsons/simplification_zones_a_importer.json` (CLAUDE.md §18) : `lieu:france` et
`lieu:afrique_du_nord` RELUS du dump, seul `zone_influences` change (PUT complet, §11).

A. Afrique du Nord — un placement entièrement recouvert par d'autres placements de la MÊME zone
   est retiré (glouton, du plus petit au plus grand) : l'ensemble des zones de CHAQUE case reste
   identique. Seul effet : une zone qui comptait double face à une autre ne compte plus qu'une fois.
B. France, `zone:plaine_ouverte` — pavage de rectangles 5×5 redessiné en grands rectangles :
   OBLIGATOIRE là où la plaine est seule (ou avec l'eau), FACULTATIVE sous un autre biome,
   INTERDITE ailleurs. Aucune case ne gagne la plaine, aucune case ne reste sans zone ; la plaine
   sort du mélange sous quelques collines/forêts (elle n'a aucun défaut ni rencontre propre, et
   son intensité est la plus basse : la fréquence des événements ne bouge pas).
C. France, `zone:tres_dangereuse` — deux ellipses qui se touchent deviennent UNE ellipse (même
   `profil_weights`), ajustée à leur union. Contraintes : le 3×3 de la Bête du Gévaudan reste
   couvert, aucune case de `zone:zone_danger_3` (géants du Mont, cf. gen_geants_mont_saint_michel)
   n'est touchée, aucune case ne reste sans zone.

Les zones `zone_danger_N` ne sont PAS touchées (la seule posée, en France, porte le Géant du Mont).
Rien à simplifier ⇒ le lieu n'est pas émis ; rien du tout ⇒ aucun fichier.

    python dev/gen_simplification_zones.py [--dump jsons/telluris-dump-….json] [--sortie …]
"""

import argparse
import glob
import json
import math
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from utils.zones import compute_bbox, compute_zone_intensity  # noqa: E402

SORTIE = os.path.join(RACINE, "jsons", "simplification_zones_a_importer.json")
FRANCE = "lieu:france"
AFRIQUE_DU_NORD = "lieu:afrique_du_nord"
PLAINE = "zone:plaine_ouverte"
TRES_DANGEREUSE = "zone:tres_dangereuse"
DANGER_3 = "zone:zone_danger_3"
# Zones d'eau de la France : leur superposition est normale (Auteur, 15/11).
EAU_FRANCE = {"zone:riviere", "zone:marais"}
# Bête du Gévaudan : le 3×3 autour de sa position doit rester en zone très dangereuse
# (dev/gen_carte_bete_gevaudan.py, verrouillé par test_la_bete_est_situee_dans_une_zone_ou_elle_rode).
BETE = (55, 32)


def dernier_dump() -> str:
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		sys.exit("Aucun dump jsons/telluris-dump-*.json")
	return dumps[-1]


# ── Géométrie sur la grille (cases entières, même test que le moteur) ──────────────────────

def dedans(p: dict, x: int, y: int) -> bool:
	return compute_zone_intensity(x, y, p, {"intensite_max": 1.0}) > 0.0


def cases_de(p: dict, larg: int, haut: int) -> set:
	b = p.get("bbox") or compute_bbox(p)
	xs = range(max(0, math.floor(b["x_min"])), min(larg, math.ceil(b["x_max"]) + 1))
	ys = range(max(0, math.floor(b["y_min"])), min(haut, math.ceil(b["y_max"]) + 1))
	return {(x, y) for x in xs for y in ys if dedans(p, x, y)}


def zones_par_case(placements: list, larg: int, haut: int) -> dict:
	"""{case: frozenset des zones} — ce que voit le moteur sur chaque case (multiplicité exclue)."""
	out: dict = {}
	for p in placements:
		for c in cases_de(p, larg, haut):
			out.setdefault(c, set()).add(p["zone"])
	return {c: frozenset(z) for c, z in out.items()}


def placement(zone: str, cx: float, cy: float, w: float, h: float, forme: str, rot: float = 0,
			  extra: dict | None = None) -> dict:
	p = {"x": cx, "y": cy, "w": w, "h": h, "rot": rot, "forme": forme, "zone": zone}
	p["bbox"] = compute_bbox(p)
	if extra:
		p.update(extra)
	return p


def rectangle_cases(zone: str, x0: int, y0: int, w: int, h: int) -> dict:
	"""Rectangle couvrant exactement les cases x0..x0+w-1 × y0..y0+h-1 (centre au milieu, demi-
	côtés w/2 : bord à une demi-case des cases extrêmes, comme les 5×5 d'origine)."""
	return placement(zone, x0 + (w - 1) / 2, y0 + (h - 1) / 2, w, h, "rectangle")


# ── A. Doublons d'une même zone ────────────────────────────────────────────────────────────

def retirer_doublons(placements: list, larg: int, haut: int) -> tuple[list, list]:
	ref = zones_par_case(placements, larg, haut)
	cases = [cases_de(p, larg, haut) for p in placements]
	garde = list(range(len(placements)))
	retires = []
	for i in sorted(range(len(placements)), key=lambda i: (len(cases[i]), i)):
		essai = [j for j in garde if j != i]
		if zones_par_case([placements[j] for j in essai], larg, haut) == ref:
			garde, retires = essai, retires + [i]
	return [placements[j] for j in garde], sorted(retires)


# ── B. Plaine redessinée ───────────────────────────────────────────────────────────────────

def couverture_tolerante(obligatoires: set, facultatives: set) -> list:
	"""Rectangles disjoints, tirés dans obligatoires ∪ facultatives, jusqu'à couvrir toutes les
	obligatoires ; à chaque pas, celui qui en couvre le plus (ex æquo : premier trouvé, ordre fixe)."""
	reste = set(obligatoires)
	libres = set(obligatoires) | set(facultatives)
	rects = []
	while reste:
		meilleur = None
		for (x, y) in sorted(libres):
			larg_max = 0
			while (x + larg_max, y) in libres:
				larg_max += 1
			w, h = larg_max, 0
			while True:
				ww = 0
				while ww < w and (x + ww, y + h) in libres:
					ww += 1
				if ww == 0:
					break
				w, h = ww, h + 1
				gain = sum(1 for i in range(w) for j in range(h) if (x + i, y + j) in reste)
				if meilleur is None or gain > meilleur[0]:
					meilleur = (gain, x, y, w, h)
		_, x, y, w, h = meilleur
		rects.append((x, y, w, h))
		for i in range(w):
			for j in range(h):
				libres.discard((x + i, y + j))
				reste.discard((x + i, y + j))
	return rects


def redessiner_plaine(placements: list, larg: int, haut: int) -> list:
	autres = [p for p in placements if p["zone"] != PLAINE]
	plaines = [p for p in placements if p["zone"] == PLAINE]
	cases_plaine = set().union(*(cases_de(p, larg, haut) for p in plaines)) if plaines else set()
	sous_biome = set()
	for p in autres:
		if p["zone"] not in EAU_FRANCE:
			sous_biome |= cases_de(p, larg, haut)
	obligatoires = cases_plaine - sous_biome
	facultatives = cases_plaine & sous_biome
	neufs = [rectangle_cases(PLAINE, *r) for r in couverture_tolerante(obligatoires, facultatives)]
	if len(neufs) >= len(plaines):
		return placements  # aucun gain : on ne touche à rien (rejeu idempotent)
	# Les plaines reprennent la place de la première plaine d'origine (ordre des autres intact).
	premier = next(i for i, p in enumerate(placements) if p["zone"] == PLAINE)
	avant = [p for p in placements[:premier] if p["zone"] != PLAINE]
	apres = [p for p in placements[premier:] if p["zone"] != PLAINE]
	return avant + neufs + apres


# ── C. Ellipses très dangereuses qui se touchent ───────────────────────────────────────────

def _voisines(a: set, b: set) -> bool:
	return any((x + dx, y + dy) in b for (x, y) in a for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)))


def ajuster_ellipse(union: set, interdites: set, imposees: set, modele: dict, larg: int, haut: int):
	"""Ellipse (centre au demi-pas, axes au demi-pas, rotation par 15°) qui reproduit au mieux
	`union` : contient `imposees`, évite `interdites`, minimise l'écart symétrique puis l'aire."""
	xs = [x for x, _ in union]
	ys = [y for _, y in union]
	cx0, cy0 = sum(xs) / len(xs), sum(ys) / len(ys)
	meilleur = None
	for dcx in range(-2, 3):
		for dcy in range(-2, 3):
			cx = round((cx0 + dcx / 2) * 2) / 2
			cy = round((cy0 + dcy / 2) * 2) / 2
			for rot in range(0, 180, 15):
				for w2 in range(6, 25):
					for h2 in range(6, 17):
						if h2 > w2:
							continue
						p = placement(TRES_DANGEREUSE, cx, cy, w2 / 2, h2 / 2, "ellipse", rot)
						c = cases_de(p, larg, haut)
						if not imposees <= c or c & interdites:
							continue
						cle = (len(c ^ union), len(c))
						if meilleur is None or cle < meilleur[0]:
							meilleur = (cle, p, c)
	return meilleur


def fusionner_paires(placements: list, larg: int, haut: int) -> tuple[list, list]:
	idx = [i for i, p in enumerate(placements) if p["zone"] == TRES_DANGEREUSE]
	cases = {i: cases_de(placements[i], larg, haut) for i in idx}
	# Blocs de placements qui se touchent (union-find).
	parent = {i: i for i in idx}

	def racine(i):
		while parent[i] != i:
			parent[i] = parent[parent[i]]
			i = parent[i]
		return i
	for a in idx:
		for b in idx:
			if a < b and _voisines(cases[a], cases[b]):
				parent[racine(b)] = racine(a)
	blocs: dict = {}
	for i in idx:
		blocs.setdefault(racine(i), []).append(i)
	danger3 = set().union(*(cases_de(p, larg, haut) for p in placements if p["zone"] == DANGER_3))
	bete = {(BETE[0] + dx, BETE[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
	remplace: dict = {}
	rapport = []
	for membres in blocs.values():
		if len(membres) < 2:
			continue
		poids = {json.dumps(placements[i].get("profil_weights"), sort_keys=True) for i in membres}
		if len(poids) != 1:
			rapport.append((membres, "profils différents, gardé tel quel"))
			continue
		union = set().union(*(cases[i] for i in membres))
		# Une case qui n'a QUE cette zone ne doit pas se retrouver sans zone : elle est imposée.
		autres = set()
		for j, p in enumerate(placements):
			if j not in membres:
				autres |= cases_de(p, larg, haut)
		imposees = (union - autres) | (bete & union)
		# Une case qui gagnerait la zone très dangereuse sans l'avoir : tolérée (minimisée), sauf
		# les géants du Mont, interdits.
		res = ajuster_ellipse(union, danger3, imposees, placements[membres[0]], larg, haut)
		if not res:
			rapport.append((membres, "aucune ellipse ne respecte les contraintes, gardé tel quel"))
			continue
		(ecart, _), p, c = res
		extra = {k: v for k, v in placements[membres[0]].items()
				 if k not in ("x", "y", "w", "h", "rot", "forme", "zone", "bbox")}
		p.update(extra)
		remplace[min(membres)] = p
		for m in membres:
			remplace.setdefault(m, None)
		rapport.append((membres, f"→ 1 ellipse, {ecart} case(s) changée(s) en bordure "
								 f"(+{len(c - union)} / −{len(union - c)})"))
	out = []
	for i, p in enumerate(placements):
		if i in remplace:
			if remplace[i] is not None:
				out.append(remplace[i])
		else:
			out.append(p)
	return out, rapport


# ── Contrôles et sortie ────────────────────────────────────────────────────────────────────

def controler(avant: list, apres: list, larg: int, haut: int, nom: str) -> None:
	za, zb = zones_par_case(avant, larg, haut), zones_par_case(apres, larg, haut)
	trous = [c for c in za if c not in zb]
	assert not trous, f"{nom} : {len(trous)} case(s) sans zone après simplification"
	for c, zs in za.items():
		if DANGER_3 in zs or DANGER_3 in zb.get(c, ()):
			assert (DANGER_3 in zs) == (DANGER_3 in zb[c]), f"{nom} : zone_danger_3 modifiée en {c}"
	for c, zs in zb.items():
		assert not (DANGER_3 in zs and TRES_DANGEREUSE in zs), f"{nom} : géants du Mont touchés en {c}"


def stats(placements: list, larg: int, haut: int) -> tuple[int, int]:
	compte: dict = {}
	for p in placements:
		for c in cases_de(p, larg, haut):
			compte[c] = compte.get(c, 0) + 1
	return len(placements), sum(1 for n in compte.values() if n >= 2)


def main(argv=None) -> int:
	ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	ap.add_argument("--dump", default=None)
	ap.add_argument("--sortie", default=SORTIE)
	args = ap.parse_args(argv)
	dump = args.dump or dernier_dump()
	with open(dump, encoding="utf-8") as f:
		docs = {d["_id"]: d for d in json.load(f)["docs"]}
	print(f"Dump : {os.path.basename(dump)}")
	sortie = []

	adn = docs[AFRIQUE_DU_NORD]
	larg, haut = adn["dimensions"]["x"], adn["dimensions"]["y"]
	zi, retires = retirer_doublons(adn["zone_influences"], larg, haut)
	assert zones_par_case(zi, larg, haut) == zones_par_case(adn["zone_influences"], larg, haut)
	if retires:
		n0, s0 = stats(adn["zone_influences"], larg, haut)
		n1, s1 = stats(zi, larg, haut)
		print(f"A. Afrique du Nord : {n0} → {n1} placements (retirés : {retires}) ; cases ≥ 2 zones : {s0} → {s1}")
		doc = {k: v for k, v in adn.items() if k != "_rev"}
		doc["zone_influences"] = zi
		sortie.append(doc)
	else:
		print("A. Afrique du Nord : rien à retirer")

	fr = docs[FRANCE]
	larg, haut = fr["dimensions"]["x"], fr["dimensions"]["y"]
	origine = fr["zone_influences"]
	n0, s0 = stats(origine, larg, haut)
	zi = redessiner_plaine(origine, larg, haut)
	nb_pl = (sum(p["zone"] == PLAINE for p in origine), sum(p["zone"] == PLAINE for p in zi))
	print(f"B. France, plaine : {nb_pl[0]} → {nb_pl[1]} placements")
	zi, rapport = fusionner_paires(zi, larg, haut)
	nb_td = (sum(p["zone"] == TRES_DANGEREUSE for p in origine), sum(p["zone"] == TRES_DANGEREUSE for p in zi))
	print(f"C. France, très dangereuse : {nb_td[0]} → {nb_td[1]} placements")
	for membres, texte in rapport:
		print(f"   {membres} {texte}")
	controler(origine, zi, larg, haut, FRANCE)
	if zi != origine:
		n1, s1 = stats(zi, larg, haut)
		za, zb = zones_par_case(origine, larg, haut), zones_par_case(zi, larg, haut)
		changees = sum(1 for c in za if za[c] != zb.get(c))
		print(f"   France : {n0} → {n1} placements ; cases ≥ 2 zones : {s0} → {s1} ; "
			  f"cases dont les zones changent : {changees}")
		doc = {k: v for k, v in fr.items() if k != "_rev"}
		doc["zone_influences"] = zi
		sortie.append(doc)

	if not sortie:
		print("Rien à émettre.")
		return 0
	with open(args.sortie, "w", encoding="utf-8") as f:
		f.write(json.dumps(sortie, ensure_ascii=False, indent=2) + "\n")
	print(f"→ {os.path.relpath(args.sortie, RACINE)} ({len(sortie)} docs)")
	return 0


if __name__ == "__main__":
	sys.exit(main())
