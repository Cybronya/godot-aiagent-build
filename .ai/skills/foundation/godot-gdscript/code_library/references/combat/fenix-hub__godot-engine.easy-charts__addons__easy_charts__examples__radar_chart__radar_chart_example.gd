# Source:  https://github.com/fenix-hub/godot-engine.easy-charts/blob/main/addons/easy_charts/examples/radar_chart/radar_chart_example.gd
# Repo:    fenix-hub/godot-engine.easy-charts (star 787) | License: MIT | Collected: 2026-10-31
# Commit:  860b256ce980
extends Control

@onready var chart: Chart = $VBoxContainer/Chart

func _ready() -> void:
	var skills: Array = [
		"Attack",
		"Defense",
		"Speed",
		"Magic",
		"Stamina",
		"Luck"
	]

	var warrior_stats: Array = [82, 91, 54, 38, 87, 45]
	var ranger_stats: Array = [61, 58, 92, 49, 64, 86]

	var cp := ChartProperties.new()
	cp.title = "Character Class Comparison"
	cp.show_legend = true
	cp.interactive = true
	cp.draw_grid_box = false
	cp.draw_vertical_grid = false
	cp.draw_horizontal_grid = false
	cp.draw_ticks = false
	cp.show_tick_labels = false
	cp.show_x_label = false
	cp.show_y_label = false

	var warrior_function := Function.new(
		skills,
		warrior_stats,
		"Warrior",
		{
			type = Function.Type.RADAR,
			color = Color("#36a2eb"),
			marker = Function.Marker.CIRCLE,
			radar_max_value = 100,
			radar_grid_levels = 5
		}
	)

	var ranger_function := Function.new(
		skills,
		ranger_stats,
		"Ranger",
		{
			type = Function.Type.RADAR,
			color = Color("#ff6384"),
			marker = Function.Marker.CROSS,
			radar_max_value = 100,
			radar_grid_levels = 5
		}
	)

	chart.plot([warrior_function, ranger_function], cp)
