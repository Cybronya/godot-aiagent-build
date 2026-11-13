# Source:  https://github.com/MrEliptik/godot_ui_components/blob/main/scenes/balatro/scripts/destroy_area.gd
# Repo:    MrEliptik/godot_ui_components (star 777) | License: MIT | Collected: 2026-10-31
# Commit:  22d235569061
extends Panel

func _on_area_2d_area_entered(area):
	area.get_parent().destroy()
