# Source:  https://github.com/derkork/godot-statecharts/blob/main/godot_state_charts_examples/platformer/fireworks_box/fireworks_box.gd
# Repo:    derkork/godot-statecharts (star 1623) | License: MIT | Collected: 2026-10-26
# Commit:  main
extends Node2D

signal clicked(node:Node2D)

@onready var _state_chart:StateChart = $StateChart as StateChart
var _counter := 0

func count_up() -> void:
	_counter += 1
	_notify()
	
func count_down() -> void:
	_counter -= 1
	_notify()
	
func _notify() -> void:
	_state_chart.set_expression_property("counter", _counter)
	_state_chart.send_event("counter_changed")


func _on_area_2d_input_event(_viewport:Node, event:InputEvent, _shape_idx:int) -> void:
	# if the left mouse button is up emit the clicked signal
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.is_pressed() == false:
		clicked.emit(self)
