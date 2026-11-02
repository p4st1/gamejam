class_name PauseMenu
extends CanvasLayer
## Меню паузы. Открывает и закрывает его Game (autoload); работает при SceneTree.paused.


func _ready() -> void:
	hide()
	%Resume.pressed.connect(Game.resume)
	%Settings.pressed.connect(_open_settings)
	%MainMenu.pressed.connect(Game.go_to_main_menu)
	%Quit.pressed.connect(Game.quit)
	%SettingsMenu.closed.connect(_on_settings_closed)


func open() -> void:
	%SettingsMenu.hide()
	%Panel.show()
	show()
	%Resume.grab_focus()


func close() -> void:
	%SettingsMenu.close()
	hide()


func _unhandled_input(event: InputEvent) -> void:
	# Esc при открытых настройках обрабатывает сам экран настроек.
	if visible and event.is_action_pressed("ui_cancel"):
		get_viewport().set_input_as_handled()
		Game.resume()


func _open_settings() -> void:
	%Panel.hide()
	%SettingsMenu.open()


func _on_settings_closed() -> void:
	%Panel.show()
	%Settings.grab_focus()
