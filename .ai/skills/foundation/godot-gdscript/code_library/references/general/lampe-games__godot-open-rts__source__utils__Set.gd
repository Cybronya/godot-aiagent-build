# Source:  https://github.com/lampe-games/godot-open-rts/blob/main/source/utils/Set.gd
# Repo:    lampe-games/godot-open-rts (star 1136) | License: MIT | Collected: 2026-10-29
# Commit:  a628ad3bb6a9
var _data = {}


func add(item):
	_data[item] = true


func merge(data):
	if data is Array:
		for item in data:
			add(item)
	else:
		for item in data.iterate():
			add(item)


func erase(item):
	_data.erase(item)


func peek():
	for item in _data:
		return item


func peek_random(rng):
	return _data.keys()[rng.randi() % _data.keys().size()]


func pop():
	if empty():
		return null
	var item = _data.keys()[0]
	_data.erase(item)
	return item


func clear():
	_data = {}


func has(item):
	return _data.has(item)


func iterate():
	return _data


func empty():
	return _data.is_empty()


func size():
	return _data.size()


func to_str():
	return "Set({0})".format([str(_data.keys())])


func to_array():
	return _data.keys()
