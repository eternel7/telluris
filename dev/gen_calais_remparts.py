"""Calais : rempart FERMÉ, portes de rempart, rues qui mènent quelque part, sortie sud sur la
route — UN seul fichier d'import (CLAUDE.md §18).

POURQUOI : la grille proposée par `gen_ports_manche` laissait la cité d'un seul tenant avec
ses faubourgs : `ouvrir_porte` avait percé le rempart à travers une TOUR (colonne x = 63, et
x = 37 sur la tour droite de la porte sud-ouest), on y marchait comme sur une rue. Et la
lecture des rues, case par case, laissait des impasses et des poches — la ruelle de la
cathédrale (28 cases) n'avait d'autre issue que la tour.

PUIS : la lecture par couleur de case (`grille_image`) prend un toit clair pour une rue et
une ruelle ombrée pour un toit. Calais est dessinée à l'encre : une rue est ce qui reste
CLAIR et BEIGE entre les traits noirs. D'où la lecture intra-muros par les TRAITS.

Ce que fait le script, sur `lieu:calais` RELU du dump (dehors : grille de l'éditeur gardée) :
  · REMPART : l'anneau des cases de bord de l'enceinte (`ENCEINTE`, polygone posé sur le mur)
    passe à 0 — une case intérieure n'a que des voisines intérieures, aucun pas ne sort —,
    ainsi que les tracés `REMPART` et le corps du rempart sud (`CORPS_REMPART`) ;
  · RUES PAR LES TRAITS (intra-muros, `grille_traits`) : pixel de rue = ni encre (gris ≥
    `SEUIL_ENCRE`) ni pierre grise (saturation ≥ `SATURATION_RUE`), dans une région d'au moins
    `AIRE_RUE` pixels (une face de toit entre ses hachures est plus petite). Case praticable
    si elle en contient `PIXELS_CASE` ; deux cases voisines ne communiquent (sinon mur `nav`)
    que si des pixels de rue les relient DANS leur fenêtre — un trait noir est une limite ;
  · PASSAGES : ceux que la lecture manque et que le dessin montre (`PASSAGES`, l'arche du mur
    du port vers le quai), ouverts à la main ;
  · RUES : chaque POCHE intra-muros d'au moins `POCHE_MIN` cases est reliée au réseau, puis
    chaque IMPASSE (case du réseau à un seul voisin) est prolongée vers une case éloignée
    d'au moins `IMPASSE_DETOUR` pas. On ouvre le chemin ORTHOGONAL le moins cher, au plus
    `*_LONGUEUR` cases, à travers des cases 0 / 2 — coût lu sur l'image (une rue est claire,
    un toit sombre : `cout_case`). Jamais une case du rempart ni hors de l'enceinte
    (`ENCEINTE`), et toute ouverture qui relierait dedans et dehors est annulée ;
  · PORTES DE REMPART : une PAIRE par porte dessinée (pont-levis sud-ouest et sud-est),
    cinq docs chacune, forme de l'éditeur (`dev/test_portes_client.js`) et `_id` à la
    convention d'Alexandrie. Images reprises du fonds (porte à pont-levis) ;
  · SORTIE SUD : `link:france_to_calais_sud` reposé sur la route qui descend de la porte
    sud-ouest (`SORTIE_SUD`).

Hors les murs, `cells` et `nav` du dump restent tels quels. ÉMIS = ce qui DIFFÈRE du dump (`gen_voisins_france.a_emettre`) : un rejeu sur un
dump à jour n'écrit rien. ⚠️ Import = PUT COMPLET (CLAUDE.md §11).

Usage :
  python dev/gen_calais_remparts.py [--dump jsons/telluris-dump-….json] [--sans-apercu]

Sortie : jsons/calais_remparts_a_importer.json (+ jsons/calais_remparts_apercu.png)
"""

import copy
import heapq
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_grille_image as ggi  # noqa: E402
from dev.gen_plaine_europeenne import case_proche, sans_rev  # noqa: E402
from dev.gen_voisins_france import a_emettre  # noqa: E402
from utils import grille_image  # noqa: E402

RACINE = ggi.RACINE
SORTIE = os.path.join(ggi.DOSSIER_JSONS, "calais_remparts_a_importer.json")
APERCU = os.path.join(ggi.DOSSIER_JSONS, "calais_remparts_apercu.png")

CITE = "lieu:calais"

