# utils/pieges.py
# Pièges posés sur les cases d'une grille de COMBAT — la règle, et rien d'autre.
#
# Deux origines, une seule forme de piège :
#   • `camp: "monde"`  — tiré à l'ouverture d'un combat (et à chaque étage) depuis le tag
#     codifié `pieges_<quantite>_<danger>` du lieu `battle_map` (ex. `pieges_4_2`). Caché au
#     groupe tant qu'un porteur de « Détection des pièges » ne l'a pas repéré. Les monstres
#     ne le déclenchent jamais : c'est leur antre.
#   • `camp: "joueur"` — posé en combat par une compétence de pose (bloc `pose_piege`,
#     voleur/forestier niveaux 2 → 8), en consommant un item. Le groupe le voit et ne le
#     déclenche jamais ; un monstre peut le flairer (jet) et le contourner, sinon il marche
#     dessus.
#
#   {
#     "id": "piege_0", "camp": "monde", "x": 4, "y": 7, "cases": [[4, 7]],
#     "danger": 2, "degats": "2D6", "effets": {}, "nom": "Piège", "icon": "🪤",
#     "etat": "cache",          # cache → detecte → desamorce | declenche
#     "tentes": [],             # ids des acteurs qui ont DÉJÀ tenté de le repérer
#     "vu_par": [],             # ids des monstres qui l'ont flairé (camp joueur)
#     "poseur_id": "joueur_0",  # camp joueur seulement
#   }
#
# ⚠️ Un piège DÉTECTÉ reste ACTIF : marcher dessus le déclenche quand même. Seul le
# désamorçage le rend inerte ; un piège déclenché sert une fois puis est hors d'usage.
#
# ⚠️ La liste COMPLÈTE vit dans le doc de combat, mais le doc part tel quel au client :
# `pieges_publics` est le seul filtre qui l'empêche de lire les pièges cachés
# (cf. `combat.vue_client`).
#
# Module PUR : aucune base, aucune connaissance du moteur de combat — le hasard passe par
# un `rand_fn` injecté (CLAUDE.md §14), la grille est passée en argument.

import random
import re

# Tag codifié d'une salle : `pieges_<quantite>_<danger>`. Underscore, comme `essence_<x>`
# (utils/bois.py) : le `:` est réservé aux `_id`.
TAG_RE = re.compile(r"^pieges_(\d+)_(\d+)$")

# Plafond de pièges d'une salle : borne de sûreté contre une faute de frappe
# (`pieges_400_2`), pas un réglage de jeu.
PIEGES_MAX = 30

# Échelle de danger 1-5 : elle règle les dégâts (`degats_de`) ET la difficulté des jets.
DANGER_MIN = 1
DANGER_MAX = 5

# Distance de Chebyshev minimale entre un piège et toute case de départ (point
# d'apparition d'un donjon/étage, ou spawn de chaque membre du groupe) — demande
# explicite : le groupe ne doit ni apparaître sur un piège ni le trouver à son premier pas.
PIEGES_DISTANCE_DEPART = 4

# Portée (Chebyshev, cases) de la détection à l'approche, de la fouille et du flair des
# monstres.
PIEGE_PORTEE_DETECTION = 2

# Points de seuil retirés par point de danger (détection, désamorçage, flair).
PIEGE_DIFFICULTE_PAR_DANGER = 15

# Bonus de la fouille volontaire (1 action) au seuil de détection, en plus du bonus de
# compétence.
PIEGE_BONUS_FOUILLE = 20

# XP PERSONNELLE au détecteur / au désamorceur — valeurs demandées.
XP_DETECTION = 5
XP_DESAMORCAGE = 10

# Animations (sprite + son) jouées par le client à la révélation de la ligne de journal.
# Ids DIRECTS (premier étage de `animations.animation_pour`) et non des canaux de
# `COMBAT_ANIMATIONS_DEFAUT` : le chargement des variables de monde vide ce dict avant de
# le remplir depuis la base, un défaut de code pour un canal neuf y serait effacé en
# silence. Doc absent ou inactif ⇒ rien ne joue, rien ne casse.
ANIM_DECLENCHEMENT = "animation:piege_declenche"
ANIM_DESAMORCAGE_REUSSI = "animation:desamorcage_reussi"
ANIM_DESAMORCAGE_RATE = "animation:desamorcage_rate"

CAMP_MONDE = "monde"
CAMP_JOUEUR = "joueur"

ETAT_CACHE = "cache"
ETAT_DETECTE = "detecte"
ETAT_DESAMORCE = "desamorce"
ETAT_DECLENCHE = "declenche"
ETATS_ACTIFS = (ETAT_CACHE, ETAT_DETECTE)

# Valeur de terrain d'une falaise (même lecture que `combat.TERRAIN_FALAISE` — recopiée,
# importer le moteur ici créerait un cycle).
_TERRAIN_FALAISE = 3

# Bornes du bloc `pose_piege` d'une compétence.
POSE_ZONE_MAX = 3
POSE_PORTEE_MAX = 3


