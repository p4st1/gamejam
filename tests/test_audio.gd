extends SceneTree
## Автотест звука v0.1: ассеты, тип поверхности, шаги, звуковые зоны, звуки меню.
## Запуск: godot --headless --path . --script res://tests/test_audio.gd
## Сцены грузятся во время выполнения, а не preload, и класс Player не указывается как тип:
## тест компилируется раньше, чем регистрируются автозагрузки (Settings, Game, AudioDirector).

const TEST_RANGE := "res://scenes/levels/prototype/test_range.tscn"
const M03 := "res://scenes/blockouts/m03_red_zone_blockout.tscn"
const KIT := "res://assets/models/kits/hospital/"
const AUDIO := "res://assets/audio/"

var _failures := 0
var _director: Node
var _player
var _steps := []


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	_director = root.get_node("AudioDirector")
	_test_assets()
	_test_surfaces()
	await _test_footsteps()
	await _test_zones()
	_test_ui()
	print("\nИТОГ: %s" % ("все проверки пройдены" if _failures == 0 else "провалено: %d" % _failures))
	# Остановить звук до выхода: иначе воспроизведения остаются в AudioServer — «утечка».
	root.propagate_call(&"stop")
	await create_timer(0.1).timeout
	quit(_failures)


func _test_assets() -> void:
	var complete := true
	for surface in SurfaceType.ALL:
		var stream := load(AUDIO + "sfx/footsteps/%s.tres" % surface) as AudioStreamRandomizer
		complete = complete and stream != null and stream.streams_count == 5
	_check(complete, "шаги: 6 поверхностей по 5 вариантов")
	for body in ["jump", "land"]:
		var stream := load(AUDIO + "sfx/body/%s.tres" % body) as AudioStreamRandomizer
		_check(stream != null and stream.streams_count == 5, "звуки тела: %s" % body)
	for ambience in ["outdoor_wind", "indoor_hum", "basement"]:
		var wav := load(AUDIO + "ambience/%s.wav" % ambience) as AudioStreamWAV
		_check(wav != null and wav.loop_mode != AudioStreamWAV.LOOP_DISABLED,
			"фон %s зациклен" % ambience)
	for bus in ["SFX", "Ambience", "ReverbRoom", "ReverbHall", "ReverbBasement"]:
		_check(AudioServer.get_bus_index(bus) >= 0, "шина %s есть" % bus)


func _test_surfaces() -> void:
	for pair in [["hosp_floor", &"tile"], ["hosp_floor_concrete", &"concrete"],
			["ext_ground_asphalt", &"asphalt"], ["ext_ground_dirt", &"dirt"],
			["hosp_stairs_flight", &"concrete"]]:
		var model: Node = load(KIT + pair[0] + ".glb").instantiate()
		root.add_child(model)
		var bodies := model.find_children("*", "StaticBody3D", true, false)
		var surface: StringName = SurfaceType.of(bodies[0]) if not bodies.is_empty() else &""
		_check(surface == pair[1], "поверхность %s → %s (факт %s)" % [pair[0], pair[1], surface])
		model.free()

	var marked: Node = load(KIT + "hosp_floor.glb").instantiate()
	marked.set_meta(&"surface", "metal")
	root.add_child(marked)
	var body: Node = marked.find_children("*", "StaticBody3D", true, false)[0]
	_check(SurfaceType.of(body) == &"metal", "метаданные surface важнее материала")
	marked.free()


