# Source:  https://github.com/GodotVR/godot-xr-tools/blob/master/scenes/main_menu/objects/settings_ui.gd
# Repo:    GodotVR/godot-xr-tools (star 740) | License: MIT | Collected: 2026-10-31
# Commit:  6c6189bdfcdf
extends Node3D

signal player_height_changed(new_height)

func _on_player_height_changed(new_height):
	emit_signal("player_height_changed", new_height)

# Called when the node enters the scene tree for the first time.
func _ready():
	var scene = $Screen/Viewport2Din3D.get_scene_instance()
	if scene:
		scene.connect("player_height_changed", _on_player_height_changed)
