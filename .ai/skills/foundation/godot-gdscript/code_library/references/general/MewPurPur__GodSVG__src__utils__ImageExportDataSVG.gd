# Source:  https://github.com/MewPurPur/GodSVG/blob/main/src/utils/ImageExportDataSVG.gd
# Repo:    MewPurPur/GodSVG (star 2784) | License: MIT | Collected: 2026-10-28
# Commit:  52ad7944fcf9
class_name ImageExportDataSVG extends ImageExportData

func get_format() -> String:
	return "svg"

func image_to_buffer(_image: Image) -> PackedByteArray:
	return State.get_export_text().to_utf8_buffer()
