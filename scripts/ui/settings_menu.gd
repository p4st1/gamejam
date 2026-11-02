class_name SettingsMenu
extends Control
## Экран настроек. Строки строятся из таблицы PAGES: новая настройка — одна строка в таблице.
## Значения применяются сразу (через Settings), сохраняются при закрытии.

signal closed

const PAGES := [
	{"title": "Графика", "rows": [
		{"key": "video/window_mode", "label": "Режим окна", "type": "option",
			"options": ["В окне", "Полный экран", "Полный экран (эксклюзивный)"]},
		{"key": "video/vsync", "label": "Вертикальная синхронизация", "type": "toggle"},
		{"key": "video/max_fps", "label": "Ограничение кадров", "type": "option",
			"options": ["Нет", "30", "60", "120", "144", "240"], "values": [0, 30, 60, 120, 144, 240]},
		{"key": "video/render_scale", "label": "Масштаб рендера", "type": "slider",
			"min": 0.5, "max": 1.0, "step": 0.05, "format": "percent"},
		{"key": "video/quality", "label": "Качество", "type": "option",
			"options": ["Низкое", "Среднее", "Высокое", "Своё"]},
		{"key": "video/shadows", "label": "Тени", "type": "option",
			"options": ["Низкие", "Средние", "Высокие"]},
		{"key": "video/antialiasing", "label": "Сглаживание", "type": "option",
			"options": ["Выкл", "FXAA", "TAA", "MSAA 2×", "MSAA 4×"]},
		{"key": "video/ssao", "label": "Затенение окружения (SSAO)", "type": "toggle"},
	]},
	{"title": "Звук", "rows": [
		{"key": "audio/master", "label": "Общая громкость", "type": "slider",
			"min": 0.0, "max": 1.0, "step": 0.05, "format": "percent"},
		{"key": "audio/music", "label": "Музыка", "type": "slider",
			"min": 0.0, "max": 1.0, "step": 0.05, "format": "percent"},
		{"key": "audio/sfx", "label": "Эффекты", "type": "slider",
			"min": 0.0, "max": 1.0, "step": 0.05, "format": "percent"},
		{"key": "audio/voice", "label": "Голоса", "type": "slider",
			"min": 0.0, "max": 1.0, "step": 0.05, "format": "percent"},
	]},
	{"title": "Управление", "rows": [
		{"key": "controls/mouse_sensitivity", "label": "Чувствительность мыши", "type": "slider",
			"min": 0.1, "max": 3.0, "step": 0.05, "format": "multiplier"},
		{"key": "controls/invert_y", "label": "Инвертировать ось Y", "type": "toggle"},
	]},
	{"title": "Клавиши", "bindings": true},
]

const _LISTEN_TEXT := "Нажмите клавишу…"

@onready var _tabs: TabContainer = %Tabs
@onready var _hint: Label = %Hint

## key -> {"row": описание, "control": виджет, "value_label": Label или null}
var _widgets := {}
## "action:slot" -> Button
var _key_buttons := {}
## Слот, ждущий нажатия: [action, slot] или пустой массив.
var _listening := []


func _ready() -> void:
	for page: Dictionary in PAGES:
		_tabs.add_child(_build_bindings_page() if page.get("bindings", false) else _build_page(page))
		_tabs.set_tab_title(_tabs.get_tab_count() - 1, page.title)
	%Reset.pressed.connect(_on_reset_pressed)
	%Back.pressed.connect(close)
	Settings.changed.connect(_on_settings_changed)
	_refresh_all()


func open() -> void:
	_hint.text = ""
	_refresh_all()
	show()
	%Back.grab_focus()


func close() -> void:
	if not visible:
		return
	_stop_listening()
	Settings.save_settings()
	hide()
	closed.emit()


func _input(event: InputEvent) -> void:
	if not visible:
		return
	if not _listening.is_empty():
		_capture_binding(event)
	elif event.is_action_pressed("ui_cancel"):
		get_viewport().set_input_as_handled()
		close()


# --- Построение ---

func _build_page(page: Dictionary) -> Control:
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	var grid := GridContainer.new()
	grid.columns = 2
	grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	grid.add_theme_constant_override("h_separation", 32)
	grid.add_theme_constant_override("v_separation", 8)
	scroll.add_child(grid)

	for row: Dictionary in page.rows:
		var label := Label.new()
		label.text = row.label
		label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		grid.add_child(label)
		var widget := _build_widget(row)
		if row.type == "toggle":
			widget.size_flags_horizontal = Control.SIZE_SHRINK_END
		else:
			widget.custom_minimum_size.x = 360
		grid.add_child(widget)
	return scroll


