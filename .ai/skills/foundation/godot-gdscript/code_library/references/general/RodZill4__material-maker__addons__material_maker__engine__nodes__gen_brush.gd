# Source:  https://github.com/RodZill4/material-maker/blob/master/addons/material_maker/engine/nodes/gen_brush.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
@tool
extends MMGenShader
class_name MMGenBrush

func can_be_deleted() -> bool:
	return false

func toggle_editable() -> bool:
	return false
