# Source:  https://github.com/lampe-games/godot-open-rts/blob/main/source/Globals.gd
# Repo:    lampe-games/godot-open-rts (star 1136) | License: MIT | Collected: 2026-10-29
# Commit:  a628ad3bb6a9
extends Node

const Options = preload("res://source/data-model/Options.gd")

var options = (
	load(Constants.OPTIONS_FILE_PATH)
	if ResourceLoader.exists(Constants.OPTIONS_FILE_PATH)
	else Options.new()
)
var god_mode = false
var cache = {}


func _unhandled_input(event):
	if event.is_action_pressed("toggle_god_mode"):
		_toggle_god_mode()


func _toggle_god_mode():
	if not FeatureFlags.god_mode:
		return
	god_mode = not god_mode
	if god_mode:
		Signals.god_mode_enabled.emit()
	else:
		Signals.god_mode_disabled.emit()
