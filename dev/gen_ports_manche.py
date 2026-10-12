"""Calais et Douvres, leurs quais, la Manche et les traversées qui les relient — UN seul fichier
d'import (CLAUDE.md §18).

POURQUOI : le système de traversées maritimes (`utils/traversee.py`, `routers/traversee.py`,
service PNJ `traversee`) n'a de sens qu'avec deux ports. Ce générateur les crée depuis les
images déposées et tout ce qui les rend jouables :

  · `lieu:calais` (sous `lieu:plaine_europeenne`, côte picarde) et `lieu:douvres` (sous
    `lieu:angleterre`, pointe du Kent) — grille PROPOSÉE (`gen_grille_image.proposer_pour_image`,
    profil ville : rues, enceinte, coins, passages), puis le RÉSEAU INTERNE rendu continu : les
    PORTES dessinées du rempart sont ouvertes dans `nav` (la proposition ferme l'enceinte par nav
    et coupe la ville de ses faubourgs) ; une sortie par route vers la carte du pays, sur le
    schéma de `gen_villes_pays` (`cases_autour` / `case_proche`, « Calais — par le sud ») ;
  · les QUAIS : une case du quai, au bord du bassin, ouverte et reliée au réseau, porte la
    connexion vers le sous-lieu `lieu:<cité>_quais` (catégorie `quai`, image fournie), où se
    tient le capitaine (`probabilite: 1`) ;
  · les CAPITAINES `pnj:capitaine_calais` / `pnj:capitaine_douvres` : dialogue + service
    `traversee` (chacun vend SA route) ;
  · `lieu:manche` (catégorie `mer`, image `maps/manche.jpg`), SANS connexion : on n'y est que
    sur un navire. Grille à 1 partout (le navire ne la lit pas) ;
  · les routes `traversee:calais_douvres` et `traversee:douvres_calais` : points de passage sur
    l'eau de la Manche, danger gradué par segment (côtier au départ et à l'arrivée, haute mer
    au milieu), rencontres marines ;
  · les ponts de navire `lieu:pont_de_navire0001`…`0004` (catégorie `battle_map`, tags
    `mer`/`eau`/`navire`/`pont`) : `select_battle_map` les tire pour un combat en mer (les zones
    marines portent `mer`/`eau`). Grille de première passe : le bois du pont est praticable,
    l'eau et les monstres non — à retoucher dans l'éditeur.

CRÉÉ UNE FOIS : un lieu déjà dans le dump garde sa grille (les retouches de l'éditeur survivent
au rejeu) ; ÉMIS = ce qui DIFFÈRE du dump (`gen_voisins_france.a_emettre`) — un rejeu sur un
dump à jour n'écrit rien. ⚠️ Import = PUT COMPLET (CLAUDE.md §11).

Usage :
  python dev/gen_ports_manche.py [--dump jsons/telluris-dump-….json] [--sans-apercu]

Sortie : jsons/ports_manche_a_importer.json (+ jsons/<slug>_grille_apercu.png par cité créée)
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_grille_image as ggi  # noqa: E402
from dev.gen_plaine_europeenne import (  # noqa: E402
	case_proche, cases_autour, connexion, libelle_sortie, sans_rev, zone_de)
from dev.gen_villes_images import _taille_image, poser_grille, villes_a_creer  # noqa: E402
from dev.gen_voisins_france import a_emettre  # noqa: E402
from utils import grille_image  # noqa: E402
from utils.lieux import VALID_MOVES  # noqa: E402

RACINE = ggi.RACINE
SORTIE = os.path.join(ggi.DOSSIER_JSONS, "ports_manche_a_importer.json")

# ── Les deux cités ──────────────────────────────────────────────────────────────────────────
# Positions en CASES de la grille 88×48 de la cité (16 px), lues sur les images fournies :
#   · `dedans` : une case au cœur de la ville (ancre de la zone intra-muros) ;
#   · `dehors` : une case des faubourgs (ancre de la zone hors les murs) ;
#   · `portes` : les portes DESSINÉES du rempart — la paire dedans/dehors la plus proche y est
#     ouverte dans `nav` ;
#   · `sorties` : où chaque route quitte la carte (nom → case visée, ramenée à la plus proche
#     de la zone principale) ;
#   · `quai` : le bord du bassin où accoste le navire.
# Sur la carte du PAYS : `pays`, la case de la cité (ses voisines portent les autres sorties).
CITES = {
	"lieu:calais": {
		"image": "calais_city.jpg",
		"parent": "lieu:plaine_europeenne",
		# Côte picarde, au plus près du Kent (carte de la plaine européenne).
		"pays": (15, 34),
		"dedans": (52, 20),
		"dehors": (80, 44),
		# Les deux portes à pont-levis du rempart sud.
		"portes": ((36, 38), (63, 39)),
		"sorties": {"sud": (35, 47), "est": (87, 26), "nord_est": (70, 0)},
		# Quai est du bassin, entre les deux tours runiques.
		"quai": (36, 19),
	},
	"lieu:douvres": {
		"image": "douvres_city.jpg",
		"parent": "lieu:angleterre",
		# Pointe du Kent, la bourgade au bord de l'eau (carte d'Angleterre).
		"pays": (78, 38),
		"dedans": (40, 25),
		"dehors": (6, 30),
		# Porte du nord-ouest (sous les tours), porte au pont-levis du sud-ouest, porte basse sud.
		"portes": ((19, 14), (19, 37), (47, 41)),
		"sorties": {"ouest": (1, 26), "nord": (30, 1), "sud": (24, 46)},
		# Quai nord du bassin semi-circulaire, face aux navires amarrés.
		"quai": (60, 24),
	},
}

# Quais : sous-lieux de la cité (sans grille, nœud en [0, 0] comme une boutique). Portraits
# des capitaines : des marchands du fonds, en attendant les leurs (sans portrait, le panneau
# de dialogue se tasse en une colonne étroite).
QUAIS = {
	"lieu:calais": {"_id": "lieu:calais_quais", "label": "Les quais de Calais",
		"image": "quai_europe_calais01.jpg", "capitaine": "pnj:capitaine_calais",
		"nom": "Mahaut Lestrade", "portrait": "marchand_humain_f_negociant02.jpg"},
	"lieu:douvres": {"_id": "lieu:douvres_quais", "label": "Les quais de Douvres",
		"image": "quai_europe_douvres01.jpg", "capitaine": "pnj:capitaine_douvres",
		"nom": "Godwin Hale", "portrait": "marchand_ogre_m_salaison01.jpg"},
}

# ── La Manche et ses routes ─────────────────────────────────────────────────────────────────
MANCHE = "lieu:manche"
IMAGE_MANCHE = "manche.jpg"
DIMS_MANCHE = {"x": 88, "y": 48}

# Points de passage sur l'eau de `manche.jpg` (88×48, 16 px) : le bassin de Calais est à
# droite (~58, 27), les falaises de Douvres en haut à gauche (~25, 6). Le navire longe la côte
# au départ, traverse le Pas en haute mer, et longe les falaises à l'arrivée.
CHEMIN_CALAIS_DOUVRES = [[54, 27], [51, 25], [46, 21], [40, 17], [35, 13], [31, 10], [29, 8]]
# `de` = première étape du segment (index de case, 0 = départ).
SEGMENTS = [
	{"de": 0, "zone": "zone:mer_cotiere", "intensite": 0.08},
	{"de": 5, "zone": "zone:haute_mer", "intensite": 0.18},
	{"de": 22, "zone": "zone:mer_cotiere", "intensite": 0.08},
]
# Rencontres par zone : le bestiaire MARIN du dump (pas de crocodile ni de naïade d'eau douce
# dans le Pas, pas de léviathan ni de kraken polaire). Chaque espèce est vérifiée au dump.
RENCONTRES = {
	"zone:mer_cotiere": ["espece:sirene", "espece:triton", "espece:nereide", "espece:ondin",
		"espece:poissons_mammiferes_marins"],
	"zone:haute_mer": ["espece:kraken", "espece:triton", "espece:sirene", "espece:oceanide",
		"espece:poissons_mammiferes_marins"],
}
# Grades : une traversée commerciale n'est pas une chasse au kraken — surtout des grades bas.
PROFIL_WEIGHTS = {"profil:novice": 3, "profil:apprenti": 3, "profil:combattant": 2,
	"profil:veteran": 1}
PRIX = {"passager_cuivre": 150, "monture_cuivre": 100}

# ── Ponts de navire (cartes de combat) ──────────────────────────────────────────────────────
PONTS = {
	"pont_de_navire0001.jpg": "Sur le pont d'un navire assailli par des serpents de mer",
	"pont_de_navire0002.jpg": "Sur le pont d'un navire étreint par une bête à tentacules",
	"pont_de_navire0003.jpg": "Sur le pont d'un drakkar battu par l'orage",
	"pont_de_navire0004.jpg": "Sur le pont d'un galion pris dans les bras d'un kraken",
}
TAGS_PONT = ["mer", "eau", "navire", "pont"]
DIMS_PONT = {"x": 32, "y": 18}


# ── Réseau interne ──────────────────────────────────────────────────────────────────────────
_BITS = {(dx, dy): (bit, op) for bit, dx, dy, op in VALID_MOVES}


def ouvrir_pas(nav: dict, a, b) -> None:
	"""Lève le mur nav entre deux cases voisines, dans les deux sens."""
	dx, dy = b[0] - a[0], b[1] - a[1]
	bit, op = _BITS[(dx, dy)]
	for (x, y), masque in ((a, bit), (b, op)):
		cle = f"{x},{y}"
		reste = nav.get(cle, 0) & ~masque
		if reste:
			nav[cle] = reste
		else:
			nav.pop(cle, None)


def ouvrir_porte(cells, nav, zone_dedans: set, zone_dehors: set, cible):
	"""Ouvre la paire (dedans, dehors) ORTHOGONALEMENT voisine la plus proche de `cible` ;
	à défaut, perce une case murée entre les deux (rempart d'une case d'épaisseur). Renvoie
	les cases ouvertes, ou None si rien n'est à moins de 4 cases."""
	cx, cy = cible
	paires = []
	for (x, y) in zone_dedans:
		if abs(x - cx) > 4 or abs(y - cy) > 4:
			continue
		for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
			if (x + dx, y + dy) in zone_dehors:
				paires.append(((x - cx) ** 2 + (y - cy) ** 2, (x, y), (x + dx, y + dy), None))
			w = (x + dx, y + dy)
			if (x + 2 * dx, y + 2 * dy) in zone_dehors and grille_image._dans(cells, *w) \
					and cells[w[1]][w[0]] != 1:
				paires.append(((x - cx) ** 2 + (y - cy) ** 2 + 1, (x, y),
							   (x + 2 * dx, y + 2 * dy), w))
	if not paires:
		return None
	_, a, b, mur = min(paires)
	if mur is None:
		ouvrir_pas(nav, a, b)
		return [a, b]
	cells[mur[1]][mur[0]] = 1
	nav.pop(f"{mur[0]},{mur[1]}", None)
	ouvrir_pas(nav, a, mur)
	ouvrir_pas(nav, mur, b)
	return [a, mur, b]