# Une case des rues intra-muros et une des faubourgs (grille 88×48, 16 px la case).
ANCRE_DEDANS = (48, 21)
ANCRE_DEHORS = (80, 44)

# Tracés du rempart, lus sur `calais_city.jpg` : du rocher de la grande tour du port à la
# tour ronde (y = 26), le long du mur jusqu'à la porte sud-ouest, puis le rempart sud jusqu'à
# la porte sud-est ; les deux colonnes de tour où l'ancienne grille passait (x = 37, x = 63).
# (L'anneau de l'enceinte ferme déjà tout ; ces tracés interdisent en plus d'y rouvrir une rue.)
REMPART = (
	((9, 26), (25, 26), (25, 31), (27, 31), (34, 34), (34, 37), (63, 37), (70, 37)),
	((63, 31), (63, 39)),
	((37, 34), (37, 39)),
	# Tour gauche de la porte sud-ouest : une impasse sur son toit sinon.
	((35, 34), (36, 34), (36, 36), (35, 36)),
)
# Corps du rempart sud (chemin de ronde et parement) : (x0, y0, x1, y1) inclus.
CORPS_REMPART = ((38, 35, 62, 39),)

# Enceinte (sommets en cases), posée sur la crête du mur : son anneau de bord est le rempart,
# son intérieur est relu par les traits, une ouverture de rue n'est permise que dedans.
ENCEINTE =((9, 26), (25, 26), (25, 31), (34, 34), (34, 37), (70, 37), (72, 35), (78, 28),
			(80, 22), (78, 18), (75, 13), (72, 10), (68, 6), (62, 6), (60, 7), (45, 7), (36, 9),
			(33, 10), (26, 10), (22, 7), (20, 10), (18, 13), (12, 14), (9, 20))

# Lecture par les traits, mesurée sur `calais_city.jpg` (1408×768, 16 px la case) : les
# traits font ~2 px, gris < 60 ; une rue est grise 150-190 et saturée 0,19-0,27 (HLS), la
# pierre des murs et du château 0,12-0,14, l'herbe du dehors 0,19.
SEUIL_ENCRE = 80
SATURATION_RUE = 0.14
AIRE_RUE = 300          # px : une face de toit entre ses hachures en fait moins
PIXELS_CASE = 10        # px de rue (sur 256) pour qu'une case soit praticable
K_CASE = 16

# Passages que la lecture manque (cases, pas orthogonaux ou diagonaux) : l'arche en ogive
# du mur intérieur du port, de la rue de la place au quai.
PASSAGES = (((41, 20), (40, 20), (40, 19), (39, 18)),)

POCHE_MIN = 3           # une poche de 1-2 cases est un reste de lecture, pas une rue
POCHE_LONGUEUR = 5      # cases ouvertes au plus pour relier une poche
POCHE_COUT = 20
IMPASSE_LONGUEUR = 3
IMPASSE_COUT = 9
IMPASSE_DETOUR = 6      # la case rejointe est à au moins 6 pas de l'impasse par les rues

# Coût d'ouverture d'une case : 1 sur une rue claire, jusqu'à ~1 + 25 × 0,15 sur un toit.
# Luminance moyenne mesurée sur Calais : rues 0,32-0,42 (quartiles), cases 0 : 0,26-0,33.
LUMINANCE_RUE = 0.40
COUT_SOMBRE = 25

# Portes de rempart : `dehors` = pied du pont-levis, `dedans` = débouché du passage dans la
# ville ; chaque case est ramenée à la plus proche de sa zone.
PORTES = (
	{"slug": "porte_sud_ouest", "label": "Porte sud-ouest", "dehors": (35, 40), "dedans": (36, 32),
	 "image_ext": "porte_de_ville_pont_exterieur01.png",
	 "image_int": "porte_de_ville_pont_interieur05.png"},
	{"slug": "porte_sud_est", "label": "Porte sud-est", "dehors": (67, 41), "dedans": (66, 31),
	 "image_ext": "porte_de_ville_pont_exterieur02.png",
	 "image_int": "porte_de_ville_pont_interieur02.png"},
)
PORTE_CATEGORIE = "Porte de rempart"
PORTE_META = {"type": "poste de garde", "status": "ouvert"}
PORTE_LABEL_EXT = "au-delà des remparts"

