#!/usr/bin/env python
"""Réduction forte des zones d'influence des cartes de pays (Auteur, 15/11).

Écrit UN fichier `jsons/reduction_zones_a_importer.json` (CLAUDE.md §18) : les lieux de `LIEUX`
RELUS du dump, seul `zone_influences` change (PUT complet, §11).

Calcul, zone par zone (cases entières, même test que le moteur) :
  1. GRAPPES — les placements d'une même zone distants d'au plus `ECART` cases sont regroupés ;
  2. RECTANGLE ENGLOBANT de chaque grappe, recoupé en deux (guillotine, coupe qui déborde le moins)
     tant que plus de `SEUIL` de ses cases TERRESTRES n'avaient pas cette zone ;
  3. la MER ne compte pas : composantes ≥ `MER_MIN` cases sans aucune zone. La côte d'une carte de
     pays est murée (`grille_image`, profil `pays`) et les traversées ont leurs propres cartes :
     une zone qui déborde sur la mer n'y est jamais vécue ;
  4. une zone qui n'y gagne rien garde ses formes d'origine.
Rejeu idempotent : un lieu dont le fond couvre déjà toute la carte est DÉJÀ réduit et n'est pas
émis (sans les cases sans zone, la mer ne se distinguerait plus des terres).

Familles (décisions de l'Auteur) :
  - RELIEF et FORÊTS : réglage « moyen » (`ECART` 3, `SEUIL` 40 %) ;
  - FOND (plaine de la France, désert de l'Afrique et de l'Égypte) : UN rectangle couvrant toute la
    carte — il se superpose à tout le reste, ce qui est accepté ;
  - tout le reste (rivières, fleuves, delta, erg, steppes, oasis…) : intact.
`zone:tres_dangereuse` et `zone:zone_danger_N` ne sont JAMAIS touchées. Les villes sont hors champ
(leurs formes suivent rues, cours d'eau et zones habitables).

Garanties contrôlées au lancement : aucune case ne perd une zone qu'elle avait ; les zones
intouchables gardent exactement leurs placements ; aucune zone ne compte plus de placements.
Effet de bord voulu : deux placements d'une même zone qui se chevauchaient comptaient double
(table d'événements, `modificateurs` sommés) ; fusionnés, ils ne comptent plus qu'une fois.

    python dev/gen_reduction_zones.py [--dump jsons/telluris-dump-….json] [--sortie …]
"""

import argparse
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from dev.gen_simplification_zones import cases_de, rectangle_cases  # noqa: E402

SORTIE = os.path.join(RACINE, "jsons", "reduction_zones_a_importer.json")
INTOUCHABLES = {"zone:tres_dangereuse", "zone:zone_danger_1", "zone:zone_danger_2", "zone:zone_danger_3"}
# Réglage « moyen » retenu par l'Auteur : écart de regroupement (cases) et part de débordement
# terrestre tolérée par rectangle.
ECART = 3
SEUIL = 0.4
# Une composante sans zone d'au moins cette taille est de la mer ; en deçà, un trou dans les terres
# (que les rectangles peuvent combler).
MER_MIN = 20

RELIEF = {"zone:montagne", "zone:collines", "zone:glacier", "zone:contreforts_arides",
		  "zone:haute_montagne"}
LIEUX = {
	"lieu:france": {"fond": "zone:plaine_ouverte"},
	"lieu:afrique_du_nord": {"fond": "zone:desert"},
	"lieu:egypte": {"fond": "zone:desert"},
}


def deja_reduit(lieu: dict, fond: str) -> bool:
	larg, haut = lieu["dimensions"]["x"], lieu["dimensions"]["y"]
	plein = rectangle_cases(fond, 0, 0, larg, haut)
	return any(p.get("zone") == fond and all(p.get(k) == plein[k] for k in ("x", "y", "w", "h", "rot", "forme"))
			   for p in lieu.get("zone_influences") or [])


def famille(zone: str, fond: str) -> str | None:
	if zone in INTOUCHABLES:
		return None
	if zone == fond:
		return "fond"
	if zone in RELIEF or zone.startswith("zone:foret_"):
		return "moyen"
	return None


def dernier_dump() -> str:
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		sys.exit("Aucun dump jsons/telluris-dump-*.json")
	return dumps[-1]


# ── Géométrie ──────────────────────────────────────────────────────────────────────────────

def mer(larg: int, haut: int, occupees: set, mini: int = MER_MIN) -> set:
	"""Cases des composantes (4-connexes) sans aucune zone d'au moins `mini` cases."""
	vide = {(x, y) for x in range(larg) for y in range(haut)} - occupees
	vu, out = set(), set()
	for c in sorted(vide):
		if c in vu:
			continue
		comp, pile = [c], [c]
		vu.add(c)
		while pile:
			x, y = pile.pop()
			for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
				if n in vide and n not in vu:
					vu.add(n)
					pile.append(n)
					comp.append(n)
		if len(comp) >= mini:
			out |= set(comp)
	return out


def grappes(ensembles: list, ecart: int) -> list:
	"""Unions des ensembles de cases dont deux cases sont à au plus `ecart` + 1 (Tchebychev)."""
	n = len(ensembles)
	parent = list(range(n))

	def racine(i):
		while parent[i] != i:
			parent[i] = parent[parent[i]]
			i = parent[i]
		return i
	boites = [bbox(e) for e in ensembles]
	d = ecart + 1
	for a in range(n):
		for b in range(a + 1, n):
			A, B = boites[a], boites[b]
			if A[0] - d > B[2] or B[0] - d > A[2] or A[1] - d > B[3] or B[1] - d > A[3]:
				continue
			if any(max(abs(x1 - x2), abs(y1 - y2)) <= d
				   for (x1, y1) in ensembles[a] for (x2, y2) in ensembles[b]):
				parent[racine(b)] = racine(a)
	out: dict = {}
	for i in range(n):
		out.setdefault(racine(i), set()).update(ensembles[i])
	return [out[k] for k in sorted(out)]


