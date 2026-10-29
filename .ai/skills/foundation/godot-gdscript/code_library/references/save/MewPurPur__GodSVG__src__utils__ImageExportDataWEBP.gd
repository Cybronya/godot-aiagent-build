# Source:  https://github.com/MewPurPur/GodSVG/blob/main/src/utils/ImageExportDataWEBP.gd
# Repo:    MewPurPur/GodSVG (star 2784) | License: MIT | Collected: 2026-10-28
# Commit:  52ad7944fcf9
class_name ImageExportDataWEBP extends ImageExportDataRaster

@export var lossy := false:
	set(new_value):
		if new_value != lossy:
			lossy = new_value
			emit_changed()

@export var quality := 0.75:
	set(new_value):
		if new_value != quality:
			quality = new_value
			emit_changed()


func get_format() -> String:
	return "webp"

func image_to_buffer(image: Image) -> PackedByteArray:
	return image.save_webp_to_buffer(lossy, quality)

func load_from_buffer(image: Image, buffer: PackedByteArray) -> void:
	image.load_webp_from_buffer(buffer)

func generate_and_save_image_to_path(file_path: String) -> void:
	return generate_image().save_webp(file_path, lossy, quality)
