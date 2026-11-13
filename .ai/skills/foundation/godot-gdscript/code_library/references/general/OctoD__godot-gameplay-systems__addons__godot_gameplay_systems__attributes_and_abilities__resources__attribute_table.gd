# Source:  https://github.com/OctoD/godot-gameplay-systems/blob/main/addons/godot_gameplay_systems/attributes_and_abilities/resources/attribute_table.gd
# Repo:    OctoD/godot-gameplay-systems (star 746) | License: MIT | Collected: 2026-10-31
# Commit:  9349931cc7a5
@icon("res://addons/godot_gameplay_systems/attributes_and_abilities/assets/AttributeTable.svg")

class_name AttributeTable extends Resource

## Represents a table of attributes

@export_category("Attributes")
## The list of attributes
@export var attributes : Array[String] = []


func _init(p_attributes: Array[String] = []) -> void:
	attributes = p_attributes
