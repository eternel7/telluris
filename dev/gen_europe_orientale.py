"""Les 12 cartes de pays d'Europe du Nord et de l'Est (02/11/2026) : grilles NETTOYÉES et
passages entre elles et avec leurs voisines déjà en jeu.

  · GRILLES (`dev/grilles_europe_orientale.py`) : le cadre décoratif lu par le profil `pays`,
    l'eau lue par croissance depuis des graines posées à la main (forêts, neiges, fleuves larges
    et marais ne sont plus murés). Un lieu déjà dans le dump garde sa grille (retouches).
  · TERRITOIRES VOISINS mis à 0 (`TERRITOIRES`) quand une carte neuve dessine clairement la
    terre d'une autre carte : l'Alsace et la Suisse (France) sur la Germanie du Sud, l'Autriche
    (Pannonie) sur la Germanie du Sud, le Jutland (Plaine européenne) sur la Scandinavie, la Kola
    (Laponie) sur le Grand Nord, le delta du Danube (Roumanie) sur la Steppe pontique. Les cartes
    déjà en jeu ne sont pas touchées (grilles peintes à la main).
  · PASSAGES (`FRONTIERES`) : pour chaque frontière, une ligne (polyligne en cases) sur chacune
    des deux cartes, parcourues dans le même sens. Postes UNE CASE SUR DEUX le long de la ligne la
    plus longue (comme entre la France et ses voisines), répartis en proportion sur l'autre ;
    chaque bout ramené à la case la plus proche de la zone de terre principale de sa carte. Un
    poste dont un bout tombe à plus de `ECART_MAX` cases de sa ligne (mer, fjord, lac) est
    abandonné : on ne passe pas la mer à pied. Deux postes aux mêmes bouts : un seul.
    Nœuds libellés « <frontière> <n> — <lieu> ».
  · Les cartes dessinées ne suivent pas exactement les cadres demandés : les lignes suivent les
    BORDS des cartes là où elles se jouxtent, pas une projection calée.

N'émet que ce qui diffère du dump (lieux absents, liens neufs ou déplacés) ; les liens
`link:<a>_to_<b>_NN` du dump que le lot ne produit plus partent en suppression.

Usage :
  python dev/gen_europe_orientale.py [--dump jsons/telluris-dump-….json] [--sans-apercu]

Sortie : jsons/europe_orientale_a_importer.json (+ jsons/<slug>_grille_apercu.png)
"""

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import grilles_europe_orientale as geo  # noqa: E402

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "europe_orientale_a_importer.json")
ECART_MAX = 3
METADATA = {"type": "chemin", "status": "ouvert"}

# Slug → (image, libellé). Tous `categorie: pays`, `sous_categorie: region`.
CARTES = {
	"scandinavie_meridionale": ("scandinavie_meridionale.jpg", "Scandinavie méridionale"),
	"laponie": ("laponie.jpg", "Laponie"),
	"germanie_du_sud": ("germanie_du_sud.jpg", "Germanie du Sud"),
	"baltique_orientale": ("baltique_orientale.jpg", "Baltique orientale"),
	"pologne_ruthenie": ("pologne_ruthenie.jpg", "Pologne et Ruthénie"),
	"balkans": ("balkans.jpg", "Balkans"),
	"steppe_pontique": ("steppe_pontique.jpg", "Steppe pontique"),
	"moscovie": ("moscovie.jpg", "Moscovie"),
	"grand_nord": ("grand_nord.jpg", "Grand Nord"),
	"volga_oural": ("volga_oural.jpg", "Volga et Oural"),
	"basse_volga": ("basse_volga.jpg", "Basse-Volga"),
	"caucase": ("caucase.jpg", "Caucase"),
}

