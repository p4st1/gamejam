extends Node
## Настройки игры: хранение, применение к движку, сохранение в user://settings.cfg.
## Техописание — docs/TECHNICAL_DESIGN.md, «Меню и настройки v0.1».
## Игровые системы читают значения через get_value() и подписываются на changed.

signal changed(key: String)

const SAVE_PATH := "user://settings.cfg"

const QUALITY_CUSTOM := 3
## Значения настроек, которые задаёт пресет качества (низкое, среднее, высокое).
const QUALITY_PRESETS := [
	{"video/shadows": 0, "video/antialiasing": 1, "video/ssao": false},
	{"video/shadows": 1, "video/antialiasing": 1, "video/ssao": true},
	{"video/shadows": 2, "video/antialiasing": 3, "video/ssao": true},
]

const DEFAULTS := {
	"video/window_mode": 0,
	"video/vsync": true,
	"video/max_fps": 0,
	"video/render_scale": 1.0,
	"video/quality": 2,
	"video/shadows": 2,
	"video/antialiasing": 3,
	"video/ssao": true,
	"audio/master": 1.0,
	"audio/music": 1.0,
	"audio/sfx": 1.0,
	"audio/voice": 1.0,
	"controls/mouse_sensitivity": 1.0,
	"controls/invert_y": false,
}

const AUDIO_BUSES := {
	"audio/master": "Master",
	"audio/music": "Music",
	"audio/sfx": "SFX",
	"audio/voice": "Voice",
}

## Действия, которые можно переназначить, и их названия в меню (порядок — порядок в меню).
const REBINDABLE_ACTIONS := {
	"move_forward": "Вперёд",
	"move_back": "Назад",
	"move_left": "Влево",
	"move_right": "Вправо",
	"sprint": "Бег",
	"crouch": "Присесть",
	"jump": "Прыжок",
	"interact": "Использовать",
}
const BINDING_SLOTS := 2

const _WINDOW_MODES := [
	DisplayServer.WINDOW_MODE_WINDOWED,
	DisplayServer.WINDOW_MODE_FULLSCREEN,
	DisplayServer.WINDOW_MODE_EXCLUSIVE_FULLSCREEN,
]
## Тени по уровню качества: размер атласов и мягкость.
const _SHADOW_LEVELS := [
	{"directional": 2048, "positional": 1024, "filter": RenderingServer.SHADOW_QUALITY_HARD},
	{"directional": 4096, "positional": 2048, "filter": RenderingServer.SHADOW_QUALITY_SOFT_LOW},
	{"directional": 4096, "positional": 4096, "filter": RenderingServer.SHADOW_QUALITY_SOFT_MEDIUM},
]
const _KEY_NAMES := {
	"Space": "Пробел", "Shift": "Shift", "Ctrl": "Ctrl", "Alt": "Alt", "Tab": "Tab",
	"Enter": "Enter", "Backspace": "Backspace", "Escape": "Esc", "CapsLock": "Caps Lock",
	"Up": "Стрелка вверх", "Down": "Стрелка вниз", "Left": "Стрелка влево", "Right": "Стрелка вправо",
}
const _MOUSE_NAMES := {
	MOUSE_BUTTON_LEFT: "ЛКМ", MOUSE_BUTTON_RIGHT: "ПКМ", MOUSE_BUTTON_MIDDLE: "СКМ",
	MOUSE_BUTTON_WHEEL_UP: "Колесо вверх", MOUSE_BUTTON_WHEEL_DOWN: "Колесо вниз",
	MOUSE_BUTTON_XBUTTON1: "Мышь 4", MOUSE_BUTTON_XBUTTON2: "Мышь 5",
}

## Путь файла настроек; автотест подменяет его, чтобы не трогать настройки создателя.
var save_path := SAVE_PATH

var _values := {}
## action -> Array из BINDING_SLOTS событий (null — пустой слот).
var _bindings := {}
var _default_bindings := {}


func _ready() -> void:
	process_mode = PROCESS_MODE_ALWAYS
	for action: String in REBINDABLE_ACTIONS:
		_default_bindings[action] = _pad_slots(InputMap.action_get_events(action))
	get_tree().node_added.connect(_on_node_added)
	load_settings()


func get_value(key: String) -> Variant:
	return _values.get(key, DEFAULTS[key])


