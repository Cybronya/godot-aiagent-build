# Source:  https://github.com/gdquest-demos/godot-platformer-2d/blob/master/game/src/Combat/DamageSource.gd
# Repo:    gdquest-demos/godot-platformer-2d (star 815) | License: MIT | Collected: 2026-10-31
# Commit:  0ea6cb6056dc
# Represents a weapon or any entity that can damage others Currently
# barebones, but we can extend this class to add an element like fire, ice, etc.
# Or a status modifier like poison, the chances to apply a given status effect,
# and other metadata that we can later transform into an actual attack. See Hit.gd
extends Area2D

class_name DamageSource

export var damage := 1
export var is_instakill := false
