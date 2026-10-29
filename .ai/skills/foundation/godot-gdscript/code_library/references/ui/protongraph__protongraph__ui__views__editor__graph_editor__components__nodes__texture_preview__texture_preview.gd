# Source:  https://github.com/protongraph/protongraph/blob/main/ui/views/editor/graph_editor/components/nodes/texture_preview/texture_preview.gd
# Repo:    protongraph/protongraph (star 1749) | License: MIT | Collected: 2026-10-29
# Commit:  1e2411a29464
class_name TexturePreviewComponent
extends GraphNodeUiComponent


const TexturePreviewUiScene := preload("./texture_preview_ui.tscn")


var _preview: TexturePreviewUi


func initialize(label_name: String, type: int, opts := SlotOptions.new()) -> void:
	super(label_name, type, opts)

	_preview = TexturePreviewUiScene.instantiate()
	add_child(_preview)


func get_value():
	return null


func set_value(value: Variant) -> void:
	if value is Array and not value.is_empty():
		value = value[0]

	_preview.show_preview_for(value)
