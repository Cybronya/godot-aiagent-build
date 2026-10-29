# Source:  https://github.com/dreadpon/godot_spatial_gardener/blob/master/testing/utility/paint_body_data.gd
# Repo:    dreadpon/godot_spatial_gardener (star 1319) | License: MIT | Collected: 2026-10-29
# Commit:  77b822f50ded
@tool
extends RefCounted


var type:String = ""
var origin:Vector3 = Vector3()
var basis:Basis = Basis()
var extent:float = 0.0




func _init(_type:String = "", _origin:Vector3 = Vector3(), _basis:Basis = Basis(), _extent:float = 0.0):
	type = _type
	origin = _origin
	basis = _basis
	extent = _extent
