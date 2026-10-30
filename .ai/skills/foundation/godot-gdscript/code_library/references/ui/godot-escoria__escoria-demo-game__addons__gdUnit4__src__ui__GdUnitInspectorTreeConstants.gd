# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/gdUnit4/src/ui/GdUnitInspectorTreeConstants.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
class_name GdUnitInspectorTreeConstants
extends RefCounted


# the inspector panel presantation
enum TREE_VIEW_MODE {
	TREE,
	FLAT
}


# The inspector sort modes
enum SORT_MODE {
	UNSORTED,
	NAME_ASCENDING,
	NAME_DESCENDING,
	EXECUTION_TIME
}


enum STATE {
	INITIAL,
	RUNNING,
	SKIPPED,
	SUCCESS,
	WARNING,
	FLAKY,
	FAILED,
	ERROR,
	ABORDED,
}
