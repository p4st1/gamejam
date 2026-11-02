extends Node
## Звук на уровне игры: фон звуковых зон с плавной сменой и звуки интерфейса.
## Техописание — docs/TECHNICAL_DESIGN.md, «Звук v0.1».

const FADE_TIME := 1.5
const SILENT_DB := -60.0
const UI_HOVER := preload("res://assets/audio/ui/hover.wav")
const UI_CLICK := preload("res://assets/audio/ui/click.wav")

## Зоны, в которых сейчас стоит игрок, в порядке входа.
var _zones: Array[AudioZone] = []
var _current: AudioZone
var _ambience: Array[AudioStreamPlayer] = []
var _active := 0
var _ui: AudioStreamPlayer


func _ready() -> void:
	process_mode = PROCESS_MODE_ALWAYS
	for i in 2:
		var player := AudioStreamPlayer.new()
		player.bus = &"Ambience"
		player.volume_db = SILENT_DB
		add_child(player)
		_ambience.append(player)
	_ui = AudioStreamPlayer.new()
	_ui.bus = &"SFX"
	_ui.max_polyphony = 3
	add_child(_ui)
	get_tree().node_added.connect(_on_node_added)


func current_zone() -> AudioZone:
	return _current


## Поток фона, который сейчас звучит или нарастает (null — тишина).
func current_ambience() -> AudioStream:
	return _ambience[_active].stream if _ambience[_active].playing else null


func enter_zone(zone: AudioZone) -> void:
	if zone not in _zones:
		_zones.append(zone)
		_update()


func exit_zone(zone: AudioZone) -> void:
	if zone in _zones:
		_zones.erase(zone)
		_update()


func play_ui(stream: AudioStream, volume_db := 0.0) -> void:
	_ui.stream = stream
	_ui.volume_db = volume_db
	_ui.play()


func _update() -> void:
	var best: AudioZone = null
	for zone in _zones:  # при равном priority побеждает зона, в которую вошли позже
		if best == null or zone.priority >= best.priority:
			best = zone
	if best == _current:
		return
	_current = best

	var stream: AudioStream = best.ambience if best else null
	var volume := best.ambience_volume_db if best else SILENT_DB
	var active := _ambience[_active]
	if stream != null and active.stream == stream and active.playing:
		_fade(active, volume, false)  # тот же фон — только громкость
		return
	_fade(active, SILENT_DB, true)
	if stream == null:
		return
	_active = 1 - _active
	var next := _ambience[_active]
	next.stream = stream
	next.volume_db = SILENT_DB
	next.play()
	_fade(next, volume, false)


func _fade(player: AudioStreamPlayer, volume_db: float, stop_after: bool) -> void:
	if player.has_meta(&"tween"):
		(player.get_meta(&"tween") as Tween).kill()
	if not player.playing:
		return
	var tween := create_tween()
	tween.tween_property(player, "volume_db", volume_db, FADE_TIME)
	if stop_after:
		tween.tween_callback(player.stop)
	player.set_meta(&"tween", tween)


func _on_node_added(node: Node) -> void:
	if node is BaseButton:
		node.mouse_entered.connect(_on_button_hovered.bind(node))
		node.pressed.connect(play_ui.bind(UI_CLICK, 0.0))


func _on_button_hovered(button: BaseButton) -> void:
	if not button.disabled:
		play_ui(UI_HOVER, -6.0)
