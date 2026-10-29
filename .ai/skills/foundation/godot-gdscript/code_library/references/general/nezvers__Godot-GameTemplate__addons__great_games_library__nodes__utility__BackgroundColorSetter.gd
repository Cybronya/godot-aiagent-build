# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/great_games_library/nodes/utility/BackgroundColorSetter.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
class_name BackgroundColorSetter
extends Node

## Games background color will be set to this color when _ready
@export var color:Color

func _ready() -> void:
	RenderingServer.set_default_clear_color(color)
