extends Control
## Главное меню прототипа: «Новая игра» ведёт к выбору сцены (D-039).
## Список сцен собирается из папок автоматически — новые уровни появляются без правки кода.

const SCENE_FOLDERS := {
	"res://scenes/levels": "Уровни",
	"res://scenes/blockouts": "Наброски",
}

@onready var _main_buttons: Control = %MainButtons
@onready var _scene_panel: Control = %ScenePanel
@onready var _scene_list: VBoxContainer = %SceneList


func _ready() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	%NewGame.pressed.connect(_show_scene_panel)
	%Settings.pressed.connect(_open_settings)
	%Quit.pressed.connect(Game.quit)
	%SceneBack.pressed.connect(_show_main_buttons)
	%SettingsMenu.closed.connect(_show_main_buttons)
	_fill_scene_list()
	_show_main_buttons()


func _unhandled_input(event: InputEvent) -> void:
	if _scene_panel.visible and event.is_action_pressed("ui_cancel"):
		get_viewport().set_input_as_handled()
		_show_main_buttons()


## Все сцены из SCENE_FOLDERS: {заголовок группы: [пути]}.
static func find_scenes() -> Dictionary:
	var result := {}
	for folder: String in SCENE_FOLDERS:
		var paths := PackedStringArray()
		_collect_scenes(folder, paths)
		paths.sort()
		result[SCENE_FOLDERS[folder]] = paths
	return result


static func _collect_scenes(folder: String, into: PackedStringArray) -> void:
	var dir := DirAccess.open(folder)
	if dir == null:
		return
	for sub in dir.get_directories():
		_collect_scenes(folder.path_join(sub), into)
	for file in dir.get_files():
		# В экспортированной сборке сцены лежат как *.tscn.remap.
		var scene_file := file.trim_suffix(".remap")
		if scene_file.ends_with(".tscn") or scene_file.ends_with(".scn"):
			into.append(folder.path_join(scene_file))


func _fill_scene_list() -> void:
	var groups := find_scenes()
	for title: String in groups:
		if groups[title].is_empty():
			continue
		var header := Label.new()
		header.theme_type_variation = &"HeaderLabel"
		header.text = title.to_upper()
		_scene_list.add_child(header)
		for path: String in groups[title]:
			var button := Button.new()
			button.alignment = HORIZONTAL_ALIGNMENT_LEFT
			button.text = _scene_title(path)
			button.tooltip_text = path
			button.pressed.connect(Game.change_scene.bind(path))
			_scene_list.add_child(button)


## «res://scenes/levels/prototype/test_range.tscn» → «prototype / test range».
func _scene_title(path: String) -> String:
	var scene_name := path.get_file().get_basename().replace("_", " ")
	var parent := path.get_base_dir().get_file()
	if parent in ["levels", "blockouts"]:
		return scene_name
	return "%s / %s" % [parent.replace("_", " "), scene_name]


func _show_main_buttons() -> void:
	_scene_panel.hide()
	%SettingsMenu.hide()
	_main_buttons.show()
	%NewGame.grab_focus()


func _show_scene_panel() -> void:
	_main_buttons.hide()
	_scene_panel.show()
	var first := _scene_list.get_children().filter(func(node: Node) -> bool: return node is Button)
	if not first.is_empty():
		first[0].grab_focus()


func _open_settings() -> void:
	%SettingsMenu.open()
