extends SceneTree
## Автотест наброска миссии 3 (версия 2): проходимы ли маршруты, которые требует сценарий.
## Запуск: godot --headless --path . --script res://tests/test_m03_blockout.gd

## Сцены грузятся во время выполнения, а не preload, и класс Player не указывается как тип:
## тест компилируется раньше, чем регистрируются автозагрузки (Settings, Game), на которые
## ссылается игрок.
const LEVEL := "res://scenes/blockouts/m03_red_zone_blockout.tscn"

var _failures := 0
var _player  # без типа Player — см. комментарий выше


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var level: Node = load(LEVEL).instantiate()
	root.add_child(level)
	_player = level.get_node("Player")

	await _wait(0.5)
	_check(_player.is_on_floor(), "старт у ворот: игрок на асфальте")

	# Сц. 1, 8: площадь → крыльцо → двустворчатый вход → вестибюль.
	await _route(Vector3(6, -1.05, 7.5), 0.0, 3.5)
	_check(_pos().z < 0.5 and _pos().y > -0.1, "площадь → крыльцо → вестибюль %s" % _fmt())

	# Сц. 3: вестибюль → дверь в стеклянной перегородке → коридор.
	await _route(Vector3(6, 0.05, 0.3), 0.0, 1.5)
	_check(_pos().z < -2.0, "вестибюль → коридор через перегородку %s" % _fmt())

	# Сц. 1: крыльцо шлюза → шлюз → коридор.
	await _route(Vector3(-6.6, -1.05, 0), -90.0, 3.0)
	_check(_pos().x > -1.0 and _pos().y > -0.1, "двор → крыльцо → шлюз %s" % _fmt())
	await _route(Vector3(3, 0.05, 0.5), 0.0, 1.5)
	_check(_pos().z < -2.0, "шлюз → коридор %s" % _fmt())

	# Сц. 2: лестница вниз → подвал → склад, кислород.
	await _route(Vector3(11.2, 0.05, -0.7), -90.0, 2.5)
	_check(_pos().y < -1.5, "первый марш вниз %s" % _fmt())
	await _route(Vector3(16.0, -1.6, 0.7), 90.0, 2.5)
	_check(_pos().y < -3.1, "второй марш вниз, подвал %s" % _fmt())
	await _route(Vector3(11.9, -3.25, -0.6), 0.0, 2.5)
	_check(_pos().z < -5.0, "лестница → коридор подвала → склад %s" % _fmt())
	await _route(Vector3(18, -3.25, -3), 180.0, 1.5)
	_check(_pos().z > -0.5, "коридор → кислород %s" % _fmt())

	# Сц. 6: петля через склад, приёмку и грузовой спуск во двор.
	await _route(Vector3(18, -3.25, -2.6), 0.0, 2.0)
	_check(_pos().z < -5.0, "коридор → склад (вторая дверь петли) %s" % _fmt())
	await _route(Vector3(6, -3.25, -5.0), 0.0, 3.5)
	_check(_pos().z < -13.5, "приёмка → ворота → приямок у «буханки» %s" % _fmt())
	await _route(Vector3(6, -3.0, -14.0), 0.0, 5.0)
	_check(_pos().z < -25.0 and _pos().y > -1.3, "грузовой спуск → задний двор %s" % _fmt())

	# Сц. 2–3: лестница вверх → 2 этаж → весь коридор с баллоном → палата 214.
	await _route(Vector3(11.2, 0.05, 0.7), -90.0, 2.5)
	_check(_pos().y > 1.5, "первый марш вверх %s" % _fmt())
	await _route(Vector3(16.0, 1.7, -0.7), 90.0, 2.5)
	_check(_pos().y > 3.2, "второй марш вверх, 2 этаж %s" % _fmt())
	await _route(Vector3(12.0, 3.35, -0.5), 0.0, 1.5)
	_check(_pos().z < -2.0 and _pos().y > 3.2, "площадка → коридор 2 этажа %s" % _fmt())
	await _route(Vector3(12.5, 3.35, -3.0), -90.0, 6.5)
	_check(_pos().x > 29.0, "весь коридор 2 этажа без помех (маршрут с баллоном) %s" % _fmt())
	await _route(Vector3(30, 3.35, -3), 180.0, 1.5)
	_check(_pos().z > -1.0, "коридор → палата 214 %s" % _fmt())
	await _route(Vector3(11.3, 3.35, 0.7), -90.0, 1.5)
	_check(_pos().x < 12.0 and _pos().y > 3.2, "ограждение площадки 2 этажа держит %s" % _fmt())

	# Сц. 6, 10: коридор → прачечная → задний двор.
	await _route(Vector3(27, 0.05, -3), 0.0, 4.5)
	_check(_pos().z < -11.0 and _pos().y < -0.5, "коридор → прачечная → крыльцо → двор %s" % _fmt())

	# Сц. 10: боковой проезд → крыльцо → коридор.
	await _route(Vector3(36.6, -1.05, -4.5), 90.0, 1.5)
	_check(_pos().y > -0.1, "проезд → боковое крыльцо %s" % _fmt())
	await _route(Vector3(33.1, 0.05, -3), 90.0, 1.5)
	_check(_pos().x < 31.0, "боковое крыльцо → коридор %s" % _fmt())

	print("\nИТОГ: %s" % ("все проверки пройдены" if _failures == 0 else "провалено: %d" % _failures))
	# Остановить звук до выхода: иначе воспроизведения остаются в AudioServer — «утечка».
	root.propagate_call(&"stop")
	await create_timer(0.1).timeout
	quit(_failures)


## Ставит игрока в точку, поворачивает (0 — смотрит в −Z, 180 — в +Z, −90 — в +X, 90 — в −X)
## и ведёт вперёд seconds секунд.
func _route(start: Vector3, yaw_degrees: float, seconds: float) -> void:
	_player.global_position = start
	_player.velocity = Vector3.ZERO
	_player.rotation = Vector3(0, deg_to_rad(yaw_degrees), 0)
	await physics_frame
	await _wait(0.3)
	Input.action_press("move_forward")
	await _wait(seconds)
	Input.action_release("move_forward")
	await _wait(0.3)


func _pos() -> Vector3:
	return _player.global_position


func _fmt() -> String:
	return "(%.1f, %.1f, %.1f)" % [_pos().x, _pos().y, _pos().z]


func _wait(seconds: float) -> void:
	await create_timer(seconds, true, true).timeout


func _check(condition: bool, description: String) -> void:
	print(("  OK   " if condition else "  FAIL ") + description)
	if not condition:
		_failures += 1
