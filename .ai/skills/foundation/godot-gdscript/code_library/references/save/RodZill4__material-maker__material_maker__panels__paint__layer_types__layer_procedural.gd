# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/panels/paint/layer_types/layer_procedural.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
extends MMPaintLayer
class_name MMProceduralLayer

var material : Dictionary = {}

func get_layer_type() -> int:
	return LAYER_PROC

func duplicate():
	var layer = super.duplicate()
	layer.material = material.duplicate(true)
	return layer

func _load_layer(data : Dictionary) -> void:
	super._load_layer(data)
	material = data.material

func _save_layer(data : Dictionary):
	super._save_layer(data)
	data.material = material
