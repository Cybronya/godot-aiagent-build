# Source:  https://github.com/yurineko73/Godot-MCP-Native/blob/main/addons/godot_mcp/native_mcp/tool_execution_context.gd
# Repo:    yurineko73/Godot-MCP-Native (star 862) | License: MIT | Collected: 2026-10-29
# Commit:  eef4807190e7
class_name ToolExecutionContext
extends RefCounted

var caller: String = "mcp"
var request_id: String = ""
var dry_run: bool = false
var apply_confirmed: bool = false
var allow_open_world: bool = false
var max_bytes: int = 65536
var fields: PackedStringArray = PackedStringArray()
var limit: int = 0
var cursor: String = ""
var depth: int = -1
