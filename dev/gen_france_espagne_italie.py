"""France ↔ Espagne et Italie, Rome posée sur l'Italie — et la frontière des Pyrénées.

Bibliothèque de `dev/gen_voisins_france.py` (qui écrit le fichier à importer unique) ; pas de
point d'entrée propre. Même règle que `gen_plaine_europeenne` : le territoire du voisin que
montre une carte est mis à 0, la connexion se pose SUR la frontière, du côté accessible.

  · ESPAGNE — nav repris pour n'en faire que le TOUR : grille du profil `pays` repartie d'un
    nav VIDE (côte seule ; l'ancien nav murait aussi les fleuves). Puis la France qu'elle
    montre au nord des Pyrénées (`FRONTIERE_ESPAGNE`) est mise à 0, et les murs posés sur ces
    cases retirés, ainsi que ceux des neiges de la crête (`NEIGES_PYRENEES`).
    ⚠️ Repris UNE fois : si la frontière est déjà posée en base, le doc relu est gardé tel
    quel (une retouche de ses murs survit au rejeu).
  · FRANCE — l'Espagne qu'elle montre au sud des Pyrénées (`FRONTIERE_FRANCE`) mise à 0 ;
    les murs peints ne perdent aucun bit (inertes sur une case à 0).
  · France ↔ Espagne : les cols des Pyrénées (`PASSAGES_ESPAGNE`), de part et d'autre de la
    crête — AVANT la limite des murs nav de la France (rangée 47).
  · ITALIE — la France qu'elle montre à l'ouest des Alpes (`FRONTIERE_ITALIE_FRANCE`), les
    Balkans à l'est de l'Adriatique et le Tyrol au-dessus de la crête
    (`FRONTIERE_ITALIE_PANNONIE`, `FRONTIERE_ITALIE_TYROL` : le territoire de
    `lieu:pannonie`) mis à 0. Côté France, l'Italie au sud-est des Alpes
    (`FRONTIERE_FRANCE_ITALIE`).
  · France ↔ Italie : les cols des Alpes et la corniche (`PASSAGES_ITALIE`), de part et
    d'autre de la crête.
  · Italie ↔ Rome : la cité dessinée sur l'Italie et ses voisines ↔ une sortie par route ;
    `lieu:rome` reçoit `lieu_parent: "lieu:italie"`.
"""

import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev.gen_plaine_europeenne import (  # noqa: E402
	ANCRE_FRANCE, FRANCE, cases_autour, cases_frontiere, case_proche, connexion, fermer,
	libelle_sortie, libelles_de, liens_nommes, sans_rev, zone_de)

ESPAGNE = "lieu:espagne"
ITALIE = "lieu:italie"
ROME = "lieu:rome"

ANCRE_ESPAGNE = (40, 24)   # Tolède

ANCRE_ITALIE = (47, 25)    # Rome

# L'ESPAGNE sur la carte de France, mise à 0 : (x_min, x_max, y) ⇒ cases y ≥ `y`.
# À l'ouest de la Bidassoa (x ≤ 25), toute la terre sous la côte cantabrique ; puis la crête
# des Pyrénées jusqu'à la Méditerranée (x 48).
FRONTIERE_FRANCE = ((0, 25, 38), (26, 29, 41), (30, 48, 42))

# L'ITALIE sur la carte de France, mise à 0 : (y_min, y_max, x) ⇒ cases x ≥ `x`.
# Au sud-est de la crête des Alpes : Val d'Aoste et lacs (Majeur, Côme), Piémont, Ligurie,
# jusqu'à la côte (y 36). La Suisse, au nord de la crête, et la Corse, au large, restent.
FRONTIERE_FRANCE_ITALIE = ((25, 26, 77), (27, 36, 73))

# La FRANCE sur la carte d'Italie, mise à 0 : (y_min, y_max, x) ⇒ cases x ≤ `x`.
# Savoie, Dauphiné et Provence, à l'ouest de l'arc enneigé des Alpes, jusqu'à Menton.
FRONTIERE_ITALIE_FRANCE = ((0, 21, 17),)

# Les BALKANS sur la carte d'Italie (le territoire de `lieu:pannonie`), mis à 0 :
# (y_min, y_max, x) ⇒ cases x ≥ `x`. Slovénie et Istrie à l'est de l'Isonzo, puis la côte
# dalmate qui descend en diagonale, l'Albanie et la Grèce au-delà du canal d'Otrante.
FRONTIERE_ITALIE_PANNONIE = ((0, 14, 53), (15, 16, 56), (17, 18, 59), (19, 20, 63),
	(21, 22, 67), (23, 24, 71), (25, 29, 76), (30, 47, 81))
