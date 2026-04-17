# combat_manager.gd
# Chef d'orchestre du combat : gère les tours, les actions, l'IA ennemie.
# Équivalent JS : resetGame(), onCellClick(), enemyTurn(), startPlayerTurn(), etc.
# Ce script est attaché au nœud racine CombatScene.
class_name CombatManager
extends Node

# ── Signaux (le UI s'y abonne) ───────────────────────────────
signal log_added(message: String, category: String)
signal ui_updated
signal game_over(victory: bool, message: String)
signal grid_changed  # Demande un re-rendu complet de la grille

# ── Modes ─────────────────────────────────────────────────────
enum Mode { MOVE, ATTACK }
enum Phase { PLAYER, ENEMY }

# ── État ──────────────────────────────────────────────────────
var combat_map  : CombatMap   = CombatMap.new()
var player      : EntityData
var entities    : Array       = []   # joueur + ennemis
var mode        : Mode        = Mode.MOVE
var phase       : Phase       = Phase.PLAYER
var turn_count  : int         = 1
var selected    : bool        = false  # true = joueur sélectionné

# Stats de session
var stat_kills  : int = 0
var stat_dmg    : int = 0
var stat_rec    : int = 0

# ── Init ──────────────────────────────────────────────────────
func _ready() -> void:
	reset_game()

func reset_game() -> void:
	combat_map.reset()
	entities = []
	stat_kills = 0
	stat_dmg   = 0
	stat_rec   = 0
	turn_count = 1
	selected   = false
	phase      = Phase.PLAYER
	mode       = Mode.MOVE

	# Joueur
	player = EntityData.new()
	player.entity_name = "Aldric von Brunn"
	player.is_player   = true
	player.hp = 18; player.max_hp = 18
	player.str = 5; player.agi = 3; player.ac = 4
	player.cc  = 5; player.mvt = 3
	player.ap  = 2; player.max_ap = 2
	player.grid_row = 2; player.grid_col = 1
	player.alive    = true; player.defending = false
	entities.append(player)

	# Ennemis
	var sk1 := _make_enemy("Squelette", 8, 2, 1, 3, 2, 1, 1,  2, 9)
	var rat  := _make_enemy("Rat géant", 5, 2, 0, 4, 4, 2, 2,  5, 9)
	var sk2  := _make_enemy("Squelette", 8, 2, 1, 3, 2, 1, 1,  7, 8)
	entities.append(sk1)
	entities.append(rat)
	entities.append(sk2)

	combat_map.entities = entities

	add_log("— DÉBUT DU COMBAT — Aldric von Brunn entre dans le donjon...", "turn")
	add_log("Clique sur ta figurine pour la sélectionner.", "")
	emit_signal("ui_updated")
	emit_signal("grid_changed")

func _make_enemy(ename:String, hp:int, strength:int, ac:int,
				 cc:int, agi:int, ap:int, mvt:int,
				 row:int, col:int) -> EntityData:
	var e := EntityData.new()
	e.entity_name = ename
	e.is_player   = false
	e.hp = hp; e.max_hp = hp
	e.str = strength; e.ac = ac; e.cc = cc; e.agi = agi
	e.ap = ap;  e.max_ap = ap; e.mvt = mvt
	e.grid_row = row; e.grid_col = col
	e.alive = true
	return e

# ── Accesseurs UI ─────────────────────────────────────────────
func get_enemies() -> Array:
	return entities.filter(func(e): return not e.is_player)

func get_tile(r: int, c: int) -> int:
	return combat_map.get_tile(r, c)

func get_entity_at(r: int, c: int) -> EntityData:
	return combat_map.entity_at(r, c)

func get_reachable_cells() -> Array:
	# Retourne les Vector2i des cases vertes (sol accessible en <= mvt pas)
	if not selected or phase != Phase.PLAYER or player.ap <= 0:
		return []
	var result : Array = []
	for r in range(CombatMap.ROWS):
		for c in range(CombatMap.COLS):
			if combat_map.get_tile(r, c) == CombatMap.TILE_FLOOR:
				if combat_map.entity_at(r, c) == null:
					var path := combat_map.find_path_astar(player.grid_row, player.grid_col, r, c, player, player)
					if path.size() > 1 and path.size() - 1 <= player.mvt:
						result.append(Vector2i(c, r))
	return result

func get_door_reachable_cells() -> Array:
	# Portes adjacentes ouvrables (distance Manhattan = 1)
	if not selected or phase != Phase.PLAYER or player.ap <= 0:
		return []
	var result : Array = []
	for r in range(CombatMap.ROWS):
		for c in range(CombatMap.COLS):
			var t := combat_map.get_tile(r, c)
			if t == CombatMap.TILE_DOOR or t == CombatMap.TILE_OPEN:
				var dist := absi(r - player.grid_row) + absi(c - player.grid_col)
				if dist == 1:
					result.append(Vector2i(c, r))
	return result

