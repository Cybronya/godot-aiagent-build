# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/pickups/ItemResource.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
class_name ItemResource
extends Resource

@export var icon:Texture2D

@export var scene_path:String

enum ItemType {
	WEAPON,
}

@export var type:ItemType

@export var unlocked:bool
