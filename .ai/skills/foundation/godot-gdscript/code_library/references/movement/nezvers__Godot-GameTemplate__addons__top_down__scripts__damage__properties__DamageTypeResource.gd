# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/damage/properties/DamageTypeResource.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  master
class_name DamageTypeResource
extends Resource

@export var value:float

enum DamageType {
	PHYSICAL, 
	FIRE, 
	ICE, 
	LIGHTNING, 
	POISON, 
	ACID, 
	MAGNETIC, 
	BLOOD, 
	DARK, 
	ARCANE,
	## Last one for fetching total count
	COUNT,
	}

@export var type:DamageType
