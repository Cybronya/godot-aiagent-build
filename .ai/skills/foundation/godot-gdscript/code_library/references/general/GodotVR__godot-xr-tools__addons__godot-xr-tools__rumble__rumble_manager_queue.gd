# Source:  https://github.com/GodotVR/godot-xr-tools/blob/master/addons/godot-xr-tools/rumble/rumble_manager_queue.gd
# Repo:    GodotVR/godot-xr-tools (star 740) | License: MIT | Collected: 2026-10-31
# Commit:  6c6189bdfcdf
class_name XRToolsRumbleManagerQueue
extends Resource

## XR Tools Rumble Manager Queue
##
## Used to sort rumble events in order of arrival

## All currently-active events
var events: Dictionary[Variant, XRToolsRumbleEvent]

## All currently-active events' remaining time
var time_remaining: Dictionary[Variant, int]


func _init() -> void:
	events = {}
	time_remaining = {}
