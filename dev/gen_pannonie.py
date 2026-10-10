"""La Pannonie, entre l'Italie et la Roumanie : le lieu, sa grille, ses frontières et ses liens.

Bibliothèque de `dev/gen_voisins_france.py` (fichier à importer unique) ; même règle que
`gen_plaine_europeenne` : le territoire du voisin que montre une carte est mis à 0, la
connexion se pose SUR la frontière, du côté accessible.

  · PANNONIE (`maps/pannonie.jpg` : Alpes orientales, Adriatique, plaine du Danube,
    Carpates) — lieu de pays créé s'il est absent, grille du profil `pays` repartie d'un nav
    VIDE. ⚠️ `masque_eau` y lit aussi le vert pâle de la plaine hongroise et les neiges des
    Alpes comme de l'eau : seuls les murs du cadre de l'Adriatique (`NAV_ADRIATIQUE`) sont
    gardés. Et ces murs FUIENT (côte dalmate découpée, mer contre le cadre) : l'eau de ce
    cadre est donc mise à 0 — la mer est inaccessible, ce qui revient au même en jeu.
    Puis l'Italie qu'elle montre (Vénétie, péninsule) et la Roumanie (Crișana, Banat,
    Transylvanie, Olténie) mises à 0. Déjà en base : relue, seules les frontières posées.
  · ROUMANIE — la plaine pannonienne à l'ouest de sa frontière dessinée et la Serbie au sud
    du Danube mises à 0 ; ses murs ne perdent aucun bit.
  · Italie ↔ Pannonie : Brenner, Tarvisio, Gorizia, Trieste. Pannonie ↔ Roumanie : Oradea,
    Arad, Timișoara, les Portes de Fer.
"""

import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev.gen_cartes_pays import cartes_a_creer  # noqa: E402
from dev.gen_france_espagne_italie import ANCRE_ITALIE  # noqa: E402
from dev.gen_plaine_europeenne import (  # noqa: E402
	cases_frontiere, fermer, lien_vise, sans_rev, zone_de)
from dev.gen_villes_images import poser_grille  # noqa: E402

IMAGE_PANNONIE = "pannonie.jpg"
PANNONIE = "lieu:pannonie"
ITALIE = "lieu:italie"
ROUMANIE = "lieu:roumanie"

# Un point de TERRE par carte : la zone qui le contient est celle où l'on marche.
ANCRE_PANNONIE = (50, 25)  # la plaine de Slavonie
ANCRE_ROUMANIE = (35, 17)  # le plateau transylvain

# Cadre de l'Adriatique (x_min, x_max, y_min, y_max) : ses murs sont gardés et son eau mise
# à 0 ; hors de lui, tout mur est un faux rivage (plaine hongroise, neiges des Alpes), retiré.
NAV_ADRIATIQUE = (0, 50, 22, 47)

# L'ITALIE sur la carte de Pannonie, mise à 0 : (y_min, y_max, x) ⇒ cases x ≤ `x`.
# La Vénétie à l'ouest de l'Isonzo et du golfe de Trieste, puis la côte adriatique de la
# péninsule qui s'écarte vers l'est en descendant.
FRONTIERE_PANNONIE_ITALIE = ((21, 27, 13), (28, 32, 14), (33, 37, 16), (38, 41, 19),
	(42, 44, 21), (45, 47, 23))

# La ROUMANIE sur la carte de Pannonie, mise à 0 : (y_min, y_max, x) ⇒ cases x ≥ `x`.
# Maramureș, Crișana, Banat et Transylvanie à l'est de la plaine, l'Olténie jusqu'au Danube ;
# au sud du fleuve, la Serbie et la Bulgarie restent.
FRONTIERE_PANNONIE_ROUMANIE = ((0, 7, 70), (8, 35, 64))

# La PANNONIE sur la carte de Roumanie, mise à 0 : (y_min, y_max, x) ⇒ cases x ≤ `x`, à
# l'ouest de la frontière dessinée ; et la Serbie au sud du Danube : (x_min, x_max, y) ⇒ y ≥ `y`.
FRONTIERE_ROUMANIE_PANNONIE = ((0, 8, 18), (9, 16, 16), (17, 22, 13), (23, 36, 10))
FRONTIERE_ROUMANIE_SERBIE = ((0, 28, 37),)

# Italie ↔ Pannonie : (case visée sur l'Italie, case visée sur la Pannonie), d'ouest en est.
PASSAGES_ITALIE = (((44, 3), (6, 20)), ((51, 5), (12, 20)), ((52, 8), (14, 23)),
	((52, 11), (14, 26)))

