# Source:  https://github.com/GDQuest/godot-steering-ai-framework/blob/master/godot/Demos/Quickstart/Bullet.gd
# Repo:    GDQuest/godot-steering-ai-framework (star 1588) | License: MIT | Collected: 2026-10-26
# Commit:  9d7cf0deff80
extends CharacterBody2D

@export var speed := 1500.0

var player: Node

@onready var timer := $Lifetime


func _ready() -> void:
	timer.connect("timeout", Callable(self, "_on_Lifetime_timeout"))
	timer.start()


func _physics_process(delta: float) -> void:
	var collision := move_and_collide(velocity * delta)
	if collision:
		timer.stop()
		clear()
		collision.get_collider().damage(10)


func start(direction: Vector2) -> void:
	velocity = direction * speed


func clear() -> void:
	queue_free()


func _on_Lifetime_timeout() -> void:
	clear()
