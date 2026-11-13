# Source:  https://github.com/GodotVR/godot-xr-tools/blob/master/addons/godot-xr-tools/rumble/rumble_event.gd
# Repo:    GodotVR/godot-xr-tools (star 740) | License: MIT | Collected: 2026-10-31
# Commit:  6c6189bdfcdf
@icon("res://addons/godot-xr-tools/editor/icons/rumble.svg")
class_name XRToolsRumbleEvent
extends Resource

## XR Tools Rumble Event Resource

## Strength of the rumbling
@export_range(0, 1, 0.10) var magnitude: float = 0.5

## Whether the rumble can be active during a tree pause
@export var active_during_pause: bool = false

@export_category("Timing")

## Whether the rumble continues until cleared
@export var indefinite: bool = false

## Time to rumble (unless indefinite)
@export_range(10, 4000, 10) var duration_ms: int = 300