# La route qui descend de la porte sud-ouest touche le bas de la carte en x = 28.
SORTIE_SUD = {"_id": "link:france_to_calais_sud", "pos": (28, 47)}


# ── Géométrie ──────────────────────────────────────────────────────────────────────────────
def trace(a, b) -> list:
	"""Cases de a à b, 4-CONNEXES : un pas diagonal du tracé est doublé de son orthogonale,
	sinon on passerait le mur en biais entre deux cases murées."""
	(x0, y0), (x1, y1) = a, b
	n = max(abs(x1 - x0), abs(y1 - y0)) or 1
	cases = []
	for i in range(n + 1):
		p = (round(x0 + (x1 - x0) * i / n), round(y0 + (y1 - y0) * i / n))
		if cases and p[0] != cases[-1][0] and p[1] != cases[-1][1]:
			cases.append((p[0], cases[-1][1]))
		if not cases or cases[-1] != p:
			cases.append(p)
	return cases


def cases_du_rempart(traces=REMPART, corps=CORPS_REMPART) -> set:
	murs = set()
	for t in traces:
		for a, b in zip(t, t[1:]):
			murs.update(trace(a, b))
	for x0, y0, x1, y1 in corps:
		murs.update((x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1))
	return murs


def dans_polygone(poly, x, y) -> bool:
	"""Le CENTRE de la case (x, y) est-il dans `poly` ? (parité des croisements)"""
	px, py = x + .5, y + .5
	dedans = False
	for (ax, ay), (bx, by) in zip(poly, poly[1:] + poly[:1]):
		if (ay > py) != (by > py) and px < ax + (py - ay) * (bx - ax) / (by - ay):
			dedans = not dedans
	return dedans


def atteint(cells, nav, depart) -> set:
	"""Cases joignables à pied depuis `depart` (règle d'exploration, `grille_image`)."""
	if not grille_image._dans(cells, *depart) or cells[depart[1]][depart[0]] != 1:
		return set()
	vu, pile = {depart}, [depart]
	while pile:
		x, y = pile.pop()
		for dx, dy in grille_image.VOISINS:
			v = (x + dx, y + dy)
			if v not in vu and grille_image.pas_praticable(cells, nav, x, y, dx, dy):
				vu.add(v)
				pile.append(v)
	return vu


def distances(cells, nav, depart) -> dict:
	"""Pas à pied depuis `depart` (BFS)."""
	dist, file = {depart: 0}, [depart]
	for x, y in file:
		for dx, dy in grille_image.VOISINS:
			v = (x + dx, y + dy)
			if v not in dist and grille_image.pas_praticable(cells, nav, x, y, dx, dy):
				dist[v] = dist[(x, y)] + 1
				file.append(v)
	return dist


def voisins_a_pied(cells, nav, x, y) -> int:
	return sum(grille_image.pas_praticable(cells, nav, x, y, dx, dy)
			   for dx, dy in grille_image.VOISINS)


# ── Rempart ────────────────────────────────────────────────────────────────────────────────
def fermer_rempart(cells, murs) -> int:
	"""Mute `cells` : chaque case du rempart à 0. Rend le nombre de cases fermées."""
	fermees = 0
	for x, y in murs:
		if grille_image._dans(cells, x, y) and cells[y][x] != 0:
			cells[y][x] = 0
			fermees += 1
	return fermees


def anneau_et_interieur(poly, cols, rows):
	"""(anneau, intérieur) des cases de l'enceinte : l'anneau a une voisine (8) hors du
	polygone — c'est le rempart —, l'intérieur n'a que des voisines dedans."""
	dedans = {(x, y) for y in range(rows) for x in range(cols) if dans_polygone(poly, x, y)}
	interieur = {(x, y) for (x, y) in dedans
				 if all((x + dx, y + dy) in dedans for dx in (-1, 0, 1) for dy in (-1, 0, 1))}
	return dedans - interieur, interieur


# ── Rues par les traits ────────────────────────────────────────────────────────────────────
def pixel_de_rue(r, g, b, seuil=SEUIL_ENCRE, saturation=SATURATION_RUE) -> bool:
	"""Ni encre (gris ITU-R 601, celui de Pillow `L`, ≥ `seuil`) ni pierre grise
	(saturation HLS ≥ `saturation`)."""
	if (r * 299 + g * 587 + b * 114) // 1000 < seuil:
		return False
	mx, mn = max(r, g, b), min(r, g, b)
	if mx == mn:
		return False
	somme = mx + mn
	return (mx - mn) / (somme if somme < 255 else 510 - somme) >= saturation


