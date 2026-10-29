# Source:  https://github.com/dreadpon/godot_spatial_gardener/blob/master/addons/dreadpon.spatial_gardener/scene_converter/converters/base_ver_converter.gd
# Repo:    dreadpon/godot_spatial_gardener (star 1319) | License: MIT | Collected: 2026-10-29
# Commit:  77b822f50ded
extends RefCounted

enum RunMode {RECREATE, DRY, CONVERT}

const Types = preload('../converter_types.gd')
var Logger = preload('../../utility/logger.gd')

var logger




func _init():
	logger = Logger.get_for(self)


func convert_gardener(parsed_scene: Array, run_mode: int, ext_res: Dictionary, sub_res: Dictionary):
	pass
