# Source:  https://github.com/derkork/godot-statecharts/blob/main/godot_state_charts_examples/history_states/history_demo.gd
# Repo:    derkork/godot-statecharts (star 1623) | License: MIT | Collected: 2026-10-26
# Commit:  76d226a3efac
extends Node

@onready var state_chart:StateChart = $StateChart

func _on_area_2d_input_event(_viewport:Node, event:InputEvent, _shape_idx:int) -> void:
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			# on release send clicked event to state chart
			if not event.is_pressed():
				state_chart.send_event("clicked")
	
