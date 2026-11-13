# Source:  https://github.com/OctoD/godot-gameplay-systems/blob/main/addons/godot_gameplay_systems/attributes_and_abilities/objects/activation_event.gd
# Repo:    OctoD/godot-gameplay-systems (star 746) | License: MIT | Collected: 2026-10-31
# Commit:  9349931cc7a5
## Is the activation event object sent to an ability
##
## This class is used to pass down to an [Ability] all the informations needed for it's own execution. 

class_name ActivationEvent extends RefCounted

## It's the executing [AbilityContainer] which passed the [ActivationEvent] to an [Ability]
var ability_container: AbilityContainer
## It's the [GameplayAttributeMap] bound to an [AbilityContainer]
var attribute_map: GameplayAttributeMap
## Returns a [Node] as the owning character
var character: Node:
	get:
		if has_attribute_map and attribute_map.owning_character != null and not attribute_map.owning_character.is_empty():
			return attribute_map.get_node(attribute_map.owning_character)
		return null
## [code]true[/code] if [member ActivationEvent.ability_container] is not [code]null[/code], [code]false[/code] otherwise.
var has_ability_container: bool:
	get:
		return ability_container != null
## [code]true[/code] if [member ActivationEvent.attribute_map] is not [code]null[/code], [code]false[/code] otherwise.
var has_attribute_map: bool:
	get:
		return attribute_map != null
## Returns if the [ActivationEvent] has been created with some tags
var has_tags: bool:
	get:
		return tags.size() > 0
## These are the tags set when the [Ability] has been activated using [method Ability.try_activate]
var tags: Array[String] = []


func _init(_ability_container: AbilityContainer) -> void:
	ability_container = _ability_container
	attribute_map = _ability_container.gameplay_attribute_map
	tags = _ability_container.tags.duplicate()


## Gets an [AttributeSpec] attribute by it's name
func get_attribute(attribute_name: String) -> AttributeSpec:
	if has_attribute_map:
		return attribute_map.get_attribute_by_name(attribute_name)
	return null
