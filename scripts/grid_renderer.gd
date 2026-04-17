# grid_renderer.gd
# Rendu visuel de la grille de combat.
# Équivalent JS : renderAll(), les classes CSS des cellules, showDmg().
# Attaché à un nœud GridContainer (ou Node2D selon structure choisie).
extends Node

# ── Couleurs (équivalent CSS variables) ──────────────────────
const C_FLOOR       := Color(0.137, 0.122, 0.102)      # --stone2
const C_WALL        := Color(0.059, 0.047, 0.035)      # mur sombre
const C_DOOR        := Color(0.227, 0.165, 0.082)      # porte fermée
const C_DOOR_OPEN   := Color(0.184, 0.133, 0.063, 0.6) # porte ouverte
const C_REACHABLE   := Color(0.290, 0.404, 0.255, 0.50)# vert mouvement
const C_DOOR_REACH  := Color(0.788, 0.573, 0.165, 0.40)# ambre porte
const C_ATTACKABLE  := Color(0.545, 0.102, 0.102, 0.50)# rouge attaque
const C_SELECTED    := Color(0.788, 0.573, 0.165, 0.25)# or sélection
const C_HOVER       := Color(0.227, 0.196, 0.157)      # survol

const C_PLAYER_GLOW := Color(0.941, 0.753, 0.290)      # halo joueur
const C_ENEMY_GLOW  := Color(0.753, 0.224, 0.169)      # halo ennemi
const C_HP_PLAYER   := Color(0.753, 0.224, 0.169)      # barre PV joueur
const C_HP_ENEMY    := Color(0.545, 0.102, 0.102)      # barre PV ennemi
const C_HP_BG       := Color(0.067, 0.067, 0.067)      # fond barre PV

const CELL_SIZE     : int = 52
const COLS          : int = 12
const ROWS          : int = 9

# ── Références (à assigner depuis la scène) ──────────────────
@export var manager_path : NodePath
var manager : CombatManager

# Nœuds enfants créés dynamiquement
var cell_panels   : Array = []   # ColorRect[ROWS][COLS]
var entity_labels : Array = []   # Label[ROWS][COLS] (emoji entité)
var hp_bars       : Array = []   # ColorRect[ROWS][COLS]

# ── Dmg float : Label temporaire ─────────────────────────────
var dmg_label_pool : Array = []

func _ready() -> void:
	manager = get_node(manager_path)
	manager.connect("grid_changed", _on_grid_changed)
	_build_grid()

# ── Construction initiale de la grille ───────────────────────
func _build_grid() -> void:
	# Utilise un GridContainer Godot pour aligner les cellules
	var grid_container := %GridContainer   # à créer dans la scène
	grid_container.columns = COLS

	cell_panels   = []
	entity_labels = []
	hp_bars       = []

	for r in range(ROWS):
		var row_panels  : Array = []
		var row_labels  : Array = []
		var row_hp      : Array = []

		for c in range(COLS):
			# Cellule principale
			var panel := Panel.new()
			panel.custom_minimum_size = Vector2(CELL_SIZE, CELL_SIZE)
			panel.mouse_filter = Control.MOUSE_FILTER_STOP # Capture le clic

			# Emoji / texte de l'entité
			var lbl := Label.new()
			lbl.mouse_filter = Control.MOUSE_FILTER_IGNORE
			lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			lbl.vertical_alignment   = VERTICAL_ALIGNMENT_CENTER
			lbl.anchor_right  = 1.0; lbl.anchor_bottom = 1.0
			lbl.add_theme_font_size_override("font_size", 24)
			panel.add_child(lbl)

			# Barre de PV (en bas de la cellule)
			var hp_bg := ColorRect.new()
			hp_bg.color = C_HP_BG
			hp_bg.anchor_left   = 0.05; hp_bg.anchor_right  = 0.95
			hp_bg.anchor_bottom = 1.0;  hp_bg.anchor_top    = 0.90
			hp_bg.mouse_filter  = Control.MOUSE_FILTER_IGNORE

			var hp_fill := ColorRect.new()
			hp_fill.color       = C_HP_PLAYER
			hp_fill.anchor_top  = 0.0; hp_fill.anchor_bottom = 1.0
			hp_fill.anchor_left = 0.0; hp_fill.anchor_right  = 1.0
			hp_fill.mouse_filter = Control.MOUSE_FILTER_IGNORE
			hp_bg.add_child(hp_fill)
			panel.add_child(hp_bg)

			# Clic
			panel.gui_input.connect(_on_cell_input.bind(r, c))

			grid_container.add_child(panel)
			row_panels.append(panel)
			row_labels.append(lbl)
			row_hp.append(hp_bg)

		cell_panels.append(row_panels)
		entity_labels.append(row_labels)
		hp_bars.append(row_hp)

	_on_grid_changed()

