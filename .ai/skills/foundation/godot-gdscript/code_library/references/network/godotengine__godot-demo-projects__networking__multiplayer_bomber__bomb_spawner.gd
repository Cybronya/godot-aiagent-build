# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/networking/multiplayer_bomber/bomb_spawner.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends MultiplayerSpawner

func _init() -> void:
	spawn_function = _spawn_bomb


func _spawn_bomb(data: Array) -> Area2D:
	if data.size() != 2 or typeof(data[0]) != TYPE_VECTOR2 or typeof(data[1]) != TYPE_INT:
		return null

	var bomb: Area2D = preload("res://bomb.tscn").instantiate()
	bomb.position = data[0]
	bomb.from_player = data[1]
	return bomb
