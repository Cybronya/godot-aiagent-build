# Source:  https://github.com/bitbrain/pandora/blob/godot-4.x/addons/pandora/model/category.gd
# Repo:    bitbrain/pandora (star 1129) | License: MIT | Collected: 2026-10-29
# Commit:  fa48e30e6609
@tool
class_name PandoraCategory extends PandoraEntity

# not persisted but computed at runtime
var _children: Array[PandoraEntity] = []


func get_child(entity_id: String) -> PandoraEntity:
	for child in _children:
		if child.get_entity_id() == entity_id:
			return child
	return null


func get_icon_path() -> String:
	if _icon_path != "":
		return _icon_path
	if _category_id != "" and get_category() != null and get_category()._icon_path != "":
		return get_category().get_icon_path()
	return "res://addons/pandora/icons/Folder.svg"


func _delete_property(name: String) -> void:
	super._delete_property(name)
	for child in _children:
		child._delete_property(name)


func _to_string() -> String:
	return "<PandoraCategory " + str(_children) + ">"
