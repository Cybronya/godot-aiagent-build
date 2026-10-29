# Source:  https://github.com/foxssake/netfox/blob/main/examples/forest-brawl/ui/menus/base-menu.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
extends Control
class_name BaseMenu

func _ready():
	visibility_changed.connect(func():
		if is_visible_in_tree(): _execute()
		else: _cancel()
	, CONNECT_DEFERRED)

func _execute() -> void:
	pass

func _cancel() -> void:
	pass

func _switch_to(menu: Control) -> void:
	menu.show()
	hide()

func _back() -> void:
	_switch_to(get_parent().find_child("Main Menu"))
