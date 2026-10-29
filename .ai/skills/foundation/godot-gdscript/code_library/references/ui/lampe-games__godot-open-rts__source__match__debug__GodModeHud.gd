# Source:  https://github.com/lampe-games/godot-open-rts/blob/main/source/match/debug/GodModeHud.gd
# Repo:    lampe-games/godot-open-rts (star 1136) | License: MIT | Collected: 2026-10-29
# Commit:  a628ad3bb6a9
extends CanvasLayer


func _ready():
	if not Globals.god_mode:
		hide()
	Signals.god_mode_enabled.connect(show)
	Signals.god_mode_disabled.connect(hide)
