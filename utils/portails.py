# utils/portails.py
# Portail de Notre-Dame : le TABLEAU DES SEUILS (pur, DB injectée, ne sauve jamais).
#
# Notre-Dame n'a AUCUN lien vers ses destinations. Les portails du monde sont des
# `connection` ordinaires (`metadata.type == "portail"`) qui relient un endroit X à un
# endroit Y ; l'ancrage de Notre-Dame COURT-CIRCUITE l'un d'eux et prend son POINT
# D'ARRIVÉE (le `pos` d'un de ses nœuds) le temps d'un passage — au prix d'un cristal de
# mana jaune (décision de l'Auteur, 25/10). D'où :
#   - les destinations sont DÉRIVÉES de tous les liens portail : un portail créé demain
#     entre au tableau sans une ligne de contenu ni de code ;
#   - on n'arrive presque jamais À Notre-Dame : un nœud posé sur l'ancrage n'est jamais
#     une destination (seul Mu y mène, par son propre lien).
#
# On ne propose que quelques seuils à la fois, ceux « qui vont être empruntés dans les
# prochains moments ». ⚠️ Aucune horloge ni tick (CLAUDE.md §5) : l'epoch réel est coupé
# en TRANCHES de `PORTAIL_FENETRE_MINUTES`, et les seuils TOURNENT par un hasard
# DÉTERMINISTE (cercle battu par période, cf. `_tirage`) — même tableau pour tous les joueurs,
# ressortir/rentrer ne re-tire rien, et la tranche suivante ne redit jamais la courante.

import hashlib
import math
import random

from models import character_stats

TYPE_PORTAIL = "portail"


def fenetre_secondes() -> int:
	return max(60, int(character_stats.PORTAIL_FENETRE_MINUTES) * 60)


def tranche_de(now: int) -> int:
	return int(now) // fenetre_secondes()


def ferme_dans_s(now: int) -> int:
	"""Secondes avant que la tranche courante ne tourne."""
	return (tranche_de(now) + 1) * fenetre_secondes() - int(now)


def arrivees_candidates(connexions: list, ancrage: str) -> list:
	"""Chaque nœud de chaque lien portail OUVERT est un point d'arrivée possible :
	`[{cle, lien, lieu, pos}]`, trié par `cle` (le tirage en dépend : un ordre stable est
	ce qui rend la graine reproductible). Les nœuds posés sur l'ancrage sont écartés."""
	vues = {}
	for conn in connexions or []:
		meta = conn.get("metadata") or {}
		if meta.get("type") != TYPE_PORTAIL or meta.get("status", "ouvert") != "ouvert":
			continue
		for node in conn.get("nodes") or []:
			lieu = node.get("lieu")
			if not lieu or lieu == ancrage:
				continue
			pos = node.get("pos") or [0, 0]
			cle = f"{conn.get('_id')}|{lieu}"
			vues.setdefault(cle, {"cle": cle, "lien": conn.get("_id"), "lieu": lieu,
								  "pos": [int(pos[0]), int(pos[1])]})
	return [vues[c] for c in sorted(vues)]


def arrivees_fixes(connexions: list, ancrage: str) -> list:
	"""Tableau FIXE (`services.portail.fixe`, Chapelle Palatine d'Aix) : les portes de
	l'ancrage LUI-MÊME — l'autre bout de chaque lien portail OUVERT dont un nœud est posé sur
	l'ancrage. Aucune tranche, aucune expiration : toutes sont ouvertes, toujours. Même forme
	que `arrivees_candidates`, triée par `cle`."""
	vues = {}
	for conn in connexions or []:
		meta = conn.get("metadata") or {}
		if meta.get("type") != TYPE_PORTAIL or meta.get("status", "ouvert") != "ouvert":
			continue
		nodes = conn.get("nodes") or []
		if not any(n.get("lieu") == ancrage for n in nodes):
			continue
		for node in nodes:
			lieu = node.get("lieu")
			if not lieu or lieu == ancrage:
				continue
			pos = node.get("pos") or [0, 0]
			cle = f"{conn.get('_id')}|{lieu}"
			vues.setdefault(cle, {"cle": cle, "lien": conn.get("_id"), "lieu": lieu,
								  "pos": [int(pos[0]), int(pos[1])]})
	return [vues[c] for c in sorted(vues)]


