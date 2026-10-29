# Source:  https://github.com/RodZill4/material-maker/blob/master/addons/gut/parameter_handler.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
var _params = null
var _call_count = 0
var _logger = null

func _init(params=null):
	_params = params
	_logger = GutUtils.get_logger()
	if(typeof(_params) != TYPE_ARRAY):
		_logger.error('You must pass an array to parameter_handler constructor.')
		_params = null


func next_parameters():
	_call_count += 1
	return _params[_call_count -1]

func get_current_parameters():
	return _params[_call_count]

func is_done():
	var done = true
	if(_params != null):
		done = _call_count == _params.size()
	return done

func get_logger():
	return _logger

func set_logger(logger):
	_logger = logger

func get_call_count():
	return _call_count

func get_parameter_count():
	return _params.size()
