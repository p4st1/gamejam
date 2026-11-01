extends SceneTree
## Автотест модульного набора «Больница» в демо-сцене.
## Запуск: godot --headless --path . --script res://tests/test_hospital_kit.gd

const DEMO := preload("res://scenes/levels/prototype/hospital_kit_demo.tscn")

var _failures := 0
var _player: Player


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var level := DEMO.instantiate()
	root.add_child(level)
	_player = level.get_node("Player")

	await _wait(0.5)
	_check(_player.is_on_floor(), "игрок стоит на полу коридора")

	# Материалы: скрипт импорта подставил общие материалы библиотеки с текстурами.
	var wall_mesh := _first_mesh(level.get_node("Walls/Wall4"))
	var paint := wall_mesh.mesh.surface_get_material(0) as StandardMaterial3D if wall_mesh else null
	_check(paint != null and paint.resource_path.begins_with("res://assets/materials/hospital/")
		and paint.albedo_texture != null and paint.normal_texture != null,
		"у стены общий материал с текстурами (%s)" % (paint.resource_path if paint else "нет"))
	_check(level.get_node_or_null("Walls/Corner0") != null, "угловые колонны на месте")

	# Стена держит: идём в глухую стену коридора — игрок остаётся в коридоре.
	await _teleport(Vector3(0, 0.05, 0), 0.0)
	await _walk(1.5)
	_check(_player.global_position.z > -1.4, "глухая стена не пропускает (z %.2f)" % _player.global_position.z)

	# Дверной проём: из коридора в палату.
	await _teleport(Vector3(3, 0.05, 0), 0.0)
	await _walk(1.5)
	_check(_player.global_position.z < -2.0, "прошёл в палату через дверь (z %.2f)" % _player.global_position.z)

	# Первый марш: подъём на промежуточную площадку (+1,65 м).
	await _teleport(Vector3(11.0, 0.05, 0.7), -90.0)
	await _walk(3.5)
	_check(_player.global_position.y > 1.55,
		"поднялся по первому маршу (высота %.2f)" % _player.global_position.y)

	# Второй марш: с площадки на второй этаж (+3,3 м).
	await _teleport(Vector3(15.6, 1.7, -0.7), 90.0)
	await _walk(3.5)
	_check(_player.global_position.y > 3.2,
		"поднялся на второй этаж (высота %.2f)" % _player.global_position.y)

	print("\nИТОГ: %s" % ("все проверки пройдены" if _failures == 0 else "провалено: %d" % _failures))
	quit(_failures)


## yaw_degrees: 0 — смотрит в −Z, −90 — в +X, 90 — в −X.
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


func _first_mesh(node: Node) -> MeshInstance3D:
	if node is MeshInstance3D:
		return node
	for child in node.get_children():
		var found := _first_mesh(child)
		if found:
			return found
	return null


func _wait(seconds: float) -> void:
	await create_timer(seconds, true, true).timeout


func _check(condition: bool, description: String) -> void:
	print(("  OK   " if condition else "  FAIL ") + description)
	if not condition:
		_failures += 1
