# Source:  https://github.com/viniciusgerevini/godot-aseprite-wizard/blob/godot_4/addons/AsepriteWizard/interface/imports_manager/aseprite_imports_manager.gd
# Repo:    viniciusgerevini/godot-aseprite-wizard (star 1396) | License: MIT | Collected: 2026-10-29
# Commit:  18ebea9868ea
@tool
extends Window

func _on_close_requested():
	self.queue_free()