func _test_footsteps() -> void:
	var level: Node = load(TEST_RANGE).instantiate()
	root.add_child(level)
	_player = level.get_node("Player")
	var footsteps: Node = _player.get_node("Footsteps")
	footsteps.stepped.connect(func(surface: StringName, volume_db: float) -> void:
		_steps.append([surface, volume_db]))
	await _wait(0.5)

	_steps.clear()
	await _walk("move_back", 2.0)
	_check(_steps.size() >= 3, "шаги при ходьбе (%d за 2 с)" % _steps.size())
	_check(_steps.all(func(s: Array) -> bool: return s[0] == &"concrete" and s[1] == 0.0),
		"шаг по полу площадки — бетон, обычная громкость")

	_steps.clear()
	Input.action_press("crouch")
	await _wait(0.3)
	await _walk("move_back", 2.0)
	Input.action_release("crouch")
	await _wait(0.5)
	_check(not _steps.is_empty() and _steps.all(func(s: Array) -> bool: return s[1] < -5.0),
		"в приседе шаги тише")

	_teleport(Vector3(0, 0.05, 20))
	await _wait(0.3)
	_steps.clear()
	Input.action_press("sprint")
	await _walk("move_forward", 1.5)
	Input.action_release("sprint")
	_check(_steps.any(func(s: Array) -> bool: return s[1] > 0.0), "на бегу шаги громче")

	await _wait(0.5)
	Input.action_press("jump")
	await _wait(0.1)
	Input.action_release("jump")
	var body: AudioStreamPlayer3D = footsteps.get_node("Body")
	_check(body.stream != null and body.stream.resource_path.ends_with("jump.tres"), "прыжок озвучен")

	await _wait(1.0)
	_steps.clear()
	_teleport(Vector3(0, 3.5, 20))
	await _wait(1.5)
	_check(not _steps.is_empty() and body.stream.resource_path.ends_with("land.tres"),
		"приземление с высоты озвучено")
	level.free()


func _test_zones() -> void:
	var level: Node = load(M03).instantiate()
	root.add_child(level)
	_player = level.get_node("Player")
	await _wait(0.5)
	_check(_zone() == "Territory" and _ambience().ends_with("outdoor_wind.wav"),
		"на улице — зона Territory, ветер (факт %s)" % _zone())

	_teleport(Vector3(4.5, 0.05, -3))
	await _wait(0.4)
	var surface: StringName = _player.get_node("Footsteps").current_surface
	_check(_zone() == "Floor1" and _ambience().ends_with("indoor_hum.wav"),
		"коридор 1 этажа — Floor1, гул (факт %s)" % _zone())
	_check(surface == &"tile", "в коридоре 1 этажа — кафель (факт %s)" % surface)

	var player_before: AudioStreamPlayer = _director._ambience[_director._active]
	_teleport(Vector3(15.7, 1.7, 0))
	await _wait(0.4)
	_check(_zone() == "Stairwell", "лестничная площадка — Stairwell (факт %s)" % _zone())
	_check(_director._ambience[_director._active] == player_before,
		"тот же фон на лестнице не перезапускается")

	_teleport(Vector3(18, -3.25, -3))
	await _wait(0.4)
	surface = _player.get_node("Footsteps").current_surface
	_check(_zone() == "Basement" and _ambience().ends_with("basement.wav"),
		"коридор подвала — Basement (факт %s)" % _zone())
	_check(surface == &"concrete", "в подвале — бетон (факт %s)" % surface)

	_teleport(Vector3(24, 3.35, -3))
	await _wait(0.4)
	_check(_zone() == "Floor2", "коридор 2 этажа — Floor2 (факт %s)" % _zone())

	var zone: Area3D = level.get_node("AudioZones/Basement")
	_check(zone.reverb_bus_enabled and zone.reverb_bus_name == &"ReverbBasement",
		"у подвала своя реверберация")

	level.free()
	_check(_director.current_zone() == null, "после выгрузки уровня зон нет")


func _test_ui() -> void:
	var button := Button.new()
	root.add_child(button)
	button.pressed.emit()
	_check(_director._ui.stream == _director.UI_CLICK, "нажатие кнопки озвучено")
	button.free()


func _zone() -> String:
	var zone: Node = _director.current_zone()
	return zone.name if zone else "—"


func _ambience() -> String:
	var stream: AudioStream = _director.current_ambience()
	return stream.resource_path if stream else ""


func _walk(action: String, seconds: float) -> void:
	Input.action_press(action)
	await _wait(seconds)
	Input.action_release(action)


func _teleport(pos: Vector3) -> void:
	_player.global_position = pos
	_player.velocity = Vector3.ZERO
	_player.rotation = Vector3.ZERO


func _wait(seconds: float) -> void:
	await create_timer(seconds, true, true).timeout


func _check(condition: bool, description: String) -> void:
	print(("  OK   " if condition else "  FAIL ") + description)
	if not condition:
		_failures += 1
