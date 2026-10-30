# Source:  https://github.com/alfredbaudisch/Godello/blob/master/scripts/models/user_model.gd
# Repo:    alfredbaudisch/Godello (star 890) | License: MIT | Collected: 2026-10-29
# Commit:  4458a143644f
class_name UserModel extends Model


var first_name : String
var last_name : String
var email : String


func _init(_id : String, _first_name : String, _last_name : String, _email : String).(ModelTypes.USER, _id):
	first_name = _first_name
	last_name = _last_name
	email = _email


func get_full_name():
	return first_name + " " + last_name
