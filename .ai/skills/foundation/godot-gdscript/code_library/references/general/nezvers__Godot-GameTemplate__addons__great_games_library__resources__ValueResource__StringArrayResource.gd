# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/great_games_library/resources/ValueResource/StringArrayResource.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  master
class_name StringArrayResource
extends ValueResource

@export var value:Array[String]

func set_value(_value:Array[String])->void:
	value = _value
	updated.emit()

func append(item:String)->void:
	value.append(item)
	updated.emit()

func set_item(i:int, item:String)->void:
	value[i] = item
	updated.emit()

func size()->int:
	return value.size()
