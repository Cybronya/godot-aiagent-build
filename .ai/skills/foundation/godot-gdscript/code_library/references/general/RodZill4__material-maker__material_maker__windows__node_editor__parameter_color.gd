# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/windows/node_editor/parameter_color.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
extends HBoxContainer

func get_model_data() -> Dictionary:
	var default_color = $Default.color

	return {
		default = { r=default_color.r, g=default_color.g, b=default_color.b, a=default_color.a },
	}

func set_model_data(data) -> void:
	if data.has("default"):
		$Default.color = Color(data.default.r, data.default.g, data.default.b, data.default.a)
