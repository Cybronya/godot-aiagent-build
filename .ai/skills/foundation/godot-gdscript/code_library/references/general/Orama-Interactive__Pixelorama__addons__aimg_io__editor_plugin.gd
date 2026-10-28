# Source:  https://github.com/Orama-Interactive/Pixelorama/blob/master/addons/aimg_io/editor_plugin.gd
# Repo:    Orama-Interactive/Pixelorama (star 10855) | License: MIT | Collected: 2026-10-27
# Commit:  master
@tool
extends EditorPlugin

var apng_importer


func _enter_tree():
	apng_importer = AImgIOAPNGImportPlugin.new()
	add_import_plugin(apng_importer)


func _exit_tree():
	remove_import_plugin(apng_importer)
	apng_importer = null
