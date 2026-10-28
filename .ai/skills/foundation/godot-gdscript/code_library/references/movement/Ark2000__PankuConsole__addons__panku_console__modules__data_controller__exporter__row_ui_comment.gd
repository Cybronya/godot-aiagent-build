# Source:  https://github.com/Ark2000/PankuConsole/blob/master/addons/panku_console/modules/data_controller/exporter/row_ui_comment.gd
# Repo:    Ark2000/PankuConsole (star 1436) | License: MIT | Collected: 2026-10-28
# Commit:  master
class_name PankuCommentRow
extends HBoxContainer

@export var button: PankuButton

var console: PankuConsole


func _ready():
	button.pressed.connect(_send_notify)


func _send_notify() -> void:
	if console:
		console.notify(button.label.text)
