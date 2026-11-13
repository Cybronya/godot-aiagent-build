# Source:  https://github.com/fenix-hub/godot-engine.easy-charts/blob/main/addons/easy_charts/utilities/classes/plotting/point.gd
# Repo:    fenix-hub/godot-engine.easy-charts (star 787) | License: MIT | Collected: 2026-10-31
# Commit:  860b256ce980
extends RefCounted
class_name Point

var position: Vector2
var value: Dictionary

func _init(position: Vector2, value: Dictionary) -> void:
	self.position = position
	self.value = value

func _to_string() -> String:
	return "Value: %s\nPosition: %s" % [self.value, self.position]