func _build_widget(row: Dictionary) -> Control:
	var key: String = row.key
	var entry := {"row": row, "value_label": null}
	var result: Control
	match row.type:
		"option":
			var option := OptionButton.new()
			for text: String in row.options:
				option.add_item(text)
			if key == "video/quality":
				option.set_item_disabled(Settings.QUALITY_CUSTOM, true)
			option.item_selected.connect(func(index: int) -> void:
				Settings.set_value(key, row.values[index] if row.has("values") else index))
			entry.control = option
			result = option
		"toggle":
			var toggle := CheckButton.new()
			toggle.toggled.connect(func(pressed: bool) -> void: Settings.set_value(key, pressed))
			entry.control = toggle
			result = toggle
		"slider":
			var box := HBoxContainer.new()
			box.add_theme_constant_override("separation", 16)
			var slider := HSlider.new()
			slider.min_value = row.min
			slider.max_value = row.max
			slider.step = row.step
			slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			slider.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			slider.value_changed.connect(func(value: float) -> void:
				Settings.set_value(key, value))
			var value_label := Label.new()
			value_label.custom_minimum_size.x = 64
			value_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
			box.add_child(slider)
			box.add_child(value_label)
			entry.control = slider
			entry.value_label = value_label
			result = box
	_widgets[key] = entry
	return result


func _build_bindings_page() -> Control:
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	var grid := GridContainer.new()
	grid.columns = 1 + Settings.BINDING_SLOTS
	grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	grid.add_theme_constant_override("h_separation", 16)
	grid.add_theme_constant_override("v_separation", 10)
	scroll.add_child(grid)

	for action: String in Settings.REBINDABLE_ACTIONS:
		var label := Label.new()
		label.text = Settings.REBINDABLE_ACTIONS[action]
		label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		grid.add_child(label)
		for slot in Settings.BINDING_SLOTS:
			var button := Button.new()
			button.theme_type_variation = &"KeyButton"
			button.custom_minimum_size.x = 200
			button.pressed.connect(_start_listening.bind(action, slot))
			grid.add_child(button)
			_key_buttons[_slot_id(action, slot)] = button

	var help := Label.new()
	help.theme_type_variation = &"HeaderLabel"
	help.text = "Щёлкните слот и нажмите клавишу или кнопку мыши. Esc — отмена, Delete — очистить слот."
	help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var page := VBoxContainer.new()
	page.add_theme_constant_override("separation", 20)
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	page.add_child(scroll)
	page.add_child(help)
	return page


# --- Обновление ---

func _refresh_all() -> void:
	for key: String in _widgets:
		_refresh_widget(key)
	for action: String in Settings.REBINDABLE_ACTIONS:
		_refresh_bindings(action)


func _refresh_widget(key: String) -> void:
	var entry: Dictionary = _widgets[key]
	var row: Dictionary = entry.row
	var value: Variant = Settings.get_value(key)
	match row.type:
		"option":
			var index: int = row.values.find(value) if row.has("values") else value
			entry.control.select(maxi(index, 0))
		"toggle":
			entry.control.set_pressed_no_signal(value)
		"slider":
			entry.control.set_value_no_signal(value)
			entry.value_label.text = _format_value(row.format, value)


func _refresh_bindings(action: String) -> void:
	for slot in Settings.BINDING_SLOTS:
		var event := Settings.get_binding(action, slot)
		_key_buttons[_slot_id(action, slot)].text = Settings.event_label(event) if event != null else "—"


func _slot_id(action: String, slot: int) -> String:
	return "%s:%d" % [action, slot]


func _format_value(format: String, value: float) -> String:
	match format:
		"percent":
			return "%d %%" % roundi(value * 100.0)
		"multiplier":
			return "%.2f×" % value
	return str(value)


func _on_settings_changed(key: String) -> void:
	if _widgets.has(key):
		_refresh_widget(key)
	elif key.begins_with("input/"):
		_refresh_bindings(key.trim_prefix("input/"))


func _on_reset_pressed() -> void:
	var page: Dictionary = PAGES[_tabs.current_tab]
	if page.get("bindings", false):
		_stop_listening()
		Settings.reset_bindings()
	else:
		var keys := []
		for row: Dictionary in page.rows:
			keys.append(row.key)
		Settings.reset(keys)
	_hint.text = "Вкладка «%s» сброшена." % page.title


# --- Переназначение клавиш ---

func _start_listening(action: String, slot: int) -> void:
	_stop_listening()
	_listening = [action, slot]
	_key_buttons[_slot_id(action, slot)].text = _LISTEN_TEXT
	_hint.text = ""


func _stop_listening() -> void:
	if _listening.is_empty():
		return
	var action: String = _listening[0]
	_listening = []
	_refresh_bindings(action)


func _capture_binding(event: InputEvent) -> void:
	var is_key: bool = event is InputEventKey and event.pressed and not event.echo
	var is_button: bool = event is InputEventMouseButton and event.pressed
	if not is_key and not is_button:
		return
	get_viewport().set_input_as_handled()

	var action: String = _listening[0]
	var slot: int = _listening[1]
	if is_key and event.physical_keycode == KEY_ESCAPE:
		_stop_listening()
		return
	if is_key and event.physical_keycode in [KEY_DELETE, KEY_BACKSPACE]:
		_listening = []
		Settings.set_binding(action, slot, null)
		return

	var binding := Settings.make_binding_event(event)
	_listening = []
	var taken_from := Settings.set_binding(action, slot, binding)
	if not taken_from.is_empty():
		_hint.text = "«%s» снята с действия «%s»." % [Settings.event_label(binding), taken_from]
	else:
		_hint.text = ""
