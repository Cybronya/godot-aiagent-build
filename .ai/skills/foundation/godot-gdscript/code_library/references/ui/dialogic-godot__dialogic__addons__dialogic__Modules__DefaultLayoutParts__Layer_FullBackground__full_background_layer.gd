# Source:  https://github.com/dialogic-godot/dialogic/blob/main/addons/dialogic/Modules/DefaultLayoutParts/Layer_FullBackground/full_background_layer.gd
# Repo:    dialogic-godot/dialogic (star 6121) | License: MIT | Collected: 2026-10-26
# Commit:  701b67bbe601
@tool
extends DialogicLayoutLayer

# Awkward way of doing this, but we need a 'none' default to preserve compatiblity
# These enums are just copies of Viewport.DefaultCanvasItemTextureFilter
enum DefaultCanvasItemTextureFilter {
	USE_PROJECT_SETTINGS=-1,
	NEAREST=0,
	LINEAR=1,
	LINEAR_WITH_MIPMAPS=2,
	NEAREST_WITH_MIPMAPS=3
}

# These enums are just copies of Viewport.DefaultCanvasItemTextureRepeat
enum DefaultCanvasItemTextureRepeat {
	USE_PROJECT_SETTINGS=-1,
	DISABLED=0,
	ENABLED=1,
	REPEAT_MIRROR=2
}


@export var bg_texture_filter : DefaultCanvasItemTextureFilter = DefaultCanvasItemTextureFilter.USE_PROJECT_SETTINGS
@export var bg_texture_repeat : DefaultCanvasItemTextureRepeat = DefaultCanvasItemTextureRepeat.USE_PROJECT_SETTINGS
