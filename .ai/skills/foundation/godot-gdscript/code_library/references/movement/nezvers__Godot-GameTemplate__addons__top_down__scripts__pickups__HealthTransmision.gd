# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/pickups/HealthTransmision.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  master
class_name HealthTransmision
extends TransmissionResource

@export var value:float

func set_value(_value:float)->void:
	value = _value
	updated.emit()

## Receiver need to provide a reference to a ResourceNode
## Override this function with specific use.
## Should result with a state change
func process(resource_node:ResourceNode)->void:
	var _health_resource:HealthResource = resource_node.get_resource(transmission_name)
	if _health_resource.is_full() || _health_resource.is_dead:
		failed()
		return
	_health_resource.add_hp(value)
	success()
