# Source:  https://github.com/godot-extended-libraries/godot-next/blob/master/addons/godot-next/global/editor_tools.gd
# Repo:    godot-extended-libraries/godot-next (star 998) | License: MIT | Collected: 2026-10-29
# Commit:  4ac438abe5b4
tool
class_name EditorTools
extends Reference
# author: willnationsdev
# description: A utility for any features useful in the context of the Editor.

static func is_in_edited_scene(p_node: Node):
	if not p_node.is_inside_tree():
		return false
	var edited_scene := p_node.get_tree().edited_scene_root
	if p_node == edited_scene:
		return true
	return edited_scene.is_parent_of(p_node)
