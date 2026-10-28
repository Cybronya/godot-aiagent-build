# Source:  https://github.com/Ark2000/PankuConsole/blob/master/addons/panku_console/modules/about/url_button.gd
# Repo:    Ark2000/PankuConsole (star 1436) | License: MIT | Collected: 2026-10-28
# Commit:  master
extends Button

@export var url:String

func _ready():
	pressed.connect(
		func():
			OS.shell_open(url)
	)