# Slug → rectangles (x_min, x_max, y_min, y_max) mis à 0 : la terre d'une AUTRE carte.
TERRITOIRES = {
	# À l'ouest du Rhin (France), puis la Suisse au sud du lac de Constance (France).
	"germanie_du_sud": ((0, 9, 0, 8), (0, 13, 9, 13), (0, 14, 14, 18), (0, 12, 19, 23),
		(0, 10, 24, 30), (0, 8, 31, 36), (0, 27, 37, 47),
		# L'Autriche, au sud du Danube et à l'est de l'Inn (Pannonie).
		(57, 85, 32, 47)),
	# Le Jutland et les îles danoises (Plaine européenne).
	"scandinavie_meridionale": ((22, 34, 31, 47),),
	# La presqu'île de Kola (Laponie).
	"grand_nord": ((3, 26, 8, 24),),
	# Le delta du Danube et la Dobroudja (Roumanie).
	"steppe_pontique": ((0, 12, 30, 47),),
}

# Un point de TERRE par carte neuve : la zone qui le contient est celle où l'on marche (sur la
# Scandinavie, la mer est la plus grande zone). Cartes déjà en jeu : leur plus grande zone.
ANCRES = {
	"scandinavie_meridionale": (45, 20), "laponie": (45, 25), "germanie_du_sud": (40, 25),
	"baltique_orientale": (40, 30), "pologne_ruthenie": (30, 25), "balkans": (40, 10),
	"steppe_pontique": (40, 15), "moscovie": (40, 25), "grand_nord": (50, 35),
	"volga_oural": (40, 30), "basse_volga": (30, 20), "caucase": (40, 36),
}

# Cadre décoratif plus épais que ce que lit le profil `pays` (haut, bas, gauche, droite) en
# cases : le cadre doré de la Steppe pontique, le bas glacé du Grand Nord.
CADRE_MINIMUM = {
	"steppe_pontique": (4, 6, 5, 4),
	"grand_nord": (2, 4, 3, 3),
}

# (nom, lieu A, ligne sur A, lieu B, ligne sur B) — lignes parcourues dans le même sens.
FRONTIERES = (
	("Gué du Rhin", "france", ((86, 2), (86, 24), (76, 26)),
		"germanie_du_sud", ((11, 4), (16, 11), (16, 17), (13, 24), (11, 31), (10, 36), (28, 38), (28, 44))),
	("Route de Thuringe", "plaine_europeenne", ((56, 47), (87, 47)),
		"germanie_du_sud", ((5, 5), (80, 5))),
	("Route du Danube", "germanie_du_sud", ((56, 44), (56, 31), (82, 31)),
		"pannonie", ((1, 20), (1, 1), (30, 1))),
	("Porte de Moravie", "germanie_du_sud", ((82, 6), (82, 30)),
		"pologne_ruthenie", ((6, 27), (8, 43))),
	("Gué de l'Oder", "plaine_europeenne", ((87, 11), (87, 46)),
		"pologne_ruthenie", ((7, 6), (9, 26))),
	("Route de Mazurie", "pologne_ruthenie", ((10, 5), (82, 5)),
		"baltique_orientale", ((8, 44), (74, 44))),
	("Col des Carpates", "pologne_ruthenie", ((9, 44), (45, 44)),
		"pannonie", ((30, 1), (68, 1))),
	("Route de Bucovine", "pologne_ruthenie", ((46, 44), (70, 44)),
		"roumanie", ((25, 0), (75, 0))),
	("Route de Podolie", "pologne_ruthenie", ((71, 44), (82, 44), (82, 30)),
		"steppe_pontique", ((6, 4), (30, 4))),
	("Route de Smolensk", "pologne_ruthenie", ((82, 5), (82, 29)),
		"moscovie", ((5, 28), (5, 44))),
	("Route de Novgorod", "baltique_orientale", ((82, 5), (82, 43)),
		"moscovie", ((5, 4), (5, 27))),
	("Isthme de Carélie", "baltique_orientale", ((55, 4), (82, 4)),
		"laponie", ((60, 44), (82, 44))),
	("Route du Nord", "scandinavie_meridionale", ((8, 6), (82, 6)),
		"laponie", ((5, 44), (58, 44))),
	("Route de la mer Blanche", "laponie", ((82, 34), (82, 44)),
		"grand_nord", ((3, 28), (3, 44))),
	("Route de la Dvina", "moscovie", ((5, 4), (82, 4)),
		"grand_nord", ((3, 44), (26, 44))),
	("Route de Perm", "grand_nord", ((27, 44), (80, 44)),
		"volga_oural", ((4, 4), (82, 4))),
	("Route de Kazan", "moscovie", ((82, 4), (82, 44)),
		"volga_oural", ((4, 4), (4, 44))),
	("Route du Don", "moscovie", ((5, 44), (57, 44)),
		"steppe_pontique", ((31, 4), (82, 4))),
	("Route de Saratov", "moscovie", ((58, 44), (82, 44)),
		"basse_volga", ((4, 4), (45, 4))),
	("Route de Samara", "volga_oural", ((4, 44), (82, 44)),
		"basse_volga", ((46, 4), (82, 4))),
	("Gué du Don", "steppe_pontique", ((82, 4), (82, 40)),
		"basse_volga", ((4, 4), (4, 40))),
	("Route du Kouban", "steppe_pontique", ((64, 41), (82, 38)),
		"caucase", ((8, 4), (40, 4))),
	("Route de Derbent", "basse_volga", ((4, 44), (43, 44)),
		"caucase", ((41, 4), (70, 4))),
	("Gué du Dniestr", "roumanie", ((87, 0), (87, 22)),
		"steppe_pontique", ((6, 4), (6, 29))),
	("Gué du Danube", "roumanie", ((30, 47), (70, 47)),
		"balkans", ((25, 6), (70, 6))),
	("Route de Serbie", "pannonie", ((48, 46), (69, 46)),
		"balkans", ((12, 6), (24, 6))),
)


