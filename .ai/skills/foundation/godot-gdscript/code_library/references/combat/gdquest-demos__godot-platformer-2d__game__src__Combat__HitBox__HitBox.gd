# Source:  https://github.com/gdquest-demos/godot-platformer-2d/blob/master/game/src/Combat/HitBox/HitBox.gd
# Repo:    gdquest-demos/godot-platformer-2d (star 815) | License: MIT | Collected: 2026-10-31
# Commit:  0ea6cb6056dc
extends Area2D

onready var collider: CollisionShape2D = $CollisionShape2D

var is_active := true setget set_is_active


func _ready() -> void:
# warning-ignore:return_value_discarded
	connect("area_entered", self, "_on_area_entered")


func _on_area_entered(damage_source: Area2D) -> void:
	var hit := Hit.new(damage_source)
	owner.take_damage(hit)


func set_is_active(value: bool) -> void:
	is_active = value
	collider.disabled = not value
