# Source:  https://github.com/OctoD/godot-gameplay-systems/blob/main/addons/godot_gameplay_systems/interactables/nodes/2d/interactable_area_2d.gd
# Repo:    OctoD/godot-gameplay-systems (star 746) | License: MIT | Collected: 2026-10-31
# Commit:  9349931cc7a5
@icon("res://addons/godot_gameplay_systems/interactables/assets/InteractableArea2D.png")
@tool
class_name InteractableArea2D extends Area2D

@export_category("Interaction")
@export var interaction: Interaction = null