func set_value(key: String, value: Variant) -> void:
	assert(DEFAULTS.has(key), "Неизвестная настройка: %s" % key)
	value = type_convert(value, typeof(DEFAULTS[key]))
	if key == "video/quality":
		if value == QUALITY_CUSTOM:
			return
		for preset_key: String in QUALITY_PRESETS[value]:
			_store(preset_key, QUALITY_PRESETS[value][preset_key])
	_store(key, value)
	if QUALITY_PRESETS[0].has(key):
		_store("video/quality", _matching_preset())


## Сбросить перечисленные настройки к значениям по умолчанию.
func reset(keys: Array) -> void:
	for key: String in keys:
		set_value(key, DEFAULTS[key])


func load_settings() -> void:
	_values.clear()
	for action: String in REBINDABLE_ACTIONS:
		_bindings[action] = _default_bindings[action].duplicate()

	var config := ConfigFile.new()
	if config.load(save_path) == OK:
		for key: String in DEFAULTS:
			var parts := key.split("/")
			var value: Variant = config.get_value(parts[0], parts[1], DEFAULTS[key])
			if typeof(value) in [TYPE_INT, TYPE_FLOAT, TYPE_BOOL]:
				_values[key] = type_convert(value, typeof(DEFAULTS[key]))
		for action: String in REBINDABLE_ACTIONS:
			if config.has_section_key("input", action):
				var codes: Array = config.get_value("input", action)
				var events := []
				for code: Variant in codes:
					events.append(_decode_event(str(code)))
				_bindings[action] = _pad_slots(events)

	for key: String in DEFAULTS:
		_apply(key)
	for action: String in REBINDABLE_ACTIONS:
		_apply_binding(action)


func save_settings() -> void:
	var config := ConfigFile.new()
	for key: String in DEFAULTS:
		var parts := key.split("/")
		config.set_value(parts[0], parts[1], get_value(key))
	for action: String in REBINDABLE_ACTIONS:
		var codes := PackedStringArray()
		for event: InputEvent in _bindings[action]:
			codes.append(_encode_event(event))
		config.set_value("input", action, codes)
	var error := config.save(save_path)
	if error != OK:
		push_error("Не удалось сохранить настройки в %s: %s" % [save_path, error_string(error)])


# --- Клавиши ---

func get_binding(action: String, slot: int) -> InputEvent:
	return _bindings[action][slot]


## Назначить событие (или null — очистить слот). Если клавиша была занята другим действием,
## она снимается оттуда; возвращается название того действия (или пустая строка).
func set_binding(action: String, slot: int, event: InputEvent) -> String:
	var taken_from := ""
	if event != null:
		for other: String in _bindings:
			for other_slot in BINDING_SLOTS:
				var existing: InputEvent = _bindings[other][other_slot]
				if (other != action or other_slot != slot) and _same_input(existing, event):
					_bindings[other][other_slot] = null
					_apply_binding(other)
					if other != action:
						taken_from = REBINDABLE_ACTIONS[other]
					changed.emit("input/" + other)
	_bindings[action][slot] = event
	_apply_binding(action)
	changed.emit("input/" + action)
	return taken_from


func reset_bindings() -> void:
	for action: String in REBINDABLE_ACTIONS:
		_bindings[action] = _default_bindings[action].duplicate()
		_apply_binding(action)
		changed.emit("input/" + action)


## Чистое событие для назначения: без модификаторов и состояния нажатия.
func make_binding_event(source: InputEvent) -> InputEvent:
	if source is InputEventKey:
		var key := InputEventKey.new()
		key.physical_keycode = source.physical_keycode if source.physical_keycode != KEY_NONE \
			else source.keycode
		return key
	if source is InputEventMouseButton:
		var button := InputEventMouseButton.new()
		button.button_index = source.button_index
		return button
	return null


## Название клавиши для меню.
func event_label(event: InputEvent) -> String:
	if event is InputEventKey:
		var code: Key = event.physical_keycode if event.physical_keycode != KEY_NONE else event.keycode
		var text := OS.get_keycode_string(code)
		return _KEY_NAMES.get(text, text)
	if event is InputEventMouseButton:
		return _MOUSE_NAMES.get(event.button_index, "Мышь %d" % event.button_index)
	return "—"


