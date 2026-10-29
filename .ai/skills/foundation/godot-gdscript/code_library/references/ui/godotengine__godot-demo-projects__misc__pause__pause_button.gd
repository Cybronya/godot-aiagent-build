# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/misc/pause/pause_button.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Button


func _ready() -> void:
	# This ensures that this Node won't be paused, allowing it to
	# process even when the SceneTree is paused. Without that it would
	# not be able to unpause the game. Note that you can set this through
	# the inspector as well.
	process_mode = Node.PROCESS_MODE_ALWAYS


func _toggled(is_button_pressed: bool) -> void:
	# Pause or unpause the SceneTree based on whether the button is
	# toggled on or off.
	get_tree().paused = is_button_pressed
	if is_button_pressed:
		text = "Unpause"
	else:
		text = "Pause"