def _as_int(valeur, defaut: int = 0) -> int:
	try:
		return int(valeur)
	except (TypeError, ValueError):
		return defaut


def _borne(valeur: int, mini: int, maxi: int) -> int:
	return max(mini, min(maxi, valeur))


# ── Tag de salle ─────────────────────────────────────────────────────────────

def parametres_du_tag(tags) -> tuple | None:
	"""`(quantite, danger)` du premier tag `pieges_<q>_<d>` valide, ou None. Quantité
	bornée à [0, PIEGES_MAX], danger à [DANGER_MIN, DANGER_MAX]."""
	for tag in tags or []:
		m = TAG_RE.match(str(tag or "").strip())
		if not m:
			continue
		return (_borne(int(m.group(1)), 0, PIEGES_MAX),
				_borne(int(m.group(2)), DANGER_MIN, DANGER_MAX))
	return None


def degats_de(danger: int) -> str:
	"""Dégâts d'un piège de danger donné : `<danger>D6` (1D6 … 5D6)."""
	return f"{_borne(_as_int(danger, 1), DANGER_MIN, DANGER_MAX)}D6"


# ── Placement ────────────────────────────────────────────────────────────────

def case_au_sol(cells: list, x: int, y: int) -> bool:
	"""Case où l'on MARCHE (praticable, pas une falaise) : là seulement un piège a un sens."""
	if not cells or y < 0 or y >= len(cells):
		return False
	row = cells[y]
	if x < 0 or x >= len(row):
		return False
	return row[x] >= 1 and row[x] != _TERRAIN_FALAISE


def _cheby_cases(a: tuple, b: tuple) -> int:
	return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def nouveau_piege(pid: str, camp: str, x: int, y: int, danger: int, *, cases=None,
				  degats: str | None = None, effets: dict | None = None,
				  nom: str = "Piège", icon: str = "🪤", etat: str | None = None,
				  poseur_id: str | None = None) -> dict:
	"""Forme UNIQUE d'un piège (les deux camps)."""
	danger = _borne(_as_int(danger, 1), DANGER_MIN, DANGER_MAX)
	piege = {
		"id": pid, "camp": camp, "x": int(x), "y": int(y),
		"cases": [list(c) for c in (cases or [[x, y]])],
		"danger": danger,
		"degats": str(degats or degats_de(danger)),
		"effets": dict(effets or {}),
		"nom": nom, "icon": icon,
		"etat": etat or (ETAT_DETECTE if camp == CAMP_JOUEUR else ETAT_CACHE),
		"tentes": [], "vu_par": [],
	}
	if poseur_id:
		piege["poseur_id"] = poseur_id
	return piege


def placer_pieges(cells: list, dims: dict, departs, interdites, qte: int, danger: int,
				  rand_fn=None, prefixe: str = "piege_") -> list:
	"""Tire `qte` pièges `camp:"monde"` sur des cases au sol, hors `interdites` et à au
	moins PIEGES_DISTANCE_DEPART (Chebyshev) de chaque case de `departs`.

	Moins de cases éligibles que demandé ⇒ moins de pièges : on ne se replie JAMAIS sur une
	case proche du départ. `rand_fn` : flottant dans [0, 1) (défaut `random.random`)."""
	rand_fn = rand_fn or random.random
	departs = [(int(x), int(y)) for x, y in (departs or [])]
	interdites = {(int(x), int(y)) for x, y in (interdites or [])}
	w, h = int((dims or {}).get("x", 0) or 0), int((dims or {}).get("y", 0) or 0)
	candidates = []
	for y in range(h):
		for x in range(w):
			if (x, y) in interdites or not case_au_sol(cells, x, y):
				continue
			if any(_cheby_cases((x, y), d) < PIEGES_DISTANCE_DEPART for d in departs):
				continue
			candidates.append((x, y))
	# Fisher-Yates partiel sur `rand_fn` : déterministe sous un hasard injecté.
	n = min(max(0, int(qte or 0)), len(candidates))
	for i in range(n):
		j = i + int(rand_fn() * (len(candidates) - i))
		j = min(j, len(candidates) - 1)
		candidates[i], candidates[j] = candidates[j], candidates[i]
	return [nouveau_piege(f"{prefixe}{i}", CAMP_MONDE, x, y, danger)
			for i, (x, y) in enumerate(candidates[:n])]


def cases_carre(cx: int, cy: int, rayon: int, cells: list) -> list:
	"""Cases au sol d'un carré de Chebyshev de `rayon` centré sur (cx, cy) — l'emprise d'un
	piège posé. Rayon 0 = la case seule."""
	rayon = max(0, int(rayon or 0))
	return [[x, y]
			for y in range(cy - rayon, cy + rayon + 1)
			for x in range(cx - rayon, cx + rayon + 1)
			if case_au_sol(cells, x, y)]


# ── Jets ─────────────────────────────────────────────────────────────────────

def _difficulte(piege: dict) -> int:
	return _as_int((piege or {}).get("danger"), 1) * PIEGE_DIFFICULTE_PAR_DANGER


