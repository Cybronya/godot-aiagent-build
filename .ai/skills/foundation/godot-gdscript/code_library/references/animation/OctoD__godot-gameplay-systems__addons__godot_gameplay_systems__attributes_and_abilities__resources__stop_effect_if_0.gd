# Source:  https://github.com/OctoD/godot-gameplay-systems/blob/main/addons/godot_gameplay_systems/attributes_and_abilities/resources/stop_effect_if_0.gd
# Repo:    OctoD/godot-gameplay-systems (star 746) | License: MIT | Collected: 2026-10-31
# Commit:  9349931cc7a5
class_name StopEffectIf0 extends AttributeEffectCondition


func should_apply(attribute_effect: AttributeEffect, effect: GameplayEffect, gameplay_attributes: GameplayAttributeMap) -> bool:
	var attribute = gameplay_attributes.get_attribute_by_name(attribute_effect.attribute_name)

	if attribute:
		return attribute.current_value > 0

	return false
