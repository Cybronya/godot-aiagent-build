# Source:  https://github.com/cherriesandmochi/gdmaim/blob/main/addons/gdmaim/ui/dock/setting.gd
# Repo:    cherriesandmochi/gdmaim (star 1327) | License: MIT | Collected: 2026-10-29
# Commit:  42a4eecf5418
@tool
extends Node


const _Settings := preload("../../settings.gd")

@export var settings_var : String
@export var node_var : String

var settings : _Settings


func set_settings(settings : _Settings) -> void:
	self.settings = settings
	deserialize()


func serialize() -> void:
	settings.set(settings_var, get(node_var))


func deserialize() -> void:
	#prints("deserialize", settings_var, settings.get(settings_var))
	set(node_var, settings.get(settings_var))
