extends SceneTree
## Автотест служебного блока набора «Больница»: шлюз, рампа, приёмка, подвал, склад.
## Запуск: godot --headless --path . --script res://tests/test_hospital_service.gd

const DEMO := preload("res://scenes/blockouts/hospital_service_blockout.tscn")

var _failures := 0
var _player: Player


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var level := DEMO.instantiate()
	root.add_child(level)
	_player = level.get_node("Player")

	await _wait(0.5)
	_check(_player.is_on_floor(), "игрок стоит на полу шлюза")
	_check(_has_material(level.get_node("Airlock/WallN0"), "wall_tile"), "в шлюзе кафель из общей библиотеки")
	_check(_has_material(level.get_node("Receiving/WallS1"), "brick"), "у приёмки снаружи кирпич")

	# Шлюз → приёмка через открытую дверь в «красную» зону.
	await _teleport(Vector3(-3.0, 0.05, 0.0), -90.0)
	await _walk(2.0)
	_check(_player.global_position.x > -0.5, "прошёл из шлюза в приёмку (x %.2f)" % _player.global_position.x)

	# Двор → рампа по ступеням.
	await _teleport(Vector3(10.0, -1.05, 3.1), 90.0)
	await _walk(2.0)
	_check(_player.global_position.y > -0.1, "поднялся со двора на рампу (высота %.2f)" % _player.global_position.y)

	# Рампа → приёмка через ворота.
	await _teleport(Vector3(0.0, 0.05, 3.2), 0.0)
	await _walk(2.0)
	_check(_player.global_position.z < 1.0, "вошёл в ворота (z %.2f)" % _player.global_position.z)

	# Ограждение у проёма лестницы держит.
	await _teleport(Vector3(9.0, 0.05, -1.0), 180.0)
	await _walk(2.0)
	_check(_player.global_position.y > -0.1 and _player.global_position.z < 0.0,
		"ограждение у проёма держит (z %.2f, высота %.2f)" % [_player.global_position.z, _player.global_position.y])

	# Спуск в подвал по двум маршам.
	await _teleport(Vector3(3.8, 0.05, 0.75), -90.0)
	await _walk(4.5)
	_check(_player.global_position.y < -3.0, "спустился в подвал (высота %.2f)" % _player.global_position.y)

	# Подвальный коридор → аптечный склад через металлическую дверь.
	await _teleport(Vector3(9.0, -3.25, -0.2), 0.0)
	await _walk(2.0)
	_check(_player.global_position.z < -2.0, "вошёл на склад (z %.2f)" % _player.global_position.z)

	print("\nИТОГ: %s" % ("все проверки пройдены" if _failures == 0 else "провалено: %d" % _failures))
	quit(_failures)


## Есть ли у модели поверхность с материалом library_name из общей библиотеки (с текстурой).
func _has_material(node: Node, library_name: String) -> bool:
	if node is MeshInstance3D and node.mesh:
		for i in node.mesh.get_surface_count():
			var material := node.mesh.surface_get_material(i) as StandardMaterial3D
			if material and material.resource_path.ends_with("/%s.tres" % library_name) \
					and material.albedo_texture:
				return true
	for child in node.get_children():
		if _has_material(child, library_name):
			return true
	return false


## yaw_degrees: 0 — смотрит в −Z, 180 — в +Z, −90 — в +X, 90 — в −X.
func _teleport(pos: Vector3, yaw_degrees: float) -> void:
	_player.global_position = pos
	_player.velocity = Vector3.ZERO
	_player.rotation = Vector3(0, deg_to_rad(yaw_degrees), 0)
	await physics_frame
	await _wait(0.3)


func _walk(seconds: float) -> void:
	Input.action_press("move_forward")
	await _wait(seconds)
	Input.action_release("move_forward")
	await _wait(0.3)


func _wait(seconds: float) -> void:
	await create_timer(seconds, true, true).timeout


func _check(condition: bool, description: String) -> void:
	print(("  OK   " if condition else "  FAIL ") + description)
	if not condition:
		_failures += 1
