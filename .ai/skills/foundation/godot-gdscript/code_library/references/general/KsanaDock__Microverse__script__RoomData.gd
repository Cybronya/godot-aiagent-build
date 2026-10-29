# Source:  https://github.com/KsanaDock/Microverse/blob/main/script/RoomData.gd
# Repo:    KsanaDock/Microverse (star 2502) | License: MIT | Collected: 2026-10-28
# Commit:  7a061d41ed67
extends RefCounted
class_name RoomData

var name: String
var position: Vector2
var size: Vector2
var description: String
var important_locations: Dictionary = {}

func _init(room_name: String, room_pos: Vector2, room_size: Vector2, room_desc: String):
	name = room_name
	position = room_pos
	size = room_size
	description = room_desc 
