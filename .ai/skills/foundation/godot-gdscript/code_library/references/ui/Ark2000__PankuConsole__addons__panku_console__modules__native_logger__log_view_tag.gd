# Source:  https://github.com/Ark2000/PankuConsole/blob/master/addons/panku_console/modules/native_logger/log_view_tag.gd
# Repo:    Ark2000/PankuConsole (star 1436) | License: MIT | Collected: 2026-10-28
# Commit:  master
extends Control

@export var tag_btn:Button
@export var rm_btn:Button

var tag_text:String
var tag_number:int = 0

func check(message:String):
	if message.contains(tag_text):
		tag_number += 1
	tag_btn.text = "%s (%d)" % [tag_text, tag_number]
