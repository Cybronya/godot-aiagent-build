# Source:  https://github.com/hi-godot/godot-ai/blob/main/test_project/tests/mcp_custom_tool_fixture.gd
# Repo:    hi-godot/godot-ai (star 3268) | License: MIT | Collected: 2026-10-29
# Commit:  a799acfa49cd
@tool
extends RefCounted

## Fixture handler for custom-tool tests: a minimal addon handler the
## CustomToolWrapper materializes lazily from spec.script_path. `echo`
## proves clean params (no _request_id) and ctx wiring; `go_deferred`
## returns the SHARED read-only McpDispatcher.DEFERRED_RESPONSE const to
## pin the wrapper's duplicate-before-stamp behavior (#820 review F1).

var last_ctx: McpCallContext = null


func echo(params: Dictionary, ctx: McpCallContext) -> Dictionary:
	last_ctx = ctx
	return {"data": {"echo": params}}


func go_deferred(_params: Dictionary, ctx: McpCallContext) -> Dictionary:
	last_ctx = ctx
	return McpDispatcher.DEFERRED_RESPONSE