def lid(slug):
	return f"lieu:{slug}"


# ── Géométrie des lignes ─────────────────────────────────────────────────────────────────
def longueur(ligne):
	return sum(math.dist(a, b) for a, b in zip(ligne, ligne[1:]))


def point_a(ligne, t):
	"""Le point à la fraction `t` (0-1) de la longueur de `ligne`."""
	total = longueur(ligne)
	if total == 0:
		return ligne[0]
	reste = t * total
	for a, b in zip(ligne, ligne[1:]):
		seg = math.dist(a, b)
		if reste <= seg or b == ligne[-1]:
			u = 0 if seg == 0 else min(1.0, reste / seg)
			return (a[0] + u * (b[0] - a[0]), a[1] + u * (b[1] - a[1]))
		reste -= seg
	return ligne[-1]


def nombre_postes(ligne_a, ligne_b):
	"""Une case sur deux le long de la ligne la plus longue."""
	return max(1, math.ceil(max(longueur(ligne_a), longueur(ligne_b)) / 2))


def proche(zone, point):
	"""(case de `zone` la plus proche de `point`, distance) ou (None, inf)."""
	if not zone:
		return None, math.inf
	px, py = point
	case = min(zone, key=lambda c: ((c[0] - px) ** 2 + (c[1] - py) ** 2, c[1], c[0]))
	return case, math.dist(case, point)


def connexion(_id, lieu_a, pos_a, lieu_b, pos_b, label_a, label_b):
	return {"_id": _id, "type": "connection",
		"nodes": [{"lieu": lieu_a, "pos": list(pos_a), "label": label_a},
			{"lieu": lieu_b, "pos": list(pos_b), "label": label_b}],
		"metadata": dict(METADATA)}


def liens_frontiere(nom, a, ligne_a, zone_a, b, ligne_b, zone_b, libelles):
	"""(docs, abandonnés) d'une frontière."""
	n = nombre_postes(ligne_a, ligne_b)
	docs, vus, abandonnes = [], set(), 0
	for i in range(n):
		t = 0.5 if n == 1 else i / (n - 1)
		pa, da = proche(zone_a, point_a(ligne_a, t))
		pb, db = proche(zone_b, point_a(ligne_b, t))
		if pa is None or pb is None or da > ECART_MAX or db > ECART_MAX:
			abandonnes += 1
			continue
		if (pa, pb) in vus:
			continue
		vus.add((pa, pb))
		k = len(docs) + 1
		docs.append(connexion(f"link:{a}_to_{b}_{k:02d}", lid(a), pa, lid(b), pb,
			f"{nom} {k} — {libelles[lid(a)]}", f"{nom} {k} — {libelles[lid(b)]}"))
	return docs, abandonnes


