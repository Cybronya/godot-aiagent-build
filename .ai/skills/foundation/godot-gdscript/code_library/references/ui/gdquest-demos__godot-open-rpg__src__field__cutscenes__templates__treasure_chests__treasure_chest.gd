# Source:  https://github.com/gdquest-demos/godot-open-rpg/blob/main/src/field/cutscenes/templates/treasure_chests/treasure_chest.gd
# Repo:    gdquest-demos/godot-open-rpg (star 3028) | License: MIT | Collected: 2026-10-26
# Commit:  d59f2f71bc04
@tool
extends Gamepiece

@export var item_type: Inventory.ItemTypes
@export var amount: = 1

@onready var interaction: = $Interaction as Interaction


func _ready() -> void:
	super._ready()
	
	if not Engine.is_editor_hint():
		interaction.item_type = item_type
		interaction.amount = amount
