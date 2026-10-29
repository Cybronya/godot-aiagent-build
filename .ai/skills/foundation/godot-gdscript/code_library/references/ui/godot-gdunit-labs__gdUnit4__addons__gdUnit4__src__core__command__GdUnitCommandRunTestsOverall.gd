# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/core/command/GdUnitCommandRunTestsOverall.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name GdUnitCommandRunTestsOverall
extends GdUnitCommandTestSession

const ID := "Run Tests Overall"


func _init() -> void:
	super(ID, GdUnitShortcut.ShortCut.RUN_TESTS_OVERALL)
	icon = GdUnitUiTools.get_run_overall_icon()


func execute(..._parameters: Array) -> void:
	var tests_to_execute := await GdUnitTestDiscoverer.run()
	super.execute(tests_to_execute, true)
