class_name Player
extends CharacterBody3D
## Контроллер игрока от первого лица: ходьба, бег, присед, прыжок, обзор мышью.
## Техописание — docs/TECHNICAL_DESIGN.md, «Контроллер игрока v0.1».

## Испускается в момент касания земли. fall_speed — скорость падения (м/с, положительная).
signal landed(fall_speed: float)
## Испускается в момент отрыва от земли прыжком.
signal jumped

@export_group("Скорость")
@export var walk_speed := 3.0
@export var sprint_speed := 5.5
@export var crouch_speed := 1.6
## Разгон вдоль желаемого направления.
@export var ground_acceleration := 20.0
## Торможение без ввода.
@export var ground_deceleration := 22.0
## Гашение сноса поперёк желаемого направления и движения назад — резкая смена направления.
@export var turn_deceleration := 30.0
## Инерция бега: скорость сверх walk_speed гасится этим темпом — игрок проскальзывает.
@export var sprint_momentum_deceleration := 7.0
@export var air_control := 0.25

@export_group("Прыжок")
@export var jump_velocity := 3.6

@export_group("Присед")
@export var stand_height := 1.8
@export var crouch_height := 1.1
@export var crouch_transition_speed := 8.0
## Расстояние от макушки капсулы до глаз.
@export var eye_offset := 0.12

@export_group("Обзор")
## Базовая чувствительность; итоговая умножается на настройку игрока.
@export var mouse_sensitivity := 0.0022
@export var max_pitch_degrees := 89.0

var is_crouching := false
var is_sprinting := false
## Идёт торможение по инерции бега (скорость сверх шага гасится медленно) — для эффектов камеры.
var is_momentum_braking := false

var _gravity: float = ProjectSettings.get_setting("physics/3d/default_gravity")
var _current_height := 1.8
var _was_on_floor := true
var _fall_speed := 0.0
var _look_sensitivity := 0.0022
var _invert_y := false

@onready var _collision: CollisionShape3D = $CollisionShape3D
@onready var _capsule: CapsuleShape3D = _collision.shape
@onready var _head: Node3D = $Head


func _ready() -> void:
	add_to_group("player")
	_current_height = stand_height
	_apply_height()
	Settings.changed.connect(_on_settings_changed)
	_apply_settings()
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		rotate_y(-event.relative.x * _look_sensitivity)
		var pitch_sign := 1.0 if _invert_y else -1.0
		_head.rotate_x(pitch_sign * event.relative.y * _look_sensitivity)
		var limit := deg_to_rad(max_pitch_degrees)
		_head.rotation.x = clampf(_head.rotation.x, -limit, limit)
	# Esc — меню паузы (autoload Game); клик возвращает захват мыши, если он потерян.
	elif event is InputEventMouseButton and event.pressed:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _physics_process(delta: float) -> void:
	_update_crouch(delta)

	if not is_on_floor():
		velocity.y -= _gravity * delta
		_fall_speed = maxf(_fall_speed, -velocity.y)
	elif Input.is_action_just_pressed("jump") and not is_crouching:
		velocity.y = jump_velocity
		jumped.emit()

	var input := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	var direction := (transform.basis * Vector3(input.x, 0.0, input.y)).normalized()

	# Бег — только вперёд, не в приседе и не в воздухе.
	is_sprinting = Input.is_action_pressed("sprint") and input.y < -0.5 \
		and not is_crouching and is_on_floor()

	var target_speed := walk_speed
	if is_crouching:
		target_speed = crouch_speed
	elif is_sprinting:
		target_speed = sprint_speed

	var horizontal := Vector3(velocity.x, 0.0, velocity.z)
	is_momentum_braking = false
	if not is_on_floor():
		var rate := ground_acceleration if direction != Vector3.ZERO else ground_deceleration
		horizontal = horizontal.move_toward(direction * target_speed, rate * air_control * delta)
	elif direction == Vector3.ZERO:
		horizontal = horizontal.limit_length(
			_slow_down(horizontal.length(), 0.0, ground_deceleration, delta))
	else:
		# Скорость вдоль желаемого направления и снос поперёк гасятся раздельно.
		var along := horizontal.dot(direction)
		var drift := horizontal - direction * along
		if along < 0.0:
			along = -_slow_down(-along, 0.0, turn_deceleration, delta)
		elif along > target_speed:
			along = _slow_down(along, target_speed, ground_deceleration, delta)
		else:
			along = move_toward(along, target_speed, ground_acceleration * delta)
		drift = drift.limit_length(_slow_down(drift.length(), 0.0, turn_deceleration, delta))
		horizontal = direction * along + drift
	velocity.x = horizontal.x
	velocity.z = horizontal.z

	move_and_slide()

	if is_on_floor() and not _was_on_floor:
		landed.emit(_fall_speed)
	if is_on_floor():
		_fall_speed = 0.0
	_was_on_floor = is_on_floor()


## Горизонтальная скорость — нужна эффектам камеры и отладочному оверлею.
func get_horizontal_speed() -> float:
	return Vector2(velocity.x, velocity.z).length()


## Снижает скорость speed до target: сверх walk_speed — медленно (инерция бега), ниже — темпом rate.
func _slow_down(speed: float, target: float, rate: float, delta: float) -> float:
	if speed > walk_speed and speed > target:
		is_momentum_braking = true
		return maxf(speed - sprint_momentum_deceleration * delta, maxf(target, walk_speed))
	return move_toward(speed, target, rate * delta)


func _apply_settings() -> void:
	_look_sensitivity = mouse_sensitivity * Settings.get_value("controls/mouse_sensitivity")
	_invert_y = Settings.get_value("controls/invert_y")


func _on_settings_changed(key: String) -> void:
	if key.begins_with("controls/"):
		_apply_settings()


func _update_crouch(delta: float) -> void:
	var wants_crouch := Input.is_action_pressed("crouch")
	if wants_crouch:
		is_crouching = true
	elif is_crouching and _has_headroom():
		is_crouching = false

	var target_height := crouch_height if is_crouching else stand_height
	if not is_equal_approx(_current_height, target_height):
		_current_height = move_toward(_current_height, target_height,
			crouch_transition_speed * delta)
		_apply_height()


## Есть ли место, чтобы выпрямиться в полный рост.
func _has_headroom() -> bool:
	var rise := stand_height - _current_height
	return not test_move(global_transform, Vector3.UP * rise)


func _apply_height() -> void:
	_capsule.height = _current_height
	_collision.position.y = _current_height * 0.5
	_head.position.y = _current_height - eye_offset
