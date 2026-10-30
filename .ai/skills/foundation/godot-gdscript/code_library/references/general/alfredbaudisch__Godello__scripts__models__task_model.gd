# Source:  https://github.com/alfredbaudisch/Godello/blob/master/scripts/models/task_model.gd
# Repo:    alfredbaudisch/Godello (star 890) | License: MIT | Collected: 2026-10-29
# Commit:  4458a143644f
class_name TaskModel extends Model


var title : String = ""
var card_id : String = ""
var is_done : bool = false


func _init(_id : String, _card_id : String, _title : String, _is_done : bool = false).(ModelTypes.TASK, _id):
	card_id = _card_id
	title = _title
	is_done = _is_done


func set_title(_title : String):
	title = _title


func set_is_done(_is_done : bool):
	is_done = _is_done
