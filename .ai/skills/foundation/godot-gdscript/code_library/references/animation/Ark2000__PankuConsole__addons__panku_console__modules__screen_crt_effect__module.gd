# Source:  https://github.com/Ark2000/PankuConsole/blob/master/addons/panku_console/modules/screen_crt_effect/module.gd
# Repo:    Ark2000/PankuConsole (star 1436) | License: MIT | Collected: 2026-10-28
# Commit:  master
class_name PankuModuleScreenCrtEffect extends PankuModule

var crt_effect_enabled := false
var crt_effect_layer:CanvasLayer = null

func toggle_crt_effect():
	crt_effect_enabled = !crt_effect_enabled
	if crt_effect_layer == null:
		crt_effect_layer = preload("./crt_effect_layer.tscn").instantiate()
		core.add_child(crt_effect_layer)
	crt_effect_layer.visible = crt_effect_enabled
