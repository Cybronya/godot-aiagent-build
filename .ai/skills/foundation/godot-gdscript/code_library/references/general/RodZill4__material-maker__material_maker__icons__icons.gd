# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/icons/icons.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
extends ImageTexture

func _init():
	var image : Image
	if FileAccess.file_exists("user://icons.svg"):
		image = Image.load_from_file("user://icons.svg")
	else:
		var texture : Texture2D = ResourceLoader.load("res://material_maker/icons/icons.svg")
		image = texture.get_image()
	set_image(image)