def case_de_quai(cells, zone: set, cible):
	"""La case de `zone` qui borde l'eau (5, voisinage 8) la plus proche de `cible`."""
	bord = {(x, y) for (x, y) in zone
			if any(grille_image._dans(cells, x + dx, y + dy) and cells[y + dy][x + dx] == 5
				   for dx in (-1, 0, 1) for dy in (-1, 0, 1))}
	return case_proche(bord, cible)


def zone_proche(cells, nav, ancre) -> set:
	"""La zone praticable de la case praticable la plus proche de `ancre` (vide s'il n'y en a
	aucune) : une ancre lue à l'œil sur l'image peut tomber sur un toit."""
	zone, _tailles = grille_image.zones(cells, nav)
	libres = {(x, y) for y, ligne in enumerate(zone) for x, v in enumerate(ligne) if v != -1}
	case = case_proche(libres, ancre)
	if case is None:
		return set()
	z = zone[case[1]][case[0]]
	return {(x, y) for y, ligne in enumerate(zone) for x, v in enumerate(ligne) if v == z}


def reseau_interne(cite_id: str, spec: dict, cells, nav):
	"""(cells, nav, rapport, refus) : portes ouvertes, ville d'un seul tenant, quai trouvé."""
	refus, ouvertes = [], []
	dedans = zone_proche(cells, nav, spec["dedans"])
	dehors = zone_proche(cells, nav, spec["dehors"])
	if not dedans or not dehors:
		return cells, nav, {}, [f"{cite_id} : ancre dedans/dehors hors de toute zone praticable"]
	# Chaque porte dessinée ouvre SON passage — toutes, pas seulement la première qui suffit.
	for porte in spec["portes"]:
		cases = ouvrir_porte(cells, nav, dedans, dehors, porte)
		if not cases:
			refus.append(f"{cite_id} : aucune porte ouvrable près de {list(porte)}")
			continue
		ouvertes.append(cases)
	principale = zone_proche(cells, nav, spec["dedans"])
	if not (principale & dehors):
		refus.append(f"{cite_id} : la ville et ses faubourgs restent séparés après les portes")
	quai = case_de_quai(cells, principale, spec["quai"])
	if quai is None:
		refus.append(f"{cite_id} : aucune case du réseau ne borde le bassin")
	return cells, nav, {"portes": ouvertes, "quai": quai, "zone": principale}, refus


