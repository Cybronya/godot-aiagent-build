# Source:  https://github.com/viniciusgerevini/godot-aseprite-wizard/blob/godot_4/addons/AsepriteWizard/creators/static_texture/texture_creator.gd
# Repo:    viniciusgerevini/godot-aseprite-wizard (star 1396) | License: MIT | Collected: 2026-10-29
# Commit:  18ebea9868ea
@tool
extends "../base_sprite_resource_creator.gd"

func load_texture(target_node: Node, aseprite_files: Dictionary, options: Dictionary) -> void:
	var source_file = aseprite_files.data_file
	var sprite_sheet = aseprite_files.sprite_sheet
	var data = _aseprite_file_exporter.load_json_content(source_file)
	var texture

	if options.get("should_create_portable_texture", false):
		texture = _load_compressed_texture(sprite_sheet)
	else:
		texture = ResourceLoader.load(sprite_sheet)

	if not data.is_ok:
		logger.error("Failed to load aseprite source", source_file)
		return

	if options.slice == "":
		target_node.texture = texture
	else:
		var region = _aseprite.get_slice_rect(data.content, options.slice)
		var atlas_texture := AtlasTexture.new()
		atlas_texture.atlas = texture
		atlas_texture.region = region
		target_node.texture = atlas_texture

	if target_node is CanvasItem:
		target_node.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	else:
		target_node.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
