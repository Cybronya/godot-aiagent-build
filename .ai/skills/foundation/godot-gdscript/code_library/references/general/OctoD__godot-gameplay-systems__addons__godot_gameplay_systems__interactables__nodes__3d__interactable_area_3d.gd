# Source:  https://github.com/OctoD/godot-gameplay-systems/blob/main/addons/godot_gameplay_systems/interactables/nodes/3d/interactable_area_3d.gd
# Repo:    OctoD/godot-gameplay-systems (star 746) | License: MIT | Collected: 2026-10-31
# Commit:  9349931cc7a5
@icon("res://addons/godot_gameplay_systems/interactables/assets/InteractableArea3D.png")
@tool
class_name InteractableArea3D extends Area3D

@export_category("Interaction")
@export var interaction: Interaction = null
