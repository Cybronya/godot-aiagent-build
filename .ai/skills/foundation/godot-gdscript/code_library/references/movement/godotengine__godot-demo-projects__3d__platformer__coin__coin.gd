# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/platformer/coin/coin.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends Area3D


var taken: bool = false


func _on_coin_body_enter(body: Node) -> void:
	if not taken and body is Player:
		$Animation.play(&"take")
		taken = true
		# We've already checked whether the colliding body is a Player, which has a `coins` property.
		# As a result, we can safely increment its `coins` property.
		body.coins += 1
