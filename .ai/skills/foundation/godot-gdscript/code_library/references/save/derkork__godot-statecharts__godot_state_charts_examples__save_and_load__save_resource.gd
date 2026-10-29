# Source:  https://github.com/derkork/godot-statecharts/blob/main/godot_state_charts_examples/save_and_load/save_resource.gd
# Repo:    derkork/godot-statecharts (star 1623) | License: MIT | Collected: 2026-10-26
# Commit:  76d226a3efac
class_name SaveResource extends Resource

@export var state_chart: SerializedStateChart = null
@export var boxes: Array[SerializedColorBox] = []
