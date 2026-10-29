# Source:  https://github.com/hi-godot/godot-ai/blob/main/test_project/tests/mcp_init_arg_fixture.gd
# Repo:    hi-godot/godot-ai (star 3268) | License: MIT | Collected: 2026-10-29
# Commit:  a799acfa49cd
@tool
class_name McpInitArgResource
extends Resource

## Fixture for the required-arg `_init()` pre-construction guard.
## A concrete @tool custom Resource whose `_init` REQUIRES an argument: in the
## editor context `can_instantiate()` returns true, so `_instantiate_resource()`
## must reject it via a pre-`scr.new()` arg-count check rather than letting
## `scr.new()` raise (which aborts mid-handler and null-cascades into a generic
## "malformed result" error). `init_count` proves `_init` never runs.
##
## Like the other mcp_*_fixture.gd files, the filename does NOT start with
## `test_`, so the suite runner ignores it as a suite while Godot still
## registers the global class_name so the test can reference it by type.

static var init_count: int = 0


func _init(required_arg) -> void:
	init_count += 1
