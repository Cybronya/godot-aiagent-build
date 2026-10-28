# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/panels/preview_3d/preview_light.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
extends Area3D

func _on_Light_input_event(camera, event, click_position, click_normal, shape_idx) -> void:
	print(event)
