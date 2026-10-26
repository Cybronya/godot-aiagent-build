# Source:  https://github.com/ramokz/phantom-camera/blob/main/addons/phantom_camera/scripts/panel/editor.gd
# Repo:    ramokz/phantom-camera (star 3640) | License: MIT | Collected: 2026-10-26
# Commit:  main
@tool
extends VBoxContainer

#region Onready

@onready var updater: Control = %UpdateButton
@onready var viewfinder: Control = %ViewfinderPanel

#endregion

#region Public Variables

var editor_plugin: EditorPlugin

#endregion


#region Private Functions

func _ready():
	updater.editor_plugin = editor_plugin

#endregion
