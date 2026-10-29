# Source:  https://github.com/blackears/cyclopsLevelBuilder/blob/master/godot/addons/cyclops_level_builder/tools/gizmos/gizmo_test.gd
# Repo:    blackears/cyclopsLevelBuilder (star 1639) | License: MIT | Collected: 2026-10-29
# Commit:  ea41feaab5dd
extends Node3D

func _input(event):
	if event is InputEventMouseButton:
		var e:InputEventMouseButton = event
		
		if e.is_pressed():
	
			var cam:Camera3D = %Camera3D
			var ray_norm:Vector3 = cam.project_ray_normal(e.position)
			var ray_orig:Vector3 = cam.project_ray_origin(e.position)
			%gizmo_translate.intersect(ray_orig, ray_norm, cam)
	
	pass

# Called when the node enters the scene tree for the first time.
func _ready():
	pass # Replace with function body.


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta):
	pass
