# Source:  https://github.com/func-godot/func_godot_plugin/blob/main/addons/func_godot/src/netradiant_custom/netradiant_custom_shader.gd
# Repo:    func-godot/func_godot_plugin (star 883) | License: MIT | Collected: 2026-10-29
# Commit:  267ed438154c
@icon("res://addons/func_godot/icons/icon_godot_ranger.svg")
class_name NetRadiantCustomShader
extends Resource
## Shader resource for NetRadiant Custom configurations.
##
## Resource that gets built into a shader file that applies a special effect to a specified texture in NetRadiant Custom.

## Path to texture without extension, eg: [i]"textures/special/clip"[/i].
@export var texture_path: String

## Array of shader properties to apply to faces using [member texture_path].
@export var shader_attributes : Array[String] = ["qer_trans 0.4"]
