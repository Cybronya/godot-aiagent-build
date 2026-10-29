# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/windows/node_editor/parameter_gradient.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
extends HBoxContainer

@onready var default = $Default

func get_model_data() -> Dictionary:
	return {
		default = default.value.serialize(),
	}

func set_model_data(data) -> void:
	if data.has("default"):
		var v = MMGradient.new()
		v.deserialize(data.default)
		default.value = v
