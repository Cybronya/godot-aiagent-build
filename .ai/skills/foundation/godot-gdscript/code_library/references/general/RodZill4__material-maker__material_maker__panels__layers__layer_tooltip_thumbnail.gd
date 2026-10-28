# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/panels/layers/layer_tooltip_thumbnail.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
extends ColorRect

func init(layer, channel : String) -> void:
	$Label.text = channel
	material.set_shader_parameter("tex", layer.get(channel))

func init_mr(layer, channel : String, element : String, text : String) -> void:
	$Label.text = text
	material.shader = load("res://material_maker/panels/layers/layer_tooltip_thumbnail_"+element+".shader")
	material.set_shader_parameter("tex", layer.get(channel))
