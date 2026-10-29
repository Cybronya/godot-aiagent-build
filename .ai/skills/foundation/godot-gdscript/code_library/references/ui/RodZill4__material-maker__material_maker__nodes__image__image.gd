# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/nodes/image/image.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
class_name MMGraphImage
extends MMGraphNodeGeneric

func on_parameter_changed(p : String, v) -> void:
	super.on_parameter_changed(p, v)
	if p == "filter":
		var image_edit : ImagePickerButton = controls["image"]
		image_edit.set_filter(v)
