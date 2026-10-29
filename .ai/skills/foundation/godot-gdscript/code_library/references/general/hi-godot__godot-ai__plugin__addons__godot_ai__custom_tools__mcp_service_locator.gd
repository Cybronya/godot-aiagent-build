# Source:  https://github.com/hi-godot/godot-ai/blob/main/plugin/addons/godot_ai/custom_tools/mcp_service_locator.gd
# Repo:    hi-godot/godot-ai (star 3268) | License: MIT | Collected: 2026-10-29
# Commit:  a799acfa49cd
@tool
class_name McpServiceLocator
extends RefCounted

var _connection: McpConnection = null
var _log_buffer: McpLogBuffer = null

func setup(connection: McpConnection, log_buffer: McpLogBuffer) -> void:
	_connection = connection
	_log_buffer = log_buffer

func get_connection() -> McpConnection:
	return _connection

func get_log_buffer() -> McpLogBuffer:
	return _log_buffer
