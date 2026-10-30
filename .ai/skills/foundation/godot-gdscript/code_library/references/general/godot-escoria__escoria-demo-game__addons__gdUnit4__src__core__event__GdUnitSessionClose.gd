# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/gdUnit4/src/core/event/GdUnitSessionClose.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
class_name GdUnitSessionClose
extends GdUnitEvent


func _init() -> void:
	_event_type = SESSION_CLOSE
