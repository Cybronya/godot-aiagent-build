# Source:  https://github.com/func-godot/func_godot_plugin/blob/main/addons/func_godot/src/import/quake_palette_file.gd
# Repo:    func-godot/func_godot_plugin (star 883) | License: MIT | Collected: 2026-10-29
# Commit:  267ed438154c
@icon("res://addons/func_godot/icons/icon_quake_file.svg")
class_name QuakePaletteFile extends Resource
## Quake LMP palette format file used with [QuakeWadFile].
##
## Quake LMP palette format file used in conjunction with a Quake WAD2 format [QuakeWadFile]. 
## Not required for the Valve WAD3 format.
##
## @tutorial(Quake Wiki Palette Article): https://quakewiki.org/wiki/Quake_palette#palette.lmp

## Collection of [Color]s retrieved from the LMP palette file.
@export var colors: PackedColorArray

func _init(colors):
	self.colors = colors
