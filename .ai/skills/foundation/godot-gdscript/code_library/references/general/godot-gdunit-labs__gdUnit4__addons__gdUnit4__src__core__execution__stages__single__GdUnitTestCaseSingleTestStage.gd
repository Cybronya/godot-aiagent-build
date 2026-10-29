# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/core/execution/stages/single/GdUnitTestCaseSingleTestStage.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name GdUnitTestCaseSingleTestStage
extends IGdUnitExecutionStage
## The single test case execution stage.[br]


## Executes a single test case 'test_<name>()'.[br]
## It executes synchronized following stages[br]
##  -> test_case() [br]
func _execute(context: GdUnitExecutionContext) -> void:
	await context.test_case.execute()
