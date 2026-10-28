# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/panels/paint/layer_types/layer_mask.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
extends MMLayer
class_name MMMaskLayer

var mask : Texture2D

func get_layer_type() -> int:
	return LAYER_MASK

func duplicate():
	var layer = super.duplicate()
	return layer

func get_channels() -> Array:
	return [ "mask" ]
