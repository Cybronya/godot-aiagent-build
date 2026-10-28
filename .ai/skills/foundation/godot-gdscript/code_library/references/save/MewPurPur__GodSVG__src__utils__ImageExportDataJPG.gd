# Source:  https://github.com/MewPurPur/GodSVG/blob/main/src/utils/ImageExportDataJPG.gd
# Repo:    MewPurPur/GodSVG (star 2784) | License: MIT | Collected: 2026-10-28
# Commit:  main
class_name ImageExportDataJPG extends ImageExportDataRaster

@export var quality := 0.75:
	set(new_value):
		if new_value != quality:
			quality = new_value
			emit_changed()


func _init() -> void:
	background_color = Color.WHITE

func get_format() -> String:
	return "jpg"

func image_to_buffer(image: Image) -> PackedByteArray:
	return image.save_jpg_to_buffer(quality)

func load_from_buffer(image: Image, buffer: PackedByteArray) -> void:
	image.load_jpg_from_buffer(buffer)

func generate_and_save_image_to_path(file_path: String) -> void:
	return generate_image().save_jpg(file_path, quality)
