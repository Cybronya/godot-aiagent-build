class_name utils


static func guess_editor_name(file_name: String) -> String:
	var base := _strip_known_extensions(file_name.get_file())

	var lower := base.to_lower()

	# Allow versions like 4.1, 4.1.1, 4.1.1.1, etc.
	var re_version := RegEx.new()
	re_version.compile(r"godot[-_]?v?(\d+(?:\.\d+)+)") 

	var re_channel := RegEx.new()
	re_channel.compile(r"-(pre-alpha|alpha|beta|rc|stable|dev)(\d*)")

	var version := ""
	var channel := ""
	var channel_num := ""
	var re_mono := RegEx.new()
	re_mono.compile(r"(?:^|[-_.])mono(?:$|[-_.])")
	var mono := re_mono.search(lower) != null

	var m := re_version.search(lower)
	if m:
		version = m.get_string(1)

	var c := re_channel.search(lower)
	if c:
		channel = c.get_string(1)
		channel_num = c.get_string(2)

	if version == "":
		# Fallback: grab first version-looking substring
		var re_any_ver := RegEx.new()
		re_any_ver.compile(r"(\d+(?:\.\d+)+)")
		var mv := re_any_ver.search(lower)
		if mv:
			version = mv.get_string(1)

	if version == "":
		return base # fallback

	var suffix := ""
	if channel != "":
		suffix = " " + channel
		if channel_num != "":
			suffix += channel_num

	var name := "Godot v%s%s" % [version, suffix]
	if mono:
		name += " mono"

	return name


static func _strip_known_extensions(base: String) -> String:
	var lower_base := base.to_lower()
	var compound_extensions: PackedStringArray = [
		".exe.zip", ".universal.dmg", ".universal.zip",
		".x86_64", ".x86_32", ".arm64", ".arm32",
	]
	for ext: String in compound_extensions:
		if lower_base.ends_with(ext):
			return base.substr(0, base.length() - ext.length())
	var simple_extensions: PackedStringArray = [
		".exe", ".zip", ".dmg", ".tpz", ".aab", ".apk", ".aar",
		".xz", ".sha256", ".tar",
	]
	for ext: String in simple_extensions:
		if lower_base.ends_with(ext):
			return base.substr(0, base.length() - ext.length())
	return base


static func find_project_godot_files(dir_path: String) -> Array[edir.DirListResult]:
	var project_configs := edir.list_recursive(
		ProjectSettings.globalize_path(dir_path), 
		false,
		(func(x: edir.DirListResult) -> bool: 
			return x.is_file and x.file == "project.godot"),
		(func(x: String) -> bool: 
			return not x.get_file().begins_with("."))
	)
	return project_configs


static func response_to_json(response: Variant, safe:=true) -> Variant:
	var body := response[3] as PackedByteArray
	var string := body.get_string_from_utf8()
	if safe:
		return parse_json_safe(string)
	else:
		return JSON.parse_string(string)


static func parse_json_safe(string: String) -> Variant:
	var json := JSON.new()
	var err := json.parse(string)
	if err != OK:
		return null
	else:
		return json.data


static func fit_height(max_height: float, cur_size: Vector2i, callback: Callable) -> void:
	var scale_ratio := max_height / (cur_size.y * Config.EDSCALE)
	if scale_ratio < 1:
		callback.call(Vector2i(
			cur_size.x * Config.EDSCALE * scale_ratio,
			cur_size.y * Config.EDSCALE * scale_ratio
		))


static func disconnect_all(obj: Object) -> void:
	for obj_signal in obj.get_signal_list():
		for connection in obj.get_signal_connection_list(obj_signal.name as StringName):
			obj.disconnect(obj_signal.name as StringName, connection.callable as Callable)


static func prop_is_readonly() -> void:
	assert(false, "Property is readonly")


static func not_implemeted() -> Variant:
	assert(false, "Not Implemented")
	return null


static func empty_func() -> void:
	pass


static func obj_has_method(obj: Variant, method: StringName) -> bool:
	if obj is Object:
		return (obj as Object).has_method(method)
	else:
		return false
