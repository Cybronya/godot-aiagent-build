# Source:  https://github.com/RodZill4/material-maker/blob/master/addons/material_maker/engine/paths.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
@tool
class_name MMPaths

const WEBSITE_ADDRESS : String = "https://www.materialmaker.org"
#const WEBSITE_ADDRESS : String = "http://localhost:3000"

const STD_GENDEF_PATH = "res://addons/material_maker/nodes"

static func get_resource_dir() -> String:
	if Engine.is_editor_hint():
		return ProjectSettings.globalize_path("res://material_maker")
	return OS.get_executable_path().get_base_dir()

static func get_nodes_paths() -> Array:
	return [ STD_GENDEF_PATH, get_resource_dir()+"/nodes", "user://shared_nodes" ]
