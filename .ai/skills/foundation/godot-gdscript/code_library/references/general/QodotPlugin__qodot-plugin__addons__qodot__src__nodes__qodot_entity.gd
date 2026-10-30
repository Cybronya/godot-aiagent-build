# Source:  https://github.com/QodotPlugin/qodot-plugin/blob/master/addons/qodot/src/nodes/qodot_entity.gd
# Repo:    QodotPlugin/qodot-plugin (star 982) | License: MIT | Collected: 2026-10-29
# Commit:  4731a36dec69
class_name QodotEntity
extends QodotSpatial

export(Dictionary) var properties setget set_properties

func set_properties(new_properties : Dictionary) -> void:
	if(properties != new_properties):
		properties = new_properties
		update_properties()

func update_properties() -> void:
	pass

func get_class() -> String:
	return 'QodotEntity'