# ── Grilles ──────────────────────────────────────────────────────────────────────────────
def fermer_territoires(cells, rectangles):
	"""Met à 0 les cases des rectangles ; rend le nombre de cases changées."""
	n = 0
	for x0, x1, y0, y1 in rectangles:
		for y in range(max(0, y0), min(len(cells) - 1, y1) + 1):
			for x in range(max(0, x0), min(len(cells[y]) - 1, x1) + 1):
				if cells[y][x]:
					cells[y][x] = 0
					n += 1
	return n


def nav_sans_cases_fermees(nav, cells):
	"""`nav` sans les clés des cases à 0 (un mur vers une case fermée ne sert à rien)."""
	return {k: v for k, v in nav.items()
		if cells[int(k.split(",")[1])][int(k.split(",")[0])]}


def _cfg(cfg):
	"""La configuration (module) : celui-ci par défaut ; `dev/gen_afrique.py` passe le sien."""
	return cfg or sys.modules[__name__]


EAUX = geo.EAUX


def lieu_neuf(slug, W, H, cfg=None):
	c = _cfg(cfg)
	image, label = c.CARTES[slug]
	sous_categorie = getattr(c, "SOUS_CATEGORIES", {}).get(slug, "region")
	return {"_id": lid(slug), "type": "lieu", "label": label, "image": image,
		"categorie": "pays", "sous_categorie": sous_categorie, "dimensions": {"x": W, "y": H},
		"cells": None, "nav": None, "tags": []}


def grille_de(slug, chemin_image, W, H, cfg=None):
	"""Doc neuf avec sa grille nettoyée et ses territoires voisins fermés (Pillow)."""
	from dev import gen_grille_image as ggi
	from utils import grille_image
	c = _cfg(cfg)
	doc = lieu_neuf(slug, W, H, c)
	prop = ggi.proposer_pour_image(chemin_image, W, H, {"categorie": "pays"}, profil="pays")
	couleurs, _, _ = ggi.echantillonner(chemin_image, W, H)
	eaux = c.EAUX[slug]
	g = geo.grille_nettoyee(prop["cells"], couleurs, W, H, eaux["graines"], eaux["tolerance"],
		grille_image.murer_barrieres, grille_image.zones)
	cells = g["cells"]
	haut, bas, gauche, droite = c.CADRE_MINIMUM.get(slug, (0, 0, 0, 0))
	fermer_territoires(cells, ((0, W - 1, 0, haut - 1), (0, W - 1, H - bas, H - 1),
		(0, gauche - 1, 0, H - 1), (W - droite, W - 1, 0, H - 1)))
	fermer_territoires(cells, c.TERRITOIRES.get(slug, ()))
	doc["cells"] = cells
	doc["nav"] = nav_sans_cases_fermees(g["nav"], cells)
	return doc


