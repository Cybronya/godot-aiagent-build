# Source:  https://github.com/OctoD/godot-gameplay-systems/blob/main/addons/godot_gameplay_systems/attributes_and_abilities/resources/stop_effect_at_value.gd
# Repo:    OctoD/godot-gameplay-systems (star 746) | License: MIT | Collected: 2026-10-31
# Commit:  9349931cc7a5
class_name StopEffectAtValue extends AttributeEffectCondition

@export_category("Rule")
## The value to stop at
@export var value_to_stop_at: float = 0.0
## The value condition
@export_enum("Equal", "Greater than", "Lesser than", "Greater Equal to", "Less Equal To") var operator = 0


func should_apply(attribute_effect: AttributeEffect, effect: GameplayEffect, gameplay_attributes: GameplayAttributeMap) -> bool:
	var attribute = gameplay_attributes.get_attribute_by_name(attribute_effect.attribute_name)

	if attribute == null:
		return false

	match operator:
		0: 	return attribute.current_value == value_to_stop_at
		1:	return attribute.current_value > value_to_stop_at
		2:	return attribute.current_value < value_to_stop_at
		3:	return attribute.current_value >= value_to_stop_at
		4:	return attribute.current_value <= value_to_stop_at


	return false
