# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/ui/menu_back_button.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
extends Button

@export var menu_traverse_manager:MenuTraverseManager

func _pressed()->void:
	menu_traverse_manager.back()
