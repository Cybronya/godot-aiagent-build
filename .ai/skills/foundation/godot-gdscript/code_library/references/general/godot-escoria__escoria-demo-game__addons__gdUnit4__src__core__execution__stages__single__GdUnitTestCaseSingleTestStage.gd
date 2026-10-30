# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/gdUnit4/src/core/execution/stages/single/GdUnitTestCaseSingleTestStage.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
## The single test case execution stage.[br]
class_name GdUnitTestCaseSingleTestStage
extends IGdUnitExecutionStage


## Executes a single test case 'test_<name>()'.[br]
## It executes synchronized following stages[br]
##  -> test_case() [br]
func _execute(context: GdUnitExecutionContext) -> void:
	await context.test_case.execute()
	await context.gc(GdUnitExecutionContext.GC_ORPHANS_CHECK.TEST_CASE)
