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
  · France ↔ Italie : colonne est accessible de la France ↔ case la plus à l'ouest de la
    terre italienne (`case_au_bord`).
  · Italie ↔ Rome : la cité dessinée sur l'Italie et ses voisines ↔ une sortie par route ;
    `lieu:rome` reçoit `lieu_parent: "lieu:italie"`.
"""

import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev.gen_plaine_europeenne import (  # noqa: E402
	ANCRE_FRANCE, FRANCE, cases_autour, cases_frontiere, case_proche, connexion, fermer,
	lien_vise, sans_rev, zone_de)

ESPAGNE = "lieu:espagne"
ITALIE = "lieu:italie"
ROME = "lieu:rome"

ANCRE_ESPAGNE = (40, 24)   # Tolède

# Colonne est accessible de la France (murs nav peints : est fermé).
FRANCE_X_EST = 86

# L'ESPAGNE sur la carte de France, mise à 0 : (x_min, x_max, y) ⇒ cases y ≥ `y`.
# À l'ouest de la Bidassoa (x ≤ 25), toute la terre sous la côte cantabrique ; puis la crête
# des Pyrénées jusqu'à la Méditerranée (x 48).
FRONTIERE_FRANCE = ((0, 25, 38), (26, 29, 41), (30, 48, 42))

# La FRANCE sur la carte d'Espagne, mise à 0 : (x_min, x_max, y) ⇒ cases y ≤ `y`.
# Béarn et Roussillon au nord de la crête enneigée (golfe de Gascogne en x 52 → cap Creus en
# x 73), puis le Languedoc et la Provence au-dessus du golfe du Lion.
FRONTIERE_ESPAGNE = ((52, 53, 6), (54, 60, 7), (61, 73, 8), (74, 87, 6))

# Les NEIGES des Pyrénées, claires et froides, sont lues comme de l'eau par `masque_eau` et
# murées comme une côte : une seconde frontière, parasite, juste sous la crête. Leurs murs
# sont retirés (x_min, x_max, y_min, y_max) — entre la côte de Biscaye (x ≤ 53) et celle
# du cap Creus (x ≥ 72), qui restent murées.
NEIGES_PYRENEES = (54, 71, 8, 13)

# France ↔ Espagne : (case visée sur la France, case visée sur l'Espagne), d'ouest en est —
# Bidassoa, Roncevaux, Somport, Le Perthus. Chacune ramenée à la case accessible la plus
# proche de sa carte : juste au nord de la bande à 0 sur la France, juste au sud sur l'Espagne.
PASSAGES_ESPAGNE = (((27, 40), (53, 7)), ((32, 41), (57, 8)), ((39, 41), (63, 9)),
	((46, 41), (71, 9)))

# France ↔ Italie : (y sur la France, y sur l'Italie), du nord au sud — Valais, Savoie,
# Dauphiné, comté de Nice. Le cadre de `italie.png` est déjà à 0.
PASSAGES_ITALIE = ((22, 5), (27, 9), (31, 13), (35, 17))

# Rome sur `italie.png` : la cité dessinée sur la rive du Tibre, au-dessus de la côte tyrrhénienne.
POSITION_ROME = (47, 25)
# Sorties de Rome : nom → point visé (une route qui quitte la carte, hors du cadre).
SORTIES_ROME = {"ouest": (3, 27), "nord": (32, 6), "est": (84, 30), "sud": (40, 44)}


def case_au_bord(principale, *, colonne=None, rangee=None, vers):
	"""Case de `principale` la plus loin dans la direction `vers` ('nord', 'sud', 'est',
	'ouest') sur la colonne (nord/sud) ou la rangée (est/ouest) donnée, ou None."""
	if vers in ("nord", "sud"):
		valeurs = [y for x, y in principale if x == colonne]
	else:
		valeurs = [x for x, y in principale if y == rangee]
	if not valeurs:
		return None
	v = min(valeurs) if vers in ("nord", "ouest") else max(valeurs)
	return (colonne, v) if vers in ("nord", "sud") else (v, rangee)


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
	"""Le doc de la France (copie, `_rev` retiré), l'Espagne qu'elle montre mise à 0."""
	doc = sans_rev(copy.deepcopy(france))
	dims = doc["dimensions"]
	fermer(doc["cells"], cases_frontiere(FRONTIERE_FRANCE, "sud", dims["x"], dims["y"]))
	return doc


def connexions_espagne(zone_france, zone_espagne):
	docs, refus = [], []
	for i, (cible_fr, cible_es) in enumerate(PASSAGES_ESPAGNE, start=1):
		doc, r = lien_vise(f"link:france_to_espagne_{i:02d}",
			FRANCE, zone_france, cible_fr, ESPAGNE, zone_espagne, cible_es)
		if r:
			refus.append(r)
		else:
			docs.append(doc)
	return docs, refus


def connexions_italie(zone_france, zone_italie):
	docs, refus = [], []
	for i, (y_fr, y_it) in enumerate(PASSAGES_ITALIE, start=1):
		pos_fr = (FRANCE_X_EST, y_fr)
		if pos_fr not in zone_france:
			refus.append(f"{FRANCE} : la case {list(pos_fr)} n'est pas dans sa zone de terre")
			continue
		pos_it = case_au_bord(zone_italie, rangee=y_it, vers="ouest")
		if pos_it is None:
			refus.append(f"{ITALIE} : aucune case de terre en rangée {y_it}")
			continue
		docs.append(connexion(f"link:france_to_italie_{i:02d}", FRANCE, pos_fr, ITALIE, pos_it))
	return docs, refus


def connexions_rome(zone_italie, zone_rome):
	"""(docs, refus) des liens Italie ↔ Rome."""
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
		docs.append(connexion(f"link:italie_to_rome_{nom}", ITALIE, pos_italie, ROME, pos_rome))
	return docs, refus


def rome_rattachee(rome_doc):
	"""Le doc de Rome relu, `_rev` retiré, avec `lieu_parent: lieu:italie`."""
	doc = sans_rev(copy.deepcopy(rome_doc))
	doc["lieu_parent"] = ITALIE
	return doc


def construire(docs, proposer_espagne_fn):
	"""(lieux, liens, refus) : France et Espagne frontière posée, Rome rattachée, et les liens.
	`lieux` = docs complets, émis par l'appelant s'ils diffèrent du dump."""
	par_id = {d.get("_id"): d for d in docs}
	manquants = [i for i in (FRANCE, ESPAGNE, ITALIE, ROME) if not (par_id.get(i) or {}).get("cells")]
	if manquants:
		return [], [], [f"absent(s) du dump ou sans grille : {', '.join(manquants)}"]
	france = preparer_france(par_id[FRANCE])
	espagne = preparer_espagne(par_id[ESPAGNE], proposer_espagne_fn)
	italie, rome = par_id[ITALIE], par_id[ROME]
	zone_france = zone_de(france["cells"], france.get("nav") or {}, ANCRE_FRANCE)
	zone_espagne = zone_de(espagne["cells"], espagne.get("nav") or {}, ANCRE_ESPAGNE)
	zone_italie = zone_de(italie["cells"], italie.get("nav") or {})
	zone_rome = zone_de(rome["cells"], rome.get("nav") or {})

	liens, refus = connexions_espagne(zone_france, zone_espagne)
	for d, r in (connexions_italie(zone_france, zone_italie), connexions_rome(zone_italie, zone_rome)):
		liens += d
		refus += r
	return [france, espagne, rome_rattachee(rome)], liens, refus
