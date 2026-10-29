# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/physics_platformer/coin/coin.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
class_name Coin
extends Area2D

var taken: bool = false

func _on_body_enter(body: Node2D) -> void:
	if not taken and body is Player:
		($AnimationPlayer as AnimationPlayer).play(&"taken")