# ── Docs ────────────────────────────────────────────────────────────────────────────────────
def connexions_cite(cite_id, label, spec, zone_cite, zone_pays):
	"""(docs, refus) des liens pays ↔ cité, un par sortie (schéma de `gen_villes_pays`)."""
	slug = cite_id.split(":", 1)[1]
	pays = spec["parent"]
	cases_pays = cases_autour(zone_pays, spec["pays"], len(spec["sorties"]))
	if not cases_pays:
		return [], [f"{cite_id} : pas {len(spec['sorties'])} cases libres autour de "
					f"{list(spec['pays'])} sur {pays}"]
	docs = []
	for (nom, cible), pos_pays in zip(spec["sorties"].items(), cases_pays):
		pos_cite = case_proche(zone_cite, cible)
		doc = connexion(f"link:{pays.split(':', 1)[1]}_to_{slug}_{nom}", pays, pos_pays,
						cite_id, pos_cite)
		doc["nodes"][1]["label"] = libelle_sortie(label, nom)
		docs.append(doc)
	return docs, []


def doc_quais(cite_id: str, q: dict) -> dict:
	return {"_id": q["_id"], "type": "lieu", "label": q["label"], "image": q["image"],
			"categorie": "quai", "lieu_parent": cite_id,
			"pnj": [{"character": q["capitaine"], "nom": q["nom"], "portrait": q["portrait"],
					 "probabilite": 1}]}


