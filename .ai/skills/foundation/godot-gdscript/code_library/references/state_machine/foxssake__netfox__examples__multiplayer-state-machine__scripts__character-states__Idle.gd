# Source:  https://github.com/foxssake/netfox/blob/main/examples/multiplayer-state-machine/scripts/character-states/Idle.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
extends RewindableState

@export var character: CharacterBody3D
@export var input: PlayerInputStateMachine

func display_enter(_previous, _t):
	character.color = Color.WHITE

func tick(delta, tick, is_fresh):
	character.velocity *= NetworkTime.physics_factor
	character.move_and_slide()
	character.velocity /= NetworkTime.physics_factor

	if input.movement != Vector3.ZERO:
		state_machine.transition(&"Move")
	elif input.jump:
		state_machine.transition(&"Jump")
