# Source:  https://github.com/func-godot/func_godot_plugin/blob/main/addons/func_godot/src/import/quake_map_file.gd
# Repo:    func-godot/func_godot_plugin (star 883) | License: MIT | Collected: 2026-10-29
# Commit:  267ed438154c
@icon("res://addons/func_godot/icons/icon_quake_file.svg")
class_name QuakeMapFile extends Resource
## Map file that can be built by [FuncGodotMap].
## 
## Map file that can be built by a [FuncGodotMap]. Supports the Quake and Valve map formats.
## 
## @tutorial(Quake Wiki Map Format Article): https://quakewiki.org/wiki/Quake_Map_Format
## @tutorial(Valve Developer Wiki VMF Article): https://developer.valvesoftware.com/wiki/VMF_(Valve_Map_Format)

## Number of times this map file has been imported.
@export var revision: int = 0

## Raw map data.
@export_multiline var map_data: String = ""
