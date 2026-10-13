"""Frontières CALÉES entre deux cartes de pays (pur) : la plus détaillée fait foi.

La carte qui FAIT FOI (la carte posée de sa paire, `dev/calage_cartes.py`) garde sa grille ;
sur sa VOISINE, chaque case dont le centre, projeté, tombe dans la zone de terre de la carte
qui fait foi est mise à 0 (`recaler`). Les deux lignes de passages se lisent ensuite l'une
par l'autre (`ligne_projetee`) : sur chaque carte, les cases de sa zone qui touchent une case
dont la projection tombe dans la zone de l'AUTRE carte — elles se font face par construction,
bord de carte compris (une carte coupée par son cadre a pour frontière ce cadre).

Passages (`liens_projetes`) : postes une case sur deux sur la ligne qui COMPTE, et pour chacun
la case de l'autre ligne la plus proche de sa projection — les deux bouts se font face.

Mêmes conventions que `gen_plaine_europeenne` : on mute, on ne sauve pas ; cases (x, y).
"""

import math

from dev.calage_cartes import projection
from dev.gen_plaine_europeenne import (  # noqa: F401 (liens_perimes réexporté)
	case_proche, connexion, liens_perimes, ligne_frontiere, postes)

ORTHO = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _dans(cells, x, y):
	return 0 <= y < len(cells) and 0 <= x < len(cells[y])


def recaler(voisine, foi, zone_foi, ancienne=frozenset(), bande_foi=frozenset(), en_plus=frozenset()):
	"""Met à 0 sur `voisine` (doc, muté) les cases dont le centre projeté tombe dans `zone_foi`,
	plus `en_plus` ; ROUVRE (1) les cases de son `ancienne` bande projetées dans `bande_foi` :
	le territoire de la voisine selon la carte qui fait foi, que les deux cartes fermaient.
	Rend (fermées, rouvertes) : les cases effectivement changées."""
	vers = projection(voisine["_id"], foi["_id"])
	cells = voisine["cells"]
	fermees, rouvertes = set(), set()
	for y, rang in enumerate(cells):
		for x, v in enumerate(rang):
			c = vers((x, y))
			if c in zone_foi or (x, y) in en_plus:
				if v != 0:
					rang[x] = 0
					fermees.add((x, y))
			elif v == 0 and (x, y) in ancienne and c in bande_foi:
				rang[x] = 1
				rouvertes.add((x, y))
	return fermees, rouvertes


def au_dela(doc, zone, autre_id, cible, cible_bord=None):
	"""Cases voisines de `zone`, hors d'elle, dont la projection sur l'autre carte vérifie
	`cible(case)` : ce que la frontière sépare. Une frontière passe contre une case FERMÉE (0),
	contre le POURTOUR de la grille (cadre muré par `nav`) ou au-delà du bord de la carte —
	ces deux-là jugés par `cible_bord` (défaut : `cible`) ; jamais contre une case intérieure
	à 1 hors de la zone (fleuve ou mer murés : le Danube)."""
	cible_bord = cible_bord or cible
	vers = projection(doc["_id"], autre_id)
	cells = doc["cells"]
	h, w = len(cells), len(cells[0])
	cases = set()
	for x, y in zone:
		for dx, dy in ORTHO:
			n = (x + dx, y + dy)
			if n in zone:
				continue
			ferme = _dans(cells, *n) and cells[n[1]][n[0]] == 0
			bord = not _dans(cells, *n) or n[0] in (0, w - 1) or n[1] in (0, h - 1)
			if (ferme and cible(vers(n))) or (not ferme and bord and cible_bord(vers(n))):
				cases.add(n)
	return cases


def lignes(voisine, zone_v, foi, zone_f, depart_v, depart_f, cadre_v=None, cadre_f=None):
	"""(ligne de la voisine, ligne de la carte qui fait foi), chacune en chaîne depuis son
	départ (`gen_plaine_europeenne.ligne_frontiere`).

	Voisine (recalée) : ses cases fermées projetées DANS la zone de la carte qui fait foi —
	exact, c'est ainsi qu'elles ont été fermées. Carte qui fait foi, plus fine (2 à 3 de ses
	cases par case de la voisine) : la projection de sa case fermée tombe souvent sur la case
	frontière de la voisine elle-même, fermée ou non selon l'arrondi — on retient celles qui
	tombent à UNE case au plus (Tchebychev) de la ligne de la voisine. Le cadre et l'au-delà du
	bord de la carte qui fait foi (la France n'a pas de bande contre la plaine : sa frontière
	est son bord) comptent quand leur projection tombe DANS la terre de la voisine, à une case
	de sa ligne — pas seulement près d'elle, sinon les coins débordent sur le cadre voisin."""
	ligne_v = ligne_frontiere(zone_v, au_dela(voisine, zone_v, foi["_id"], zone_f.__contains__),
		depart_v, cadre_v)
	proches = {(x + dx, y + dy) for x, y in ligne_v for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
	ligne_f = ligne_frontiere(zone_f, au_dela(foi, zone_f, voisine["_id"], proches.__contains__,
		lambda c: c in proches and c in zone_v), depart_f, cadre_f)
	return ligne_v, ligne_f


def liens_projetes(prefixe, lieu_compte, ligne_compte, lieu_autre, ligne_autre, noms, libelles,
		rang0=0, ordre=None):
	"""(docs, refus, avertissements) : un lien `<prefixe>_NN` par nom, posté une case sur deux
	sur `ligne_compte` (`postes`), l'autre bout sur la case de `ligne_autre` la plus proche de
	sa projection. Nœuds libellés « <nom> — <libellé du lieu> » ; `ordre` = (lieu du premier
	nœud, lieu du second) — par défaut (compte, autre). Compte qui ne tombe pas juste ⇒
	avertissement (la liste de noms est à revoir)."""
	if not ligne_compte or not ligne_autre:
		manque = lieu_compte if not ligne_compte else lieu_autre
		return [], [f"{prefixe} : aucune case de frontière sur {manque}"], []
	attendu = math.ceil(len(ligne_compte) / 2)
	avert = [] if len(noms) == attendu else [f"{prefixe} : {len(noms)} nom(s) pour {attendu} "
		f"poste(s) — frontière de {len(ligne_compte)} case(s) sur {lieu_compte}, "
		f"{len(ligne_autre)} sur {lieu_autre}"]
	vers = projection(lieu_compte, lieu_autre)
	autre = set(ligne_autre)
	premier, second = ordre or (lieu_compte, lieu_autre)
	docs = []
	for i, (nom, pos) in enumerate(zip(noms, postes(ligne_compte, len(noms))), start=rang0 + 1):
		pos_autre = case_proche(autre, vers(pos))
		bouts = {lieu_compte: pos, lieu_autre: pos_autre}
		doc = connexion(f"{prefixe}_{i:02d}", premier, bouts[premier], second, bouts[second])
		for noeud in doc["nodes"]:
			noeud["label"] = f"{nom} — {libelles.get(noeud['lieu'], noeud['lieu'])}"
		docs.append(doc)
	return docs, [], avert