func get_attackable_cells() -> Array:
	if not selected or mode != Mode.ATTACK or phase != Phase.PLAYER or player.ap <= 0:
		return []
	var result : Array = []
	for e in get_enemies():
		if e.alive:
			var cd := combat_map.cheby_dist(player, e)
			if cd <= 1:
				result.append(Vector2i(e.grid_col, e.grid_row))
	return result

# ── Actions joueur ────────────────────────────────────────────
func set_mode(new_mode: Mode) -> void:
	mode = new_mode
	emit_signal("grid_changed")

func select_player() -> void:
	selected = true
	emit_signal("grid_changed")

func on_cell_clicked(r: int, c: int) -> void:
	if phase != Phase.PLAYER:
		return

	var ent := combat_map.entity_at(r, c)
	# Clic sur le joueur → sélection
	if ent == player and player.alive:
		select_player()
		return

	if not selected:
		return

	# ── Porte (ouvrir / fermer) ───────────────────────────────
	var tile := combat_map.get_tile(r, c)
	if mode == Mode.MOVE and (tile == CombatMap.TILE_DOOR or tile == CombatMap.TILE_OPEN):
		var dist := absi(r - player.grid_row) + absi(c - player.grid_col)
		if dist == 1:
			if player.ap >= 1:
				if tile == CombatMap.TILE_DOOR:
					combat_map.set_tile(r, c, CombatMap.TILE_OPEN)
					add_log("Aldric ouvre la porte. (-1 PA)", "move")
				else:
					combat_map.set_tile(r, c, CombatMap.TILE_DOOR)
					add_log("Aldric ferme la porte. (-1 PA)", "move")
				player.ap -= 1
				emit_signal("ui_updated")
				emit_signal("grid_changed")
				if player.ap <= 0:
					_schedule(0.6, end_player_turn)
			else:
				add_log("Pas assez de PA pour manipuler la porte !", "")
		else:
			add_log("Trop loin pour atteindre cette porte.", "")
		return

	# ── Déplacement ───────────────────────────────────────────
	if mode == Mode.MOVE:
		if tile != CombatMap.TILE_FLOOR and tile != CombatMap.TILE_OPEN:
			return
		if ent != null:
			return
		if player.ap <= 0:
			add_log("Plus d'actions disponibles !", "")
			return
		var path := combat_map.find_path_astar(player.grid_row, player.grid_col, r, c, player, player)
		if path.size() > 1 and path.size() - 1 <= player.mvt:
			player.grid_row = r
			player.grid_col = c
			player.ap -= 1
			add_log("Aldric se déplace en [%d,%d]. (-1 PA)" % [r, c], "move")
			emit_signal("ui_updated")
			emit_signal("grid_changed")
			if player.ap <= 0:
				add_log("Plus d'actions — fin du tour.", "")
				_schedule(0.6, end_player_turn)
		return

	# ── Attaque ───────────────────────────────────────────────
	if mode == Mode.ATTACK:
		if ent == null or ent.is_player or not ent.alive:
			return
		if combat_map.cheby_dist(player, ent) > 1:
			return
		if player.ap <= 0:
			add_log("Plus d'actions disponibles !", "")
			return
		_resolve_attack(player, ent)
		player.ap -= 1
		emit_signal("ui_updated")
		emit_signal("grid_changed")
		if player.ap <= 0:
			add_log("Plus d'actions — fin du tour.", "")
			_schedule(0.6, end_player_turn)

func do_defend() -> void:
	player.defending = true
	add_log("Aldric se met en posture de défense (+2 PA ce tour).", "")
	end_player_turn()

func end_player_turn() -> void:
	selected = false
	phase = Phase.ENEMY
	emit_signal("ui_updated")
	emit_signal("grid_changed")
	_schedule(0.7, _run_enemy_turn)

# ── IA ennemie ────────────────────────────────────────────────
var _enemy_queue : Array = []
var _enemy_index : int   = 0

func _run_enemy_turn() -> void:
	_enemy_queue = get_enemies().filter(func(e): return e.alive)
	_enemy_index = 0
	_process_next_enemy()

func _process_next_enemy() -> void:
	if _enemy_index >= _enemy_queue.size():
		_start_player_turn()
		return

	var e : EntityData = _enemy_queue[_enemy_index]
	_enemy_index += 1

	var cd := combat_map.cheby_dist(e, player)

	if cd <= 1:
		# Attaque
		_enemy_attack_all(e)
		emit_signal("ui_updated")
		emit_signal("grid_changed")
		if not player.alive:
			return
		_schedule(0.5, _process_next_enemy)
	else:
		# Déplacement vers le joueur (limité par e.mvt)
		_enemy_move(e)
		emit_signal("grid_changed")
		_schedule(0.4, _process_next_enemy)

