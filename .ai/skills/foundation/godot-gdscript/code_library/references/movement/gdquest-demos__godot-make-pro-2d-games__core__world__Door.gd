# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/core/world/Door.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends Area2D

signal player_entered(map_path)

export(String, FILE, "*.tscn") var map_path
var PlayerController = preload("res://actors/player/PlayerController.gd")

export(bool) var ACTIVE_AT_START = true

func _ready():
	set_active(ACTIVE_AT_START)
	assert(map_path != "")

func _on_body_entered(body):
	if not body is PlayerController:
		return
	emit_signal("player_entered", map_path)

func set_active(value):
	visible = value
	$CollisionShape2D.disabled = not value
