# Source:  https://github.com/GDQuest/godot-steering-ai-framework/blob/master/godot/Demos/SeekFlee/Spawner.gd
# Repo:    GDQuest/godot-steering-ai-framework (star 1588) | License: MIT | Collected: 2026-10-26
# Commit:  9d7cf0deff80
extends Node2D
# Holds data to instantiate and configure a number of agent entities.

@export var Entity: PackedScene
@export var entity_count := 10
@export var entity_color := Color.BLUE
