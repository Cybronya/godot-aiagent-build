# Source:  https://github.com/alfredbaudisch/Godello/blob/master/scripts/list_mouse_preview.gd
# Repo:    alfredbaudisch/Godello (star 890) | License: MIT | Collected: 2026-10-29
# Commit:  4458a143644f
class_name ListPreview extends PanelContainer


var title_label
var drag_data

onready var cards_container := $Panel/MarginContainer/VerticalContent/ScrollContainer/CardsContainer
onready var card_template := $Panel/MarginContainer/VerticalContent/ScrollContainer/CardsContainer/Card


func _ready():
	title_label = get_node("Panel/MarginContainer/VerticalContent/ListNameLabel")


func set_data(_node, _model : ListModel):
	drag_data = DragUtils.get_drag_data(_node, _model)
	set_title(_model.title)

	# TODO: add utility functional methods to help in situations like this (map, filter, count, etc)
	var size = 0
	for card in _model.cards:
		size += 1 if not card.is_archived else 0

	if size == 0:
		card_template.set_visible(false)


func set_title(_title):
	title_label.set_text(_title)
