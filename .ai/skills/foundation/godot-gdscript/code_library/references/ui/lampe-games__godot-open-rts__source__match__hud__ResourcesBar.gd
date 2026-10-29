# Source:  https://github.com/lampe-games/godot-open-rts/blob/main/source/match/hud/ResourcesBar.gd
# Repo:    lampe-games/godot-open-rts (star 1136) | License: MIT | Collected: 2026-10-29
# Commit:  a628ad3bb6a9
extends PanelContainer

var player = null

@onready var _resource_a_label = find_child("ResourceALabel")
@onready var _resource_b_label = find_child("ResourceBLabel")
@onready var _resource_a_color_rect = find_child("ResourceAColorRect")
@onready var _resource_b_color_rect = find_child("ResourceBColorRect")


func _ready():
	_resource_a_color_rect.color = Constants.Match.Resources.A.COLOR
	_resource_b_color_rect.color = Constants.Match.Resources.B.COLOR


func setup(a_player):
	assert(player == null, "player cannot be null")
	player = a_player
	_on_player_resource_changed()
	player.changed.connect(_on_player_resource_changed)


func _on_player_resource_changed():
	_resource_a_label.text = str(player.resource_a)
	_resource_b_label.text = str(player.resource_b)
