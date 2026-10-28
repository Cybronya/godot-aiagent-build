# Source:  https://github.com/MewPurPur/GodSVG/blob/main/src/config_classes/PreviewPresentationLossless.gd
# Repo:    MewPurPur/GodSVG (star 2784) | License: MIT | Collected: 2026-10-28
# Commit:  main
class_name PreviewPresentationLossless extends PreviewPresentation

func get_presentation_name() -> String:
	return Translator.translate("Lossless")

func get_extra_info() -> String:
	return Translator.translate("Lossless")

func get_equivalent_export_data() -> ImageExportData:
	return ImageExportDataPNG.new()
