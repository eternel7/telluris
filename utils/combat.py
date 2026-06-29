import re
import math
import random
import uuid
from db.config import get_doc, save_doc, find_docs
from models import character_stats
from models.character_stats import (
	BaseStats, compute_derived_stats
)
from utils.lieux import nav_allows, MOVE_OFFSETS
from utils.characters import grant_xp, recompute_equipment_bonus, carried_weight, poids_bounds, item_ref_id
from utils.quetes import maj_progress_kills

BATTLE_MAPS = [
	"map0001.jpg", "map0002.jpg", "map0003.jpg", "map0004.jpg",
	"map0005.jpg", "map0006.jpg", "map0007.jpg", "abandonned_church01.webp",
]


def _compute_actions_max(ag: int, v: int) -> int:
	"""Nombre d'actions par tour dérivé des stats : max(1, ceil(Ag/20 + V/5))."""
	return max(1, math.ceil(ag / 20 + v / 5))


def _charge_penalized_deplacement(deplacement_base: int, charge: float, charge_max: float) -> int:
	"""Déplacement de combat après malus de charge.

	Au-delà de la moitié de la charge max, le déplacement est divisé par deux
	(arrondi à l'inférieur, minimum 1). En-dessous, valeur de base inchangée.
	"""
	if charge_max > 0 and charge > charge_max / 2:
		return max(1, deplacement_base // 2)
	return max(1, deplacement_base)


def _recompute_player_deplacement(joueur: dict) -> None:
	"""Réapplique le malus de charge au déplacement du joueur (après un ramassage)."""
	joueur["deplacement"] = _charge_penalized_deplacement(
		joueur.get("deplacement_base", joueur.get("deplacement", 1)),
		joueur.get("charge", 0), joueur.get("charge_max", 0),
	)


# ── Grille de combat ─────────────────────────────────────────────────────────
# Terrain cells[y][x] : -1 inaccessible, 0 inaccessible sauf vol, 1 accessible,
# n>1 accessible sous condition. Le vol n'étant pas implémenté, seuil >= 1.
DEFAULT_GRID_W = 13
DEFAULT_GRID_H = 11


def _open_grid(w: int = DEFAULT_GRID_W, h: int = DEFAULT_GRID_H) -> dict:
	"""Grille entièrement praticable (terrain ouvert, fallback sans battle map)."""
	return {"dims": {"x": w, "y": h}, "cells": [[1] * w for _ in range(h)]}


def _passable(cells: list, x: int, y: int) -> bool:
	if not cells or y < 0 or y >= len(cells):
		return False
	row = cells[y]
	if x < 0 or x >= len(row):
		return False
	return row[x] >= 1


def _cheby(a: dict, b: dict) -> int:
	return max(abs(a["pos"]["x"] - b["pos"]["x"]), abs(a["pos"]["y"] - b["pos"]["y"]))


def _line_of_sight(cells: list, x0: int, y0: int, x1: int, y1: int) -> bool:
	"""Ligne de vue libre entre deux cases (tracé de Bresenham).

	Bloquée si une case INTERMÉDIAIRE (hors extrémités) n'est pas praticable
	(`cells < 1`) — un mur arrête le projectile. `nav` n'est pas consulté : le tir
	survole les coins nav-bloqués, seul le terrain (murs) bloque la trajectoire.
	"""
	dx = abs(x1 - x0)
	dy = abs(y1 - y0)
	sx = 1 if x0 < x1 else -1
	sy = 1 if y0 < y1 else -1
	err = dx - dy
	x, y = x0, y0
	while True:
		if (x, y) != (x0, y0) and (x, y) != (x1, y1) and not _passable(cells, x, y):
			return False
		if x == x1 and y == y1:
			return True
		e2 = 2 * err
		if e2 > -dy:
			err -= dy
			x += sx
		if e2 < dx:
			err += dx
			y += sy


def _occupied_set(combat_doc: dict, exclude: dict | None = None) -> set:
	"""Ensemble des (x,y) occupés par des acteurs vivants (hors `exclude`)."""
	occ = set()
	for j in combat_doc["joueurs"]:
		if j is not exclude and j.get("currentPV", 1) > 0:
			occ.add((j["pos"]["x"], j["pos"]["y"]))
	for m in combat_doc["monstres"]:
		if m is not exclude and m["vivant"]:
			occ.add((m["pos"]["x"], m["pos"]["y"]))
	return occ


def _occupied_at(combat_doc: dict, x: int, y: int) -> bool:
	return (x, y) in _occupied_set(combat_doc)


def _move_ap_used_for(actor: dict, cells_moved: int) -> int:
	"""AP consommés pour `cells_moved` cases : ceil(cells * actions_max / deplacement)."""
	dep = max(1, actor.get("deplacement", 1))
	return math.ceil(cells_moved * actor["actions_max"] / dep)


def _refresh_actions(actor: dict) -> None:
	"""Recalcule actions_restantes = actions_max - attaques - ramassages - AP_déplacement."""
	used = (actor.get("attaques", 0) + actor.get("ramasses", 0)
			+ _move_ap_used_for(actor, actor.get("cells_moved", 0)))
	actor["actions_restantes"] = max(0, actor["actions_max"] - used)


def _reset_turn_budget(actor: dict) -> None:
	"""Réinitialise le budget d'un acteur en début de tour."""
	actor["cells_moved"] = 0
	actor["attaques"] = 0
	actor["ramasses"] = 0
	actor["actions_restantes"] = actor["actions_max"]


def _find_path(cells: list, dims: dict, start: tuple, goal: tuple, blocked: set,
			   nav: dict | None = None) -> list | None:
	"""A* 8-directions (heuristique Chebyshev). Porté du prototype client.

	Mêmes règles que le déplacement du joueur : un pas est valide s'il vise une case
	dans la grille, praticable (`cells >= 1`), non `blocked` (sauf la case d'arrivée,
	occupable par la cible) et autorisé par `nav` (masques de la carte, diagonales
	incluses). Les diagonales coûtant 1 case, l'heuristique est la distance de
	Chebyshev (admissible) plutôt que Manhattan.
	Retourne la liste [(x,y), ...] de start à goal inclus, ou None.
	"""
	nav = nav or {}
	w, h = dims["x"], dims["y"]
	sx, sy = start
	gx, gy = goal
	start_node = {"x": sx, "y": sy, "g": 0, "h": max(abs(gx - sx), abs(gy - sy)), "parent": None}
	start_node["f"] = start_node["h"]
	open_list = [start_node]
	closed = set()

	while open_list:
		open_list.sort(key=lambda n: n["f"])
		cur = open_list.pop(0)
		if cur["x"] == gx and cur["y"] == gy:
			path = []
			node = cur
			while node:
				path.append((node["x"], node["y"]))
				node = node["parent"]
			return path[::-1]
		closed.add((cur["x"], cur["y"]))
		for dx, dy in MOVE_OFFSETS:
			nx, ny = cur["x"] + dx, cur["y"] + dy
			if nx < 0 or nx >= w or ny < 0 or ny >= h:
				continue
			if not _passable(cells, nx, ny):
				continue
			if not nav_allows(nav, cur["x"], cur["y"], dx, dy):
				continue
			if (nx, ny) in closed:
				continue
			is_goal = (nx == gx and ny == gy)
			if (nx, ny) in blocked and not is_goal:
				continue
			g = cur["g"] + 1
			existing = next((n for n in open_list if n["x"] == nx and n["y"] == ny), None)
			if existing is None:
				node = {"x": nx, "y": ny, "g": g, "h": max(abs(gx - nx), abs(gy - ny)), "parent": cur}
				node["f"] = node["g"] + node["h"]
				open_list.append(node)
			elif g < existing["g"]:
				existing["g"] = g
				existing["f"] = g + existing["h"]
				existing["parent"] = cur
	return None


def _nearest_passable(cells: list, dims: dict, tx: int, ty: int, occupied: set) -> tuple:
	"""Case praticable et libre la plus proche de (tx, ty) par recherche en spirale."""
	w, h = dims["x"], dims["y"]
	tx = max(0, min(w - 1, tx))
	ty = max(0, min(h - 1, ty))
	for radius in range(0, max(w, h) + 1):
		for dy in range(-radius, radius + 1):
			for dx in range(-radius, radius + 1):
				if max(abs(dx), abs(dy)) != radius:
					continue
				x, y = tx + dx, ty + dy
				if _passable(cells, x, y) and (x, y) not in occupied:
					return (x, y)
	return (tx, ty)


# ── Placement initial des acteurs ─────────────────────────────────────────────
# Central placé aléatoirement sur un sol type 1 : 50 % à ~5 cases du centre, 50 % à
# ~5 cases des bords (distance élargie « ou plus » si nécessaire pour pouvoir loger
# et rejoindre les monstres). Les monstres sont ensuite dispersés aléatoirement sur
# des cases atteignables depuis lui — la région joignable est calculée une fois par
# flood fill, donc toute case tirée garantit un chemin (équivaut à « tirer au hasard
# puis tester un chemin, sinon reboucler », sans le coût de la boucle).
PLAYER_CENTER_DIST: int = 5   # mode « centre »  : distance cible depuis le centre
PLAYER_BORDER_INSET: int = 5  # mode « bordure » : distance cible depuis les bords


def _iter_cells(dims: dict):
	for y in range(dims["y"]):
		for x in range(dims["x"]):
			yield x, y


def _is_type1(cells: list, x: int, y: int) -> bool:
	"""Sol « normal » praticable (type exactement 1)."""
	return 0 <= y < len(cells) and 0 <= x < len(cells[y]) and cells[y][x] == 1


def _reachable_region(cells: list, dims: dict, nav: dict, start: tuple) -> set:
	"""Toutes les cases praticables (>=1) atteignables depuis `start`.

	Flood fill 8-directions respectant `nav` — mêmes règles que l'A* de
	déplacement, donc cette région == l'ensemble des cases que l'A* sait joindre.
	"""
	sx, sy = start
	if not _passable(cells, sx, sy):
		return set()
	w, h = dims["x"], dims["y"]
	seen = {(sx, sy)}
	stack = [(sx, sy)]
	while stack:
		x, y = stack.pop()
		for dx, dy in MOVE_OFFSETS:
			nx, ny = x + dx, y + dy
			if (nx, ny) in seen or nx < 0 or nx >= w or ny < 0 or ny >= h:
				continue
			if not _passable(cells, nx, ny) or not nav_allows(nav, x, y, dx, dy):
				continue
			seen.add((nx, ny))
			stack.append((nx, ny))
	return seen


def _player_cell_candidates(cells: list, dims: dict, occupied: set, mode: str) -> list:
	"""Cases type 1 libres, ordonnées selon le mode de placement du central.

	Préférence aux cases à >= distance cible (5) du centre (mode 'centre') ou des
	bords (mode 'bordure'), la plus proche de la cible d'abord puis de plus en plus
	loin (« ou plus »). Ordre aléatoire à l'intérieur d'un même palier de distance.
	"""
	w, h = dims["x"], dims["y"]
	cx, cy = w // 2, h // 2
	target = PLAYER_CENTER_DIST if mode == "centre" else PLAYER_BORDER_INSET
	tiers: dict = {}
	for x, y in _iter_cells(dims):
		if not _is_type1(cells, x, y) or (x, y) in occupied:
			continue
		if mode == "centre":
			d = max(abs(x - cx), abs(y - cy))
		else:
			d = min(x, y, w - 1 - x, h - 1 - y)
		# « d cases ou plus » : d >= cible prioritaire (excédent minimal d'abord),
		# cases plus proches que la cible reléguées en dernier recours.
		key = (0, d - target) if d >= target else (1, target - d)
		tiers.setdefault(key, []).append((x, y))
	ordered = []
	for key in sorted(tiers):
		bucket = tiers[key]
		random.shuffle(bucket)
		ordered.extend(bucket)
	return ordered


def _nearest_of(pool, ref: tuple) -> tuple | None:
	"""Case de `pool` la plus proche de `ref` (distance Chebyshev), ou None si vide."""
	best, best_d = None, None
	for c in pool:
		d = max(abs(c[0] - ref[0]), abs(c[1] - ref[1]))
		if best_d is None or d < best_d:
			best, best_d = c, d
	return best


def _first_passable_cells(cells: list, dims: dict, count: int) -> list:
	"""Les `count` premières cases praticables (>0) en balayant depuis (0,0)."""
	out = []
	for x, y in _iter_cells(dims):
		if _passable(cells, x, y):
			out.append((x, y))
			if len(out) >= count:
				return out
	return out


def _place_actors(combat_doc: dict, grid: dict) -> None:
	"""Place le groupe joueur puis disperse les monstres aléatoirement, en garantissant
	qu'ils peuvent rejoindre le personnage central.

	1. Tirage 50/50 du mode du central : ~5 cases du centre, ou ~5 cases des bords.
	2. Central + groupe potentiel sur des cases type 1 libres ; la distance s'élargit
	   (« ou plus ») jusqu'à une case dont la région atteignable peut tout loger.
	3. Vérification que tous les joueurs se rejoignent (sols >= 1) ; sinon repli sur
	   les premiers sols > 0 trouvés depuis (0,0).
	4. Monstres placés aléatoirement sur des cases de la région du central — donc
	   toujours joignables (remplace « tirer au hasard puis reboucler si non joint »).
	"""
	cells, dims = grid["cells"], grid["dims"]
	nav = grid.get("nav", {})
	joueurs = combat_doc["joueurs"]
	monstres = combat_doc["monstres"]
	occupied: set = set()

	need = len(joueurs) + len(monstres)  # cases distinctes à loger dans la région

	# 1-2. Mode + recherche d'une case type 1 pour le central dont la région
	#      atteignable est assez grande pour le groupe ET les monstres.
	mode = "centre" if random.random() < 0.5 else "bordure"
	main = joueurs[0]
	main_cell, region = None, set()
	for cand in _player_cell_candidates(cells, dims, occupied, mode):
		reg = _reachable_region(cells, dims, nav, cand)
		if len(reg) >= need:
			main_cell, region = cand, reg
			break

	placed_ok = False
	if main_cell is not None:
		main["pos"] = {"x": main_cell[0], "y": main_cell[1]}
		occupied.add(main_cell)
		# Groupe potentiel : cases type 1 libres de la région, au plus près du central.
		ok = True
		for j in joueurs[1:]:
			free = [c for c in region if c not in occupied]
			pick = _nearest_of([c for c in free if _is_type1(cells, c[0], c[1])] or free, main_cell)
			if pick is None:
				ok = False
				break
			j["pos"] = {"x": pick[0], "y": pick[1]}
			occupied.add(pick)
		# 3. Tous les joueurs doivent partager la région du central.
		placed_ok = ok and all((j["pos"]["x"], j["pos"]["y"]) in region for j in joueurs)

	# 3. (repli) Aucun placement valide : premiers sols > 0 depuis (0,0).
	if not placed_ok:
		fallback = _first_passable_cells(cells, dims, len(joueurs))
		occupied = set()
		for i, j in enumerate(joueurs):
			pos = fallback[i] if i < len(fallback) else (0, 0)
			j["pos"] = {"x": pos[0], "y": pos[1]}
			occupied.add(pos)
		region = _reachable_region(cells, dims, nav, (main["pos"]["x"], main["pos"]["y"]))

	# 4. Monstres : cases aléatoires de la région du central (toutes joignables).
	base = (main["pos"]["x"], main["pos"]["y"])
	for m in monstres:
		pool = [c for c in region if c not in occupied]
		if pool:
			pos = random.choice(pool)
		else:  # région saturée (carte minuscule) : repli sur la case libre la plus proche.
			pos = _nearest_passable(cells, dims, base[0], base[1], occupied)
		m["pos"] = {"x": pos[0], "y": pos[1]}
		occupied.add(pos)


def select_battle_map(zone_tags: list, depart_lieu: dict | None) -> dict | None:
	"""Sélection pondérée d'un lieu battle map selon le recoupement de tags.

	Poids = nb de tags communs entre la battle map et (tags zone ∪ tags lieu départ),
	avec un minimum de 1 pour rester tirable. Retourne le lieu ou None si aucun.
	"""
	candidates = [
		b for b in (find_docs({"type": "lieu", "categorie": "battle_map"}) or [])
		if b.get("cells")
	]
	if not candidates:
		return None
	pool_tags = set(zone_tags or []) | set((depart_lieu or {}).get("tags", []))
	weights = [max(1, len(set(b.get("tags", [])) & pool_tags)) for b in candidates]
	return random.choices(candidates, weights=weights, k=1)[0]


def get_combat_grid(combat_doc: dict) -> dict:
	"""Résout la grille {dims, cells, nav} du combat.

	`cells`/`nav` ne sont PAS dupliqués dans le doc combat : on référence le lieu
	battle map (`battle_map_id`) et on lit sa grille à la demande. `nav` = masque des
	directions interdites par case (cf. utils.lieux.get_final_mask), comme play_town.
	Repli sur une grille ouverte (taille `grid_dims`) si aucun lieu. Tolère un ancien
	doc avec `grid` en ligne.
	"""
	bm_id = combat_doc.get("battle_map_id")
	if bm_id:
		lieu = get_doc(bm_id)
		if lieu and lieu.get("cells"):
			return {
				"dims": lieu["dimensions"],
				"cells": lieu["cells"],
				"nav": lieu.get("nav", {}),
			}
	if combat_doc.get("grid", {}).get("cells"):  # rétro-compat docs existants
		grid = combat_doc["grid"]
		grid.setdefault("nav", {})
		return grid
	dims = combat_doc.get("grid_dims") or {"x": DEFAULT_GRID_W, "y": DEFAULT_GRID_H}
	grid = _open_grid(dims["x"], dims["y"])
	grid["nav"] = {}  # grille ouverte = aucune direction interdite
	return grid


def roll_dice(notation: str) -> int:
	"""Évalue une notation de dégâts et retourne au moins 1.

	Gère les termes simples ('1D6+3', '2D8', 'D4-1') comme les expressions
	composites issues des armes ('1D6+1D4+2', '1D8+1D6-1') : chaque terme 'nDm'
	est lancé (signe pris en compte), puis les entiers isolés sont additionnés.
	"""
	notation = notation.upper().replace(" ", "")
	total = 0
	for sign, n, sides in re.findall(r"([+-]?)(\d*)D(\d+)", notation):
		rolled = sum(random.randint(1, int(sides)) for _ in range(int(n or "1")))
		total += -rolled if sign == "-" else rolled
	# Modificateurs plats : entiers signés restants une fois les dés retirés.
	for mod in re.findall(r"[+-]?\d+", re.sub(r"[+-]?\d*D\d+", "", notation)):
		total += int(mod)
	return max(1, total)


def roll_monster_stats(espece: dict, profil: dict) -> BaseStats:
	base = espece.get("base_attributes", {})
	mods = profil.get("attributs_modifier", {})

	def roll(key):
		bmin = base.get(key, {}).get("min", 1)
		bmax = base.get(key, {}).get("max", 5)
		mod = mods.get(key, {})
		delta = random.randint(mod.get("min", 0), mod.get("max", 0)) if mod else 0
		return max(bmin, min(bmax, bmin + delta))

	return BaseStats(
		v=roll("V"), f=roll("F"), r=roll("R"), ag=roll("Ag"),
		vol=roll("Vol"), int_=roll("Int"), cha=roll("Cha"), ch=roll("Ch"),
	)


def _espece_midpoint(espece: dict) -> BaseStats:
	base = espece.get("base_attributes", {})
	def mid(key):
		bmin = base.get(key, {}).get("min", 1)
		bmax = base.get(key, {}).get("max", 5)
		return (bmin + bmax) // 2
	return BaseStats(
		v=mid("V"), f=mid("F"), r=mid("R"), ag=mid("Ag"),
		vol=mid("Vol"), int_=mid("Int"), cha=mid("Cha"), ch=mid("Ch"),
	)


def _weapon_attacks(character: dict, base: BaseStats) -> list:
	"""Profils d'attaque disponibles selon les armes équipées.

	Une entrée par mode (cac/jet/tir) : la meilleure portée si plusieurs armes du même
	mode. Le mode vient d'un tag de l'item (`tir`/`jet`, défaut `cac`) ; les armes d'hast
	sont du `cac` à `portee >= 2` (pas de mode dédié). Une attaque de mêlée (poings,
	portée 1) est TOUJOURS disponible. Chaque profil porte les clés à lire dans le
	snapshot joueur : `toucher` (cc|cd) et `degats` (degats_cc|degats_cd).

	- cac : toucher cc, dégâts degats_cc (basé F), portée = item.portee (>=1).
	- jet : toucher cd, dégâts degats_cc (basé F), portée = item.portee + F//JET_PORTEE_F_DIV.
	- tir : toucher cd, dégâts degats_cd (basé Ag), portée = item.portee.
	"""
	jet_div = max(1, character_stats.JET_PORTEE_F_DIV)
	best: dict = {}

	def consider(mode, portee, ranged, toucher, degats, label):
		cur = best.get(mode)
		if cur is None or portee > cur["portee"]:
			best[mode] = {"mode": mode, "portee": max(1, int(portee)), "ranged": ranged,
						  "toucher": toucher, "degats": degats, "label": label}

	for ref in (character.get("slots") or {}).values():
		item_id = item_ref_id(ref)
		if not item_id:
			continue
		item = get_doc(item_id)
		if not item or item.get("categorie") != "arme":
			continue
		tags = set(item.get("tags", []))
		base_portee = int(item.get("portee", 1) or 1)
		nom = item.get("nom", "Arme")
		if "tir" in tags:
			consider("tir", base_portee, True, "cd", "degats_cd", nom)
		elif "jet" in tags:
			consider("jet", base_portee + base.f // jet_div, True, "cd", "degats_cc", nom)
		else:  # cac par défaut (inclut les armes d'hast, portee >= 2)
			consider("cac", base_portee, False, "cc", "degats_cc", nom)

	best.setdefault("cac", {"mode": "cac", "portee": 1, "ranged": False,
							"toucher": "cc", "degats": "degats_cc", "label": "Mains nues"})
	return [best[m] for m in ("cac", "jet", "tir") if m in best]


def build_joueur_snapshot(character: dict, joueur_index: int = 0) -> dict:
	stats = character.get("caracteristiques_current", {})
	base = BaseStats(
		v=stats.get("V", 0), f=stats.get("F", 0), r=stats.get("R", 0),
		ag=stats.get("Ag", 0), vol=stats.get("Vol", 0), int_=stats.get("Int", 0),
		cha=stats.get("Cha", 0), ch=stats.get("Ch", 0),
	)
	# Bonus recalculé depuis les items équipés (slots = IDs) plutôt que depuis le champ
	# stocké equipment_bonus, périmé si un item a été modifié en base sans ré-équiper.
	equipment = recompute_equipment_bonus(character.get("slots", {}))
	voc_niveau = character.get("vocations_niveaux", {}).get(character.get("voc", ""), 0)
	derived = compute_derived_stats(base, niveau=voc_niveau, equipment=equipment)

	# Charge portée à l'entrée en combat → malus de déplacement si > charge_max/2.
	charge = round(carried_weight(character), 2)
	deplacement = _charge_penalized_deplacement(derived.deplacement, charge, derived.charge_max)

	# Profils d'attaque selon les armes équipées (mêlée/jet/tir) + portée de mêlée (legacy).
	attaques = _weapon_attacks(character, base)
	portee_cac = next((a["portee"] for a in attaques if a["mode"] == "cac"), 1)

	return {
		"id": f"joueur_{joueur_index}",
		"character_id": character["_id"],
		"nom": character.get("nom", "Aventurier"),
		"voc": character.get("voc", ""),
		"race": character.get("race", ""),
		"image": character.get("image", ""),
		"currentPV": character.get("currentPV", derived.pv_max),
		"pv_max": derived.pv_max,
		"currentPM": character.get("currentPM", derived.pm_max),
		"pm_max": derived.pm_max,
		"actions_restantes": _compute_actions_max(base.ag, base.v),
		"actions_max": _compute_actions_max(base.ag, base.v),
		"cc": derived.cc,
		"cd": derived.cd,
		"ag": base.ag,
		"pa": derived.pa,
		"degats_cc": derived.degats_cc,
		"degats_cd": derived.degats_cd,
		"initiative": derived.initiative,
		"deplacement": deplacement,            # après malus de charge
		"deplacement_base": derived.deplacement,  # sans malus (pour recalcul au ramassage)
		"charge": charge,
		"charge_max": derived.charge_max,
		"portee": portee_cac,
		"attaque_profils": attaques,   # profils d'attaque (cac/jet/tir) ; ≠ "attaques" (compteur)
		"pos": {"x": 0, "y": 0},
		"facing": 0,
		"cells_moved": 0,
		"attaques": 0,
		"ramasses": 0,
		"butin_ramasse": [],   # références {item, poids} des carcasses ramassées en combat
	}


def _pick_profil(profils: list, profil_weights: dict | None):
	"""Tire un profil parmi `profils` (déjà filtrés, p.ex. cap ville).

	Si `profil_weights` est fourni, tirage pondéré restreint aux profils présents
	dans `profils` (les ids inconnus / hors cap / poids ≤ 0 sont ignorés). Repli sur
	un tirage uniforme si aucun candidat pondéré ne subsiste.
	"""
	if not profils:
		return None
	if profil_weights:
		by_id = {p["_id"]: p for p in profils}
		candidates, poids = [], []
		for pid, w in profil_weights.items():
			p = by_id.get(pid)
			if p is not None and isinstance(w, (int, float)) and not isinstance(w, bool) and w > 0:
				candidates.append(p)
				poids.append(w)
		if candidates:
			return random.choices(candidates, weights=poids, k=1)[0]
	return random.choice(profils)


def instantiate_monsters(
	especes: list, profils: list, nb: int, zone_tags: list,
	profil_weights: dict | None = None,
) -> list:
	matching = [e for e in especes if set(e.get("tags", [])) & set(zone_tags)]
	pool = matching if matching else especes
	if not pool:
		return []

	monstres = []
	for i in range(nb):
		espece = random.choice(pool)
		profil = _pick_profil(profils, profil_weights)

		if profil:
			base_stats = roll_monster_stats(espece, profil)
			niveau = profil.get("niveau", 1)
			profil_id = profil["_id"]
		else:
			base_stats = _espece_midpoint(espece)
			niveau = 1
			profil_id = None

		derived = compute_derived_stats(base_stats, niveau=niveau)
		# XP dérivée de la difficulté : niveau du profil + somme des stats du monstre.
		sum_stats = (
			base_stats.v + base_stats.f + base_stats.r + base_stats.ag
			+ base_stats.vol + base_stats.int_ + base_stats.cha + base_stats.ch
		)
		xp_reward = max(1, niveau * 4 + sum_stats // 10)

		monstres.append({
			"id": f"monstre_{i}",
			"nom": espece.get("nom", "Monstre"),
			"espece_id": espece["_id"],
			"profil_id": profil_id,
			"image": espece.get("image", ""),
			"currentPV": max(1, derived.pv_max),
			"pv_max": max(1, derived.pv_max),
			"actions_restantes": _compute_actions_max(base_stats.ag, base_stats.v),
			"actions_max": _compute_actions_max(base_stats.ag, base_stats.v),
			"cc": derived.cc,
			"ag": base_stats.ag,
			"pa": derived.pa,
			"degats_cc": derived.degats_cc,
			"initiative": derived.initiative,
			"deplacement": derived.deplacement,
			"portee": 1,
			"pos": {"x": 0, "y": 0},
			"cells_moved": 0,
			"attaques": 0,
			"vivant": True,
			"xp_reward": xp_reward,
			"niveau": niveau,   # niveau du profil → pondère le tirage du poids de carcasse
		})

	return monstres


def create_combat_doc(
	character: dict, monstres: list, zone_tags: list, map_image: str,
	battle_map: dict | None = None,
) -> dict:
	joueur = build_joueur_snapshot(character, joueur_index=0)
	joueurs = [joueur]

	all_actors = [(j["id"], j["initiative"]) for j in joueurs]
	all_actors += [(m["id"], m["initiative"]) for m in monstres]
	all_actors.sort(key=lambda x: x[1], reverse=True)
	ordre = [a[0] for a in all_actors]

	combat_id = f"combat:{uuid.uuid4().hex}"
	combat_doc = {
		"_id": combat_id,
		"type": "combat",
		"user_id": character["user_id"],
		"character_id": character["_id"],
		"status": "active",
		"tour": 1,
		"ordre_initiative": ordre,
		"acteur_courant_index": 0,
		"map_image": map_image,
		"zone_tags": zone_tags,
		"joueurs": joueurs,
		"monstres": monstres,
		"log": [{"tour": 1, "acteur": "Système", "kind": "sys", "texte": "Le combat commence !"}],
		"xp_gagnee": 0,
	}
	# On référence le lieu battle map (grille statique non dupliquée). `cells` est
	# résolu à la demande via get_combat_grid(). Repli = grille ouverte.
	# `nav` DOIT être inclus : le placement (_reachable_region) suit les mêmes règles que
	# le déplacement (_find_path, qui charge nav via get_combat_grid). Sans lui, une carte
	# scindée par des masques nav (ex. chemin2) ferait spawn un monstre dans une région
	# nav-séparée du joueur → injoignable malgré la garantie de _place_actors.
	if battle_map:
		combat_doc["battle_map_id"] = battle_map["_id"]
		grid = {"dims": battle_map["dimensions"], "cells": battle_map["cells"],
				"nav": battle_map.get("nav", {})}
	else:
		grid = _open_grid()
		combat_doc["grid_dims"] = grid["dims"]
	_place_actors(combat_doc, grid)
	return combat_doc


# ── Helpers internes ────────────────────────────────────────────────────────

def _get_joueur(combat_doc: dict, actor_id: str) -> dict | None:
	for j in combat_doc["joueurs"]:
		if j["id"] == actor_id:
			return j
	return None


def _get_monstre(combat_doc: dict, actor_id: str) -> dict | None:
	for m in combat_doc["monstres"]:
		if m["id"] == actor_id:
			return m
	return None


def _hit_threshold(attaquant_cc: int, defenseur_ag: int) -> int:
	"""Seuil de réussite sur un d100 (jet <= seuil = touché).

	Jet sous CC, difficulté = Ag du défenseur : seuil = 50 + CC - Ag.
	Donc CC == Ag → 50 %. Clampé à [5, 95] pour garder toujours une marge.
	"""
	return max(5, min(95, 50 + attaquant_cc - defenseur_ag))


def _flee_threshold(joueur_init: int, monstre_init_max: int) -> int:
	"""Seuil de fuite sur d100 : 50 + init joueur - meilleure init ennemie, clampé [5, 95]."""
	return max(5, min(95, 50 + joueur_init - monstre_init_max))


def _check_victory(combat_doc: dict) -> None:
	if all(not m["vivant"] for m in combat_doc["monstres"]):
		xp = sum(m["xp_reward"] for m in combat_doc["monstres"])
		combat_doc["xp_gagnee"] = xp
		combat_doc["status"] = "victoire"
		joueur = combat_doc["joueurs"][0]
		combat_doc["log"].append({
			"tour": combat_doc["tour"],
			"acteur": "Système",
			"kind": "sys",
			"texte": f"Victoire ! {xp} XP gagnés.",
		})


def _do_monster_attack(combat_doc: dict, monstre: dict) -> None:
	joueur = combat_doc["joueurs"][0]
	seuil = _hit_threshold(monstre["cc"], joueur.get("ag", 0))
	roll = random.randint(1, 100)
	if roll <= seuil:
		dmg = max(1, roll_dice(monstre["degats_cc"]) - joueur["pa"])
		joueur["currentPV"] = max(0, joueur["currentPV"] - dmg)
		combat_doc["log"].append({
			"tour": combat_doc["tour"],
			"acteur": monstre["nom"],
			"kind": "hit",
			"texte": (
				f"{monstre['nom']} touche {joueur['nom']} pour {dmg} dégâts ! "
				f"(PV : {joueur['currentPV']}/{joueur['pv_max']})"
			),
		})
		if joueur["currentPV"] <= 0:
			combat_doc["status"] = "defaite"
			combat_doc["log"].append({
				"tour": combat_doc["tour"],
				"acteur": "Système",
				"kind": "sys",
				"texte": f"{joueur['nom']} est à terre !",
			})
	else:
		combat_doc["log"].append({
			"tour": combat_doc["tour"],
			"acteur": monstre["nom"],
			"kind": "miss",
			"texte": f"{monstre['nom']} rate son attaque ! (jet {roll} / seuil {seuil})",
		})


def _monster_step_toward(combat_doc: dict, monstre: dict, joueur: dict, grid: dict) -> bool:
	"""Avance le monstre d'une case vers le joueur via A*. Retourne True si déplacé."""
	blocked = _occupied_set(combat_doc, exclude=monstre)
	path = _find_path(
		grid["cells"], grid["dims"],
		(monstre["pos"]["x"], monstre["pos"]["y"]),
		(joueur["pos"]["x"], joueur["pos"]["y"]),
		blocked,
		grid.get("nav", {}),
	)
	if not path or len(path) < 2:
		return False
	nxt = path[1]
	# Ne pas entrer sur la case du joueur (cible) ni une case occupée.
	if nxt == (joueur["pos"]["x"], joueur["pos"]["y"]) or nxt in blocked:
		return False
	# Vérifier qu'il reste assez d'AP pour ce pas (coût proportionnel).
	projected = monstre["attaques"] + _move_ap_used_for(monstre, monstre["cells_moved"] + 1)
	if projected > monstre["actions_max"]:
		return False
	monstre["pos"] = {"x": nxt[0], "y": nxt[1]}
	monstre["cells_moved"] += 1
	_refresh_actions(monstre)
	return True


def _run_monster_turn(combat_doc: dict, monstre: dict, grid: dict) -> None:
	"""Tour d'un monstre : se rapprocher du joueur (A*) puis attaquer si à portée."""
	_reset_turn_budget(monstre)
	joueur = combat_doc["joueurs"][0]
	portee = monstre.get("portee", 1)

	# Phase déplacement : avancer vers le joueur tant qu'éloigné et budget dispo.
	steps = 0
	safety = 0
	while (combat_doc["status"] == "active" and monstre["actions_restantes"] > 0
		   and _cheby(monstre, joueur) > portee
		   and monstre["cells_moved"] < monstre.get("deplacement", 1)
		   and safety < 100):
		safety += 1
		if not _monster_step_toward(combat_doc, monstre, joueur, grid):
			break
		steps += 1
	if steps > 0:
		combat_doc["log"].append({
			"tour": combat_doc["tour"],
			"acteur": monstre["nom"],
			"kind": "move",
			"texte": f"{monstre['nom']} avance vers {joueur['nom']} ({steps} case(s)).",
		})

	# Phase attaque : frapper tant qu'à portée et qu'il reste des actions.
	while (combat_doc["status"] == "active" and monstre["actions_restantes"] > 0
		   and _cheby(monstre, joueur) <= portee):
		_do_monster_attack(combat_doc, monstre)
		monstre["attaques"] += 1
		_refresh_actions(monstre)

	idx = combat_doc["acteur_courant_index"] + 1
	if idx >= len(combat_doc["ordre_initiative"]):
		idx = 0
		combat_doc["tour"] += 1
	combat_doc["acteur_courant_index"] = idx


def _resolve_until_player(combat_doc: dict, grid: dict, start_at_current: bool = False) -> None:
	"""Run monster turns until it's a player's turn.

	start_at_current=True  : process the actor at acteur_courant_index first (combat init).
	start_at_current=False : advance past the current actor first (after player action).
	"""
	ordre = combat_doc["ordre_initiative"]
	max_iter = len(ordre) * 20

	if not start_at_current:
		# Move past current actor before entering the loop
		idx = combat_doc["acteur_courant_index"] + 1
		if idx >= len(ordre):
			idx = 0
			combat_doc["tour"] += 1
		combat_doc["acteur_courant_index"] = idx

	for _ in range(max_iter):
		if combat_doc["status"] != "active":
			break
		actor_id = ordre[combat_doc["acteur_courant_index"]]
		if actor_id.startswith("joueur_"):
			joueur = _get_joueur(combat_doc, actor_id)
			if joueur:
				_reset_turn_budget(joueur)
			break
		monstre = _get_monstre(combat_doc, actor_id)
		if not monstre or not monstre["vivant"]:
			# Dead monster — skip
			idx = combat_doc["acteur_courant_index"] + 1
			if idx >= len(ordre):
				idx = 0
				combat_doc["tour"] += 1
			combat_doc["acteur_courant_index"] = idx
			continue
		_run_monster_turn(combat_doc, monstre, grid)


def _advance_and_resolve(combat_doc: dict, grid: dict) -> None:
	"""After a player action: advance past the player and resolve all monster turns."""
	_resolve_until_player(combat_doc, grid, start_at_current=False)


def resolve_first_turns(combat_doc: dict) -> None:
	"""Called after combat creation: if monsters go first, resolve their turns."""
	_resolve_until_player(combat_doc, get_combat_grid(combat_doc), start_at_current=True)


# ── API publique ────────────────────────────────────────────────────────────

def resolve_action(
	combat_doc: dict, action_type: str, cible_id: str | None = None,
	dx: int | None = None, dy: int | None = None, sens: int | None = None,
	mode: str | None = None,
) -> dict:
	ordre = combat_doc["ordre_initiative"]
	actor_id = ordre[combat_doc["acteur_courant_index"]]

	if not actor_id.startswith("joueur_"):
		return {"error": "Ce n'est pas le tour du joueur."}

	joueur = _get_joueur(combat_doc, actor_id)
	if not joueur:
		return {"error": "Joueur introuvable."}
	if joueur["actions_restantes"] <= 0:
		return {"error": "Plus d'actions disponibles."}

	portee = joueur.get("portee", 1)
	grid = get_combat_grid(combat_doc)
	result: dict = {}

	if action_type == "deplacer":
		if dx is None or dy is None:
			return {"error": "Direction manquante."}
		dx = max(-1, min(1, int(dx)))
		dy = max(-1, min(1, int(dy)))
		if dx == 0 and dy == 0:
			return {"error": "Direction nulle."}

		dims, cells = grid["dims"], grid["cells"]
		nx, ny = joueur["pos"]["x"] + dx, joueur["pos"]["y"] + dy
		if nx < 0 or nx >= dims["x"] or ny < 0 or ny >= dims["y"]:
			return {"error": "Hors de la zone."}
		if not _passable(cells, nx, ny):
			return {"error": "Terrain infranchissable."}
		if not nav_allows(grid.get("nav", {}), joueur["pos"]["x"], joueur["pos"]["y"], dx, dy):
			return {"error": "Direction bloquée."}
		if _occupied_at(combat_doc, nx, ny):
			return {"error": "Case occupée."}
		if joueur["cells_moved"] >= joueur.get("deplacement", 1):
			return {"error": "Budget de déplacement épuisé."}
		projected = joueur["attaques"] + _move_ap_used_for(joueur, joueur["cells_moved"] + 1)
		if projected > joueur["actions_max"]:
			return {"error": "Plus d'actions pour se déplacer."}

		joueur["pos"] = {"x": nx, "y": ny}
		joueur["cells_moved"] += 1
		_refresh_actions(joueur)
		combat_doc["log"].append({
			"tour": combat_doc["tour"],
			"acteur": joueur["nom"],
			"kind": "move",
			"texte": f"{joueur['nom']} se déplace en [{nx},{ny}].",
		})
		result = {"moved": True, "pos": joueur["pos"]}

	elif action_type == "tourner":
		# Rotation ±90° (caméra). Coûte une case du budget de déplacement.
		if sens not in (-1, 1):
			return {"error": "Sens de rotation invalide."}
		if joueur["cells_moved"] >= joueur.get("deplacement", 1):
			return {"error": "Budget de déplacement épuisé."}
		projected = joueur["attaques"] + _move_ap_used_for(joueur, joueur["cells_moved"] + 1)
		if projected > joueur["actions_max"]:
			return {"error": "Plus d'actions pour pivoter."}

		joueur["facing"] = (joueur.get("facing", 0) + sens * 90) % 360
		joueur["cells_moved"] += 1
		_refresh_actions(joueur)
		combat_doc["log"].append({
			"tour": combat_doc["tour"],
			"acteur": joueur["nom"],
			"kind": "move",
			"texte": f"{joueur['nom']} pivote ({'droite' if sens > 0 else 'gauche'}).",
		})
		result = {"turned": True, "facing": joueur["facing"]}

	elif action_type == "attaquer":
		alive = [m for m in combat_doc["monstres"] if m["vivant"]]
		if not alive:
			return {"error": "Aucune cible disponible."}

		# Profil d'attaque selon le mode demandé (arme), repli sur la mêlée (cac).
		attaques = joueur.get("attaque_profils") or []
		profil = next((a for a in attaques if a["mode"] == mode), None) if mode else None
		if profil is None:
			profil = next((a for a in attaques if a["mode"] == "cac"), None)
		if profil is None:
			profil = {"mode": "cac", "portee": joueur.get("portee", 1), "ranged": False,
					  "toucher": "cc", "degats": "degats_cc"}
		atk_portee = max(1, int(profil.get("portee", 1)))
		is_ranged = bool(profil.get("ranged"))
		skill = joueur.get("cd" if profil.get("toucher") == "cd" else "cc", 0)
		notation = joueur.get(profil.get("degats", "degats_cc")) or joueur.get("degats_cc", "1D4")

		if cible_id:
			monstre = _get_monstre(combat_doc, cible_id)
			if not monstre or not monstre["vivant"]:
				return {"error": "Cible invalide."}
		else:
			candidats = [m for m in alive if _cheby(joueur, m) <= atk_portee]
			if not candidats:
				return {"error": "Aucune cible à portée. Rapprochez-vous."}
			monstre = candidats[0]

		# Règles de combat à distance (jet/tir) : pas d'engagement au corps à corps + ligne de vue.
		if is_ranged:
			if any(m["vivant"] and _cheby(joueur, m) <= 1 for m in combat_doc["monstres"]):
				return {"error": "Un ennemi vous menace au corps à corps : impossible de tirer."}
			if not _line_of_sight(grid["cells"], joueur["pos"]["x"], joueur["pos"]["y"],
								   monstre["pos"]["x"], monstre["pos"]["y"]):
				return {"error": "Ligne de vue obstruée."}
		if _cheby(joueur, monstre) > atk_portee:
			return {"error": "Cible hors de portée."}

		seuil = _hit_threshold(skill, monstre.get("ag", 0))
		roll = random.randint(1, 100)
		if roll <= seuil:
			dmg = max(1, roll_dice(notation) - monstre["pa"])
			monstre["currentPV"] = max(0, monstre["currentPV"] - dmg)
			if monstre["currentPV"] <= 0:
				monstre["vivant"] = False
				combat_doc["log"].append({
					"tour": combat_doc["tour"],
					"acteur": joueur["nom"],
					"kind": "kill",
					"texte": f"{joueur['nom']} élimine {monstre['nom']} !",
				})
			else:
				combat_doc["log"].append({
					"tour": combat_doc["tour"],
					"acteur": joueur["nom"],
					"kind": "hit",
					"texte": (
						f"{joueur['nom']} touche {monstre['nom']} pour {dmg} dégâts ! "
						f"(PV : {monstre['currentPV']}/{monstre['pv_max']})"
					),
				})
			result = {"hit": True, "dmg": dmg, "cible": monstre["nom"], "cible_pv": monstre["currentPV"]}
		else:
			combat_doc["log"].append({
				"tour": combat_doc["tour"],
				"acteur": joueur["nom"],
				"kind": "miss",
				"texte": f"{joueur['nom']} rate son attaque sur {monstre['nom']} ! (jet {roll} / seuil {seuil})",
			})
			result = {"hit": False, "roll": roll, "seuil": seuil}

		joueur["attaques"] += 1
		_refresh_actions(joueur)
		_check_victory(combat_doc)

	elif action_type == "passer":
		combat_doc["log"].append({
			"tour": combat_doc["tour"],
			"acteur": joueur["nom"],
			"kind": "sys",
			"texte": f"{joueur['nom']} passe son tour.",
		})
		joueur["actions_restantes"] = 0
		result = {"passed": True}

	elif action_type == "fuir":
		init_max = max(
			(m["initiative"] for m in combat_doc["monstres"] if m["vivant"]),
			default=0,
		)
		seuil = _flee_threshold(joueur["initiative"], init_max)
		flee_roll = random.randint(1, 100)
		if flee_roll <= seuil:
			combat_doc["status"] = "fuite"
			combat_doc["log"].append({
				"tour": combat_doc["tour"],
				"acteur": joueur["nom"],
				"kind": "flee",
				"texte": f"{joueur['nom']} prend la fuite !",
			})
			result = {"fled": True}
		else:
			combat_doc["log"].append({
				"tour": combat_doc["tour"],
				"acteur": joueur["nom"],
				"kind": "flee",
				"texte": f"{joueur['nom']} tente de fuir mais échoue ! (jet {flee_roll}/{seuil})",
			})
			joueur["actions_restantes"] = 0
			result = {"fled": False, "roll": flee_roll, "seuil": seuil}

	elif action_type == "ramasser":
		# Ramasser la carcasse d'un ennemi mort adjacent, coûte 1 action. Interdit si
		# un ennemi VIVANT est au corps à corps (adjacent) → il faut d'abord se dégager.
		if any(m["vivant"] and _cheby(joueur, m) <= 1 for m in combat_doc["monstres"]):
			return {"error": "Un ennemi vous menace au corps à corps."}
		morts_adj = [
			m for m in combat_doc["monstres"]
			if not m["vivant"] and not m.get("loote") and _cheby(joueur, m) <= 1
		]
		if not morts_adj:
			return {"error": "Aucune carcasse à portée."}
		if cible_id:
			monstre = next((m for m in morts_adj if m["id"] == cible_id), None)
			if monstre is None:
				return {"error": "Carcasse invalide."}
		else:
			monstre = morts_adj[0]

		item = _ensure_loot_item(monstre.get("espece_id", ""), monstre.get("nom", ""))
		if item is None:
			return {"error": "Cette créature ne laisse aucun reste."}
		poids = _roll_carcasse_weight(item, monstre.get("niveau", 1))
		if joueur.get("charge", 0) + poids > joueur.get("charge_max", 0):
			return {"error": "Trop lourd : vous ne pouvez pas porter cette carcasse."}

		monstre["loote"] = True
		# Référence {item, poids} : le poids d'instance tiré est conservé dans l'inventaire.
		joueur.setdefault("butin_ramasse", []).append({"item": item["_id"], "poids": poids})
		joueur["charge"] = round(joueur.get("charge", 0) + poids, 2)
		_recompute_player_deplacement(joueur)  # malus de charge éventuel
		joueur["ramasses"] = joueur.get("ramasses", 0) + 1
		_refresh_actions(joueur)
		combat_doc["log"].append({
			"tour": combat_doc["tour"],
			"acteur": joueur["nom"],
			"kind": "sys",
			"texte": f"{joueur['nom']} récupère {item.get('nom', 'une carcasse')}.",
		})
		result = {"looted": True, "item": item.get("nom"), "charge": joueur["charge"]}

	else:
		return {"error": f"Action inconnue : {action_type}"}

	if combat_doc["status"] == "active" and joueur["actions_restantes"] <= 0:
		_advance_and_resolve(combat_doc, grid)

	return result


# ── Butin (loot) ──────────────────────────────────────────────────────────────
# Loot 1-pour-1 avec le bestiaire : un monstre tué laisse une « carcasse » dont
# l'_id suit la règle item:<sub_id>, où sub_id = la partie de l'espece_id après
# "espece:". Les 133 carcasses sont pré-générées (item.json importé) ; on en crée
# une à la volée pour toute espèce ajoutée ensuite au bestiaire sans item associé.
# Ces carcasses sont des composants destinés à être transformés par les PNJ
# (boucher, alchimiste, magicien, forgeron…).

def _loot_item_id(espece_id: str) -> str | None:
	"""item:<sub_id> à partir d'un espece_id ('espece:<sub_id>'), ou None si malformé."""
	if not espece_id or not espece_id.startswith("espece:"):
		return None
	return "item:" + espece_id[len("espece:"):]


def _build_loot_item(item_id: str, espece_id: str, nom_fallback: str) -> dict:
	"""Doc item « Restes de … » créé à la volée pour une espèce sans carcasse pré-générée.

	Lit le doc espèce (si présent) pour le nom et un poids dérivé de la Force moyenne
	(échelle ×10 : F_moy/5, ×0.5 si petite_taille, ×2 si géant, borné 0.5–25 kg).
	"""
	espece = get_doc(espece_id) or {}
	nom = espece.get("nom") or nom_fallback or item_id[len("item:"):]
	base_f = espece.get("base_attributes", {}).get("F", {})
	f_avg = (base_f.get("min", 10) + base_f.get("max", 10)) / 2
	poids = f_avg / 5
	tags = set(espece.get("tags", []))
	if "petite_taille" in tags:
		poids *= 0.5
	if "geant" in tags:
		poids *= 2
	poids = round(max(0.5, min(25.0, poids)), 1)
	return {
		"_id": item_id,
		"type": "item",
		"nom": f"Restes de {nom}",
		"icon": "🦴",
		"rarete": "commun",
		"categorie": "composant",
		"slots": [],
		"poids": poids,
		"description": f"Dépouille de {nom} récupérée à l'issue du combat.",
		"source_espece": espece_id,
		"loot_defaut": True,
	}


def _ensure_loot_item(espece_id: str, nom_fallback: str = "") -> dict | None:
	"""Retourne le doc item carcasse d'une espèce, en le créant en base si absent.

	None si l'espece_id est malformé ou si la création échoue. Partagé par le
	ramassage en combat et par la construction du butin disponible à la victoire.
	"""
	item_id = _loot_item_id(espece_id)
	if not item_id:
		return None
	item = get_doc(item_id)
	if item is not None:
		return item
	item = _build_loot_item(item_id, espece_id, nom_fallback)
	if save_doc(item) is None:
		return None
	return item


def _roll_carcasse_weight(item: dict, niveau: int) -> float:
	"""Poids tiré pour une instance de carcasse.

	Si l'item a un poids fixe → ce poids. S'il a un poids [min, max] → on tire min OU
	max via random.choices, pondéré par le niveau du profil de l'ennemi :
	weights = [max(1, 7-niveau), max(1, 1+niveau)] → bas niveau ⇒ plutôt le min (léger),
	haut niveau ⇒ plutôt le max (lourd).
	"""
	pmin, pmax = poids_bounds(item)
	if pmin == pmax:
		return pmin
	w_min = max(1, 7 - niveau)
	w_max = max(1, 1 + niveau)
	return random.choices([pmin, pmax], weights=[w_min, w_max])[0]


def _carcasse_payload(monstre: dict) -> dict | None:
	"""Descripteur {monstre_id, item_id, nom, poids} de la carcasse d'un monstre, le
	poids étant tiré selon le niveau du profil (cf. _roll_carcasse_weight).

	None si la créature ne laisse pas de reste (espece_id malformé) ou si la
	création de l'item échoue.
	"""
	item = _ensure_loot_item(monstre.get("espece_id", ""), monstre.get("nom", ""))
	if item is None:
		return None
	return {
		"monstre_id": monstre["id"],
		"item_id": item["_id"],
		"nom": item.get("nom", item["_id"]),
		"poids": _roll_carcasse_weight(item, monstre.get("niveau", 1)),
	}


def finalize_combat(combat_doc: dict) -> bool:
	"""Applique l'issue du combat (XP/PV) au personnage en base.

	Idempotent ET atomique : l'id du combat est enregistré dans
	`character["combats_recompenses"]`, c.-à-d. DANS LE MÊME document que l'XP.
	La récompense ne peut donc être appliquée qu'une seule fois, même si la
	sauvegarde du doc combat échoue par ailleurs, et reste rattrapable (par /play)
	si `combat_action` n'a pas pu la finaliser.

	Retourne True si une récompense vient d'être appliquée et sauvegardée.
	"""
	status = combat_doc.get("status")
	if status not in ("victoire", "defaite", "fuite"):
		return False  # combat encore actif → rien à appliquer

	character = get_doc(combat_doc["character_id"])
	if not character:
		return False

	combat_id = combat_doc.get("_id")
	rewarded = character.get("combats_recompenses", [])
	if combat_id in rewarded:
		combat_doc["recompense_appliquee"] = True  # déjà appliqué à ce personnage
		return False

	joueur = combat_doc["joueurs"][0]
	if status == "victoire":
		character["currentPV"] = joueur["currentPV"]
		# XP + montée de niveau : règle partagée avec la découverte de lieux.
		grant_xp(character, combat_doc.get("xp_gagnee", 0))
	elif status == "defaite":
		character["currentPV"] = 1
	elif status == "fuite":
		character["currentPV"] = max(1, joueur["currentPV"])

	# Butin ramassé en plein combat (action « ramasser ») : conservé quelle que soit
	# l'issue — c'est tout l'intérêt de pouvoir saisir une carcasse puis fuir. Ajouté
	# dans le MÊME doc que l'XP → couvert par l'idempotence atomique (pas de double).
	ramasse = [i for i in joueur.get("butin_ramasse", []) if i]
	if ramasse:
		inventaire = character.get("inventaire", [])
		inventaire.extend(ramasse)
		character["inventaire"] = inventaire

	# Carcasses laissées au sol (monstres tués non ramassés) : proposées dans l'overlay
	# de fin UNIQUEMENT en cas de victoire. Le joueur choisit lesquelles emporter via
	# POST /api/combat/{id}/collect (borné par charge_max) — pas d'ajout automatique.
	if status == "victoire":
		dispo = []
		for m in combat_doc["monstres"]:
			if m.get("loote"):
				continue  # déjà ramassée pendant le combat
			payload = _carcasse_payload(m)
			if payload:
				dispo.append(payload)
		combat_doc["butin_disponible"] = dispo

	# Progression des quêtes de chasse : compte les monstres tués (toute issue), sous le
	# même garde exactly-once que l'XP → pas de double comptage si /play re-finalise.
	maj_progress_kills(character, combat_doc.get("monstres", []))

	# Idempotence atomique : on enregistre le combat dans le doc personnage,
	# sauvegardé avec l'XP. Borné pour éviter une croissance illimitée.
	rewarded.append(combat_id)
	character["combats_recompenses"] = rewarded[-50:]

	if save_doc(character) is None:
		return False  # échec de sauvegarde → ne pas marquer, on réessaiera

	combat_doc["recompense_appliquee"] = True
	return True