# Pannonie ↔ Roumanie : (case visée sur la Pannonie, case visée sur la Roumanie), du nord au sud.
PASSAGES_ROUMANIE = (((63, 12), (19, 9)), ((63, 19), (14, 19)), ((63, 25), (11, 26)),
	((63, 31), (12, 34)))


def _bandes_pannonie(dims):
	return (cases_frontiere(FRONTIERE_PANNONIE_ITALIE, "ouest", dims["x"], dims["y"])
		| cases_frontiere(FRONTIERE_PANNONIE_ROUMANIE, "est", dims["x"], dims["y"]))


def preparer_pannonie(docs, taille_fn, proposer_fn, eau_fn):
	"""(doc, proposition | None, refus) : la Pannonie créée ou relue, frontières posées.
	`eau_fn(doc) -> eau[y][x]` : `grille_image.masque_eau` de l'image (Pillow côté CLI)."""
	par_id = {d.get("_id"): d for d in docs}
	if PANNONIE in par_id:
		doc = sans_rev(copy.deepcopy(par_id[PANNONIE]))
		fermer(doc["cells"], _bandes_pannonie(doc["dimensions"]))
		return doc, None, []
	neufs, refus = cartes_a_creer([IMAGE_PANNONIE], docs, taille_fn)
	if not neufs:
		return None, None, refus or [f"{IMAGE_PANNONIE} : déjà citée par un autre lieu, ou absente de CARTES"]
	prop = proposer_fn(neufs[0], "pays")
	doc = poser_grille(neufs[0], prop)
	x_min, x_max, y_min, y_max = NAV_ADRIATIQUE
	doc["nav"] = {k: v for k, v in prop["nav"].items()
		if x_min <= int(k.split(",")[0]) <= x_max and y_min <= int(k.split(",")[1]) <= y_max}
	eau = eau_fn(doc)
	fermer(doc["cells"], {(x, y) for y in range(y_min, y_max + 1) for x in range(x_min, x_max + 1)
		if eau[y][x]})
	bandes = _bandes_pannonie(doc["dimensions"])
	fermer(doc["cells"], bandes)
	for x, y in bandes:
		doc["nav"].pop(f"{x},{y}", None)
	return doc, prop, []


def preparer_roumanie(roumanie):
	"""Le doc de la Roumanie (copie, `_rev` retiré), la Pannonie et la Serbie qu'elle montre à 0."""
	doc = sans_rev(copy.deepcopy(roumanie))
	dims = doc["dimensions"]
	fermer(doc["cells"], cases_frontiere(FRONTIERE_ROUMANIE_PANNONIE, "ouest", dims["x"], dims["y"]))
	fermer(doc["cells"], cases_frontiere(FRONTIERE_ROUMANIE_SERBIE, "sud", dims["x"], dims["y"]))
	return doc


def _liens(prefixe, lieu_a, zone_a, lieu_b, zone_b, passages):
	docs, refus = [], []
	for i, (cible_a, cible_b) in enumerate(passages, start=1):
		doc, r = lien_vise(f"{prefixe}_{i:02d}", lieu_a, zone_a, cible_a, lieu_b, zone_b, cible_b)
		if r:
			refus.append(r)
		else:
			docs.append(doc)
	return docs, refus


def construire(docs, taille_fn, proposer_fn, eau_fn, italie):
	"""(lieux, liens, refus, propositions). `italie` : le doc de l'Italie TEL QU'IL SERA ÉCRIT
	(frontières posées par `gen_france_espagne_italie`) — lu ici, jamais modifié."""
	par_id = {d.get("_id"): d for d in docs}
	if not (par_id.get(ROUMANIE) or {}).get("cells"):
		return [], [], [f"{ROUMANIE} absent du dump ou sans grille"], {}
	pannonie, prop, refus = preparer_pannonie(docs, taille_fn, proposer_fn, eau_fn)
	if refus:
		return [], [], refus, {}
	roumanie = preparer_roumanie(par_id[ROUMANIE])
	zone_pan = zone_de(pannonie["cells"], pannonie.get("nav") or {}, ANCRE_PANNONIE)
	zone_rou = zone_de(roumanie["cells"], roumanie.get("nav") or {}, ANCRE_ROUMANIE)
	zone_ita = zone_de(italie["cells"], italie.get("nav") or {}, ANCRE_ITALIE)
	liens, refus = _liens("link:italie_to_pannonie", ITALIE, zone_ita, PANNONIE, zone_pan,
		PASSAGES_ITALIE)
	d, r = _liens("link:pannonie_to_roumanie", PANNONIE, zone_pan, ROUMANIE, zone_rou,
		PASSAGES_ROUMANIE)
	return [pannonie, roumanie], liens + d, refus + r, ({PANNONIE: prop} if prop else {})
