# Source:  https://github.com/Orama-Interactive/Pixelorama/blob/master/src/UI/Canvas/CurrentFrameDrawer.gd
# Repo:    Orama-Interactive/Pixelorama (star 10855) | License: MIT | Collected: 2026-10-27
# Commit:  master
extends Node2D


func _draw() -> void:
	# Placeholder so we can have a material here
	var image_to_draw := Global.current_project.empty_image_texture
	draw_texture(image_to_draw, Vector2.ZERO)
