extends Label
## Отладочный оверлей прототипа: скорость и состояние игрока. F3 — показать/скрыть.

@export var player: Player


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo \
			and event.physical_keycode == KEY_F3:
		visible = not visible


func _process(_delta: float) -> void:
	if not visible or player == null:
		return
	var state := "присед" if player.is_crouching else ("бег" if player.is_sprinting else "шаг")
	if not player.is_on_floor():
		state = "в воздухе"
	var footsteps = player.get_node_or_null("Footsteps")
	var surface: String = footsteps.current_surface if footsteps else "—"
	var zone: Node = AudioDirector.current_zone()
	text = "FPS %d\nСкорость %.1f м/с\nСостояние: %s\nПоверхность: %s · зона: %s\n\nWASD — ходьба, Shift — бег, Ctrl/C — присед,\nПробел — прыжок, Esc — пауза, F3 — скрыть" \
		% [Engine.get_frames_per_second(), player.get_horizontal_speed(), state, surface,
			zone.name if zone else "—"]
