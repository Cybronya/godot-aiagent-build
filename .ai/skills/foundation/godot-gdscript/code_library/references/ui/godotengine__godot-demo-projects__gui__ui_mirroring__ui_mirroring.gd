# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/gui/ui_mirroring/ui_mirroring.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends Control

func _ready() -> void:
	$Label.text = TranslationServer.get_locale()


func _on_Button_pressed() -> void:
	if TranslationServer.get_locale() != "ar":
		TranslationServer.set_locale("ar")
	else:
		TranslationServer.set_locale("en")

	$Label.text = TranslationServer.get_locale()
