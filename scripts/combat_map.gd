# combat_map.gd
# Gère la grille du donjon : données de tuiles, A*, requêtes spatiales.
# Équivalent JS : MAP_TEMPLATE, findPath(), entityAt().
class_name CombatMap
extends RefCounted

# ── Valeurs de tuile ──────────────────────────────────────────
const TILE_FLOOR  : int = 0
const TILE_WALL   : int = 1
const TILE_DOOR   : int = 2   # porte fermée
const TILE_OPEN   : int = 3   # porte ouverte

const COLS : int = 12
const ROWS : int = 9

# Grille courante (tableau 2D [ligne][colonne])
var grid : Array = []

# Référence aux entités vivantes (injectée par CombatManager)
var entities : Array = []

# ── Carte initiale ────────────────────────────────────────────
const MAP_TEMPLATE : Array = [
	[1,1,1,1,1,1,1,1,1,1,1,1],
	[1,0,0,0,0,1,0,0,0,0,0,1],
	[1,0,0,0,0,2,0,0,0,0,0,1],
	[1,0,0,0,0,1,0,0,0,0,0,1],
	[1,0,0,0,0,1,1,2,1,0,0,1],
	[1,0,0,0,0,0,0,0,0,0,0,1],
	[1,1,2,1,0,0,0,0,0,0,0,1],
	[1,0,0,0,0,0,1,0,0,0,0,1],
	[1,1,1,1,1,1,1,1,1,1,1,1],
]

var astar = AStarGrid2D.new()

func reset() -> void:
	grid = []
	for r in range(ROWS):
		var row : Array = []
		for c in range(COLS):
			row.append(MAP_TEMPLATE[r][c])
		grid.append(row)
	setup_astar()

func get_tile(r: int, c: int) -> int:
	if r < 0 or r >= ROWS or c < 0 or c >= COLS:
		return TILE_WALL
	return grid[r][c]

func set_tile(r: int, c: int, value: int) -> void:
	grid[r][c] = value

func is_walkable(r: int, c: int) -> bool:
	var t := get_tile(r, c)
	return t == TILE_FLOOR or t == TILE_OPEN

# Entité vivante sur la case (null si vide)
func entity_at(r: int, c: int) -> EntityData:
	for e in entities:
		if e.alive and e.grid_row == r and e.grid_col == c:
			return e
	return null

func setup_astar():
	astar.region = Rect2i(0, 0, COLS, ROWS)
	astar.cell_size = Vector2(1, 1) # On travaille en coordonnées de grille (0,1,2...)
	astar.default_compute_heuristic = AStarGrid2D.HEURISTIC_MANHATTAN
	astar.diagonal_mode = AStarGrid2D.DIAGONAL_MODE_NEVER

	astar.update()
	# Marquer les murs comme solides
	for r in ROWS:
		for c in COLS:
			if grid[r][c] == TILE_WALL:
				astar.set_point_solid(Vector2i(c, r), true)
				
# Distance de Chebyshev (pour portée d'attaque au contact)
func cheby_dist(a: EntityData, b: EntityData) -> int:
	return maxi(absi(a.grid_row - b.grid_row), absi(a.grid_col - b.grid_col))
	
func update_obstacles(mover: EntityData):
	# On commence par vider les obstacles temporaires (unités)
	# sans toucher aux murs statiques
	for r in ROWS:
		for c in COLS:
			astar.set_point_solid(Vector2i(c, r), (grid[r][c] == TILE_WALL))
	
	# On ajoute les entités comme obstacles, sauf le "mover"
	for e in entities:
		if e.alive and e != mover:
			astar.set_point_solid(Vector2i(e.grid_col, e.grid_row), true)
# ── A* ────────────────────────────────────────────────────────
# Retourne un Array de Vector2i [start, ..., target] ou [] si pas de chemin.
# mover : EntityData en cours de déplacement (pour ne pas se bloquer lui-même).
# include_doors : si true, les portes fermées sont traitées comme des tuiles
#                 cibles (utile pour afficher qu'on peut ouvrir une porte).
func find_path_astar(start_r: int, start_c: int, end_r: int, end_c: int, mover: EntityData, player: EntityData) -> Array:
	update_obstacles(mover)
	var enemi = mover != player
	var start = Vector2i(start_c, start_r)
	var end = Vector2i(end_c, end_r)
	# Vérifier si la destination est accessible
	if !enemi && (not astar.is_in_boundsv(end) or astar.is_point_solid(end)):
		return []
	
	# Retourne un PackedVector2Array de points
	var path = astar.get_id_path(start, end, enemi)
	
	return path
