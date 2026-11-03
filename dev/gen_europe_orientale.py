"""Les 12 cartes de pays d'Europe du Nord et de l'Est (02/11/2026) : grilles NETTOYÉES et
passages entre elles et avec leurs voisines déjà en jeu.

  · GRILLES (`dev/grilles_europe_orientale.py`) : le cadre décoratif lu par le profil `pays`,
    l'eau lue par croissance depuis des graines posées à la main (forêts, neiges, fleuves larges
    et marais ne sont plus murés). Un lieu déjà dans le dump garde sa grille (retouches).
  · CALAGE PAR SUPERPOSITION (`dev/georeferencement_cartes.py`) : chaque carte porte ses repères
    géographiques réels (lon, lat) ↔ case ; chaque paire de `PAIRES_CALEES` en tire des repères
    au format de `calage_cartes.PAIRES` (similitude sans rotation), et tout l'outillage existant
    s'applique : `frontieres_calees.recaler`, `superposer_cartes.py` pour valider.
  · RECALAGE (`PAIRES_CALEES`, dans l'ordre) : la carte qui fait foi (déjà en jeu, ou plus
    détaillée) garde sa terre ; sur l'autre, toute case projetée dans cette terre passe à 0. Une
    carte neuve entièrement recouverte n'est pas créée (la Germanie du Sud : France, plaine et
    Pannonie en jeu la dessinent déjà). Une carte en jeu recalée est émise ; autour de ses liens
    en base (rayon `RAYON_PROTEGE`), rien n'est fermé.
  · PASSAGES, une case sur deux le long de la ligne de la carte qui fait foi :
      – cartes qui se RECOUVRENT : chaque poste face à sa projection
        (`frontieres_calees.liens_projetes`), écarté si ses deux bouts sont à plus de `ECART_MAX`
        cases sur la superposition ;
      – cartes BORD À BORD (aucune ne dessine la bande entre elles) : les deux bords qui se font
        face (`lignes_face`), bouts à la même fraction (`liens_proportionnels`).
    Nom `None` : recalage seul (détroits : Otrante, Gibraltar). Nœuds « <frontière> <n> — <lieu> ».

N'émet que ce qui diffère du dump (lieux absents, liens neufs ou déplacés) ; les liens
`link:<a>_to_<b>_NN` du dump que le lot ne produit plus partent en suppression.

Validation : python dev/superposer_cartes.py <pose>_<fond> --import jsons/europe_orientale_a_importer.json
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

# Rectangles (x_min, x_max, y_min, y_max) mis à 0 que le calage ne lit pas (aucun pour l'Europe :
# la terre des cartes voisines est fermée par le RECALAGE, cf. `PAIRES_CALEES`).
TERRITOIRES = {}

# Un point de TERRE par carte : la zone qui le contient est celle où l'on marche (sur la
# Scandinavie, la mer est la plus grande zone). Cartes déjà en jeu comprises.
ANCRES = {
	"scandinavie_meridionale": (45, 20), "laponie": (45, 25), "germanie_du_sud": (40, 25),
	"baltique_orientale": (40, 30), "pologne_ruthenie": (30, 25), "balkans": (40, 10),
	"steppe_pontique": (40, 15), "moscovie": (40, 25), "grand_nord": (50, 35),
	"volga_oural": (40, 30), "basse_volga": (30, 20), "caucase": (40, 36),
	"france": (45, 25), "plaine_europeenne": (41, 29), "pannonie": (50, 25),
	"roumanie": (35, 17), "italie": (47, 25),
}

# Cadre décoratif plus épais que ce que lit le profil `pays` (haut, bas, gauche, droite) en
# cases : le cadre doré de la Steppe pontique, le bas glacé du Grand Nord.
CADRE_MINIMUM = {
	"steppe_pontique": (4, 6, 5, 4),
	"grand_nord": (2, 4, 3, 3),
}

# Paires CALÉES (`dev/georeferencement_cartes.py` → `calage_cartes.PAIRES`) : (carte qui FAIT
# FOI, carte RECALÉE sur elle, nom de la frontière). La carte recalée perd (0) toute case dont
# la projection tombe dans la terre de l'autre ; les passages se posent une case sur deux le
# long de la ligne de la carte qui fait foi, chacun face à sa projection
# (`frontieres_calees.liens_projetes`). Une carte déjà en jeu fait toujours foi (sa grille est
# peinte à la main) ; un recouvrement par la mer seule ne donne aucun passage.
PAIRES_CALEES = (
	("france", "germanie_du_sud", "Gué du Rhin"),
	("plaine_europeenne", "germanie_du_sud", "Route de Thuringe"),
	("pannonie", "germanie_du_sud", "Route du Danube"),
	("plaine_europeenne", "pologne_ruthenie", "Gué de l'Oder"),
	("germanie_du_sud", "pologne_ruthenie", "Porte de Moravie"),
	("pannonie", "pologne_ruthenie", "Col des Carpates"),
	("roumanie", "pologne_ruthenie", "Route de Bucovine"),
	("roumanie", "steppe_pontique", "Gué du Dniestr"),
	("roumanie", "balkans", "Gué du Danube"),
	("pannonie", "balkans", "Route de Serbie"),
	# Le talon des Pouilles fermé sur les Balkans ; le détroit ne se passe pas à pied.
	("italie", "balkans", None),
	("scandinavie_meridionale", "laponie", "Route du Nord"),
	("scandinavie_meridionale", "baltique_orientale", "Route d'Åbo"),
	("baltique_orientale", "laponie", "Isthme de Carélie"),
	("baltique_orientale", "pologne_ruthenie", "Route de Mazurie"),
	("baltique_orientale", "moscovie", "Route de Novgorod"),
	("pologne_ruthenie", "moscovie", "Route de Smolensk"),
	("pologne_ruthenie", "steppe_pontique", "Route de Podolie"),
	("laponie", "grand_nord", "Route de la mer Blanche"),
	("moscovie", "grand_nord", "Route de la Dvina"),
	("moscovie", "volga_oural", "Route de Kazan"),
	("moscovie", "steppe_pontique", "Route du Don"),
	("moscovie", "basse_volga", "Route de Saratov"),
	("grand_nord", "volga_oural", "Route de Perm"),
	("volga_oural", "basse_volga", "Route de Samara"),
	("steppe_pontique", "basse_volga", "Gué du Don"),
	("steppe_pontique", "caucase", "Route du Kouban"),
	("basse_volga", "caucase", "Route de Derbent"),
)


def lid(slug):
	return f"lieu:{slug}"


# ── Lignes de frontière ──────────────────────────────────────────────────────────────
def extremite(cases):
	"""Un bout de l'ensemble `cases` : la case la plus éloignée de leur barycentre (puis y, x)."""
	if not cases:
		return None
	mx = sum(x for x, _ in cases) / len(cases)
	my = sum(y for _, y in cases) / len(cases)
	return max(cases, key=lambda c: ((c[0] - mx) ** 2 + (c[1] - my) ** 2, -c[1], -c[0]))


