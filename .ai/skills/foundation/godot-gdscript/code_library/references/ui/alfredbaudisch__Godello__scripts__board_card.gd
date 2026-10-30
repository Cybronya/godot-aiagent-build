# Source:  https://github.com/alfredbaudisch/Godello/blob/master/scripts/board_card.gd
# Repo:    alfredbaudisch/Godello (star 890) | License: MIT | Collected: 2026-10-29
# Commit:  4458a143644f
extends Button


var model : BoardModel setget set_model, get_model

onready var title_label := $Title


func _ready():
# warning-ignore:return_value_discarded
	DataRepository.connect("board_deleted", self, "_on_board_deleted")


func set_model(_model : BoardModel):
	model = _model
	title_label.set_text(model.title)


func get_model():
	return model


func _on_board_deleted(board):
	if model and board.id == model.id:
		queue_free()