# Le TYROL au-dessus de la crête des Alpes : (x_min, x_max, y) ⇒ cases y ≤ `y`.
FRONTIERE_ITALIE_TYROL = ((26, 52, 2),)

# La FRANCE sur la carte d'Espagne, mise à 0 : (x_min, x_max, y) ⇒ cases y ≤ `y`.
# Béarn et Roussillon au nord de la crête enneigée (golfe de Gascogne en x 52 → cap Creus en
# x 73), puis le Languedoc et la Provence au-dessus du golfe du Lion.
FRONTIERE_ESPAGNE = ((52, 53, 6), (54, 60, 7), (61, 73, 8), (74, 87, 6))

# Les NEIGES des Pyrénées, claires et froides, sont lues comme de l'eau par `masque_eau` et
# murées comme une côte : une seconde frontière, parasite, juste sous la crête. Leurs murs
# sont retirés (x_min, x_max, y_min, y_max) — entre la côte de Biscaye (x ≤ 53) et celle
# du cap Creus (x ≥ 72), qui restent murées.
NEIGES_PYRENEES = (54, 71, 8, 13)

# France ↔ Espagne : (nom, case visée sur la France, case visée sur l'Espagne), d'ouest en
# est. Chacune ramenée à la case accessible la plus proche de sa carte : juste au nord de la
# bande à 0 sur la France, juste au sud sur l'Espagne.
# ⚠️ Ordre = suffixe d'`_id` : un passage s'ajoute en FIN (cf. gen_plaine_europeenne).
PASSAGES_ESPAGNE = (
	("Gué de la Bidassoa", (27, 40), (53, 7)),
	("Col de Roncevaux", (32, 41), (57, 8)),
	("Col du Somport", (39, 41), (63, 9)),
	("Col du Perthus", (46, 41), (71, 9)),
)

# France ↔ Italie : (nom, case visée sur la France, case visée sur l'Italie), du nord au sud.
PASSAGES_ITALIE = (
	("Col du Petit-Saint-Bernard", (72, 26), (18, 6)),
	("Col du Mont-Cenis", (72, 29), (18, 10)),
	("Col de Montgenèvre", (72, 32), (18, 14)),
	("Corniche de Menton", (72, 34), (18, 19)),
)

# Rome sur `italie.png` : la cité dessinée sur la rive du Tibre, au-dessus de la côte tyrrhénienne.
POSITION_ROME = (47, 25)
# Sorties de Rome : nom → point visé (une route qui quitte la carte, hors du cadre).
SORTIES_ROME = {"ouest": (3, 27), "nord": (32, 6), "est": (84, 30), "sud": (40, 44)}


def frontiere_posee(cells, cases) -> bool:
	return all(cells[y][x] == 0 for x, y in cases if 0 <= y < len(cells) and 0 <= x < len(cells[y]))


def preparer_espagne(espagne, proposer_fn):
	"""Le doc de l'Espagne (copie, `_rev` retiré) : tour repris et France mise à 0, sauf si la
	frontière est déjà posée. `proposer_fn(doc) -> {cells, nav}` : profil pays, nav VIDE."""
	doc = sans_rev(copy.deepcopy(espagne))
	dims = doc["dimensions"]
	cases = cases_frontiere(FRONTIERE_ESPAGNE, "nord", dims["x"], dims["y"])
	if frontiere_posee(doc.get("cells") or [], cases):
		return doc
	prop = proposer_fn(doc)
	doc["cells"], doc["nav"] = prop["cells"], dict(prop["nav"])
	fermer(doc["cells"], cases)
	x_min, x_max, y_min, y_max = NEIGES_PYRENEES
	neiges = {(x, y) for x in range(x_min, x_max + 1) for y in range(y_min, y_max + 1)}
	for x, y in cases | neiges:
		doc["nav"].pop(f"{x},{y}", None)
	return doc


def preparer_france(france):
	"""Le doc de la France (copie, `_rev` retiré), l'Espagne et l'Italie qu'elle montre à 0."""
	doc = sans_rev(copy.deepcopy(france))
	dims = doc["dimensions"]
	fermer(doc["cells"], cases_frontiere(FRONTIERE_FRANCE, "sud", dims["x"], dims["y"]))
	fermer(doc["cells"], cases_frontiere(FRONTIERE_FRANCE_ITALIE, "est", dims["x"], dims["y"]))
	return doc


