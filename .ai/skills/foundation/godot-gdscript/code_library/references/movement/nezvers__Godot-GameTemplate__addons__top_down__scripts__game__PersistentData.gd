# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/game/PersistentData.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
extends Node

@export var saveable_list:Array[SaveableResource]

## Hold any data. Main use is to keep resources in memory
@export var data:Dictionary
