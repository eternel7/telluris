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
  · Italie ↔ Pannonie : Brenner, Tarvisio, Isonzo, Trieste, Resia. Pannonie ↔ Roumanie :
    Oradea, le Mureș, Timișoara, les Portes de Fer. Passages NOMMÉS (cf. gen_plaine_europeenne).
  · BUCAREST posée sur la Roumanie : la cité dessinée en Valachie ↔ une sortie par route, chacune
    dans l'EXTÉRIEUR de la ville qu'elle vise (sa grille peinte sépare l'extérieur ouest,
    l'extérieur est et l'intérieur, reliés par les portes de rempart) ; `lieu:bucarest`
    reçoit `lieu_parent: "lieu:roumanie"`.
"""

import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev.gen_cartes_pays import cartes_a_creer  # noqa: E402
from dev.gen_france_espagne_italie import ANCRE_ITALIE  # noqa: E402
from dev.gen_plaine_europeenne import (  # noqa: E402
	cases_autour, cases_frontiere, case_proche, connexion, fermer, libelle_sortie, libelles_de,
	liens_nommes, sans_rev, zone_de)
from dev.gen_villes_images import poser_grille  # noqa: E402

IMAGE_PANNONIE = "pannonie.jpg"
PANNONIE = "lieu:pannonie"
ITALIE = "lieu:italie"
ROUMANIE = "lieu:roumanie"
BUCAREST = "lieu:bucarest"

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

# Italie ↔ Pannonie : (nom, case visée sur l'Italie, case visée sur la Pannonie).
# ⚠️ Ordre = suffixe d'`_id` : un passage s'ajoute en FIN (Resia, à l'ouest du Tyrol, est venu
# après coup desserrer les quatre premiers, groupés vers Trieste).
PASSAGES_ITALIE = (
	("Col du Brenner", (44, 3), (6, 20)),
	("Col de Tarvisio", (51, 5), (12, 20)),
	("Gué de l'Isonzo", (52, 8), (14, 23)),
	("Route de Trieste", (52, 11), (14, 26)),
	("Col de Resia", (34, 3), (2, 19)),
)

# Pannonie ↔ Roumanie : (nom, case visée sur la Pannonie, case visée sur la Roumanie).
PASSAGES_ROUMANIE = (
	("Route d'Oradea", (63, 12), (19, 9)),
	("Vallée du Mureș", (63, 19), (14, 19)),
	("Route de Timișoara", (63, 25), (11, 26)),
	("Portes de Fer", (63, 31), (12, 34)),
)

# Bucarest sur `roumanie.png` : la cité dessinée en Valachie, entre la Moldavian et le Danube.
POSITION_BUCAREST = (51, 36)
# Sorties de Bucarest : nom → (point visé, ancre de l'extérieur visé). Les ancres sont les
# nœuds carte des portes de rempart (`link:bucarest_porte_sud_*_carte_exterieur`).
SORTIES_BUCAREST = {
	"ouest": ((4, 37), (21, 34)),
	"nord_est": ((78, 6), (68, 34)),
	"est": ((85, 28), (68, 34)),
	"sud": ((64, 44), (68, 34)),
}


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


def connexions_bucarest(zone_roumanie, bucarest, bucarest_label="Bucarest"):
	"""(docs, refus) des liens Roumanie ↔ Bucarest, chaque sortie dans son extérieur."""
	if POSITION_BUCAREST not in zone_roumanie:
		return [], [f"{ROUMANIE} : la case {list(POSITION_BUCAREST)} n'est pas dans sa zone de terre"]
	cases = cases_autour(zone_roumanie, POSITION_BUCAREST, len(SORTIES_BUCAREST))
	if not cases:
		return [], [f"{ROUMANIE} : pas {len(SORTIES_BUCAREST)} cases libres autour de "
			f"{list(POSITION_BUCAREST)}"]
	docs, refus = [], []
	for (nom, (cible, ancre)), pos_rou in zip(SORTIES_BUCAREST.items(), cases):
		pos = case_proche(zone_de(bucarest["cells"], bucarest.get("nav") or {}, ancre), cible)
		if pos is None:
			refus.append(f"{BUCAREST} : aucune case de l'extérieur {list(ancre)} pour la sortie {nom}")
			continue
		doc = connexion(f"link:roumanie_to_bucarest_{nom}", ROUMANIE, pos_rou, BUCAREST, pos)
		doc["nodes"][1]["label"] = libelle_sortie(bucarest_label, nom)
		docs.append(doc)
	return docs, refus


def bucarest_rattachee(bucarest_doc):
	"""Le doc de Bucarest relu, `_rev` retiré, avec `lieu_parent: lieu:roumanie`."""
	doc = sans_rev(copy.deepcopy(bucarest_doc))
	doc["lieu_parent"] = ROUMANIE
	return doc


def construire(docs, taille_fn, proposer_fn, eau_fn, italie):
	"""(lieux, liens, refus, propositions). `italie` : le doc de l'Italie TEL QU'IL SERA ÉCRIT
	(frontières posées par `gen_france_espagne_italie`) — lu ici, jamais modifié."""
	par_id = {d.get("_id"): d for d in docs}
	manquants = [i for i in (ROUMANIE, BUCAREST) if not (par_id.get(i) or {}).get("cells")]
	if manquants:
		return [], [], [f"absent(s) du dump ou sans grille : {', '.join(manquants)}"], {}
	pannonie, prop, refus = preparer_pannonie(docs, taille_fn, proposer_fn, eau_fn)
	if refus:
		return [], [], refus, {}
	roumanie = preparer_roumanie(par_id[ROUMANIE])
	zone_pan = zone_de(pannonie["cells"], pannonie.get("nav") or {}, ANCRE_PANNONIE)
	zone_rou = zone_de(roumanie["cells"], roumanie.get("nav") or {}, ANCRE_ROUMANIE)
	zone_ita = zone_de(italie["cells"], italie.get("nav") or {}, ANCRE_ITALIE)
	bucarest = bucarest_rattachee(par_id[BUCAREST])
	libelles = libelles_de(docs, [pannonie, italie])
	liens, refus = liens_nommes("link:italie_to_pannonie", ITALIE, zone_ita, PANNONIE, zone_pan,
		PASSAGES_ITALIE, libelles)
	for d, r in (liens_nommes("link:pannonie_to_roumanie", PANNONIE, zone_pan, ROUMANIE, zone_rou,
			PASSAGES_ROUMANIE, libelles),
			connexions_bucarest(zone_rou, bucarest, libelles[BUCAREST])):
		liens += d
		refus += r
	return [pannonie, roumanie, bucarest], liens, refus, ({PANNONIE: prop} if prop else {})
