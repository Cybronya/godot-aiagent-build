# Source:  https://github.com/lampe-games/godot-open-rts/blob/main/source/match/debug/TimeManager.gd
# Repo:    lampe-games/godot-open-rts (star 1136) | License: MIT | Collected: 2026-10-29
# Commit:  a628ad3bb6a9
extends PanelContainer


func _on_time_scale_spin_box_value_changed(value):
	Engine.time_scale = value