def lien_quais(cite_id: str, q: dict, pos) -> dict:
	slug = cite_id.split(":", 1)[1]
	doc = connexion(f"link:quai01_to_{slug}", cite_id, pos, q["_id"], (0, 0))
	doc["metadata"] = {"type": "quai", "status": "ouvert"}
	return doc


def doc_manche() -> dict:
	return {"_id": MANCHE, "type": "lieu", "label": "Le Pas de Calais", "image": IMAGE_MANCHE,
			"categorie": "mer", "dimensions": dict(DIMS_MANCHE),
			"cells": [[1] * DIMS_MANCHE["x"] for _ in range(DIMS_MANCHE["y"])],
			"texte": "Le navire file sur les eaux grises du Pas. Les marins guettent la houle.",
			"tags": ["mer"]}


def rencontres_route() -> list:
	par_espece: dict = {}
	for zone, especes in RENCONTRES.items():
		for e in especes:
			par_espece.setdefault(e, []).append(zone)
	return [{"espece": e, "zones": zs} for e, zs in sorted(par_espece.items())]


def doc_route(depart_cite: str, arrivee_cite: str, chemin: list) -> dict:
	d, a = depart_cite.split(":", 1)[1], arrivee_cite.split(":", 1)[1]
	total = len(_cases(chemin))
	# Le segment d'arrivée commence `5` cases avant le bout, quel que soit le sens.
	segments = [dict(SEGMENTS[0]), dict(SEGMENTS[1]),
				dict(SEGMENTS[2], de=max(SEGMENTS[1]["de"] + 1, total - 5))]
	return {"_id": f"traversee:{d}_{a}", "type": "traversee",
			"label": f"Traversée vers {a.capitalize()}",
			"depart": {"lieu": QUAIS[depart_cite]["_id"]},
			"arrivee": {"lieu": QUAIS[arrivee_cite]["_id"], "pos": [0, 0]},
			"carte": MANCHE, "chemin": chemin, "segments": segments,
			"rencontres": rencontres_route(), "profil_weights": dict(PROFIL_WEIGHTS),
			"prix": dict(PRIX)}


