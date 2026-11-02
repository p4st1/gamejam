extends Node
## Ход игры: смена сцен с экраном загрузки и пауза по Esc.
## Техописание — docs/TECHNICAL_DESIGN.md, «Меню и настройки v0.1».

const MAIN_MENU := "res://scenes/ui/main_menu.tscn"
const PAUSE_MENU := preload("res://scenes/ui/pause_menu.tscn")

var pause_menu: PauseMenu

var _loading_path := ""
var _loading_layer: CanvasLayer
var _loading_label: Label


func _ready() -> void:
	process_mode = PROCESS_MODE_ALWAYS
	pause_menu = PAUSE_MENU.instantiate()
	add_child(pause_menu)
	_build_loading_screen()
	set_process(false)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel") and not get_tree().paused and can_pause():
		get_viewport().set_input_as_handled()
		pause()


## Пауза доступна в любой сцене с игроком и не во время загрузки.
func can_pause() -> bool:
	return _loading_path.is_empty() and get_tree().get_first_node_in_group("player") != null


func pause() -> void:
	get_tree().paused = true
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	pause_menu.open()


func resume() -> void:
	pause_menu.close()
	get_tree().paused = false
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func change_scene(path: String) -> void:
	if not _loading_path.is_empty():
		return
	pause_menu.close()
	get_tree().paused = false
	var error := ResourceLoader.load_threaded_request(path)
	if error != OK:
		push_error("Не удалось начать загрузку %s: %s" % [path, error_string(error)])
		return
	_loading_path = path
	_loading_label.text = "Загрузка…"
	_loading_layer.show()
	set_process(true)


func go_to_main_menu() -> void:
	change_scene(MAIN_MENU)


func quit() -> void:
	get_tree().quit()


func _process(_delta: float) -> void:
	var progress := []
	var status := ResourceLoader.load_threaded_get_status(_loading_path, progress)
	if status == ResourceLoader.THREAD_LOAD_IN_PROGRESS:
		_loading_label.text = "Загрузка… %d %%" % roundi(progress[0] * 100.0)
		return

	set_process(false)
	var path := _loading_path
	_loading_path = ""
	if status == ResourceLoader.THREAD_LOAD_LOADED:
		get_tree().change_scene_to_packed(ResourceLoader.load_threaded_get(path))
		# Новая сцена встаёт в дерево в следующем кадре — прячем экран после неё.
		await get_tree().process_frame
		await get_tree().process_frame
	else:
		push_error("Не удалось загрузить сцену %s" % path)
	_loading_layer.hide()


func _build_loading_screen() -> void:
	_loading_layer = CanvasLayer.new()
	_loading_layer.layer = 100
	_loading_layer.hide()
	add_child(_loading_layer)

	var background := ColorRect.new()
	background.color = Color(0.055, 0.06, 0.058)
	background.set_anchors_preset(Control.PRESET_FULL_RECT)
	_loading_layer.add_child(background)

	_loading_label = Label.new()
	_loading_label.theme = preload("res://scenes/ui/menu_theme.tres")
	_loading_label.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_RIGHT, Control.PRESET_MODE_MINSIZE, 48)
	_loading_label.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	_loading_label.grow_vertical = Control.GROW_DIRECTION_BEGIN
	_loading_layer.add_child(_loading_label)
