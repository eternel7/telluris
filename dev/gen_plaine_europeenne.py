"""La Plaine européenne, Bruges et Aix-la-Chapelle — et les outils de FRONTIÈRE partagés.

Bibliothèque de `dev/gen_voisins_france.py` (qui écrit le fichier à importer unique) ; pas de
point d'entrée propre.

TROIS LIEUX : les deux cités sont POSÉES sur la plaine (`lieu_parent` + connexions) et la
plaine est rattachée à `lieu:france`. Docs minimaux par `cartes_a_creer` / `villes_a_creer`,
grilles par `gen_grille_image.proposer_pour_image` (profil `pays` : côte murée en nav ; profil
ville : `cells` + `nav`). Déjà en base ⇒ le doc RELU du dump sert de base (retouches gardées).

RÈGLE DES FRONTIÈRES — on ne passe d'une carte à l'autre QUE par une connexion :
  · le territoire du VOISIN que montre une carte est mis à 0 (`FRONTIERE_*`, bandes lues sur
    l'image) : il ne se traverse plus, le joueur doit prendre la connexion ;
  · les connexions se posent SUR la frontière, du côté accessible — avant la limite des murs
    nav quand la carte montre plus loin que la frontière.
  · cité ↔ plaine : sur la plaine, la case de la cité et ses voisines (une case par lien, le
    schéma de Reims ↔ France) ; dans la cité, une sortie par route qui quitte la carte.
  Chaque case visée est ramenée à la case libre la plus proche DANS LA ZONE de la terre de sa
  carte (`zone_de`, ancrée sur un point de terre : sur une carte de pays la mer est une zone à
  part, parfois plus grande que la terre) ; aucune case ⇒ lot refusé.
"""

import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_grille_image as ggi  # noqa: E402
from dev.gen_cartes_pays import cartes_a_creer  # noqa: E402
from dev.gen_villes_images import poser_grille, villes_a_creer  # noqa: E402
from utils import grille_image  # noqa: E402

IMAGE_PLAINE = "plaine_europeenne.jpg"
PLAINE = "lieu:plaine_europeenne"
FRANCE = "lieu:france"
IMAGES_CITES = ("bruges_city.jpg", "aix_la_chapelle_city.jpg")

# Un point de TERRE par carte de pays : la zone qui le contient est celle où l'on marche.
ANCRE_PLAINE = (41, 29)    # Aix-la-Chapelle
ANCRE_FRANCE = (45, 25)    # Massif central

# Place des cités sur la plaine (lue sur l'image, 88×48 cases de 16 px) :
#   Bruges — le château dessiné sur le delta de l'Escaut, au débouché du Zwin ;
#   Aix-la-Chapelle — entre Meuse et Rhin, au nord des forêts de l'Ardenne et de l'Eifel.
POSITIONS_PLAINE = {
	"lieu:bruges": (28, 25),
	"lieu:aix_la_chapelle": (41, 29),
}

# Sorties des cités : nom → point visé (une route qui quitte la carte, hors du cadre).
# Bruges n'a pas de sortie au nord : c'est le Zwin et la mer.
SORTIES_CITES = {
	"lieu:bruges": {"ouest": (1, 30), "sud": (40, 46), "est": (86, 30)},
	"lieu:aix_la_chapelle": {"nord": (53, 1), "ouest": (4, 22), "est": (83, 20), "sud": (55, 43)},
}

# Le NORD DE LA FRANCE sur la plaine, mis à 0 : (x_min, x_max, y) ⇒ cases y ≥ `y` à 0.
# Côte picarde, puis la frontière au sud de l'Ardenne, la Lorraine et l'Alsace jusqu'au Rhin ;
# au-delà (x ≥ 56) le bas de la carte est l'Empire, pas la France.
FRONTIERE_PLAINE = ((0, 12, 38), (13, 20, 39), (21, 34, 41), (35, 44, 43), (45, 55, 45))

# France ↔ plaine : (case visée sur la France, case visée sur la plaine), d'ouest en est —
# Flandres, Ardenne, Luxembourg, Rhin. Sur la France, la rangée 1 peinte (nord fermé par nav)
# EST la frontière ; sur la plaine, la case juste au nord de la bande mise à 0.
PASSAGES_PLAINE = (((49, 1), (16, 38)), ((56, 1), (28, 40)), ((64, 1), (39, 42)),
	((76, 1), (50, 44)))

