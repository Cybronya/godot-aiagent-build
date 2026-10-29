# Source:  https://github.com/dreadpon/godot_spatial_gardener/blob/master/addons/dreadpon.spatial_gardener/arborist/stroke_handler/sh_manual.gd
# Repo:    dreadpon/godot_spatial_gardener (star 1319) | License: MIT | Collected: 2026-10-29
# Commit:  77b822f50ded
@tool
extends "stroke_handler.gd"


#-------------------------------------------------------------------------------
# Make painting changes by manually supplying data
#-------------------------------------------------------------------------------

# Meant to be used from code to add or remove instances


func _init():
	super(null, [], [], null, null, -1)
	
	set_meta("class", "SH_Manual")


func add_instance(placement: Vector3, surface_normal: Vector3, transform: Transform3D, plant_index: int, painting_changes: PaintingChanges):
	var placeform:Array = Placeform.mk(placement, surface_normal, transform)
	painting_changes.add_change(PaintingChanges.ChangeType.APPEND, plant_index, placeform, placeform) 


func add_instance_placeform(placeform: Array, plant_index: int, painting_changes: PaintingChanges):
	painting_changes.add_change(PaintingChanges.ChangeType.APPEND, plant_index, placeform, placeform) 


func remove_instance(placeform: Array, plant_index: int, painting_changes: PaintingChanges):
	painting_changes.add_change(PaintingChanges.ChangeType.ERASE, plant_index, placeform, placeform)