def masque_rues(libre, largeur, hauteur, aire=AIRE_RUE) -> bytearray:
	"""Pixels `libre` (suite de booléens, ligne par ligne) dont la région 4-connexe fait au
	moins `aire` pixels : 1, sinon 0."""
	rue = bytearray(largeur * hauteur)
	vu = bytearray(largeur * hauteur)
	for depart in range(largeur * hauteur):
		if not libre[depart] or vu[depart]:
			continue
		vu[depart] = 1
		region, pile = [], [depart]
		while pile:
			i = pile.pop()
			region.append(i)
			x = i % largeur
			for j in (i - largeur, i + largeur, i - 1 if x else -1, i + 1 if x + 1 < largeur else -1):
				if 0 <= j < largeur * hauteur and libre[j] and not vu[j]:
					vu[j] = 1
					pile.append(j)
		if len(region) >= aire:
			for i in region:
				rue[i] = 1
	return rue


def relies(rue, largeur, k, a, b) -> bool:
	"""Des pixels de rue relient-ils les cases voisines `a` et `b` SANS sortir de leur
	fenêtre (2 cases, ou le carré 2×2 d'un pas diagonal) ? Un trait noir les sépare sinon."""
	x0, y0 = min(a[0], b[0]) * k, min(a[1], b[1]) * k
	x1, y1 = (max(a[0], b[0]) + 1) * k, (max(a[1], b[1]) + 1) * k

	def dans(p, case):
		return case[0] * k <= p[0] < (case[0] + 1) * k and case[1] * k <= p[1] < (case[1] + 1) * k

	pile = [(px, py) for py in range(a[1] * k, (a[1] + 1) * k)
			for px in range(a[0] * k, (a[0] + 1) * k) if rue[py * largeur + px]]
	vus = set(pile)
	while pile:
		p = pile.pop()
		if dans(p, b):
			return True
		for q in ((p[0] + 1, p[1]), (p[0] - 1, p[1]), (p[0], p[1] + 1), (p[0], p[1] - 1)):
			if x0 <= q[0] < x1 and y0 <= q[1] < y1 and q not in vus and rue[q[1] * largeur + q[0]]:
				vus.add(q)
				pile.append(q)
	return False


def grille_traits(cells, nav, rue, largeur, interieur, k=K_CASE, pixels_case=PIXELS_CASE) -> int:
	"""Mute `cells`/`nav` sur l'`intérieur` : case à 1 si elle porte `pixels_case` pixels de
	rue, sinon 0 (l'eau, 5, reste) ; ses murs nav repartent de zéro, un mur est posé entre
	deux cases praticables que `relies` ne joint pas. Rend le nombre de murs posés."""
	for (x, y) in interieur:
		nav.pop(f"{x},{y}", None)
		if cells[y][x] == grille_image.TERRAIN_EAU:
			continue
		compte = sum(rue[py * largeur + px] for py in range(y * k, (y + 1) * k)
					 for px in range(x * k, (x + 1) * k))
		cells[y][x] = 1 if compte >= pixels_case else 0
	poses = 0
	for (x, y) in sorted(interieur):
		if cells[y][x] != 1:
			continue
		for dx, dy in ((1, 0), (0, 1), (1, 1), (-1, 1)):
			v = (x + dx, y + dy)
			if v in interieur and cells[v[1]][v[0]] == 1 and not relies(rue, largeur, k, (x, y), v):
				grille_image.interdire(nav, x, y, dx, dy)
				poses += 1
	return poses


def ouvrir_passages(cells, nav, passages=PASSAGES) -> None:
	"""Mute : chaque passage à 1, murs nav levés sur ses pas (orthogonaux ou diagonaux)."""
	for chemin in passages:
		for x, y in chemin:
			cells[y][x] = 1
		for a, b in zip(chemin, chemin[1:]):
			for p, q in ((a, b), (b, a)):
				bit, _op = grille_image._BIT[(q[0] - p[0], q[1] - p[1])]
				cle = f"{p[0]},{p[1]}"
				reste = int(nav.get(cle, 0) or 0) & ~bit
				if reste:
					nav[cle] = reste
				else:
					nav.pop(cle, None)


