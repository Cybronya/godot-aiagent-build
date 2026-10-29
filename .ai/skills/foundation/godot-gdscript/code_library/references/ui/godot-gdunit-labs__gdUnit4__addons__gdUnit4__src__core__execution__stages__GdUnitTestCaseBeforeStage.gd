# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/core/execution/stages/GdUnitTestCaseBeforeStage.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name GdUnitTestCaseBeforeStage
extends IGdUnitExecutionStage
## The test case startup hook implementation.[br]
## It executes the 'test_before()' block from the test-suite.

var _call_stage: bool


func _init(call_stage := true) -> void:
	_call_stage = call_stage


func _execute(context: GdUnitExecutionContext) -> void:
	var test_suite := context.test_suite

	if _call_stage:
		@warning_ignore("redundant_await")
		await test_suite.before_test()

	context.error_monitor_start()
