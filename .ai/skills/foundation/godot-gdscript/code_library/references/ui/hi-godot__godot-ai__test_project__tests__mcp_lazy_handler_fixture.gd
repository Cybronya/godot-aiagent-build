# Source:  https://github.com/hi-godot/godot-ai/blob/main/test_project/tests/mcp_lazy_handler_fixture.gd
# Repo:    hi-godot/godot-ai (star 3268) | License: MIT | Collected: 2026-10-29
# Commit:  a799acfa49cd
@tool
extends RefCounted

## Fixture for McpDispatcher lazy-registration tests (#736): a minimal
## handler the dispatcher constructs via load() + callv("new", ctor_args)
## at first dispatch. `prefix` proves ctor args arrive; `calls` proves the
## instance is cached and shared across commands of one handler key.

var prefix: String
var calls := 0
var teardown_calls := 0


func _init(fixture_prefix: String = "") -> void:
	prefix = fixture_prefix


func echo(params: Dictionary) -> Dictionary:
	return {"data": {"echo": prefix + str(params.get("value", ""))}}


func count(_params: Dictionary) -> Dictionary:
	calls += 1
	return {"data": {"calls": calls}}


func malformed(_params: Dictionary) -> Dictionary:
	return {}


func quiesce_for_script_swap() -> Dictionary:
	teardown_calls += 1
	return {"ok": true}
