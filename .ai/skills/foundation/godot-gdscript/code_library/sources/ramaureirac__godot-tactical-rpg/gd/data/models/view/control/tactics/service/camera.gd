class_name TacticsControlsCameraService
extends RefCounted
## Service class for managing camera controls in the Tactics game.

## Reference to the TacticsCameraResource.
var t_cam: TacticsCameraResource


## Initializes the TacticsControlsCameraService with the necessary camera resource.
func _init(_t_cam: TacticsCameraResource) -> void:
	t_cam = _t_cam


## Handles camera movement based on input.
## The movement is determined by the input strengths for left, right, forward, and backward actions.
func move_camera(delta: float, is_joystick: bool) -> void:
	var h: float = -Input.get_action_strength("camera_left") + Input.get_action_strength("camera_right")
	var v: float = Input.get_action_strength("camera_forward") - Input.get_action_strength("camera_backwards")
	
	t_cam.move_camera(h, v, is_joystick, delta)
