# Source:  https://github.com/Ark2000/PankuConsole/blob/master/addons/panku_console/modules/texture_viewer/texture_viewer.gd
# Repo:    Ark2000/PankuConsole (star 1436) | License: MIT | Collected: 2026-10-28
# Commit:  863324dfb752
extends Control

@onready var trect:TextureRect = $TextureRect

var _module:PankuModule
var expr:String

func _physics_process(delta: float) -> void:
	if Engine.get_physics_frames() % 10 != 1:
		return
	var result = _module.core.gd_exprenv.execute(expr)["result"]
	if result is Texture2D:
		trect.texture = ImageTexture.create_from_image(result.get_image())
