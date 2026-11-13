# Source:  https://github.com/gdquest-demos/godot-platformer-2d/blob/master/game/src/Combat/DummyEnemy.gd
# Repo:    gdquest-demos/godot-platformer-2d (star 815) | License: MIT | Collected: 2026-10-31
# Commit:  0ea6cb6056dc
extends Node2D

# Takes damage from a damage source, i.e. Hit, dying if health is depleated

onready var stats: Stats = $Stats as Stats

func _ready() -> void:
	stats.connect("health_depleted", self, "_on_Stats_health_depleated")


func take_damage(source: Hit) -> void:
	stats.take_damage(source)


func _on_Stats_health_depleated():
	queue_free()