# ── Lot ──────────────────────────────────────────────────────────────────────────────────
def construire(docs_dump, grille_fn, cfg=None):
	"""(lieux à émettre, liens, suppressions, rapport). `grille_fn(slug) -> doc` : grille d'une
	carte absente du dump (injectée : Pillow côté CLI). `cfg.extras(par_id, cartes, zones)`,
	s'il existe, rend (docs, suppressions, lignes de rapport) en plus (cités déplacées…)."""
	from dev.gen_plaine_europeenne import zone_de
	c = _cfg(cfg)
	CARTES, FRONTIERES, ANCRES = c.CARTES, c.FRONTIERES, c.ANCRES
	par_id = {d.get("_id"): d for d in docs_dump}
	lieux, cartes = [], {}
	for slug in CARTES:
		if lid(slug) in par_id and par_id[lid(slug)].get("cells"):
			cartes[slug] = par_id[lid(slug)]
		else:
			cartes[slug] = grille_fn(slug)
			lieux.append(cartes[slug])
	rapport = []
	voisins = {s for f in FRONTIERES for s in (f[1], f[3])} - set(CARTES)
	for slug in sorted(voisins):
		if not (par_id.get(lid(slug)) or {}).get("cells"):
			return [], [], [], [f"✗ {lid(slug)} absent du dump ou sans grille"]
		cartes[slug] = par_id[lid(slug)]
	zones = {s: zone_de(d["cells"], d.get("nav") or {}, ANCRES.get(s)) for s, d in cartes.items()}
	for s, z in zones.items():
		if not z:
			return [], [], [], [f"✗ {lid(s)} : l'ancre {ANCRES.get(s)} n'est pas sur une case libre"]
	libelles = {lid(s): d.get("label") or s for s, d in cartes.items()}
	liens = []
	for nom, a, ligne_a, b, ligne_b in FRONTIERES:
		docs, abandonnes = liens_frontiere(nom, a, ligne_a, zones[a], b, ligne_b, zones[b], libelles)
		liens += docs
		rapport.append(f"{nom} : {libelles[lid(a)]} ↔ {libelles[lid(b)]} — {len(docs)} passage(s)"
			+ (f", {abandonnes} poste(s) sur l'eau abandonné(s)" if abandonnes else ""))
	produits = {l["_id"] for l in liens}
	prefixes = {f"link:{a}_to_{b}_" for _, a, _, b, _ in FRONTIERES}
	suppressions = [{"_id": d["_id"], "_deleted": True} for d in docs_dump
		if d.get("type") == "connection" and d["_id"] not in produits
		and any(d["_id"].startswith(p) for p in prefixes)]
	a_emettre = [l for l in liens if _differe(l, par_id.get(l["_id"]))]
	if hasattr(c, "extras"):
		docs, suppr, lignes = c.extras(par_id, cartes, zones)
		a_emettre += [d for d in docs if d.get("type") != "connection" or _differe(d, par_id.get(d["_id"]))]
		suppressions += suppr
		rapport += lignes
	return lieux, a_emettre, suppressions, rapport


def _differe(lien, en_base):
	if not en_base:
		return True
	return ([(n["lieu"], n["pos"], n.get("label")) for n in lien["nodes"]]
		!= [(n.get("lieu"), n.get("pos"), n.get("label")) for n in en_base.get("nodes") or []])


def main(cfg=None) -> int:
	from dev import gen_grille_image as ggi
	c = _cfg(cfg)
	args = sys.argv[1:]
	chemin_dump = args[args.index("--dump") + 1] if "--dump" in args else None
	docs = ggi.charger_dump(chemin_dump)
	if not docs:
		print("✗ aucun dump dans jsons/")
		return 1
	from dev.gen_villes_images import _taille_image

	def grille_fn(slug):
		image = c.CARTES[slug][0]
		l, h = _taille_image(image)
		return grille_de(slug, ggi.trouver_image(image), round(l / 16), round(h / 16), c)

	lieux, liens, suppressions, rapport = construire(docs, grille_fn, c)
	for ligne in rapport:
		print(ligne)
	if rapport and rapport[0].startswith("✗"):
		return 1
	if "--sans-apercu" not in args:
		for doc in lieux:
			chemin = ggi.trouver_image(doc["image"])
			apercu = os.path.join(RACINE, "jsons", f"{doc['_id'].split(':')[1]}_grille_apercu.png")
			ggi.ecrire_apercu(chemin, doc["cells"], apercu, doc["nav"], {})
	sortants = lieux + liens + suppressions
	if not sortants:
		print("Rien à émettre : le dump est à jour.")
		return 0
	with open(c.SORTIE, "w", encoding="utf-8") as f:
		json.dump(sortants, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"✎ {os.path.relpath(c.SORTIE, RACINE)} — {len(lieux)} lieu(x), {len(liens)} lien(s), "
		f"{len(suppressions)} suppression(s)")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
