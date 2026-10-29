# Source:  https://github.com/lampe-games/godot-open-rts/blob/main/source/match/debug/FogOfWarManager.gd
# Repo:    lampe-games/godot-open-rts (star 1136) | License: MIT | Collected: 2026-10-29
# Commit:  a628ad3bb6a9
extends PanelContainer

@onready var _match = find_parent("Match")


func _on_toggle_button_pressed():
	_match.fog_of_war.visible = not _match.fog_of_war.visible
	_match.find_child("UnitVisibilityHandler").visible = not (
		_match.find_child("UnitVisibilityHandler").visible
	)
