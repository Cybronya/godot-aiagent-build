# Source:  https://github.com/RodZill4/material-maker/blob/master/addons/material_maker/engine/shader_material.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
extends MMShaderBase
class_name MMShaderMaterial


var material : ShaderMaterial


func _init(m : ShaderMaterial = null):
	material = m
	if material == null:
		material = ShaderMaterial.new()
	if material.shader == null:
		material.shader = Shader.new()

func set_shader(shader_code : String) -> bool:
	# Remove the Texture2D references, otherwise they will remain
	if material.shader != null and not material.shader.code.is_empty():
		for p in material.get_property_list():
			if p.hint_string == "Texture2D" and p.name.begins_with("shader_parameter/"):
				material.set_shader_parameter(p.name.right(-17), null)
	var shader : Shader = Shader.new()
	shader.code = shader_code
	material.shader = shader
	return true

func get_parameters() -> Dictionary:
	var rv : Dictionary = {}
	for p in material.get_property_list():
		if p.name.left(17) != "shader_parameter/":
			continue
		var parameter_name : String = p.name.right(-17)
		rv[parameter_name] = material.get_shader_parameter(parameter_name)
	return rv

func set_parameter(name : String, value) -> void:
	if value is MMTexture:
		material.set_shader_parameter(name, await value.get_texture())
	else:
		material.set_shader_parameter(name, value)
