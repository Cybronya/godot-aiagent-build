class_name PathRegistry
extends RefCounted
## 路径注册表：管理命名路径列表和替换字符串映射，持久化到 ProjectSettings。
##
## 抽象自 Maaack/Godot-Game-Template (MIT)，简化：
## - 去掉编辑器文件复制/清理逻辑（编辑器专用）
## - 保留核心：路径列表管理 + 替换字符串映射 + ProjectSettings 持久化
## - 静态 API，无需实例化

const SETTINGS_PREFIX := "path_registry/"


static func get_paths(name: String) -> Array[String]:
	return ProjectSettings.get_setting(SETTINGS_PREFIX + name, []) as Array[String]


static func set_paths(name: String, paths: Array[String]) -> void:
	ProjectSettings.set_setting(SETTINGS_PREFIX + name, paths)
	ProjectSettings.save()


static func add_path(name: String, path: String) -> void:
	var paths := get_paths(name)
	if not paths.has(path):
		paths.append(path)
	set_paths(name, paths)


static func remove_path(name: String, path: String) -> void:
	var paths := get_paths(name)
	paths.erase(path)
	set_paths(name, paths)


static func has_path(name: String, path: String) -> bool:
	return get_paths(name).has(path)


static func get_replace_strings() -> Dictionary:
	return ProjectSettings.get_setting(SETTINGS_PREFIX + "replace_strings", {}) as Dictionary


static func set_replace_string(find: String, replace: String) -> void:
	var map := get_replace_strings()
	map[find] = replace
	ProjectSettings.set_setting(SETTINGS_PREFIX + "replace_strings", map)
	ProjectSettings.save()


static func remove_replace_string(find: String) -> void:
	var map := get_replace_strings()
	map.erase(find)
	ProjectSettings.set_setting(SETTINGS_PREFIX + "replace_strings", map)
	ProjectSettings.save()
