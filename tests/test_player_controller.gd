extends SceneTree
## Автотест контроллера игрока на тестовой площадке.
## Запуск: godot --headless --path . --script res://tests/test_player_controller.gd

## Сцены грузятся во время выполнения, а не preload, и класс Player не указывается как тип:
## тест компилируется раньше, чем регистрируются автозагрузки (Settings, Game), на которые
## ссылается игрок.
const TEST_RANGE := "res://scenes/levels/prototype/test_range.tscn"

var _failures := 0
var _player  # без типа Player — см. комментарий выше


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var level: Node = load(TEST_RANGE).instantiate()
	root.add_child(level)
	_player = level.get_node("Player")

	await _wait(0.5)
	_check(_player.is_on_floor(), "игрок стоит на полу после спавна")

	# Ходьба: скорость выходит на walk_speed.
	Input.action_press("move_back")
	await _wait(1.0)
	_check(absf(_player.get_horizontal_speed() - _player.walk_speed) < 0.2,
		"скорость шага ≈ %.1f (факт %.2f)" % [_player.walk_speed, _player.get_horizontal_speed()])
	Input.action_release("move_back")
	await _wait(1.0)
	_check(_player.get_horizontal_speed() < 0.05, "игрок останавливается без ввода")

	# Лестница: подъём на площадку высотой 1,6 м.
	_teleport(Vector3(0, 0.05, 4))
	Input.action_press("move_forward")
	await _wait(3.5)
	Input.action_release("move_forward")
	await _wait(0.3)
	_check(_player.global_position.y > 1.5,
		"поднялся по лестнице (высота %.2f)" % _player.global_position.y)

	# Тоннель: в приседе заходим, отпускаем присед — встать нельзя.
	_teleport(Vector3(6, 0.05, 4))
	Input.action_press("crouch")
	await _wait(0.5)
	Input.action_press("move_forward")
	await _wait(2.0)
	Input.action_release("move_forward")
	Input.action_release("crouch")
	await _wait(0.5)
	_check(_player.is_crouching, "под низким потолком игрок остаётся в приседе")
	Input.action_press("move_forward")
	await _wait(3.0)
	Input.action_release("move_forward")
	await _wait(0.5)
	_check(not _player.is_crouching, "выйдя из тоннеля, игрок встаёт")

	# Бег — быстрее шага.
	_teleport(Vector3(0, 0.05, 20))
	Input.action_press("move_forward")
	Input.action_press("sprint")
	await _wait(1.0)
	_check(_player.get_horizontal_speed() > _player.walk_speed + 1.0,
		"бег быстрее шага (факт %.2f)" % _player.get_horizontal_speed())
	Input.action_release("sprint")
	Input.action_release("move_forward")

	# Инерция бега: после остановки с бега игрок проскальзывает вперёд, с шага — почти нет.
	var slide: float = await _stop_distance()
	_check(slide > 1.2 and slide < 2.2, "остановка с бега — проскальзывание %.2f м" % slide)
	_teleport(Vector3(0, 0.05, 20))
	Input.action_press("move_forward")
	await _wait(1.0)
	Input.action_release("move_forward")
	var step_stop: float = await _stop_distance()
	_check(step_stop < 0.35, "остановка с шага — %.2f м" % step_stop)

	# Стрейф влево → вправо: скорость шага в новую сторону набирается быстро.
	_teleport(Vector3(0, 0.05, 20))
	Input.action_press("move_left")
	await _wait(1.0)
	Input.action_release("move_left")
	Input.action_press("move_right")
	var reversal := 0.0
	while _player.velocity.x < _player.walk_speed * 0.95 and reversal < 2.0:
		await physics_frame
		reversal += 1.0 / Engine.physics_ticks_per_second
	Input.action_release("move_right")
	_check(reversal <= 0.3, "стрейф туда-обратно — %.2f с" % reversal)
	await _wait(0.5)

	print("\nИТОГ: %s" % ("все проверки пройдены" if _failures == 0 else "провалено: %d" % _failures))
	# Остановить звук до выхода: иначе воспроизведения остаются в AudioServer — «утечка».
	root.propagate_call(&"stop")
	await create_timer(0.1).timeout
	quit(_failures)


func _teleport(pos: Vector3) -> void:
	_player.global_position = pos
	_player.velocity = Vector3.ZERO
	_player.rotation = Vector3.ZERO
	await physics_frame


## Путь по горизонтали (м) от текущей точки до полной остановки.
func _stop_distance() -> float:
	var start: Vector3 = _player.global_position
	var frames := 0
	while _player.get_horizontal_speed() > 0.01 and frames < 300:
		await physics_frame
		frames += 1
	var path: Vector3 = _player.global_position - start
	return Vector2(path.x, path.z).length()


func _wait(seconds: float) -> void:
	await create_timer(seconds, true, true).timeout


func _check(condition: bool, description: String) -> void:
	print(("  OK   " if condition else "  FAIL ") + description)
	if not condition:
		_failures += 1
