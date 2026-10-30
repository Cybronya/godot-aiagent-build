# Source:  https://github.com/godot-extended-libraries/godot-next/blob/master/addons/godot-next/resources/singletons/singleton_cache.gd
# Repo:    godot-extended-libraries/godot-next (star 998) | License: MIT | Collected: 2026-10-29
# Commit:  4ac438abe5b4
tool
extends Resource
# author: xdgamestudios
# license: MIT
# description:
#	A resource file that is preloaded into memory to allow for accessing
#	singleton classes project wide using Singletons

var _cache: Dictionary = {}
var _paths: Dictionary = {}

func get_cache() -> Dictionary:
	return _cache


func get_paths() -> Dictionary:
	return _paths
