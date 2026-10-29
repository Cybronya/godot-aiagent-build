# Source:  https://github.com/hi-godot/godot-ai/blob/main/test_project/tests/mcp_derived_resource_fixture.gd
# Repo:    hi-godot/godot-ai (star 3268) | License: MIT | Collected: 2026-10-29
# Commit:  a799acfa49cd
@tool
class_name McpDerivedResource
extends MyTestResource

## Two-level fixture (McpDerivedResource -> MyTestResource -> Resource) for the
## multi-level parent_class / deep-introspection get_info tests. Like the other
## mcp_*_fixture.gd files, the name does NOT start with `test_`, so the suite
## runner ignores it while Godot still registers the global class_name.

@export var extra: int = 0
