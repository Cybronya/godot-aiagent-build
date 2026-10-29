# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/misc/pause/process_mode.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends OptionButton


@onready var cube_animation: AnimationPlayer = $"../../AnimationPlayer"


func _on_option_button_item_selected(index: int) -> void:
	cube_animation.process_mode = index as ProcessMode
