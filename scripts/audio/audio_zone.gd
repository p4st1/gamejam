class_name AudioZone
extends Area3D
## Звуковая зона: фон и реверберация для всего, что звучит внутри.
## Реверберация — встроенные свойства Area3D (раздел Reverb Bus); фон переключает AudioDirector.
## Из перекрывающихся зон действует зона с большим priority (свойство Area3D).
## Техописание — docs/TECHNICAL_DESIGN.md, «Звук v0.1».

@export var ambience: AudioStream
@export_range(-40.0, 6.0) var ambience_volume_db := 0.0


func _ready() -> void:
	body_entered.connect(_on_body_entered)
	body_exited.connect(_on_body_exited)


func _exit_tree() -> void:
	AudioDirector.exit_zone(self)


func _on_body_entered(body: Node3D) -> void:
	if body.is_in_group("player"):
		AudioDirector.enter_zone(self)


func _on_body_exited(body: Node3D) -> void:
	if body.is_in_group("player"):
		AudioDirector.exit_zone(self)
