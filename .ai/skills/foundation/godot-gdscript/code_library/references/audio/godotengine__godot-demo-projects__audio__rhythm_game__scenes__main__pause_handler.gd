# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/audio/rhythm_game/scenes/main/pause_handler.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
# Pause logic is separated out since it needs to run with PROCESS_MODE_ALWAYS.
extends Node


func _process(_delta: float) -> void:
	if Input.is_action_just_pressed(&"pause"):
		get_tree().paused = not get_tree().paused
		$"../Control/PauseLabel".visible = get_tree().paused
