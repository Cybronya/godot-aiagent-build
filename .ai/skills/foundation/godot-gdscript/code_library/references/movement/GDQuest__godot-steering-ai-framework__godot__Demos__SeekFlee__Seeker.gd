# Source:  https://github.com/GDQuest/godot-steering-ai-framework/blob/master/godot/Demos/SeekFlee/Seeker.gd
# Repo:    GDQuest/godot-steering-ai-framework (star 1588) | License: MIT | Collected: 2026-10-26
# Commit:  9d7cf0deff80
extends CharacterBody2D

var player_agent: GSAIAgentLocation
var start_speed: float
var start_accel: float
var use_seek := true

@onready var agent := await GSAICharacterBody2DAgent.new(self)
@onready var accel := GSAITargetAcceleration.new()
@onready var seek := GSAISeek.new(agent, player_agent)
@onready var flee := GSAIFlee.new(agent, player_agent)


func _ready() -> void:
	agent.linear_acceleration_max = start_accel
	agent.linear_speed_max = start_speed


func _physics_process(delta: float) -> void:
	if not player_agent:
		return

	if use_seek:
		seek.calculate_steering(accel)
	else:
		flee.calculate_steering(accel)

	agent._apply_steering(accel, delta)
