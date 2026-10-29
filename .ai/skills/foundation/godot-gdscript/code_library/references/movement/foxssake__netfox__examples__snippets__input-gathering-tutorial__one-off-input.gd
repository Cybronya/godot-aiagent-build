# Source:  https://github.com/foxssake/netfox/blob/main/examples/snippets/input-gathering-tutorial/one-off-input.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
extends BaseNetInput

var is_jumping: bool = false
var _is_jumping_buffer: bool = false

func _ready():
	super()
	NetworkTime.after_tick.connect(func(_dt, _t): _gather_always())

func _process(_dt: float) -> void:
	if Input.is_action_just_pressed("move_jump"):
		_is_jumping_buffer = true

func _gather_always():
	is_jumping = _is_jumping_buffer
	_is_jumping_buffer = false
