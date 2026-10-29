# Source:  https://github.com/KsanaDock/Microverse/blob/main/script/ui/MapSelection.gd
# Repo:    KsanaDock/Microverse (star 2502) | License: MIT | Collected: 2026-10-28
# Commit:  7a061d41ed67
extends Control

func _ready():
	# 连接地图选择按钮信号
	$MarginContainer/ScrollContainer/GridContainer/PanelContainer/VBoxContainer/OfficeButton.pressed.connect(_on_office_selected)
	$BackButton.pressed.connect(_on_back_pressed)

func _on_office_selected():
	# 设置办公室故事背景
	BackgroundStoryManager.set_background("Office")
	# 加载办公室场景
	get_tree().change_scene_to_file("res://scene/maps/Office.tscn")

func _on_back_pressed():
	# 返回主菜单
	get_tree().change_scene_to_file("res://scene/MainMenu.tscn")
