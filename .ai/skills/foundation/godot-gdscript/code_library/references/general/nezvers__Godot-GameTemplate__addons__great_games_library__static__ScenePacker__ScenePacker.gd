# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/great_games_library/static/ScenePacker/ScenePacker.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  master
class_name ScenePacker

static func create_package(_node:Node, makeLocal:bool = false)->PackedScene:
	set_owner(_node, _node, makeLocal)
	var package: = PackedScene.new()
# warning-ignore:return_value_discarded
	package.pack(_node)
	return package

static func set_owner(_node:Node, _owner:Node, makeLocal:bool = false)->void:
	for child in _node.get_children():
		if makeLocal: #everything is owned
			child.owner = _owner
		else:
			if child.owner == null: #only null is owned
				child.owner = _owner
		set_owner(child, _owner, makeLocal)