def masque_image(chemin):
	"""(masque de rue, largeur, hauteur) de l'image (Pillow)."""
	from PIL import Image
	with Image.open(chemin) as img:
		img = img.convert("RGB")
		largeur, hauteur = img.size
		octets = img.tobytes()
		libre = [pixel_de_rue(octets[i], octets[i + 1], octets[i + 2])
				 for i in range(0, len(octets), 3)]
	return masque_rues(libre, largeur, hauteur), largeur, hauteur


# ── Rues ───────────────────────────────────────────────────────────────────────────────────
def ouvrir_chemin(cells, nav, chemin) -> None:
	"""Mute : les cases du chemin à 1, et les murs nav levés sur ses pas (dans les deux
	sens) — chemin = [case du réseau, cases à ouvrir…, case du réseau], pas orthogonaux."""
	for x, y in chemin[1:-1]:
		cells[y][x] = 1
	for a, b in zip(chemin, chemin[1:]):
		for p, q in ((a, b), (b, a)):
			bit, _op = grille_image._BIT[(q[0] - p[0], q[1] - p[1])]
			cle = f"{p[0]},{p[1]}"
			reste = int(nav.get(cle, 0) or 0) & ~bit
			if reste:
				nav[cle] = reste
			else:
				nav.pop(cle, None)


def chemin_le_moins_cher(cells, depart, cibles, ouvrable, cout, longueur, plafond):
	"""Chemin ORTHOGONAL le moins cher d'une case de `depart` à une case de `cibles` à travers
	des cases `ouvrable` (au plus `longueur`, coût cumulé ≤ `plafond`) ; None sinon."""
	tas = []
	for (x, y) in sorted(depart):
		for dx, dy in grille_image.ORTHOGONAUX:
			v = (x + dx, y + dy)
			if ouvrable(*v) and cout(*v) <= plafond:
				heapq.heappush(tas, (cout(*v), 1, v, ((x, y), v)))
	vus = set()
	while tas:
		total, lg, u, chemin = heapq.heappop(tas)
		if u in vus:
			continue
		vus.add(u)
		for dx, dy in grille_image.ORTHOGONAUX:
			v = (u[0] + dx, u[1] + dy)
			if v in cibles:
				return list(chemin) + [v]
			if lg < longueur and v not in vus and ouvrable(*v):
				t = total + cout(*v)
				if t <= plafond:
					heapq.heappush(tas, (t, lg + 1, v, chemin + (v,)))
	return None


def relier_rues(cells, nav, murs, enceinte, cout, dedans=ANCRE_DEDANS, dehors=ANCRE_DEHORS):
	"""Mute `cells`/`nav` : poches puis impasses intra-muros reliées au réseau. Rend la liste
	des ouvertures `(motif, cases ouvertes)`. Une ouverture qui joindrait dedans et dehors
	est annulée et ses cases écartées."""
	ecartees = set()

	def ouvrable(x, y):
		return (grille_image._dans(cells, x, y) and cells[y][x] in (0, 2) and (x, y) not in murs
				and (x, y) not in ecartees and dans_polygone(enceinte, x, y))

	def tenter(chemin):
		avant = [cells[y][x] for x, y in chemin[1:-1]], dict(nav)
		ouvrir_chemin(cells, nav, chemin)
		if not atteint(cells, nav, dedans) & atteint(cells, nav, dehors):
			return True
		for (x, y), v in zip(chemin[1:-1], avant[0]):
			cells[y][x] = v
		nav.clear()
		nav.update(avant[1])
		ecartees.update(chemin[1:-1])
		return False

	ouvertures = []
	exterieur = atteint(cells, nav, dehors)
	while True:  # poches, la plus grande d'abord
		reseau = atteint(cells, nav, dedans)
		zone, tailles = grille_image.zones(cells, nav)
		par_zone = {}
		for y, ligne in enumerate(zone):
			for x, z in enumerate(ligne):
				if z != -1:
					par_zone.setdefault(z, set()).add((x, y))
		poches = [p for p in par_zone.values() if len(p) >= POCHE_MIN and not p & reseau
				  and not p & exterieur and sum(dans_polygone(enceinte, *c) for c in p) * 2 > len(p)]
		chemins = [chemin_le_moins_cher(cells, p, reseau, ouvrable, cout, POCHE_LONGUEUR, POCHE_COUT)
				   for p in sorted(poches, key=lambda p: (-len(p), min(p)))]
		chemin = next((c for c in chemins if c), None)
		if not chemin:
			break
		if tenter(chemin):
			ouvertures.append(("poche", chemin[1:-1]))
	while True:  # impasses, dans l'ordre des cases
		reseau = atteint(cells, nav, dedans)
		fait = False
		for t in sorted(c for c in reseau if voisins_a_pied(cells, nav, *c) <= 1
						and dans_polygone(enceinte, *c)):
			dist = distances(cells, nav, t)
			loin = {c for c, d in dist.items() if d >= IMPASSE_DETOUR}
			chemin = chemin_le_moins_cher(cells, {t}, loin, ouvrable, cout, IMPASSE_LONGUEUR,
										  IMPASSE_COUT)
			if chemin:
				if tenter(chemin):
					ouvertures.append(("impasse", chemin[1:-1]))
				fait = True
				break
		if not fait:
			break
	return ouvertures


