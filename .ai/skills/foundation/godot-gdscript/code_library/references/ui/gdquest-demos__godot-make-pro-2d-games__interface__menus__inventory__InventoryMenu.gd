# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/interface/menus/inventory/InventoryMenu.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends Menu

onready var items_list = $Column/ItemsMenu

"""args: {inventory}"""
func initialize(args={}):
	items_list.initialize(args['inventory'])

"""args: {inventory}"""
func open(args={}):
	assert(args.size() == 1)
	var inventory = args['inventory']
	.open()

func close():
	.close()
	queue_free()