# --- Применение ---

func _store(key: String, value: Variant) -> void:
	if _values.has(key) and _values[key] == value:
		return
	_values[key] = value
	_apply(key)
	changed.emit(key)


func _matching_preset() -> int:
	for i in QUALITY_PRESETS.size():
		var matches := true
		for key: String in QUALITY_PRESETS[i]:
			if get_value(key) != QUALITY_PRESETS[i][key]:
				matches = false
		if matches:
			return i
	return QUALITY_CUSTOM


func _apply(key: String) -> void:
	var value: Variant = get_value(key)
	var viewport := get_tree().root
	var has_window := DisplayServer.get_name() != "headless"
	match key:
		"video/window_mode":
			if has_window:
				DisplayServer.window_set_mode(_WINDOW_MODES[value])
		"video/vsync":
			if has_window:
				DisplayServer.window_set_vsync_mode(
					DisplayServer.VSYNC_ENABLED if value else DisplayServer.VSYNC_DISABLED)
		"video/max_fps":
			Engine.max_fps = value
		"video/render_scale":
			viewport.scaling_3d_scale = value
			viewport.scaling_3d_mode = Viewport.SCALING_3D_MODE_FSR \
				if value < 0.999 else Viewport.SCALING_3D_MODE_BILINEAR
		"video/shadows":
			var level: Dictionary = _SHADOW_LEVELS[value]
			RenderingServer.directional_shadow_atlas_set_size(level.directional, true)
			RenderingServer.directional_soft_shadow_filter_set_quality(level.filter)
			RenderingServer.positional_soft_shadow_filter_set_quality(level.filter)
			viewport.positional_shadow_atlas_size = level.positional
		"video/antialiasing":
			# 0 выкл, 1 FXAA, 2 TAA, 3 MSAA 2×, 4 MSAA 4×.
			viewport.screen_space_aa = Viewport.SCREEN_SPACE_AA_FXAA \
				if value == 1 else Viewport.SCREEN_SPACE_AA_DISABLED
			viewport.use_taa = value == 2
			viewport.msaa_3d = [Viewport.MSAA_DISABLED, Viewport.MSAA_DISABLED,
				Viewport.MSAA_DISABLED, Viewport.MSAA_2X, Viewport.MSAA_4X][value]
		"video/ssao":
			for node in get_tree().root.find_children("*", "WorldEnvironment", true, false):
				_apply_environment(node)
		_:
			if AUDIO_BUSES.has(key):
				var bus := AudioServer.get_bus_index(AUDIO_BUSES[key])
				if bus >= 0:
					AudioServer.set_bus_volume_db(bus, linear_to_db(maxf(value, 0.0001)))
					AudioServer.set_bus_mute(bus, value <= 0.0)


func _apply_environment(world: WorldEnvironment) -> void:
	if world.environment != null:
		world.environment.ssao_enabled = get_value("video/ssao")


func _on_node_added(node: Node) -> void:
	if node is WorldEnvironment:
		_apply_environment(node)


func _apply_binding(action: String) -> void:
	InputMap.action_erase_events(action)
	for event: InputEvent in _bindings[action]:
		if event != null:
			InputMap.action_add_event(action, event)


func _pad_slots(events: Array) -> Array:
	var slots := []
	for i in BINDING_SLOTS:
		slots.append(events[i] if i < events.size() else null)
	return slots


func _same_input(a: InputEvent, b: InputEvent) -> bool:
	if a == null or b == null:
		return false
	return _encode_event(a) == _encode_event(b)


func _encode_event(event: InputEvent) -> String:
	if event is InputEventKey:
		return "key:%d" % (event.physical_keycode if event.physical_keycode != KEY_NONE \
			else event.keycode)
	if event is InputEventMouseButton:
		return "mouse:%d" % event.button_index
	return ""


func _decode_event(code: String) -> InputEvent:
	var parts := code.split(":")
	if parts.size() != 2 or not parts[1].is_valid_int():
		return null
	if parts[0] == "key":
		var key := InputEventKey.new()
		key.physical_keycode = int(parts[1]) as Key
		return key
	if parts[0] == "mouse":
		var button := InputEventMouseButton.new()
		button.button_index = int(parts[1]) as MouseButton
		return button
	return null