def _arc(arrivees: list, ancrage: str, periode: int, debut: int, nb: int) -> list:
	"""Les `nb` arrivées à partir du rang `debut` du cercle battu de la période."""
	graine = int(hashlib.sha256(f"{ancrage}:{periode}".encode("utf-8")).hexdigest()[:16], 16)
	cercle = random.Random(graine).sample(arrivees, len(arrivees))
	return [cercle[(debut + i) % len(cercle)] for i in range(nb)]


def _debuts(n: int, nb: int) -> list:
	"""Rang de départ de chaque arc d'une période, un par tranche : arcs bout à bout jusqu'à
	retomber sur le premier. Avec exactement 2 × `nb` arrivées il n'y en aurait que deux, et
	l'échange de jonction toucherait le dernier : on refait le tour décalé d'un cran."""
	debuts = [j * nb % n for j in range(n // math.gcd(n, nb))]
	return [0, nb, 1, nb + 1] if len(debuts) == 2 and nb > 1 else debuts


def _tirage(arrivees: list, ancrage: str, tranche: int) -> list:
	"""ROTATION, pas tirage indépendant : deux tranches qui se suivent ne ressortent jamais
	les mêmes seuils (un tirage indépendant le faisait une fois sur quatre avec 4 arrivées
	pour 3 seuils : le tableau d'Aénor paraissait figé). Les arrivées sont battues en cercle
	une fois par PÉRIODE (graine = ancrage + période) ; chaque tranche prend l'arc suivant de
	`nb` arrivées (`_debuts`) — chacune passe donc par période. À la jonction, si le premier
	arc redit le dernier de la période d'avant, les deux premiers s'échangent : le dernier ne
	bouge jamais, aucune dépendance en chaîne."""
	n = len(arrivees)
	nb = min(max(1, int(character_stats.PORTAIL_SEUILS_OUVERTS)), n)
	if not nb:
		return []
	if n == 2 and nb == 1:
		return [arrivees[tranche % 2]]
	debuts = _debuts(n, nb)
	w = len(debuts)
	periode, j = divmod(tranche, w)
	if w >= 3 and j <= 1:
		cles = lambda arc: {a["cle"] for a in arc}
		if cles(_arc(arrivees, ancrage, periode, debuts[0], nb)) == cles(
				_arc(arrivees, ancrage, periode - 1, debuts[-1], nb)):
			j = 1 - j
	return _arc(arrivees, ancrage, periode, debuts[j], nb)


def seuils_ouverts(arrivees: list, ancrage: str, now: int) -> list:
	"""Les seuils de la tranche courante, chacun avec `ferme_dans_s` (secondes restantes)."""
	reste = ferme_dans_s(now)
	return [dict(a, ferme_dans_s=reste) for a in _tirage(arrivees, ancrage, tranche_de(now))]


def seuils_suivants(arrivees: list, ancrage: str, now: int) -> list:
	"""Les seuils de la tranche SUIVANTE — ceux que la commanderesse annonce."""
	return _tirage(arrivees, ancrage, tranche_de(now) + 1)


def seuil_franchissable(arrivees: list, ancrage: str, cle: str, now: int) -> dict | None:
	"""Le seuil `cle` s'il est ouvert dans la tranche courante OU LA PRÉCÉDENTE — une tranche
	de grâce couvre la lecture du tableau entre son affichage et le clic. None sinon."""
	tranche = tranche_de(now)
	for t in (tranche, tranche - 1):
		for a in _tirage(arrivees, ancrage, t):
			if a["cle"] == cle:
				return a
	return None


def texte_duree(secondes: int) -> str:
	"""« 1 min 40 », « 35 s » — la fenêtre est courte, on compte en secondes."""
	s = max(0, int(secondes))
	m, s = divmod(s, 60)
	if not m:
		return f"{s} s"
	return f"{m} min {s:02d}" if s else f"{m} min"