def cout_depuis_luminances(luminances):
	"""Fonction de coût d'ouverture d'une case depuis sa luminance moyenne (0..1)."""
	def cout(x, y):
		return 1 + COUT_SOMBRE * max(0.0, LUMINANCE_RUE - luminances[y][x])
	return cout


def luminances_image(chemin, cols, rows):
	"""Luminance HLS moyenne de chaque case (Pillow : moyenne d'aire, `Image.BOX`)."""
	from PIL import Image
	with Image.open(chemin) as img:
		petite = img.convert("RGB").resize((cols, rows), Image.BOX)
		px = petite.load()
	return [[(max(px[x, y]) + min(px[x, y])) / 510 for x in range(cols)] for y in range(rows)]


# ── Docs ───────────────────────────────────────────────────────────────────────────────────
def docs_porte(cite_id, porte, pos_dehors, pos_dedans) -> list:
	"""Les cinq docs d'une porte de rempart (forme de l'éditeur, `test_portes_client.js`)."""
	ville = cite_id.split(":", 1)[1]
	base = f"{ville}_{porte['slug']}"
	ext, inte = f"lieu:{base}_exterieur", f"lieu:{base}_interieur"

	def lieu(_id, cote, image):
		return {"_id": _id, "type": "lieu", "label": f"{porte['label']} — {cote}", "image": image,
				"categorie": PORTE_CATEGORIE, "lieu_parent": cite_id}

	def lien(_id, a, b):
		return {"_id": _id, "type": "connection", "nodes": [a, b], "metadata": dict(PORTE_META)}

	return [
		lieu(ext, "extérieur", porte["image_ext"]),
		lieu(inte, "intérieur", porte["image_int"]),
		lien(f"link:{base}_carte_exterieur",
			 {"lieu": cite_id, "pos": list(pos_dehors), "label": PORTE_LABEL_EXT},
			 {"lieu": ext, "pos": [0, 0]}),
		lien(f"link:{base}_carte_interieur", {"lieu": cite_id, "pos": list(pos_dedans)},
			 {"lieu": inte, "pos": [0, 0]}),
		lien(f"link:{base}_passage", {"lieu": ext, "pos": [0, 0]}, {"lieu": inte, "pos": [0, 0]}),
	]


