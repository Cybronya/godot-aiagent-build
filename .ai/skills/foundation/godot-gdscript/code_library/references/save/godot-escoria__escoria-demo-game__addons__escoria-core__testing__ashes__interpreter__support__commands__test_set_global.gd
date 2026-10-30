# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/escoria-core/testing/ashes/interpreter/support/commands/test_set_global.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
class_name TestSetGlobalCommand
extends ESCBaseCommand


func configure() -> ESCCommandArgumentDescriptor:
	return ESCCommandArgumentDescriptor.new(
		2,
		[[TYPE_STRING], [TYPE_STRING]],
		[null, null]
	)


func run(command_params: Array) -> int:
	escoria.globals_manager.set_global(command_params[0], command_params[1])
	return ESCExecution.RC_OK
