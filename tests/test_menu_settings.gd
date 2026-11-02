extends SceneTree
## Автотест меню и настроек v0.1.
## Запуск: godot --headless --path . --script res://tests/test_menu_settings.gd
## Настройки создателя (user://settings.cfg) не трогает: пишет во временный файл.
## Сцены грузятся во время выполнения, класс Player не указывается как тип: тест компилируется
## раньше, чем регистрируются автозагрузки (Settings, Game).

const TEST_RANGE := "res://scenes/levels/prototype/test_range.tscn"
const MAIN_MENU := "res://scenes/ui/main_menu.tscn"
const SETTINGS_MENU := "res://scenes/ui/settings_menu.tscn"
const TEMP_PATH := "user://test_settings.cfg"

var _failures := 0
var _settings: Node
var _game: Node


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	_settings = root.get_node("Settings")
	_game = root.get_node("Game")
	_settings.save_path = TEMP_PATH
	_settings.load_settings()  # временного файла нет — значения по умолчанию

	_test_values()
	_test_bindings()
	_test_save_load()
	await _test_menus()
	await _test_pause()

	DirAccess.remove_absolute(ProjectSettings.globalize_path(TEMP_PATH))
	print("\nИТОГ: %s" % ("все проверки пройдены" if _failures == 0 else "провалено: %d" % _failures))
	# Остановить звук до выхода: иначе воспроизведения остаются в AudioServer — «утечка».
	root.propagate_call(&"stop")
	await create_timer(0.1).timeout
	quit(_failures)


func _test_values() -> void:
	_check(_settings.get_value("controls/mouse_sensitivity") == 1.0,
		"значение по умолчанию: чувствительность 1.0")

	_settings.set_value("video/quality", 0)
	_check(_settings.get_value("video/shadows") == 0 and not _settings.get_value("video/ssao"),
		"пресет «Низкое» выставляет тени и SSAO")
	_settings.set_value("video/ssao", true)
	_check(_settings.get_value("video/quality") == _settings.QUALITY_CUSTOM,
		"ручная правка переводит пресет в «Своё»")
	_settings.set_value("video/quality", 2)
	_check(_settings.get_value("video/quality") == 2, "возврат к пресету «Высокое»")
	_check(root.msaa_3d == Viewport.MSAA_2X, "сглаживание применено к окну (MSAA 2×)")

	_settings.set_value("video/render_scale", 0.75)
	_check(is_equal_approx(root.scaling_3d_scale, 0.75), "масштаб рендера применён")

	_settings.set_value("audio/music", 0.5)
	var bus := AudioServer.get_bus_index("Music")
	_check(bus >= 0 and absf(AudioServer.get_bus_volume_db(bus) - linear_to_db(0.5)) < 0.01,
		"громкость шины Music применена")
	_settings.set_value("audio/sfx", 0.0)
	_check(AudioServer.is_bus_mute(AudioServer.get_bus_index("SFX")), "громкость 0 — шина без звука")

	_settings.reset(_settings.DEFAULTS.keys())
	_check(_settings.get_value("audio/music") == 1.0 and is_equal_approx(root.scaling_3d_scale, 1.0),
		"сброс к значениям по умолчанию")


func _test_bindings() -> void:
	var j := _key(KEY_J)
	_settings.set_binding("jump", 0, j)
	_check(InputMap.action_has_event("jump", j), "переназначение: J — прыжок")
	_check(not InputMap.action_has_event("jump", _key(KEY_SPACE)), "старая клавиша прыжка снята")

	var taken: String = _settings.set_binding("interact", 0, _key(KEY_J))
	_check(taken == "Прыжок" and InputMap.action_has_event("interact", j)
		and not InputMap.action_has_event("jump", j), "конфликт: клавиша снимается с другого действия")

	var mouse := InputEventMouseButton.new()
	mouse.button_index = MOUSE_BUTTON_RIGHT
	_settings.set_binding("crouch", 1, mouse)
	_check(_settings.event_label(_settings.get_binding("crouch", 1)) == "ПКМ", "кнопка мыши в слоте")

	_settings.reset_bindings()
	_check(InputMap.action_has_event("jump", _key(KEY_SPACE))
		and InputMap.action_has_event("crouch", _key(KEY_C))
		and not InputMap.action_has_event("interact", j), "сброс клавиш по умолчанию")


