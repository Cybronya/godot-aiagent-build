# Source:  https://github.com/RodZill4/material-maker/blob/master/addons/material_maker/engine/shader_compute.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
extends MMShaderBase
class_name MMShaderCompute


var compute_shader : MMComputeShader = MMComputeShader.new()


func set_shader_from_shadercode(shader_code : MMGenBase.ShaderCode, is_32_bits : bool = false) -> bool:
	return await compute_shader.set_shader_from_shadercode(shader_code, is_32_bits)

func get_parameters() -> Dictionary:
	return compute_shader.get_parameters()

func set_parameter(name : String, value):
	compute_shader.set_parameter(name, value)

func get_texture_type(index : int = 0) -> int:
	return compute_shader.output_textures[index].type

func render(texture : MMTexture, size : int) -> bool:
	return await compute_shader.render(texture, Vector2i(size, size))

func get_render_time() -> int:
	return compute_shader.render_time