def preparer_italie(italie):
	"""Le doc de l'Italie (copie, `_rev` retiré), la France, les Balkans et le Tyrol qu'elle
	montre à 0 ; ses murs peints ne perdent aucun bit."""
	doc = sans_rev(copy.deepcopy(italie))
	dims = doc["dimensions"]
	for bandes, sens in ((FRONTIERE_ITALIE_FRANCE, "ouest"), (FRONTIERE_ITALIE_PANNONIE, "est"),
			(FRONTIERE_ITALIE_TYROL, "nord")):
		fermer(doc["cells"], cases_frontiere(bandes, sens, dims["x"], dims["y"]))
	return doc


def connexions_espagne(zone_france, zone_espagne, libelles):
	return liens_nommes("link:france_to_espagne", FRANCE, zone_france, ESPAGNE, zone_espagne,
		PASSAGES_ESPAGNE, libelles)


def connexions_italie(zone_france, zone_italie, libelles):
	return liens_nommes("link:france_to_italie", FRANCE, zone_france, ITALIE, zone_italie,
		PASSAGES_ITALIE, libelles)


def connexions_rome(zone_italie, zone_rome, rome_label="Rome"):
	"""(docs, refus) des liens Italie ↔ Rome ; le nœud de Rome libellé par sa sortie."""
	if POSITION_ROME not in zone_italie:
		return [], [f"{ITALIE} : la case {list(POSITION_ROME)} n'est pas dans sa zone de terre"]
	cases = cases_autour(zone_italie, POSITION_ROME, len(SORTIES_ROME))
	if not cases:
		return [], [f"{ITALIE} : pas {len(SORTIES_ROME)} cases libres autour de {list(POSITION_ROME)}"]
	docs, refus = [], []
	for (nom, cible), pos_italie in zip(SORTIES_ROME.items(), cases):
		pos_rome = case_proche(zone_rome, cible)
		if pos_rome is None:
			refus.append(f"{ROME} : aucune case de sa zone principale pour la sortie {nom}")
			continue
		doc = connexion(f"link:italie_to_rome_{nom}", ITALIE, pos_italie, ROME, pos_rome)
		doc["nodes"][1]["label"] = libelle_sortie(rome_label, nom)
		docs.append(doc)
	return docs, refus


def rome_rattachee(rome_doc):
	"""Le doc de Rome relu, `_rev` retiré, avec `lieu_parent: lieu:italie`."""
	doc = sans_rev(copy.deepcopy(rome_doc))
	doc["lieu_parent"] = ITALIE
	return doc


def construire(docs, proposer_espagne_fn):
	"""(lieux, liens, refus) : France, Espagne et Italie frontières posées, Rome rattachée, et
	les liens. `lieux` = docs complets, émis par l'appelant s'ils diffèrent du dump ; l'Italie
	en sort telle qu'elle sera écrite (lue ensuite par `gen_pannonie`)."""
	par_id = {d.get("_id"): d for d in docs}
	manquants = [i for i in (FRANCE, ESPAGNE, ITALIE, ROME) if not (par_id.get(i) or {}).get("cells")]
	if manquants:
		return [], [], [f"absent(s) du dump ou sans grille : {', '.join(manquants)}"]
	france = preparer_france(par_id[FRANCE])
	espagne = preparer_espagne(par_id[ESPAGNE], proposer_espagne_fn)
	italie, rome = preparer_italie(par_id[ITALIE]), par_id[ROME]
	zone_france = zone_de(france["cells"], france.get("nav") or {}, ANCRE_FRANCE)
	zone_espagne = zone_de(espagne["cells"], espagne.get("nav") or {}, ANCRE_ESPAGNE)
	zone_italie = zone_de(italie["cells"], italie.get("nav") or {}, ANCRE_ITALIE)
	zone_rome = zone_de(rome["cells"], rome.get("nav") or {})

	libelles = libelles_de(docs)
	liens, refus = connexions_espagne(zone_france, zone_espagne, libelles)
	for d, r in (connexions_italie(zone_france, zone_italie, libelles),
			connexions_rome(zone_italie, zone_rome, libelles[ROME])):
		liens += d
		refus += r
	return [france, espagne, italie, rome_rattachee(rome)], liens, refus