def seuil_detection(detecteur: dict, piege: dict, bonus: int = 0) -> int:
	"""Seuil d100 (jet ≤ seuil = repéré) : 50 + Int + bonus de compétence + `bonus` (fouille)
	− danger × PIEGE_DIFFICULTE_PAR_DANGER, borné à [5, 95] — idiome de
	`combat._detection_threshold`."""
	d = detecteur or {}
	return _borne(50 + _as_int(d.get("int")) + _as_int(d.get("detection_pieges"))
				  + _as_int(bonus) - _difficulte(piege), 5, 95)


def seuil_desamorcage(acteur: dict, piege: dict) -> int:
	"""Seuil d100 du désamorçage : 50 + Ag (les mains) + bonus de compétence − difficulté."""
	a = acteur or {}
	return _borne(50 + _as_int(a.get("ag")) + _as_int(a.get("desamorcage"))
				  - _difficulte(piege), 5, 95)


def seuil_detection_monstre(monstre: dict, piege: dict) -> int:
	"""Seuil d100 du flair d'un monstre : même compétence de détection que
	`combat._detection_threshold` (Vol, repli Int−10, repli Ag−30) − difficulté du piège."""
	m = monstre or {}
	vol, intel = _as_int(m.get("vol")), _as_int(m.get("int"))
	if vol > 0:
		skill = vol
	elif intel > 0:
		skill = intel - 10
	else:
		skill = _as_int(m.get("ag")) - 30
	return _borne(50 + skill - _difficulte(piege), 5, 95)


# ── Lectures ─────────────────────────────────────────────────────────────────

def est_actif(piege: dict) -> bool:
	return (piege or {}).get("etat") in ETATS_ACTIFS


def couvre(piege: dict, cases) -> bool:
	"""Le piège a-t-il une case dans `cases` (emprise d'un acteur) ?"""
	emprise = {tuple(c) for c in cases or []}
	return any(tuple(c) in emprise for c in (piege or {}).get("cases") or [])


def distance_piege(piege: dict, cases) -> int:
	"""Chebyshev entre les cases du piège et une emprise (la plus courte)."""
	pc = [tuple(c) for c in (piege or {}).get("cases") or []]
	ec = [tuple(c) for c in cases or []]
	if not pc or not ec:
		return 10 ** 6
	return min(_cheby_cases(a, b) for a in pc for b in ec)


def pieges_publics(pieges) -> list:
	"""Ce que le CLIENT peut voir : tout sauf les pièges encore cachés."""
	return [dict(p) for p in pieges or [] if (p or {}).get("etat") != ETAT_CACHE]


def pieges_desamorcables(pieges, acteur: dict, emprise) -> list:
	"""Pièges du MONDE détectés à Chebyshev ≤ 1 de l'emprise, si l'acteur sait désamorcer."""
	if _as_int((acteur or {}).get("desamorcage")) <= 0:
		return []
	return [p for p in pieges or []
			if p.get("camp") == CAMP_MONDE and p.get("etat") == ETAT_DETECTE
			and distance_piege(p, emprise) <= 1]


# ── Compétences de pose ──────────────────────────────────────────────────────

def normaliser_pose(raw) -> dict | None:
	"""Bloc `pose_piege` d'une compétence, normalisé, ou None s'il est absent/inexploitable
	(sans item à consommer, la compétence ne pose rien).

	{item, danger, degats, zone, portee, effets, nom, icon} — `degats` vide ⇒ `degats_de`,
	`zone` = rayon du carré couvert (0 = la case seule), `portee` ≥ 1."""
	if not isinstance(raw, dict):
		return None
	item = str(raw.get("item") or "").strip()
	if not item:
		return None
	danger = _borne(_as_int(raw.get("danger"), 1), DANGER_MIN, DANGER_MAX)
	# ⚠️ Seuls `buffs` (signés : une entrave est un buff négatif), `regen_pv`/`regen_pm`
	# (signées : négatif = POISON, perte au tour de la victime) et `duree` passent : c'est ce
	# que `combat._appliquer_effet_sur_cible` sait poser sur un monstre. Sans durée, rien.
	brut = raw.get("effets") if isinstance(raw.get("effets"), dict) else {}
	effets = {}
	duree = _as_int(brut.get("duree"))
	buffs = {str(k): _as_int(v) for k, v in (brut.get("buffs") or {}).items() if _as_int(v)}
	regen = {k: _as_int(brut.get(k)) for k in ("regen_pv", "regen_pm") if _as_int(brut.get(k))}
	if (buffs or regen) and duree > 0:
		effets = dict(regen, duree=duree)
		if buffs:
			effets["buffs"] = buffs
	return {
		"item": item,
		"danger": danger,
		"degats": str(raw.get("degats") or "").strip() or degats_de(danger),
		"zone": _borne(_as_int(raw.get("zone")), 0, POSE_ZONE_MAX),
		"portee": _borne(_as_int(raw.get("portee"), 1) or 1, 1, POSE_PORTEE_MAX),
		"effets": dict(effets),
		"nom": str(raw.get("nom") or "").strip(),
		"icon": str(raw.get("icon") or "").strip(),
	}
