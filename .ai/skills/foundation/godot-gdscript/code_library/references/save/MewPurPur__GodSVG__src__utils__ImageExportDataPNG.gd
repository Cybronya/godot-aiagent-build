# Source:  https://github.com/MewPurPur/GodSVG/blob/main/src/utils/ImageExportDataPNG.gd
# Repo:    MewPurPur/GodSVG (star 2784) | License: MIT | Collected: 2026-10-28
# Commit:  52ad7944fcf9
class_name ImageExportDataPNG extends ImageExportDataRaster

func get_format() -> String:
	return "png"

func image_to_buffer(image: Image) -> PackedByteArray:
	return image.save_png_to_buffer()

func load_from_buffer(image: Image, buffer: PackedByteArray) -> void:
	image.load_png_from_buffer(buffer)

func generate_and_save_image_to_path(file_path: String) -> void:
	return generate_image().save_png(file_path)
