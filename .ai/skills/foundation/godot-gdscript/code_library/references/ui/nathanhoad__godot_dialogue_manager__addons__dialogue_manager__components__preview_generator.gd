# Source:  https://github.com/nathanhoad/godot_dialogue_manager/blob/main/addons/dialogue_manager/components/preview_generator.gd
# Repo:    nathanhoad/godot_dialogue_manager (star 3946) | License: MIT | Collected: 2026-10-26
# Commit:  ebfc3f0cb6e1
class_name DMPreviewGenerator extends EditorResourcePreviewGenerator


const ICON: Texture2D = preload("../assets/resource.svg")


func _handles(type: String) -> bool:
	return type == "Resource"


func _generate(resource: Resource, size: Vector2i, _metadata: Dictionary) -> Texture2D:
	if resource is DialogueResource:
		var image: Image = ICON.get_image()
		image.resize(size.x, size.y, Image.INTERPOLATE_LANCZOS)
		return ImageTexture.create_from_image(image)


	return null


func _generate_small_preview_automatically() -> bool:
	return true