def _cases(chemin):
	from utils.traversee import cases_du_chemin
	return cases_du_chemin(chemin)


def doc_capitaine(cite_id: str, route_id: str, port: str) -> dict:
	"""Le capitaine d'un quai. ⚠️ Aucun nom de PNJ en dur dans un texte : {pnj}."""
	if cite_id == "lieu:calais":
		_id, race, accueil, danger = (
			"pnj:capitaine_calais", "humain",
			"{pnj} lève les yeux d'un rouleau de cordage. « Pour Douvres ? Le Pas est court, mais "
			"il a des dents. On part avec la marée, on arrive avant la nuit, la plupart du temps. "
			"Pour vous tous — {passagers} à bord —, ce sera {tarif}. »",
			"« Des sirènes près des côtes, qui chantent pour qu'on approche des récifs. Au large, "
			"des tritons, et parfois un bras de kraken qui sort de l'eau sans prévenir. » {pnj} "
			"montre du menton les deux tours dont les runes rougeoient au-dessus du bassin. « Tant "
			"qu'on les voit briller, rien n'entre au port. Après, c'est l'équipage… et vous. »",
		)
	else:
		_id, race, accueil, danger = (
			"pnj:capitaine_douvres", "ogre",
			"{pnj} se déplie de toute sa hauteur sur le quai. « Calais ? Bonne idée, la mer est "
			"calme. Pour l'instant. Avec vous tous — {passagers} à bord —, le passage coûte "
			"{tarif}. »",
			"« Le vieux phare des falaises nous garde l'entrée du port, depuis plus longtemps que "
			"n'importe qui ne s'en souvient. Plus loin, il ne garde plus rien. » {pnj} hausse ses "
			"énormes épaules. « Les serpents suivent les coques, les sirènes guettent les "
			"imprudents. On repousse ce qui monte à bord. Le reste, on le contourne. »",
		)
	return {
		"_id": _id, "type": "pnj", "nom": QUAIS[cite_id]["nom"], "race": race,
		"portrait": QUAIS[cite_id]["portrait"],
		"vocation": "guerrier",
		"description": (f"{'Patronne' if cite_id == 'lieu:calais' else 'Patron'} d'un navire "
						f"qui fait la traversée du Pas vers {port}."),
		"services": {"traversee": {"route": route_id,
								   "noeuds": {"embarque": "a_bord", "sans_fonds": "pauvre"}}},
		"dialogue": {"noeud_depart": "accueil", "noeuds": {
			"accueil": {"texte": accueil, "choix": [
				{"id": "embarquer", "label": "Payer {tarif} et monter à bord.",
				 "action": {"service": "traversee", "op": "embarquer"}},
				{"id": "danger", "label": "Qu'est-ce qui rôde au large ?", "next": "danger"},
				{"id": "fin", "label": "Une autre fois.", "next": "fin"}]},
			"danger": {"texte": danger, "choix": [
				{"id": "retour", "label": "Revenir au passage.", "next": "accueil"},
				{"id": "fin", "label": "Une autre fois.", "next": "fin"}]},
			"a_bord": {"texte": f"« Larguez les amarres ! » Le navire s'écarte du quai et prend le "
								f"vent. Cap sur {port}.",
					   "choix": [{"id": "fin", "label": "Monter à bord.", "next": "fin"}]},
			"pauvre": {"texte": "{pnj} compte vos pièces et secoue la tête. « Ça ne paie pas la "
								"place. Revenez avec {tarif}, et on lève l'ancre. »",
					   "choix": [{"id": "fin", "label": "Repartir.", "next": "fin"}]},
		}},
	}


