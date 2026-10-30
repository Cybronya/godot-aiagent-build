# Source:  https://github.com/godot-extended-libraries/godot-next/blob/master/addons/godot-next/global/project_tools.gd
# Repo:    godot-extended-libraries/godot-next (star 998) | License: MIT | Collected: 2026-10-29
# Commit:  4ac438abe5b4
tool
class_name ProjectTools
extends Reference
# author: willnationsdev
# license: MIT
# description: A utility for any features useful in the context of a Godot Project.

static func try_set_setting(p_name: String, p_default_value, p_pinfo: PropertyInfo) -> bool:
	if ProjectSettings.has_setting(p_name):
		return false
	set_setting(p_name, p_default_value, p_pinfo)
	return true


static func set_setting(p_name: String, p_default_value, p_pinfo: PropertyInfo) -> void:
	ProjectSettings.set_setting(p_name, p_default_value)
	ProjectSettings.add_property_info(p_pinfo.to_dict())
	ProjectSettings.set_initial_value(p_name, p_default_value)