METADATA = {"type": "chemin", "status": "ouvert"}

# Voisines d'une case, dans l'ordre où les liens les prennent (la case elle-même d'abord).
VOISINES = ((0, 0), (1, 0), (0, 1), (1, 1), (-1, 0), (0, -1), (-1, -1), (1, -1), (-1, 1))


# ── Outils de frontière (partagés avec gen_france_espagne_italie) ────────────────────────────
def zone_de(cells, nav, ancre=None):
	"""Cases `(x, y)` de la zone de `ancre` sous la règle de marche, ou de la plus grande zone
	sans ancre. Ancre hors de toute zone ⇒ ensemble vide."""
	zone, tailles = grille_image.zones(cells, nav)
	if not tailles:
		return set()
	if ancre is not None:
		x, y = ancre
		z = zone[y][x] if grille_image._dans(cells, x, y) else -1
		if z == -1:
			return set()
	else:
		z = max(range(len(tailles)), key=tailles.__getitem__)
	return {(x, y) for y, ligne in enumerate(zone) for x, v in enumerate(ligne) if v == z}


def case_proche(principale, cible):
	"""La case de `principale` la plus proche de `cible` (euclidienne, puis y, puis x) ou None."""
	if not principale:
		return None
	cx, cy = cible
	return min(principale, key=lambda c: ((c[0] - cx) ** 2 + (c[1] - cy) ** 2, c[1], c[0]))


def cases_autour(principale, centre, n):
	"""`n` cases distinctes de `principale` autour de `centre` (lui d'abord), ou None."""
	cases = [(centre[0] + dx, centre[1] + dy) for dx, dy in VOISINES]
	cases = [c for c in cases if c in principale]
	return cases[:n] if len(cases) >= n else None


def cases_frontiere(bandes, sens, cols, rows):
	"""Cases mises à 0 par `bandes` = ((x_min, x_max, y), …) : y ≥ `y` si `sens` est 'sud',
	y ≤ `y` si 'nord'."""
	cases = set()
	for x_min, x_max, borne in bandes:
		for x in range(max(0, x_min), min(cols - 1, x_max) + 1):
			ys = range(borne, rows) if sens == "sud" else range(0, min(rows - 1, borne) + 1)
			cases.update((x, y) for y in ys)
	return cases


def fermer(cells, cases) -> int:
	"""Met `cases` à 0 dans `cells` (muté) ; rend le nombre de cases changées."""
	n = 0
	for x, y in cases:
		if grille_image._dans(cells, x, y) and cells[y][x] != 0:
			cells[y][x] = 0
			n += 1
	return n


def connexion(_id, lieu_a, pos_a, lieu_b, pos_b):
	return {"_id": _id, "type": "connection",
		"nodes": [{"lieu": lieu_a, "pos": list(pos_a)}, {"lieu": lieu_b, "pos": list(pos_b)}],
		"metadata": dict(METADATA)}


def lien_vise(_id, lieu_a, zone_a, cible_a, lieu_b, zone_b, cible_b):
	"""(doc, refus) : chaque bout ramené à la case de sa zone la plus proche du point visé."""
	pos_a, pos_b = case_proche(zone_a, cible_a), case_proche(zone_b, cible_b)
	if pos_a is None or pos_b is None:
		manque = lieu_a if pos_a is None else lieu_b
		return None, f"{_id} : aucune case accessible sur {manque}"
	return connexion(_id, lieu_a, pos_a, lieu_b, pos_b), None


def sans_rev(doc):
	return {k: v for k, v in doc.items() if k != "_rev"}


# ── La plaine et ses cités ───────────────────────────────────────────────────────────────
def lieux_a_creer(docs, taille_fn):
	"""(plaine, [cités], refus) — docs SANS grille des lieux ABSENTS du dump."""
	ids = {d.get("_id") for d in docs}
	plaines, cites, refus = [], [], []
	if PLAINE not in ids:
		plaines, refus = cartes_a_creer([IMAGE_PLAINE], docs, taille_fn)
		if not plaines and not refus:
			refus.append(f"{IMAGE_PLAINE} : déjà citée par un autre lieu, ou absente de CARTES")
	manquantes = [nom for nom in IMAGES_CITES
		if f"lieu:{os.path.splitext(nom)[0].rsplit('_city', 1)[0]}" not in ids]
	if manquantes:
		cites, refus_c = villes_a_creer(manquantes, docs, taille_fn)
		refus += refus_c
	for cite in cites:
		cite["lieu_parent"] = PLAINE
	return (plaines[0] if plaines else None), sorted(cites, key=lambda c: c["_id"]), refus


