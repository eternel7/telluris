# hud.gd
# Interface utilisateur : panneaux stats, log, boutons d'action.
# Équivalent JS : updateUI(), addLog(), setMode(), setPhase(), les boutons HTML.
extends Control

# ── Références vers CombatManager ───────────────────────────
@export var manager_path : NodePath
var manager : CombatManager

# Couleurs log (équivalent CSS)
const C_LOG_DEFAULT := Color(0.659, 0.749, 0.800)
const C_LOG_HIT     := Color(0.910, 0.788, 0.529)
const C_LOG_KILL    := Color(0.753, 0.224, 0.169)
const C_LOG_MOVE    := Color(0.416, 0.580, 0.376)
const C_LOG_TURN    := Color(0.788, 0.573, 0.165)

func _ready() -> void:
	manager = get_node(manager_path)
	manager.connect("ui_updated",  _on_ui_updated)
	manager.connect("log_added",   _on_log_added)
	manager.connect("game_over",   _on_game_over)
	manager.connect("grid_changed", _on_ui_updated)

	%btn_move.pressed.connect(func(): manager.set_mode(CombatManager.Mode.MOVE))
	%btn_attack.pressed.connect(func(): manager.set_mode(CombatManager.Mode.ATTACK))
	%btn_defend.pressed.connect(manager.do_defend)
	%btn_pass.pressed.connect(manager.end_player_turn)
	%btn_reset.pressed.connect(func():
		%Overlay.visible = false
		manager.reset_game())
	%btn_replay.pressed.connect(func():
		%Overlay.visible = false
		manager.reset_game())

	%Overlay.visible = false
	_on_ui_updated()

# ── Mise à jour du panneau joueur ────────────────────────────
func _on_ui_updated() -> void:
	var p := manager.player

	# HP
	%lbl_hp.text = "%d / %d" % [maxi(0, p.hp), p.max_hp]
	%bar_hp.value = float(maxi(0, p.hp)) / float(p.max_hp) * 100.0

	# AP
	%lbl_ap.text = "%d / %d" % [p.ap, p.max_ap]
	%bar_ap.value = float(p.ap) / float(p.max_ap) * 100.0

	# Stats
	%lbl_str.text = "Force : %d" % p.str
	%lbl_agi.text = "Agilité : %d" % p.agi

	# Tour
	%lbl_turn.text = str(manager.turn_count)
	%lbl_who.text  = "ENNEMIS" if manager.phase == CombatManager.Phase.ENEMY else "JOUEUR"

	# Résumé
	%lbl_kills.text = "Kills : %d"             % manager.stat_kills
	%lbl_dmg.text   = "Dégâts infligés : %d"   % manager.stat_dmg
	%lbl_rec.text   = "Dégâts reçus : %d"      % manager.stat_rec

	# Phase dots
	_set_phase_active(%ph_move,   manager.phase == CombatManager.Phase.PLAYER
								 and manager.mode  == CombatManager.Mode.MOVE)
	_set_phase_active(%ph_attack, manager.phase == CombatManager.Phase.PLAYER
								 and manager.mode  == CombatManager.Mode.ATTACK)
	_set_phase_active(%ph_enemy,  manager.phase == CombatManager.Phase.ENEMY)

	# Boutons actifs / inactifs
	%btn_move.disabled   = (manager.phase != CombatManager.Phase.PLAYER)
	%btn_attack.disabled = (manager.phase != CombatManager.Phase.PLAYER)
	%btn_defend.disabled = (manager.phase != CombatManager.Phase.PLAYER)
	%btn_pass.disabled   = (manager.phase != CombatManager.Phase.PLAYER)
	_set_btn_active(%btn_move,   manager.mode == CombatManager.Mode.MOVE)
	_set_btn_active(%btn_attack, manager.mode == CombatManager.Mode.ATTACK)

	# Liste des ennemis
	for child in %enemy_list.get_children():
		child.queue_free()
	for e in manager.get_enemies():
		var row := HBoxContainer.new()
		var icon := Label.new()
		icon.text = "💀" if "Squelette" in e.entity_name else "🐀"
		icon.add_theme_font_size_override("font_size", 16)
		row.add_child(icon)

		var info := VBoxContainer.new()
		info.size_flags_horizontal = Control.SIZE_EXPAND_FILL

		var name_lbl := Label.new()
		name_lbl.text = e.entity_name + ("  ☠" if not e.alive else "")
		name_lbl.add_theme_font_size_override("font_size", 10)
		info.add_child(name_lbl)

		var hp_bar := ProgressBar.new()
		hp_bar.value = float(maxi(0, e.hp)) / float(e.max_hp) * 100.0
		hp_bar.show_percentage = false
		hp_bar.custom_minimum_size.y = 5
		info.add_child(hp_bar)

		var stat_lbl := Label.new()
		stat_lbl.text = "PV %d/%d · Ag %d" % [maxi(0,e.hp), e.max_hp, e.agi]
		stat_lbl.add_theme_font_size_override("font_size", 8)
		info.add_child(stat_lbl)

		row.add_child(info)
		row.modulate.a = 1.0 if e.alive else 0.4
		%enemy_list.add_child(row)

# ── Log ───────────────────────────────────────────────────────
func _on_log_added(msg: String, category: String) -> void:
	var color : Color
	match category:
		"hit":   color = C_LOG_HIT
		"kill":  color = C_LOG_KILL
		"move":  color = C_LOG_MOVE
		"turn":  color = C_LOG_TURN
		_:       color = C_LOG_DEFAULT

	%log_box.push_color(color)
	%log_box.add_text(msg + "\n")
	%log_box.pop()
	# Scroll vers le bas
	await get_tree().process_frame
	%log_box.scroll_to_line(%log_box.get_line_count() - 1)

# ── Game Over ─────────────────────────────────────────────────
func _on_game_over(victory: bool, message: String) -> void:
	%overlay_title.text = "⚔ VICTOIRE" if victory else "☠ DÉFAITE"
	%overlay_msg.text   = message
	%Overlay.visible    = true

# ── Utilitaires UI ───────────────────────────────────────────
func _set_phase_active(panel: Panel, active: bool) -> void:
	var style := StyleBoxFlat.new()
	if active:
		style.bg_color     = Color(0.788, 0.573, 0.165, 0.25)
		style.border_color = Color(0.788, 0.573, 0.165)
	else:
		style.bg_color     = Color(0, 0, 0, 0)
		style.border_color = Color(0.788, 0.573, 0.165, 0.2)
	style.set_border_width_all(1)
	panel.add_theme_stylebox_override("panel", style)

func _set_btn_active(btn: Button, active: bool) -> void:
	btn.modulate = Color(1.0, 0.88, 0.55) if active else Color(1, 1, 1)