def doc_pont(image: str, label: str, cells) -> dict:
	return {"_id": f"lieu:{os.path.splitext(image)[0]}", "type": "lieu", "label": label,
			"image": image, "dimensions": dict(DIMS_PONT), "cells": cells,
			"tags": list(TAGS_PONT), "categorie": "battle_map"}


def grille_pont(pixels, largeur, hauteur) -> list:
	"""Première passe d'un pont de navire : une case est praticable si sa couleur moyenne est
	CHAUDE (bois du pont : rouge au-dessus du bleu, même dans l'orage), sinon 0 (mer, ciel,
	monstres) ;
	seule la plus grande zone chaude est gardée (le pont, pas une voile isolée)."""
	cw, ch = largeur / DIMS_PONT["x"], hauteur / DIMS_PONT["y"]
	cells = []
	for y in range(DIMS_PONT["y"]):
		ligne = []
		for x in range(DIMS_PONT["x"]):
			rs = gs = bs = n = 0
			for py in range(int(y * ch), int((y + 1) * ch), 3):
				for px in range(int(x * cw), int((x + 1) * cw), 3):
					r, g, b = pixels[px, py][:3]
					rs, gs, bs, n = rs + r, gs + g, bs + b, n + 1
			r, g, b = rs / n, gs / n, bs / n
			ligne.append(1 if (r > b + 6 and r > 40) else 0)
		cells.append(ligne)
	zone, tailles = grille_image.zones(cells, {})
	if not tailles:
		return cells
	grande = max(range(len(tailles)), key=tailles.__getitem__)
	return [[1 if zone[y][x] == grande else 0 for x in range(DIMS_PONT["x"])]
			for y in range(DIMS_PONT["y"])]


def _grille_pont_image(image: str):
	from PIL import Image
	with Image.open(ggi.trouver_image(image)) as img:
		img = img.convert("RGB")
		return grille_pont(img.load(), *img.size)


