# Source:  https://github.com/OctoD/godot-gameplay-systems/blob/main/addons/godot_gameplay_systems/attributes_and_abilities/resources/attribute.gd
# Repo:    OctoD/godot-gameplay-systems (star 746) | License: MIT | Collected: 2026-10-31
# Commit:  9349931cc7a5
class_name AttributeResource extends Resource

@export_category("Attribute")
## Is the attribute name
@export var attribute_name := ""
## Is the attribute minimum value
@export var minimum_value := 0.0
## Is the attribute maximum value
@export var maximum_value := 0.0
## Is the attribute initial value
@export var current_value := 0.0


func _init(p_attribute_name: String = "", p_minimum_value: float = 0.0, p_maximum_value: float = 0.0, p_current_value: float = 0.0) -> void:
	attribute_name = p_attribute_name
	minimum_value = p_minimum_value
	maximum_value = p_maximum_value
	current_value = p_current_value
