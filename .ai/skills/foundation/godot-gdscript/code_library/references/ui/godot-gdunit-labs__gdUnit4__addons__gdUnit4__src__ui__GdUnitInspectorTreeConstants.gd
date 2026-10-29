# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/ui/GdUnitInspectorTreeConstants.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name GdUnitInspectorTreeConstants
extends RefCounted

# the inspector panel presantation
enum TreeViewMode {
	TREE,
	FLAT,
}
# The inspector sort modes
enum SortMode {
	UNSORTED,
	NAME_ASCENDING,
	NAME_DESCENDING,
	EXECUTION_TIME,
}
enum STATE {  # gdstyle:ignore=naming/enum-name-pascal-case
	INITIAL,
	RUNNING,
	SKIPPED,
	SUCCESS,
	WARNING,
	FLAKY,
	FAILED,
	ERROR,
	ABORDED,
	ORPHAN,
}