# ── Mise à jour du rendu ─────────────────────────────────────
func _on_grid_changed() -> void:
	if cell_panels.is_empty():
		return

	var reachable   := manager.get_reachable_cells()      # Array[Vector2i]
	var door_reach  := manager.get_door_reachable_cells()
	var attackable  := manager.get_attackable_cells()
		
	for r in range(ROWS):
		for c in range(COLS):
			var panel     : Panel     = cell_panels[r][c]
			var lbl       : Label     = entity_labels[r][c]
			var hp_bar    : ColorRect = hp_bars[r][c]
			var tile      : int       = manager.get_tile(r, c)
			var ent       : EntityData = manager.get_entity_at(r, c)
			var cell_vec  := Vector2i(c, r)

			# ── Couleur de fond ──────────────────────────────
			var bg_color : Color
			match tile:
				CombatMap.TILE_WALL:
					bg_color = C_WALL
				CombatMap.TILE_DOOR:
					bg_color = C_DOOR
				CombatMap.TILE_OPEN:
					bg_color = C_DOOR_OPEN
				_:
					bg_color = C_FLOOR

			# Surbrillances
			if cell_vec in attackable:
				bg_color = C_ATTACKABLE
			elif cell_vec in reachable:
				bg_color = C_REACHABLE
			elif cell_vec in door_reach:
				bg_color = C_DOOR_REACH

			# Sélection joueur
			if ent != null and ent == manager.player:
				bg_color = C_SELECTED

			_set_panel_color(panel, bg_color)

			# ── Contenu de la cellule ────────────────────────
			lbl.text = ""
			hp_bar.visible = false

			match tile:
				CombatMap.TILE_DOOR:
					lbl.text = "🚪"
				CombatMap.TILE_OPEN:
					lbl.add_theme_color_override("font_color", Color(1,1,1,0.35))
					lbl.text = "🚪"

			if ent != null and ent.alive:
				if ent.is_player:
					lbl.text = "⚔"
					lbl.add_theme_color_override("font_color", C_PLAYER_GLOW)
				else:
					# Nom court → emoji selon type
					lbl.text = "💀" if "Squelette" in ent.entity_name else "🐀"
					lbl.add_theme_color_override("font_color", C_ENEMY_GLOW)

				# Barre de PV
				var ratio := float(ent.hp) / float(ent.max_hp)
				hp_bar.visible = true
				var fill : ColorRect = hp_bar.get_child(0)
				fill.color = C_HP_PLAYER if ent.is_player else C_HP_ENEMY
				fill.anchor_right = clampf(ratio, 0.0, 1.0)

# ── Clic sur une cellule ─────────────────────────────────────
func _on_cell_input(event: InputEvent, r: int, c: int) -> void:
	if event is InputEventMouseButton \
	   and event.button_index == MOUSE_BUTTON_LEFT \
	   and event.pressed:
		manager.on_cell_clicked(r, c)

# ── Floating damage label ─────────────────────────────────────
# Affiche un label animé au-dessus de la cellule (tween).
func show_damage(r: int, c: int, value: int, miss: bool = false) -> void:
	if cell_panels.is_empty():
		return
	var panel : Panel = cell_panels[r][c]
	var pos   := panel.global_position + Vector2(CELL_SIZE * 0.5 - 15, -10)

	var lbl := Label.new()
	lbl.text = "ESQUIVE" if miss else "-%d" % value
	lbl.add_theme_font_size_override("font_size", 20 if not miss else 13)
	lbl.add_theme_color_override("font_color",
		Color(0.753, 0.224, 0.169) if not miss else Color(0.478, 0.561, 0.627))
	lbl.global_position = pos
	get_tree().root.add_child(lbl)

	var tween := create_tween()
	tween.tween_property(lbl, "position:y", lbl.position.y - 60, 1.0)
	tween.parallel().tween_property(lbl, "modulate:a", 0.0, 1.0)
	tween.tween_callback(lbl.queue_free)

# ── Utilitaire ───────────────────────────────────────────────
func _set_panel_color(panel: Panel, color: Color) -> void:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.border_width_left   = 1
	style.border_width_right  = 1
	style.border_width_top    = 1
	style.border_width_bottom = 1
	style.border_color = Color(0.05, 0.04, 0.03)
	panel.add_theme_stylebox_override("panel", style)
