# Source:  https://github.com/gdquest-demos/godot-open-rpg/blob/main/src/field/cutscenes/templates/doors/door_trigger.gd
# Repo:    gdquest-demos/godot-open-rpg (star 3028) | License: MIT | Collected: 2026-10-26
# Commit:  main
extends Trigger

@export var _anim: AnimationPlayer


func _ready() -> void:
	super._ready()
	assert(_anim, "%s error: animation player reference is not set!" % name)


func _on_area_entered(area: Area2D) -> void:
	super._on_area_entered(area)
	_anim.play("open")