def connexions_cite(cite_id, zone_cite, zone_plaine):
	"""(docs, refus) des liens plaine ↔ cité."""
	slug = cite_id.split(":", 1)[1]
	sorties = SORTIES_CITES[cite_id]
	centre = POSITIONS_PLAINE[cite_id]
	if centre not in zone_plaine:
		return [], [f"{cite_id} : la case {list(centre)} de la plaine n'est pas dans sa zone de terre"]
	cases_plaine = cases_autour(zone_plaine, centre, len(sorties))
	if not cases_plaine:
		return [], [f"{cite_id} : pas {len(sorties)} cases libres autour de {list(centre)} sur la plaine"]
	docs, refus = [], []
	for (nom, cible), pos_plaine in zip(sorties.items(), cases_plaine):
		pos_cite = case_proche(zone_cite, cible)
		if pos_cite is None:
			refus.append(f"{cite_id} : aucune case de sa zone principale pour la sortie {nom}")
			continue
		docs.append(connexion(f"link:plaine_europeenne_to_{slug}_{nom}",
			PLAINE, pos_plaine, cite_id, pos_cite))
	return docs, refus


def connexions_france_plaine(zone_france, zone_plaine):
	"""(docs, refus) des liens France ↔ plaine (`PASSAGES_PLAINE`)."""
	docs, refus = [], []
	for i, (cible_fr, cible_pl) in enumerate(PASSAGES_PLAINE, start=1):
		doc, r = lien_vise(f"link:france_to_plaine_europeenne_{i:02d}",
			FRANCE, zone_france, cible_fr, PLAINE, zone_plaine, cible_pl)
		if r:
			refus.append(r)
		else:
			docs.append(doc)
	return docs, refus


def construire(docs, taille_fn, proposer_fn, france):
	"""(lieux, liens, refus, propositions) de la plaine, de ses cités et des liens France ↔ plaine.

	`proposer_fn(doc, profil) -> {cells, nav, rapport}` : grille d'un lieu NEUF (Pillow côté
	CLI). Lieu déjà en base : son doc relu, seule la frontière y est appliquée.
	`lieux` = docs complets (`_rev` retiré), émis par l'appelant s'ils diffèrent du dump.
	`france` : le doc de la France TEL QU'IL SERA ÉCRIT (frontière espagnole posée par
	`gen_france_espagne_italie`) — lu ici, jamais modifié."""
	par_id = {d.get("_id"): d for d in docs}
	plaine_neuve, cites_neuves, refus = lieux_a_creer(docs, taille_fn)
	if refus:
		return [], [], refus, {}
	propositions = {}
	lieux = []
	neufs = ([plaine_neuve] if plaine_neuve else []) + cites_neuves
	for doc in neufs:
		prop = proposer_fn(doc, "pays" if doc["_id"] == PLAINE else "")
		propositions[doc["_id"]] = prop
		lieux.append(poser_grille(doc, prop))
	ids_neufs = {d["_id"] for d in lieux}
	for _id in [PLAINE] + sorted(POSITIONS_PLAINE):
		if _id not in ids_neufs:
			lieux.append(sans_rev(copy.deepcopy(par_id[_id])))
	par_lieu = {d["_id"]: d for d in lieux}

	plaine = par_lieu[PLAINE]
	dims = plaine["dimensions"]
	fermer(plaine["cells"], cases_frontiere(FRONTIERE_PLAINE, "sud", dims["x"], dims["y"]))
	zone_plaine = zone_de(plaine["cells"], plaine.get("nav") or {}, ANCRE_PLAINE)
	zone_france = zone_de(france.get("cells") or [], france.get("nav") or {}, ANCRE_FRANCE)

	liens, refus = connexions_france_plaine(zone_france, zone_plaine)
	for cite_id in sorted(POSITIONS_PLAINE):
		cite = par_lieu[cite_id]
		d, r = connexions_cite(cite_id, zone_de(cite["cells"], cite.get("nav") or {}), zone_plaine)
		liens += d
		refus += r
	return lieux, liens, refus, propositions
