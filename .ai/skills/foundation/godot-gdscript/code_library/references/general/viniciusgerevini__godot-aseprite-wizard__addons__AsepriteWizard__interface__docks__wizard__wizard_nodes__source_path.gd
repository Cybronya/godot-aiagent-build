# Source:  https://github.com/viniciusgerevini/godot-aseprite-wizard/blob/godot_4/addons/AsepriteWizard/interface/docks/wizard/wizard_nodes/source_path.gd
# Repo:    viniciusgerevini/godot-aseprite-wizard (star 1396) | License: MIT | Collected: 2026-10-29
# Commit:  18ebea9868ea
@tool
extends LineEdit

func set_entry(entry: Dictionary):
	self.text = entry.source_file
	self.tooltip_text = entry.source_file
