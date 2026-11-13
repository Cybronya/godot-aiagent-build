# Source:  https://github.com/MenacingMecha/godot-psx-style-demo/blob/master/world/orbit_camera.gd
# Repo:    MenacingMecha/godot-psx-style-demo (star 741) | License: MIT | Collected: 2026-10-31
# Commit:  91bd24988f70
extends Node3D

const ROTATION_SPEED := 1.0

var _time = 0.0

@onready var _default_y_rotation: float = rotation.y


func _process(p_delta: float):
	self._time += p_delta
	self.rotation.y = self._default_y_rotation + self._time * ROTATION_SPEED


func restart():
	self.rotation.y = self._default_y_rotation
	self._time = 0.0
