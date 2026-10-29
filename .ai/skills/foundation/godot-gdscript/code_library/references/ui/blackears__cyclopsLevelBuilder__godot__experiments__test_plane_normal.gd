# Source:  https://github.com/blackears/cyclopsLevelBuilder/blob/master/godot/experiments/test_plane_normal.gd
# Repo:    blackears/cyclopsLevelBuilder (star 1639) | License: MIT | Collected: 2026-10-29
# Commit:  ea41feaab5dd
extends Control


func _on_button_pressed() -> void:
	print("llll")
	print(MathUtil.estimate_plane_normal_from_points_3d([
		Vector3(1, 0, 1),
		Vector3(1, 0, 2),
		Vector3(2, 0, 2),
	]))

	print(MathUtil.estimate_plane_normal_from_points_3d([
		Vector3(1, 0, 1),
		Vector3(1, 0, 2),
		Vector3(2, 0, 2),
		Vector3(2, 0, 1),
	]))

	print(MathUtil.estimate_plane_normal_from_points_3d([
		Vector3(1, 0, 1),
		Vector3(1, 0, 2),
		Vector3(1.5, 0, 2.5),
		Vector3(2, 0, 2),
		Vector3(2, 0, 1),
	]))
	
	pass # Replace with function body.
