# Source:  https://github.com/bitbrain/beehave/blob/godot-4.x/addons/beehave/utils/utils.gd
# Repo:    bitbrain/beehave (star 3312) | License: MIT | Collected: 2026-10-26
# Commit:  fe589153fa78
@tool


static func get_plugin() -> EditorPlugin:
	var tree: SceneTree = Engine.get_main_loop()
	return tree.get_root().get_child(0).get_node_or_null("BeehavePlugin")


static func get_editor_scale() -> float:
	var plugin := get_plugin()
	if plugin:
		return plugin.get_editor_interface().get_editor_scale()
	return 1.0


static func get_frames() -> RefCounted:
	var plugin := get_plugin()
	if plugin:
		return plugin.frames
	push_error("Can't find Beehave Plugin")
	return null
