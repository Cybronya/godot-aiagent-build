# Source:  https://github.com/ceceppa/anima/blob/main/addons/gut/lazy_loader.gd
# Repo:    ceceppa/anima (star 769) | License: MIT | Collected: 2026-10-31
# Commit:  f4a454ebd4d5
@tool
# ------------------------------------------------------------------------------
# Static
# ------------------------------------------------------------------------------
static var usage_counter = load('res://addons/gut/thing_counter.gd').new()
static var WarningsManager = load('res://addons/gut/warnings_manager.gd')

static func load_all():
	for key in usage_counter.things:
		key.get_loaded()


static func print_usage():
	for key in usage_counter.things:
		print(key._path, '  (', usage_counter.things[key], ')')


static func clear():
	usage_counter.things.clear()

# ------------------------------------------------------------------------------
# Class
# ------------------------------------------------------------------------------
var _loaded = null
var _path = null

func _init(path):
	_path = path
	usage_counter.add_thing_to_count(self)


func get_loaded():
	if(_loaded == null):
		_loaded = WarningsManager.load_script_ignoring_all_warnings(_path)
	usage_counter.add(self)
	return _loaded