func _test_save_load() -> void:
	_settings.set_value("controls/mouse_sensitivity", 1.75)
	_settings.set_value("controls/invert_y", true)
	_settings.set_binding("sprint", 0, _key(KEY_Q))
	_settings.save_settings()
	_settings.reset(_settings.DEFAULTS.keys())
	_settings.reset_bindings()

	_settings.load_settings()
	_check(is_equal_approx(_settings.get_value("controls/mouse_sensitivity"), 1.75)
		and _settings.get_value("controls/invert_y"), "настройки переживают перезапуск")
	_check(InputMap.action_has_event("sprint", _key(KEY_Q))
		and not InputMap.action_has_event("sprint", _key(KEY_SHIFT)), "клавиши переживают перезапуск")

	_settings.reset(_settings.DEFAULTS.keys())
	_settings.reset_bindings()


func _test_menus() -> void:
	var settings_menu: Control = load(SETTINGS_MENU).instantiate()
	root.add_child(settings_menu)
	var tabs: TabContainer = settings_menu.get_node("%Tabs")
	_check(tabs.get_tab_count() == 4, "экран настроек: 4 вкладки")

	# Смена пресета через виджет обновляет связанный виджет теней.
	_settings.set_value("video/quality", 0)
	var shadows: OptionButton = settings_menu._widgets["video/shadows"].control
	_check(shadows.selected == 0, "виджеты обновляются при смене пресета")
	_settings.reset(_settings.DEFAULTS.keys())
	settings_menu.queue_free()

	var groups: Dictionary = load("res://scripts/ui/main_menu.gd").find_scenes()
	_check(TEST_RANGE in groups["Уровни"], "в выборе сцены есть тестовая площадка")
	_check(groups["Наброски"].size() >= 3, "в выборе сцены есть наброски (%d)" % groups["Наброски"].size())

	_game.change_scene(MAIN_MENU)
	await _wait_for_scene(MAIN_MENU)
	_check(current_scene != null and current_scene.scene_file_path == MAIN_MENU,
		"главное меню загружается")
	_check(not _game.can_pause(), "в главном меню паузы нет")


func _test_pause() -> void:
	_game.change_scene(TEST_RANGE)
	await _wait_for_scene(TEST_RANGE)
	var player: Node = current_scene.get_node("Player")
	_settings.set_value("controls/mouse_sensitivity", 2.0)
	_check(is_equal_approx(player._look_sensitivity, player.mouse_sensitivity * 2.0),
		"смена чувствительности применяется на лету")
	_settings.reset(["controls/mouse_sensitivity"])

	_press_escape()
	await process_frame
	_check(paused and _game.pause_menu.visible, "Esc ставит игру на паузу и открывает меню")
	_press_escape()
	await process_frame
	_check(not paused and not _game.pause_menu.visible, "повторный Esc снимает паузу")

	_game.pause()
	_game.pause_menu.get_node("%Settings").pressed.emit()
	_check(_game.pause_menu.get_node("%SettingsMenu").visible, "из паузы открываются настройки")
	_press_escape()
	await process_frame
	_check(paused and not _game.pause_menu.get_node("%SettingsMenu").visible,
		"Esc в настройках возвращает в меню паузы, пауза сохраняется")
	_game.pause_menu.get_node("%MainMenu").pressed.emit()
	await _wait_for_scene(MAIN_MENU)
	_check(not paused and current_scene.scene_file_path == MAIN_MENU,
		"«В главное меню» снимает паузу и возвращает в меню")


func _press_escape() -> void:
	var event := InputEventKey.new()
	event.keycode = KEY_ESCAPE
	event.physical_keycode = KEY_ESCAPE
	event.pressed = true
	root.push_input(event)
	var release := event.duplicate()
	release.pressed = false
	root.push_input(release)


func _wait_for_scene(path: String) -> void:
	for i in 600:
		await process_frame
		if current_scene != null and current_scene.scene_file_path == path \
				and _game.can_pause() == (path != MAIN_MENU) \
				and not _game._loading_layer.visible:
			return
	_check(false, "сцена %s не загрузилась за 600 кадров" % path)


func _key(code: Key) -> InputEventKey:
	var event := InputEventKey.new()
	event.physical_keycode = code
	return event


func _check(condition: bool, description: String) -> void:
	print(("  OK   " if condition else "  FAIL ") + description)
	if not condition:
		_failures += 1
