# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/panels/layers/layer_tooltip.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
extends PanelContainer

func _ready():
	pass # Replace with function body.

func set_layer(l) -> void:
	$VBoxContainer/LayerName.text = l.name
	var thumbnail_scene = preload("res://material_maker/panels/layers/layer_tooltip_thumbnail.tscn")
	for c in l.get_channels():
		if c == "mr" or c == "do":
			var t = thumbnail_scene.instantiate()
			t.init_mr(l, c, "m", "metallic" if c == "mr" else "depth")
			$VBoxContainer/Thumbnails.add_child(t)
			t = thumbnail_scene.instantiate()
			t.init_mr(l, c, "r", "roughness" if c == "mr" else "occlusion")
			$VBoxContainer/Thumbnails.add_child(t)
		else:
			var t = thumbnail_scene.instantiate()
			t.init(l, c)
			$VBoxContainer/Thumbnails.add_child(t)
