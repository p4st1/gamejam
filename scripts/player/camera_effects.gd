extends Node3D
## Визуальные эффекты камеры: покачивание при ходьбе, просадка при приземлении, крен при стрейфе.
## Не влияет на физику игрока. Узел стоит между Head и Camera3D.

## Общий множитель силы эффектов (0 — выключить, для настройки против укачивания).
@export_range(0.0, 1.5) var strength := 1.0

@export_group("Покачивание")
@export var bob_frequency := 1.9
@export var bob_vertical := 0.035
@export var bob_horizontal := 0.02
## Во сколько раз сильнее покачивание при беге.
@export var sprint_bob_multiplier := 1.6

@export_group("Приземление")
## Просадка камеры (м) на каждый м/с скорости падения.
@export var land_dip_per_speed := 0.012
@export var land_dip_max := 0.12
@export var land_recover_speed := 6.0

@export_group("Крен")
@export var strafe_roll_degrees := 1.2
@export var roll_smoothing := 6.0

@export_group("Торможение")
## «Клевок» камеры вперёд при торможении по инерции бега (на полной скорости бега).
@export var brake_pitch_degrees := 1.2
@export var brake_pitch_smoothing := 8.0

var _bob_time := 0.0
var _land_offset := 0.0

@onready var _player: Player = owner


func _ready() -> void:
	_player.landed.connect(_on_player_landed)


func _process(delta: float) -> void:
	var speed := _player.get_horizontal_speed()
	var offset := Vector3.ZERO

	if _player.is_on_floor() and speed > 0.1:
		var speed_ratio := speed / _player.walk_speed
		_bob_time += delta * bob_frequency * speed_ratio * TAU
		var amplitude := sprint_bob_multiplier if _player.is_sprinting else 1.0
		offset.y = sin(_bob_time) * bob_vertical * amplitude
		offset.x = cos(_bob_time * 0.5) * bob_horizontal * amplitude
	else:
		_bob_time = 0.0

	_land_offset = lerpf(_land_offset, 0.0, minf(1.0, land_recover_speed * delta))
	offset.y -= _land_offset

	position = position.lerp(offset * strength, minf(1.0, delta * 12.0))

	var local_velocity := _player.global_basis.inverse() * _player.velocity
	var target_roll := -local_velocity.x / _player.sprint_speed \
		* deg_to_rad(strafe_roll_degrees) * strength
	rotation.z = lerpf(rotation.z, target_roll, minf(1.0, delta * roll_smoothing))

	var target_pitch := 0.0
	if _player.is_momentum_braking:
		var excess := inverse_lerp(_player.walk_speed, _player.sprint_speed, speed)
		target_pitch = -clampf(excess, 0.0, 1.0) * deg_to_rad(brake_pitch_degrees) * strength
	rotation.x = lerpf(rotation.x, target_pitch, minf(1.0, delta * brake_pitch_smoothing))


func _on_player_landed(fall_speed: float) -> void:
	_land_offset = minf(fall_speed * land_dip_per_speed, land_dip_max)
