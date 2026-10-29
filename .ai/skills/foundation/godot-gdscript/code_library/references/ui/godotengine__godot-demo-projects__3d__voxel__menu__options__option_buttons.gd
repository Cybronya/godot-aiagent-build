# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/voxel/menu/options/option_buttons.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Control

@onready var render_distance_label: Label = $RenderDistanceLabel
@onready var render_distance_slider: Slider = $RenderDistanceSlider
@onready var fog_checkbox: CheckBox = $FogCheckBox


func _ready() -> void:
	render_distance_slider.value = Settings.render_distance
	render_distance_label.text = "Render distance: " + String.num_int64(Settings.render_distance)
	fog_checkbox.button_pressed = Settings.fog_enabled


func _on_RenderDistanceSlider_value_changed(value: float) -> void:
	Settings.render_distance = int(value)
	render_distance_label.text = "Render distance: " + String.num_int64(Settings.render_distance)
	Settings.save_settings()


func _on_FogCheckBox_pressed() -> void:
	Settings.fog_enabled = fog_checkbox.button_pressed
	Settings.save_settings()