def _touchent(zone, au_dela):
	return {(x, y) for x, y in zone
		if any((x + dx, y + dy) in au_dela for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))}


# Cartes BORD À BORD (aucun recouvrement : le dessin s'arrête avant la voisine) : la frontière
# est le bord de chaque carte dont la projection tombe à `JOINT_MAX` cases au plus de la terre
# de l'autre.
JOINT_MAX = 6
# Cases de terre, en retrait du bout de la carte, encore comptées comme son bord.
BORD_PROFONDEUR = 3
# Rayon (cases) gardé ouvert autour d'un lien en base sur une carte en jeu recalée.
RAYON_PROTEGE = 2


def _proche_de(zone, d):
	"""Prédicat : la case est à `d` cases au plus (Tchebychev) d'une case de `zone`."""
	autour = {(x + dx, y + dy) for x, y in zone for dx in range(-d, d + 1) for dy in range(-d, d + 1)}
	return autour.__contains__


def lignes(voisine, zone_v, foi, zone_f):
	"""(ligne de la voisine RECALÉE, ligne de la carte qui fait foi) — `frontieres_calees.lignes`,
	départs pris au BOUT de chaque frontière (aucun départ à lire à la main). Sans recouvrement
	(ligne vide), les deux BORDS qui se font face (`JOINT_MAX`)."""
	v, f = _lignes(voisine, zone_v, foi, zone_f, zone_f.__contains__)
	if v and f:
		return v, f, True
	v, f = _lignes(voisine, zone_v, foi, zone_f, _proche_de(zone_f, JOINT_MAX),
		_proche_de(zone_v, JOINT_MAX))
	if v and f:
		return v, f, False
	return (*lignes_face(voisine, zone_v, foi, zone_f), False)


