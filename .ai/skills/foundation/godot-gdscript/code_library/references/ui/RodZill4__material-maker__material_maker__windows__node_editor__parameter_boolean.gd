# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/windows/node_editor/parameter_boolean.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
extends HBoxContainer


func get_model_data() -> Dictionary:
	return {
		default = $Default.button_pressed,
	}

func set_model_data(data) -> void:
	if data.has("default"):
		$Default.button_pressed = data.default
