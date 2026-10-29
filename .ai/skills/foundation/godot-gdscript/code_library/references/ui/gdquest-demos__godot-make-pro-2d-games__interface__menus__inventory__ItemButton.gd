# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/interface/menus/inventory/ItemButton.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends Button

var description = ""

func initialize(item):
	$Name.text = item.display_name
	$Amount.text = str(item.amount)
	$Icon.texture = item.icon
	
	description = item.description
	
	disabled = not item.usable
	
	item.connect("amount_changed", self, "_on_Item_amount_changed")
	item.connect("depleted", self, "queue_free")

func _on_Item_amount_changed(amount):
	$Amount.text = str(amount)
