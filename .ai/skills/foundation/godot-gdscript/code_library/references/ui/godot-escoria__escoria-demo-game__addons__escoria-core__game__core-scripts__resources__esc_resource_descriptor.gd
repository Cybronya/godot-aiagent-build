# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/escoria-core/game/core-scripts/resources/esc_resource_descriptor.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
## Describes a resource for use in the resource cache.
class_name ESCResourceDescriptor
extends Resource

## The resource being described.
var res

## Whether the resource is permanent.
var permanent: bool

## Constructor for ESCResourceDescriptor. Sets the resource and permanence flag.[br]
## [br]
## #### Parameters[br]
## [br]
## | Name | Type | Description | Required? |[br]
## |:-----|:-----|:------------|:----------|[br]
## |res_in|`Variant`|The resource to describe.|yes|[br]
## |permanent_in|`bool`|Whether the resource is permanent.|yes|[br]
## [br]
## #### Returns[br]
## [br]
## Returns nothing.
func _init(res_in, permanent_in: bool) -> void:
	res = res_in
	permanent = permanent_in