def bbox(cases: set) -> tuple:
	xs = [x for x, _ in cases]
	ys = [y for _, y in cases]
	return min(xs), min(ys), max(xs), max(ys)


def _debord(cases: set, mer_: set) -> tuple[int, int]:
	"""(cases terrestres du rectangle englobant hors `cases`, cases terrestres du rectangle)."""
	x0, y0, x1, y1 = bbox(cases)
	terre = [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) if (x, y) not in mer_]
	return sum(1 for c in terre if c not in cases), len(terre)


def guillotine(cases: set, mer_: set, seuil: float) -> list:
	"""Rectangles (x0, y0, x1, y1 inclusifs) couvrant `cases` : le rectangle englobant, recoupé
	en deux (coupe verticale ou horizontale qui déborde le moins, première trouvée en cas
	d'égalité) tant que son débordement terrestre dépasse `seuil`."""
	hors, terre = _debord(cases, mer_)
	if hors <= seuil * max(terre, 1) or len(cases) == 1:
		return [bbox(cases)]
	x0, y0, x1, y1 = bbox(cases)
	meilleur = None
	for axe, (lo, hi) in enumerate(((x0, x1), (y0, y1))):
		for coupe in range(lo, hi):
			a = {c for c in cases if c[axe] <= coupe}
			b = cases - a
			if a and b:
				k = _debord(a, mer_)[0] + _debord(b, mer_)[0]
				if meilleur is None or k < meilleur[0]:
					meilleur = (k, a, b)
	return guillotine(meilleur[1], mer_, seuil) + guillotine(meilleur[2], mer_, seuil)


def placement_rect(zone: str, r: tuple) -> dict:
	x0, y0, x1, y1 = r
	return rectangle_cases(zone, x0, y0, x1 - x0 + 1, y1 - y0 + 1)


# ── Réduction d'un lieu ────────────────────────────────────────────────────────────────────

def reduire(lieu: dict, fond: str, ecart: int = ECART, seuil: float = SEUIL) -> tuple[list, list]:
	"""(nouveaux placements, rapport [(zone, avant, après, cases gagnées)]). Ordre conservé : les
	placements neufs d'une zone prennent la place de son premier placement d'origine."""
	larg, haut = lieu["dimensions"]["x"], lieu["dimensions"]["y"]
	origine = lieu.get("zone_influences") or []
	cases = [cases_de(p, larg, haut) for p in origine]
	occupees = set().union(*cases) if cases else set()
	mer_ = mer(larg, haut, occupees)
	par_zone: dict = {}
	for i, p in enumerate(origine):
		par_zone.setdefault(p["zone"], []).append(i)
	neufs: dict = {}
	rapport = []
	for zone, idx in par_zone.items():
		fam = famille(zone, fond)
		if fam is None:
			continue
		if fam == "fond":
			rects = [(0, 0, larg - 1, haut - 1)]
		else:
			rects = []
			for g in grappes([cases[i] for i in idx], ecart):
				rects += guillotine(g, mer_, seuil)
		if len(rects) >= len(idx):
			continue
		S = set().union(*(cases[i] for i in idx))
		ps = [placement_rect(zone, r) for r in rects]
		couv = set().union(*(cases_de(p, larg, haut) for p in ps)) - mer_
		neufs[zone] = ps
		rapport.append((zone, len(idx), len(ps), len(couv - S)))
	out = []
	for p in origine:
		z = p["zone"]
		if z in neufs:
			out.extend(neufs.pop(z))
		elif not any(r[0] == z for r in rapport):
			out.append(p)
	return out, rapport


def controler(avant: list, apres: list, larg: int, haut: int, nom: str) -> None:
	def par_zone(pl):
		out: dict = {}
		for p in pl:
			out.setdefault(p["zone"], set()).update(cases_de(p, larg, haut))
		return out
	za, zb = par_zone(avant), par_zone(apres)
	for z, S in za.items():
		perdues = S - zb.get(z, set())
		assert not perdues, f"{nom} : {z} perd {len(perdues)} case(s)"
	for z in INTOUCHABLES:
		pa = [p for p in avant if p["zone"] == z]
		pb = [p for p in apres if p["zone"] == z]
		assert pa == pb, f"{nom} : {z} modifiée"
	for z in za:
		na = sum(p["zone"] == z for p in avant)
		nb = sum(p["zone"] == z for p in apres)
		assert nb <= na, f"{nom} : {z} passe de {na} à {nb} placements"


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
	for lid, conf in LIEUX.items():
		lieu = docs.get(lid)
		if not lieu:
			print(f"{lid} : absent du dump")
			continue
		if deja_reduit(lieu, conf["fond"]):
			print(f"{lid} : déjà réduit (fond sur toute la carte)")
			continue
		larg, haut = lieu["dimensions"]["x"], lieu["dimensions"]["y"]
		origine = lieu.get("zone_influences") or []
		zi, rapport = reduire(lieu, conf["fond"])
		controler(origine, zi, larg, haut, lid)
		if not rapport:
			print(f"{lid} : rien à réduire")
			continue
		print(f"{lid} : {len(origine)} → {len(zi)} placements")
		for zone, a, b, gain in rapport:
			print(f"   {zone:28} {a:3} → {b:3}  (+{gain} case(s) terrestre(s) gagnent la zone)")
		doc = {k: v for k, v in lieu.items() if k != "_rev"}
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
