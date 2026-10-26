# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/actor/PushResource.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  master
## Signals an intention to be pushed
class_name PushResource
extends SaveableResource

signal impulse_event(impulse:Vector2)

func add_impulse(impulse:Vector2)->void:
	impulse_event.emit(impulse)
