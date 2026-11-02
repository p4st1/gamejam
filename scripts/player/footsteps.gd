extends Node3D
## Шаги, прыжок и приземление игрока. Узел в сцене игрока, на уровне голени: так на звук
## действует реверберация звуковых зон. Техописание — docs/TECHNICAL_DESIGN.md, «Звук v0.1».

## Каждый шаг — тип поверхности и громкость. Пригодится слуху ИИ.
signal stepped(surface: StringName, volume_db: float)

const FOOTSTEPS_DIR := "res://assets/audio/sfx/footsteps/"
const JUMP_PATH := "res://assets/audio/sfx/body/jump.tres"
const LAND_PATH := "res://assets/audio/sfx/body/land.tres"

## Путь между шагами, м. Совпадает с периодом покачивания камеры (walk_speed / bob_frequency).
@export var stride_length := 1.55
@export var crouch_volume_db := -9.0
@export var sprint_volume_db := 3.0
## Медленнее этого (м/с) приземление не озвучивается — например, сход со ступеньки.
@export var land_min_fall_speed := 2.5
## При какой скорости падения приземление звучит в полную силу.
@export var land_max_fall_speed := 8.0

var current_surface := SurfaceType.DEFAULT

var _distance := 0.0
var _streams := {}
var _jump: AudioStream
var _land: AudioStream

@onready var _player: Player = owner
@onready var _step: AudioStreamPlayer3D = $Step
@onready var _body: AudioStreamPlayer3D = $Body


func _ready() -> void:
	for surface in SurfaceType.ALL:
		var path := FOOTSTEPS_DIR + surface + ".tres"
		if ResourceLoader.exists(path):
			_streams[surface] = load(path)
	_jump = load(JUMP_PATH)
	_land = load(LAND_PATH)
	_player.landed.connect(_on_landed)
	_player.jumped.connect(_on_jumped)


func _physics_process(delta: float) -> void:
	if not _player.is_on_floor():
		return
	_update_surface()
	var speed := _player.get_horizontal_speed()
	if speed < 0.3:
		_distance = stride_length * 0.6  # первый шаг — вскоре после начала движения
		return
	_distance += speed * delta
	if _distance >= stride_length:
		_distance -= stride_length
		var volume := 0.0
		if _player.is_crouching:
			volume = crouch_volume_db
		elif _player.is_sprinting:
			volume = sprint_volume_db
		_play_step(volume)


func _play_step(volume_db: float) -> void:
	var stream: AudioStream = _streams.get(current_surface, _streams.get(SurfaceType.DEFAULT))
	if stream == null:
		return
	if _step.stream != stream:
		_step.stream = stream
	_step.volume_db = volume_db
	_step.play()
	stepped.emit(current_surface, volume_db)


## Поверхность — по столкновению с полом из последнего move_and_slide игрока.
func _update_surface() -> void:
	for i in _player.get_slide_collision_count():
		var collision := _player.get_slide_collision(i)
		if collision.get_normal().y > 0.7:
			current_surface = SurfaceType.of(collision.get_collider())
			return


func _on_jumped() -> void:
	_body.stream = _jump
	_body.volume_db = 0.0
	_body.play()


func _on_landed(fall_speed: float) -> void:
	_distance = 0.0
	if fall_speed < land_min_fall_speed:
		return
	await get_tree().physics_frame  # поверхность приземления — после следующего move_and_slide
	_update_surface()
	var t := clampf(inverse_lerp(land_min_fall_speed, land_max_fall_speed, fall_speed), 0.0, 1.0)
	var volume := lerpf(-8.0, 3.0, t)
	_play_step(volume)
	_body.stream = _land
	_body.volume_db = volume
	_body.play()
