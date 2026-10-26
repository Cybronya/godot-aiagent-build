# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/physics_tests/utils/scroll_log.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends ScrollContainer


@export var auto_scroll: bool = false


func _process(_delta: float) -> void:
	if auto_scroll:
		var scrollbar := get_v_scroll_bar()
		scrollbar.value = scrollbar.max_value


func _on_check_box_scroll_toggled(button_pressed: bool) -> void:
	auto_scroll = button_pressed
