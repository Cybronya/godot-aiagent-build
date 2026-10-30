# Source:  https://github.com/QodotPlugin/qodot-plugin/blob/master/addons/qodot/game_definitions/fgd/solid_classes/trigger.gd
# Repo:    QodotPlugin/qodot-plugin (star 982) | License: MIT | Collected: 2026-10-29
# Commit:  4731a36dec69
extends Node

signal trigger()

func _ready():
	connect("body_entered", self, "handle_body_entered")

func handle_body_entered(body: Node):
	if body is StaticBody:
		return

	emit_signal("trigger")
