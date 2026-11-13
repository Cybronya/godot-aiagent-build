# Source:  https://github.com/GodotVR/godot-xr-tools/blob/master/scenes/main_menu/objects/settings_ui_content.gd
# Repo:    GodotVR/godot-xr-tools (star 740) | License: MIT | Collected: 2026-10-31
# Commit:  6c6189bdfcdf
extends VBoxContainer

signal player_height_changed(new_height)


func _on_user_settings_ui_player_height_changed(new_height):
	emit_signal("player_height_changed", new_height)
