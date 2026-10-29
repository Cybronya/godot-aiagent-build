# Source:  https://github.com/gaea-godot/gaea/blob/2.0/addons/gaea/runtime/resources/materials/distribution/pointwise_random_material.gd
# Repo:    gaea-godot/gaea (star 1663) | License: MIT | Collected: 2026-10-28
# Commit:  79461f6491e7
@tool
class_name PointwiseRandomGaeaMaterial
extends PickRandomGaeaMaterial
## A material that randomly selects between multiple materials.
##
## Each material can have a different weight assigned to it, which affects its probability of being selected.[br]
## [br]
## Example:[br]
## [codeblock]
## var random_material = PointwiseRandomGaeaMaterial.new()
## random_material.materials = [grass_material, stone_material]
## random_material.weights = [70.0, 30.0]
## # 70% chance for grass, 30% for stone
## [/codeblock]


func _is_sampled() -> bool:
	return true


func _get_sampled_resource(rng: RandomNumberGenerator, _value: float) -> GaeaMaterial:
	return get_resource(rng)
