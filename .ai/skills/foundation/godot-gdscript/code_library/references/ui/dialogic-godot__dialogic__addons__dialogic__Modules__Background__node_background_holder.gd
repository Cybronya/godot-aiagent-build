# Source:  https://github.com/dialogic-godot/dialogic/blob/main/addons/dialogic/Modules/Background/node_background_holder.gd
# Repo:    dialogic-godot/dialogic (star 6121) | License: MIT | Collected: 2026-10-26
# Commit:  main
class_name DialogicNode_BackgroundHolder
extends ColorRect


func _ready() -> void:
	add_to_group('dialogic_background_holders')
