# Source:  https://github.com/alfredbaudisch/Godello/blob/master/scripts/models/model.gd
# Repo:    alfredbaudisch/Godello (star 890) | License: MIT | Collected: 2026-10-29
# Commit:  4458a143644f
class_name Model extends Object


enum ModelTypes {BOARD, LIST, CARD, TASK, USER}

var model_type : int
var id : String


func _init(_model_type : int, _id : String):
	model_type = _model_type
	id = _id
