# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/interface/items/ItemButton.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends Button

signal amount_changed(value)

var description = ""
var amount = 0

func initialize(item, price, purse):
	$Name.text = item.display_name
	$Price.text = str(price)
	$Icon.texture = item.icon
	
	description = item.description
	amount = item.amount

	if purse.coins < price:
		disabled = true
	
	item.connect("amount_changed", self, "_on_Item_amount_changed")
	item.connect("depleted", self, "_on_Item_depleted")
	purse.connect("coins_changed", self, "_on_Purse_coins_changed", [price])

func _on_Item_depleted():
	disabled = true

func _on_Item_amount_changed(value):
	amount = value
	emit_signal("amount_changed", value)

func _on_Purse_coins_changed(coins, price):
	if price > coins:
		disabled = true
