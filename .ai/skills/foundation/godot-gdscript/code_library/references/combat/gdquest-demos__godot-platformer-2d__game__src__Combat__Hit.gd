# Source:  https://github.com/gdquest-demos/godot-platformer-2d/blob/master/game/src/Combat/Hit.gd
# Repo:    gdquest-demos/godot-platformer-2d (star 815) | License: MIT | Collected: 2026-10-31
# Commit:  0ea6cb6056dc
# Represents an attack or a hit
# Created from a DamageSource.
# See DamageSource for more information.
class_name Hit

var damage := 0
var is_instakill := false

func _init(source: DamageSource) -> void:
	damage = source.damage
	is_instakill = source.is_instakill