def _cote_vers(doc, zone, autre_id, autre_zone):
	"""Le côté (« haut », « bas », « gauche », « droite ») de `doc` tourné vers l'autre carte : celui
	qu'indique le barycentre de la terre de l'autre, projeté sur `doc`."""
	from dev.calage_cartes import projection
	vers = projection(autre_id, doc["_id"])
	px = [vers(c) for c in autre_zone]
	cx = sum(p[0] for p in px) / len(px)
	cy = sum(p[1] for p in px) / len(px)
	w, h = len(doc["cells"][0]), len(doc["cells"])
	ex = (cx - w / 2) / w
	ey = (cy - h / 2) / h
	if abs(ex) >= abs(ey):
		return "droite" if ex > 0 else "gauche"
	return "bas" if ey > 0 else "haut"


def _bord(zone, cote, garder):
	"""Pour chaque rangée (gauche/droite) ou colonne (haut/bas), la case de `zone` la plus avancée
	vers `cote`, si `garder(case)`."""
	extremes = {}
	for x, y in zone:
		cle, val = ((y, x) if cote in ("gauche", "droite") else (x, y))
		meilleur = extremes.get(cle)
		if meilleur is None or (val > meilleur[1] if cote in ("droite", "bas") else val < meilleur[1]):
			extremes[cle] = ((x, y), val)
	if not extremes:
		return []
	vals = [v for _, v in extremes.values()]
	bout = max(vals) if cote in ("droite", "bas") else min(vals)
	# Seul le BORD de la carte compte : une colonne de mer dont la première terre est une côte
	# lointaine (le golfe de Riga vu du haut de la carte) n'est pas une frontière.
	return [c for c, v in extremes.values() if abs(v - bout) <= BORD_PROFONDEUR and garder(c)]


def lignes_face(voisine, zone_v, foi, zone_f):
	"""Cartes SÉPARÉES par une bande que nulle ne dessine (la Moscovie s'arrête au 57e parallèle,
	le Grand Nord commence au 63e) : les deux BORDS qui se font face, chacun réduit à la portion
	dont la projection tombe en face de la terre de l'autre (même rangée ou colonne, à 2 cases
	près). Rend (ligne de la voisine, ligne de la carte qui fait foi), ordonnées le long du bord."""
	from dev.calage_cartes import projection
	cote_v = _cote_vers(voisine, zone_v, foi["_id"], zone_f)
	cote_f = _cote_vers(foi, zone_f, voisine["_id"], zone_v)
	lat = cote_v in ("gauche", "droite")

	def en_face(doc_id, zone_autre, cote_autre):
		vers = projection(doc_id, voisine["_id"] if doc_id == foi["_id"] else foi["_id"])
		bord = _bord(zone_autre, cote_autre, lambda c: True)
		axe = sorted((c[1] if lat else c[0]) for c in bord)
		if not axe:
			return lambda c: False
		lo, hi = axe[0] - 2, axe[-1] + 2

		def garder(c):
			p = vers(c)
			return lo <= (p[1] if lat else p[0]) <= hi
		return garder

	ligne_v = _bord(zone_v, cote_v, en_face(voisine["_id"], zone_f, cote_f))
	ligne_f = _bord(zone_f, cote_f, en_face(foi["_id"], zone_v, cote_v))
	cle = (lambda c: (c[1], c[0])) if lat else (lambda c: (c[0], c[1]))
	return sorted(ligne_v, key=cle), sorted(ligne_f, key=cle)


