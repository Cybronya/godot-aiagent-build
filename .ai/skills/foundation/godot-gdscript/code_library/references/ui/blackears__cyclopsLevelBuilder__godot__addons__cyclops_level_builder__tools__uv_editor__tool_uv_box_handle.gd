# Source:  https://github.com/blackears/cyclopsLevelBuilder/blob/master/godot/addons/cyclops_level_builder/tools/uv_editor/tool_uv_box_handle.gd
# Repo:    blackears/cyclopsLevelBuilder (star 1639) | License: MIT | Collected: 2026-10-29
# Commit:  ea41feaab5dd
@tool
extends Node
class_name ToolUvBoxHandle

enum Style { SQUARE, AREA }

@export var uv_position:Vector2
@export var style:Style
@export var viewport_handle:Node2D