# ── Construction ────────────────────────────────────────────────────────────────────────────
def construire(docs, taille_fn, proposer_fn, grille_pont_fn):
	"""(sortants, refus, rapports) — docs complets (`_rev` retiré)."""
	par_id = {d.get("_id"): d for d in docs}
	refus, rapports, sortants = [], {}, []
	for e in sorted({e for es in RENCONTRES.values() for e in es}) + sorted(PROFIL_WEIGHTS):
		if e not in par_id:
			refus.append(f"{e} : absent du dump")
	for z in {s["zone"] for s in SEGMENTS}:
		if z not in par_id:
			refus.append(f"{z} : absent du dump")
	for img in [c["image"] for c in CITES.values()] + [q["image"] for q in QUAIS.values()] \
			+ [IMAGE_MANCHE] + list(PONTS):
		if not ggi.trouver_image(img):
			refus.append(f"{img} : image absente de templates/resources")
	if refus:
		return [], refus, {}

	neuves, refus_v = villes_a_creer(
		[c["image"] for cid, c in CITES.items() if cid not in par_id], docs, taille_fn)
	refus += refus_v
	neuves = {d["_id"]: d for d in neuves}
	for cite_id, spec in CITES.items():
		if cite_id in par_id:
			cite = sans_rev(par_id[cite_id])   # créée une fois : grille de l'éditeur gardée
			cells, nav = cite["cells"], cite.get("nav") or {}
			principale = zone_proche(cells, nav, spec["dedans"])
			quai = case_de_quai(cells, principale, spec["quai"])
		else:
			cite = neuves.get(cite_id)
			if not cite:
				refus.append(f"{cite_id} : non créée depuis {spec['image']}")
				continue
			cite["lieu_parent"] = spec["parent"]
			prop = proposer_fn(cite)
			cells, nav, rapport, refus_r = reseau_interne(
				cite_id, spec, prop["cells"], dict(prop["nav"]))
			refus += refus_r
			rapports[cite_id] = dict(rapport, proposition=prop)
			cite = poser_grille(cite, {"cells": cells, "nav": nav})
			principale, quai = rapport.get("zone") or set(), rapport.get("quai")
		sortants.append(cite)
		pays = par_id.get(spec["parent"])
		if not pays:
			refus.append(f"{spec['parent']} : absent du dump")
			continue
		zone_pays = zone_proche(pays["cells"], pays.get("nav") or {}, spec["pays"])
		liens, refus_l = connexions_cite(cite_id, cite["label"], spec, principale, zone_pays)
		refus += refus_l
		sortants += liens
		if quai is None:
			refus.append(f"{cite_id} : pas de case de quai")
			continue
		q = QUAIS[cite_id]
		sortants += [doc_quais(cite_id, q), lien_quais(cite_id, q, quai)]

	sortants.append(doc_manche())
	# Le retour reprend l'aller CASE PAR CASE, à l'envers (l'arrondi de `cases_du_chemin`
	# n'est pas symétrique : inverser les seuls points de passage donnerait un autre tracé).
	retour = list(reversed(_cases(CHEMIN_CALAIS_DOUVRES)))
	routes = [doc_route("lieu:calais", "lieu:douvres", CHEMIN_CALAIS_DOUVRES),
			  doc_route("lieu:douvres", "lieu:calais", retour)]
	sortants += routes
	sortants += [doc_capitaine("lieu:calais", routes[0]["_id"], "Douvres"),
				 doc_capitaine("lieu:douvres", routes[1]["_id"], "Calais")]
	for image, label in PONTS.items():
		pid = f"lieu:{os.path.splitext(image)[0]}"
		sortants.append(sans_rev(par_id[pid]) if pid in par_id
						else doc_pont(image, label, grille_pont_fn(image)))
	return sortants, refus, rapports


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

	sortants, refus, rapports = construire(docs, _taille_image, proposer, _grille_pont_image)
	for r in refus:
		print(f"✗ {r}")
	if refus:
		print("✗ lot refusé : rien n'est écrit.")
		return 1
	for cite_id, rapport in rapports.items():
		print(f"{cite_id} — portes ouvertes : {rapport['portes']} · quai {list(rapport['quai'])}")
		if "--sans-apercu" not in args:
			doc = next(d for d in sortants if d["_id"] == cite_id)
			slug = cite_id.split(":", 1)[1]
			apercu = os.path.join(ggi.DOSSIER_JSONS, f"{slug}_grille_apercu.png")
			ggi.ecrire_apercu(ggi.trouver_image(doc["image"]), doc["cells"], apercu, doc["nav"],
							  rapport["proposition"]["rapport"])
			print(f"  ✎ {os.path.relpath(apercu, RACINE)}")
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