def _lignes(voisine, zone_v, foi, zone_f, cible_v, cible_f=None):
	from dev import frontieres_calees
	from dev.gen_plaine_europeenne import ligne_frontiere
	au_v = frontieres_calees.au_dela(voisine, zone_v, foi["_id"], cible_v)
	if cible_f is not None:
		au_f = frontieres_calees.au_dela(foi, zone_f, voisine["_id"], cible_f)
		ligne_v = ligne_frontiere(zone_v, au_v, extremite(_touchent(zone_v, au_v)) or (0, 0))
		ligne_f = ligne_frontiere(zone_f, au_f, extremite(_touchent(zone_f, au_f)) or (0, 0))
		return ligne_v, ligne_f
	ligne_v = ligne_frontiere(zone_v, au_v, extremite(_touchent(zone_v, au_v)) or (0, 0))
	proches = {(x + dx, y + dy) for x, y in ligne_v for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
	au_f = frontieres_calees.au_dela(foi, zone_f, voisine["_id"], proches.__contains__,
		lambda c: c in proches and c in zone_v)
	ligne_f = ligne_frontiere(zone_f, au_f, extremite(_touchent(zone_f, au_f)) or (0, 0))
	return ligne_v, ligne_f


def liens_proportionnels(prefixe, lieu_a, ligne_a, lieu_b, ligne_b, noms, libelles):
	"""(docs, refus) : cartes BORD À BORD, rien ne se superpose — postes une case sur deux sur
	`ligne_a`, l'autre bout à la MÊME FRACTION de `ligne_b` (les deux lignes vont dans le même
	sens : `lignes_face`). Projeter chaque poste ramènerait tous ceux d'une ligne plus longue sur
	le même bout de la plus courte (éventail)."""
	from dev.gen_plaine_europeenne import postes
	n = len(noms)
	docs = []
	for i, (nom, pa) in enumerate(zip(noms, postes(ligne_a, n)), start=1):
		k = ligne_a.index(pa)
		f = k / max(1, len(ligne_a) - 1)
		pb = ligne_b[round(f * (len(ligne_b) - 1))]
		docs.append({"_id": f"{prefixe}_{i:02d}", "type": "connection",
			"nodes": [{"lieu": lieu_a, "pos": list(pa), "label": f"{nom} — {libelles[lieu_a]}"},
				{"lieu": lieu_b, "pos": list(pb), "label": f"{nom} — {libelles[lieu_b]}"}],
			"metadata": dict(METADATA)})
	return docs, []


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
	s'il existe, rend (docs, suppressions, lignes de rapport) en plus (cités déplacées…).

	1. Cartes : neuves (grille nettoyée) ou relues du dump ; voisines déjà en jeu relues.
	2. Paires géoréférencées enregistrées dans `calage_cartes.PAIRES`.
	3. RECALAGE, dans l'ordre de `PAIRES_CALEES` (une carte recalée peut ensuite faire foi).
	4. Passages projetés, une case sur deux le long de la ligne de la carte qui fait foi.
	Une carte déjà en jeu RECALÉE (l'Afrique du Nord) est émise ; ses liens tombés dans une case
	fermée sont signalés (⚠)."""
	import math
	from dev import frontieres_calees
	from dev import georeferencement_cartes as georef
	from dev.gen_plaine_europeenne import sans_rev, zone_de
	c = _cfg(cfg)
	par_id = {d.get("_id"): d for d in docs_dump}
	lieux, cartes, neuves = [], {}, set()
	for slug in c.CARTES:
		if lid(slug) in par_id and par_id[lid(slug)].get("cells"):
			cartes[slug] = par_id[lid(slug)]
		else:
			cartes[slug] = grille_fn(slug)
			neuves.add(slug)
	for slug in sorted({s for p in c.PAIRES_CALEES for s in p[:2]} - set(c.CARTES)):
		if not (par_id.get(lid(slug)) or {}).get("cells"):
			return [], [], [], [f"✗ {lid(slug)} absent du dump ou sans grille"]
		cartes[slug] = sans_rev(json.loads(json.dumps(par_id[lid(slug)])))
	dims = {lid(s): (len(d["cells"][0]), len(d["cells"])) for s, d in cartes.items()}
	georef.enregistrer([(lid(f), lid(v)) for f, v, _ in c.PAIRES_CALEES], dims)

	def zone(slug):
		"""Zone de l'ancre ; ancre fermée par un recalage ⇒ la plus grande zone de TERRE restante
		(celle qui contient le plus de cases d'origine de la zone de l'ancre)."""
		z = zone_de(cartes[slug]["cells"], cartes[slug].get("nav") or {}, c.ANCRES.get(slug))
		if z:
			return z
		if slug not in origine:
			raise ValueError(f"✗ {lid(slug)} : l'ancre {c.ANCRES.get(slug)} n'est pas sur une case libre")
		from utils import grille_image
		zz, tailles = grille_image.zones(cartes[slug]["cells"], cartes[slug].get("nav") or {})
		compte = {}
		for x, y in origine[slug]:
			if zz[y][x] != -1:
				compte[zz[y][x]] = compte.get(zz[y][x], 0) + 1
		if not compte:
			raise ValueError(f"✗ {lid(slug)} : toute sa terre est recouverte par ses voisines")
		n = max(compte, key=compte.get)
		return {(x, y) for y, l in enumerate(zz) for x, v in enumerate(l) if v == n}

	origine = {}
	for slug in cartes:
		origine[slug] = zone(slug)

	rapport, recalees, recouvertes = [], set(), set()

	def zone_ou_rien(slug):
		try:
			return zone(slug)
		except ValueError:
			if slug in neuves:
				recouvertes.add(slug)
				return set()
			raise

	# Cases PROTÉGÉES d'une carte déjà en jeu : autour (rayon `RAYON_PROTEGE`) de chaque bout de
	# lien en base qui n'est ni régénéré ni supprimé par ce lot (Abou Simbel sur l'Afrique du
	# Nord) — le recalage ne coupe pas une cité de sa carte.
	regeneres = tuple(f"link:{f}_to_{v}_" for f, v, _ in c.PAIRES_CALEES) + tuple(
		getattr(c, "LIENS_REMPLACES", ()))
	protegees = {}
	for d in docs_dump:
		if d.get("type") != "connection" or d["_id"].startswith(regeneres):
			continue
		for n in d.get("nodes") or []:
			s = (n.get("lieu") or "").split(":", 1)[-1]
			if s in cartes and s not in neuves and n.get("pos"):
				x, y = n["pos"]
				protegees.setdefault(s, set()).update((x + dx, y + dy)
					for dx in range(-RAYON_PROTEGE, RAYON_PROTEGE + 1)
					for dy in range(-RAYON_PROTEGE, RAYON_PROTEGE + 1))
	try:
		for foi, voisine, _ in c.PAIRES_CALEES:
			z = zone_ou_rien(foi)
			if not z or voisine in recouvertes:
				continue
			fermees, _ = frontieres_calees.recaler(cartes[voisine], cartes[foi], z)
			for x, y in fermees & protegees.get(voisine, set()):
				cartes[voisine]["cells"][y][x] = 1
			if fermees - protegees.get(voisine, set()):
				recalees.add(voisine)
		zones = {s: zone_ou_rien(s) for s in cartes}
	except ValueError as e:
		return [], [], [], [str(e)]
	for slug in sorted(recouvertes):
		rapport.append(f"⚠ {lid(slug)} : toute sa terre est déjà dessinée par ses voisines en jeu — "
			"carte NON créée")
	neuves -= recouvertes
	recalees -= recouvertes
	for slug in sorted(recalees):
		if slug not in origine or not origine[slug]:
			continue
		reste = len(zones[slug]) / max(1, len(origine[slug]))
		rapport.append(f"recalage : {lid(slug)} garde {reste:.0%} de sa terre ({len(zones[slug])} cases)")
	for slug in neuves:
		cartes[slug]["nav"] = nav_sans_cases_fermees(cartes[slug]["nav"], cartes[slug]["cells"])
		lieux.append(cartes[slug])
	for slug in sorted(recalees - neuves):
		lieux.append(cartes[slug])
		for d in docs_dump:
			if d.get("type") != "connection" or d["_id"].startswith(regeneres):
				continue
			for n in d.get("nodes") or []:
				x, y = n.get("pos") or (0, 0)
				if n.get("lieu") == lid(slug) and (x, y) not in zones[slug]:
					rapport.append(f"⚠ {d['_id']} : bout {[x, y]} hors de la terre de {lid(slug)} recalée")
	libelles = {lid(s): d.get("label") or s for s, d in cartes.items()}
	liens = []
	for foi, voisine, nom in c.PAIRES_CALEES:
		if foi in recouvertes or voisine in recouvertes or nom is None:
			continue
		ligne_v, ligne_f, recouvrement = lignes(cartes[voisine], zones[voisine], cartes[foi], zones[foi])
		if not ligne_v or not ligne_f:
			rapport.append(f"{nom} : {libelles[lid(foi)]} ↔ {libelles[lid(voisine)]} — aucun passage "
				"(pas de frontière terrestre)")
			continue
		noms = [f"{nom} {k}" for k in range(1, math.ceil(len(ligne_f) / 2) + 1)]
		if recouvrement:
			docs, refus, _ = frontieres_calees.liens_projetes(f"link:{foi}_to_{voisine}", lid(foi),
				ligne_f, lid(voisine), ligne_v, noms, libelles)
		else:
			docs, refus = liens_proportionnels(f"link:{foi}_to_{voisine}", lid(foi), ligne_f,
				lid(voisine), ligne_v, noms, libelles)
		ecartes = 0
		if recouvrement:
			# Cartes qui se RECOUVRENT : les deux bouts doivent se faire face sur la superposition.
			from dev.calage_cartes import projection
			vers = projection(lid(foi), lid(voisine))
			garde = []
			for d in docs:
				a_, b_ = d["nodes"][0]["pos"], d["nodes"][1]["pos"]
				if math.dist(vers(tuple(a_)), b_) <= ECART_MAX:
					garde.append(d)
			ecartes = len(docs) - len(garde)
			for k, d in enumerate(garde, start=1):
				d["_id"] = f"link:{foi}_to_{voisine}_{k:02d}"
				for n in d["nodes"]:
					n["label"] = f"{nom} {k} — {libelles[n['lieu']]}"
			docs = garde
		liens += docs
		rapport += refus
		rapport.append(f"{nom} : {libelles[lid(foi)]} ↔ {libelles[lid(voisine)]} — {len(docs)} passage(s)"
			+ (f", {ecartes} écarté(s) (bouts qui ne se font pas face)" if ecartes else "")
			+ ("" if recouvrement else " — cartes bord à bord"))
	produits = {l["_id"] for l in liens}
	prefixes = {f"link:{f}_to_{v}_" for f, v, _ in c.PAIRES_CALEES}
	suppressions = [{"_id": d["_id"], "_deleted": True} for d in docs_dump
		if d.get("type") == "connection" and d["_id"] not in produits
		and any(d["_id"].startswith(p) for p in prefixes)]
	a_emettre = [l for l in liens if _differe(l, par_id.get(l["_id"]))]
	if hasattr(c, "extras"):
		docs, suppr, lignes_extra = c.extras(par_id, cartes, zones)
		a_emettre += [d for d in docs if d.get("type") != "connection" or _differe(d, par_id.get(d["_id"]))]
		suppressions += suppr
		rapport += lignes_extra
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
	if any(r.startswith("✗") for r in rapport):
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
