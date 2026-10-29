# Source:  https://github.com/Arnklit/Waterways/blob/main/addons/waterways/gui/water_system_controls.gd
# Repo:    Arnklit/Waterways (star 1342) | License: MIT | Collected: 2026-10-29
# Commit:  cd2e2193fe2c
# Copyright © 2021 Kasper Arnklit Frandsen - MIT License
# See `LICENSE.md` included in the source distribution for details.
tool
extends HBoxContainer

var menu

func _enter_tree() -> void:
	menu = $WaterSystemMenu
