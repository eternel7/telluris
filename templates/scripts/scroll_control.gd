extends ScrollContainer

var dragging = false

func _gui_input(event):
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			dragging = event.pressed
			
	if event is InputEventMouseMotion and dragging:
		# On soustrait le mouvement de la souris à la position actuelle du scroll
		scroll_horizontal -= event.relative.x
		scroll_vertical -= event.relative.y
