# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/escoria-core/testing/ashes/interpreter/support/commands/test_delayed_set_global.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
class_name TestDelayedSetGlobalCommand
extends ESCBaseCommand


func configure() -> ESCCommandArgumentDescriptor:
	return ESCCommandArgumentDescriptor.new(
		3,
		[[TYPE_STRING], [TYPE_STRING], [TYPE_FLOAT, TYPE_INT]],
		[null, null, null]
	)


func run(command_params: Array) -> int:
	await escoria.get_tree().create_timer(float(command_params[2])).timeout
	escoria.globals_manager.set_global(command_params[0], command_params[1])
	return ESCExecution.RC_OK
