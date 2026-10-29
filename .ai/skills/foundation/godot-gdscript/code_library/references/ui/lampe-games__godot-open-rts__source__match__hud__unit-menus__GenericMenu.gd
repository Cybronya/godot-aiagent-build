# Source:  https://github.com/lampe-games/godot-open-rts/blob/main/source/match/hud/unit-menus/GenericMenu.gd
# Repo:    lampe-games/godot-open-rts (star 1136) | License: MIT | Collected: 2026-10-29
# Commit:  a628ad3bb6a9
extends GridContainer

const Structure = preload("res://source/match/units/Structure.gd")

var units = []


func _on_cancel_action_button_pressed():
	if len(units) == 1 and units[0] is Structure and units[0].is_under_construction():
		units[0].cancel_construction()
		return
	for unit in units:
		unit.action = null