func _enemy_move(e: EntityData) -> void:
	var path := combat_map.find_path_astar(e.grid_row,e.grid_col, player.grid_row, player.grid_col, e, player)
	
	if path.size() < 1:
		add_log("%s est bloqué." % e.entity_name, "")
		return

	# path[0] = position actuelle, on s'arrête avant la case du joueur (-2)
	var stop_idx := mini(e.mvt, path.size() - 2)
	if stop_idx < 1:
		add_log("%s est bloqué." % e.entity_name, "")
		return

	var dest : Vector2i = path[stop_idx]
	# Si la case est occupée, reculer
	if combat_map.entity_at(dest.y, dest.x) != null:
		var moved := false
		for i in range(stop_idx - 1, 0, -1):
			var p : Vector2i = path[i]
			if combat_map.entity_at(p.y, p.x) == null:
				dest = p
				moved = true
				break
		if not moved:
			add_log("%s est bloqué." % e.entity_name, "")
			return

	e.grid_row = dest.y
	e.grid_col = dest.x
	add_log("%s avance de %d case(s)." % [e.entity_name, e.mvt], "move")

func _enemy_attack_all(e: EntityData) -> void:
	add_log("%s attaque %d fois !" % [e.entity_name, e.ap], "")
	while e.ap > 0:
		if not player.alive:
			break
		_resolve_attack(e, player)
		e.ap -= 1

# ── Résolution d'un jet d'attaque (Légende) ───────────────────
# Jet 1-10 sous CC de l'attaquant, diff = Ag du défenseur.
# Formule table Légende : seuil = max(2, min(10, 6 + (def_agi - att_cc)))
func _resolve_attack(attacker: EntityData, defender: EntityData) -> void:
	var roll   : int = randi_range(1, 10)
	var needed : int = clampi(6 + (defender.agi - attacker.cc), 2, 10)
	var hit    : bool = roll >= needed or roll == 10
	var crit   : bool = roll == 10

	if hit:
		var pa     : int = defender.ac + (2 if defender.defending else 0)
		var raw_dmg: int = randi_range(1, 10) + attacker.str - pa
		var dmg    : int = maxi(0 if not attacker.is_player else 1, raw_dmg)

		defender.hp = maxi(0, defender.hp - dmg)

		if attacker.is_player:
			stat_dmg += dmg
			var prefix := "CRITIQUE — " if crit else ""
			add_log("%sAldric frappe %s pour %d dégâts ! [jet %d / besoin %d+]" \
				% [prefix, defender.entity_name, dmg, roll, needed], "hit")
			if defender.hp <= 0:
				defender.alive = false
				stat_kills += 1
				add_log("%s est vaincu !" % defender.entity_name, "kill")
				_check_victory()
		else:
			stat_rec += dmg
			add_log("%s frappe Aldric pour %d dégâts ! [jet %d / besoin %d+]" \
				% [attacker.entity_name, dmg, roll, needed], "hit")
			if defender.hp <= 0:
				defender.alive = false
				_check_defeat()
	else:
		if attacker.is_player:
			add_log("Aldric manque %s. [jet %d / besoin %d+]" \
				% [defender.entity_name, roll, needed], "")
		else:
			add_log("%s manque Aldric. [jet %d / besoin %d+]" \
				% [attacker.entity_name, roll, needed], "")

	emit_signal("ui_updated")

# ── Tour joueur ───────────────────────────────────────────────
func _start_player_turn() -> void:
	turn_count += 1
	player.ap       = player.max_ap
	player.defending = false
	for e in get_enemies():
		if e.alive:
			e.ap = e.max_ap
	selected = true
	phase    = Phase.PLAYER
	mode     = Mode.MOVE
	add_log("— TOUR %d — À toi de jouer !" % turn_count, "turn")
	emit_signal("ui_updated")
	emit_signal("grid_changed")

# ── Victoire / Défaite ────────────────────────────────────────
func _check_victory() -> void:
	if get_enemies().all(func(e): return not e.alive):
		_schedule(0.8, func():
			emit_signal("game_over", true,
				"Tous les ennemis vaincus en %d tours. Dégâts infligés : %d." \
				% [turn_count, stat_dmg]))

func _check_defeat() -> void:
	emit_signal("game_over", false,
		"Aldric von Brunn est tombé au combat.\nIl faut un temple pour le ressusciter...")
	emit_signal("ui_updated")
	emit_signal("grid_changed")

# ── Log ───────────────────────────────────────────────────────
func add_log(msg: String, category: String = "") -> void:
	emit_signal("log_added", msg, category)

# ── Utilitaire : délai sans bloquer ──────────────────────────
func _schedule(delay: float, callable: Callable) -> void:
	await get_tree().create_timer(delay).timeout
	callable.call()
