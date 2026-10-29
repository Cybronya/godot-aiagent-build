# Source:  https://github.com/dialogic-godot/dialogic/blob/main/addons/dialogic/Modules/DefaultLayoutParts/Base_Default/default_layout_base.gd
# Repo:    dialogic-godot/dialogic (star 6121) | License: MIT | Collected: 2026-10-26
# Commit:  701b67bbe601
@tool
extends DialogicLayoutBase

## The default layout base scene.

@export var canvas_layer: int = 1
@export var follow_viewport: bool = false

@export_subgroup("Global")
@export var global_bg_color: Color = Color(0, 0, 0, 0.9)
@export var global_font_color: Color = Color("white")
@export_file('*.ttf', '*.tres') var global_font: String = ""
@export var global_font_size: int = 18


func _apply_export_overrides() -> void:
	# apply layer
	set(&'layer', canvas_layer)
	set(&'follow_viewport_enabled', follow_viewport)
