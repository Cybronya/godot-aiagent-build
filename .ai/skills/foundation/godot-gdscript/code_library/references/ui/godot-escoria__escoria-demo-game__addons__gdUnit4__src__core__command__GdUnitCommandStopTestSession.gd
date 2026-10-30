# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/gdUnit4/src/core/command/GdUnitCommandStopTestSession.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
class_name GdUnitCommandStopTestSession
extends GdUnitBaseCommand

const ID := "Stop Test Session"


var _test_session_command: GdUnitCommandTestSession


func _init(test_session_command: GdUnitCommandTestSession) -> void:
	super(ID, GdUnitShortcut.ShortCut.STOP_TEST_RUN)
	icon = GdUnitUiTools.get_icon("Stop")
	_test_session_command = test_session_command


func is_running() -> bool:
	return _test_session_command.is_running()


func execute(..._parameters: Array) -> void:
	await _test_session_command.stop()
