# Source:  https://github.com/derkork/godot-statecharts/blob/main/godot_state_charts_examples/save_and_load/color_box/serialized_color_box.gd
# Repo:    derkork/godot-statecharts (star 1623) | License: MIT | Collected: 2026-10-26
# Commit:  76d226a3efac
class_name SerializedColorBox extends Resource

@export var box_id: String = ""
@export var color_index: int = 0
@export var time_in_state: float = 0.0


func _to_string() -> String:
	return """SerializedColorBox(
		box_id: %s
		color_index: %s
		time_in_state: %s
	)""" % [box_id, color_index, time_in_state]