def construire(docs, luminances_fn, masque_fn):
	"""(sortants, refus, rapport) — docs complets (`_rev` retiré). `masque_fn(image)` →
	(masque de rue, largeur, hauteur)."""
	par_id = {d.get("_id"): d for d in docs}
	refus = []
	if CITE not in par_id:
		return [], [f"{CITE} : absent du dump"], {}
	for p in PORTES:
		for img in (p["image_ext"], p["image_int"]):
			if not ggi.trouver_image(img):
				refus.append(f"{img} : image absente de templates/resources")
	sortie = par_id.get(SORTIE_SUD["_id"])
	if not sortie:
		refus.append(f"{SORTIE_SUD['_id']} : absent du dump")
	if refus:
		return [], refus, {}

	cite = copy.deepcopy(sans_rev(par_id[CITE]))
	cells = [list(ligne) for ligne in cite["cells"]]
	nav = dict(cite.get("nav") or {})
	cols, rows = len(cells[0]), len(cells)
	anneau, interieur = anneau_et_interieur(ENCEINTE, cols, rows)
	rue, largeur, hauteur = masque_fn(cite["image"])
	if (largeur, hauteur) != (cols * K_CASE, rows * K_CASE):
		return [], [f"{cite['image']} : {largeur}×{hauteur} px, {K_CASE} px la case attendus"], {}
	murs_nav = grille_traits(cells, nav, rue, largeur, interieur)
	murs = cases_du_rempart() | anneau
	for x, y in anneau:
		nav.pop(f"{x},{y}", None)
	fermees = fermer_rempart(cells, {c for c in murs if cells[c[1]][c[0]] != grille_image.TERRAIN_EAU})
	ouvrir_passages(cells, nav)
	if atteint(cells, nav, ANCRE_DEDANS) & atteint(cells, nav, ANCRE_DEHORS):
		return [], [f"{CITE} : le rempart fermé laisse encore passer du dedans au dehors"], {}
	cout = cout_depuis_luminances(luminances_fn(cite["image"], cols, rows))
	ouvertures = relier_rues(cells, nav, murs, ENCEINTE, cout)
	dedans, dehors = atteint(cells, nav, ANCRE_DEDANS), atteint(cells, nav, ANCRE_DEHORS)
	if dedans & dehors:
		return [], [f"{CITE} : dedans et dehors se rejoignent après les rues"], {}
	cite["cells"], cite["nav"] = cells, nav
	sortants = [cite]

	for p in PORTES:
		pos_dehors, pos_dedans = case_proche(dehors, p["dehors"]), case_proche(dedans, p["dedans"])
		sortants += docs_porte(CITE, p, pos_dehors, pos_dedans)

	sortie = copy.deepcopy(sans_rev(sortie))   # nœuds partagés avec le dump sinon
	noeud = next(n for n in sortie["nodes"] if n.get("lieu") == CITE)
	if tuple(SORTIE_SUD["pos"]) not in dehors:
		refus.append(f"{SORTIE_SUD['_id']} : {list(SORTIE_SUD['pos'])} hors des faubourgs")
	noeud["pos"] = list(SORTIE_SUD["pos"])
	sortants.append(sortie)

	# Toute connexion de la cité doit tomber sur une case joignable (dedans ou dehors).
	joignables = dedans | dehors
	emis_ids = {d["_id"] for d in sortants}
	for d in sortants + [d for d in docs if d.get("type") == "connection"
						  and d["_id"] not in emis_ids]:
		for n in d.get("nodes", []):
			if n.get("lieu") == CITE and tuple(n["pos"]) not in joignables:
				refus.append(f"{d['_id']} : case {n['pos']} injoignable après le rempart")
	impasses = sorted(c for c in dedans if voisins_a_pied(cells, nav, *c) <= 1)
	rapport = {"fermees": fermees, "murs_nav": murs_nav, "ouvertures": ouvertures,
			   "dedans": len(dedans),
			   "dehors": len(dehors), "impasses": impasses}
	return sortants, refus, rapport


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

	def luminances(image, cols, rows):
		return luminances_image(ggi.trouver_image(image), cols, rows)

	def masque(image):
		return masque_image(ggi.trouver_image(image))

	sortants, refus, rapport = construire(docs, luminances, masque)
	for r in refus:
		print(f"✗ {r}")
	if refus:
		print("✗ lot refusé : rien n'est écrit.")
		return 1
	print(f"{CITE} — {rapport['fermees']} case(s) de rempart fermée(s) · "
		  f"{rapport['murs_nav']} mur(s) nav posé(s) sur les traits · dedans "
		  f"{rapport['dedans']} cases, dehors {rapport['dehors']}")
	for motif, cases in rapport["ouvertures"]:
		print(f"  {motif} : {[list(c) for c in cases]}")
	print(f"  impasses restantes : {[list(c) for c in rapport['impasses']]}")
	if "--sans-apercu" not in args:
		cite = sortants[0]
		ggi.ecrire_apercu(ggi.trouver_image(cite["image"]), cite["cells"], APERCU, cite["nav"])
		print(f"  ✎ {os.path.relpath(APERCU, RACINE)}")
	emis, refus = a_emettre(docs, sortants)
	for r in refus:
		print(f"✗ {r}")
	if refus:
		return 1
	if not emis:
		print("Rien à importer : le dump contient déjà tout.")
		return 0
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(emis, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"✎ {os.path.relpath(SORTIE, RACINE)} — {len(emis)} doc(s) à importer")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
