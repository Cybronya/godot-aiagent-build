# Source:  https://github.com/don-tnowe/godot-resources-as-sheets-plugin/blob/master/example/Items/item_type.gd
# Repo:    don-tnowe/godot-resources-as-sheets-plugin (star 1031) | License: MIT | Collected: 2026-10-29
# Commit:  3363e0d2136c
extends Resource

enum SlotType {
	SMALL,
	LARGE,
	EQUIPMENT,
	QUEST,
	POTION,
	AMMO,
	CURRENCY,
	FUEL,
	CRAFTING,
	E_MAINHAND,
	E_OFFHAND,
	E_HELM,
	E_CHEST,
	E_BELT,
	E_HANDS,
	E_FEET,
	E_RING,
	E_NECK,
}
@export var name := ""
@export_multiline var description := ""
@export var max_stack_count := 1
@export var in_inventory_width := 1
@export var in_inventory_height := 1
@export var texture : Texture
@export var mesh : Mesh

@export var slot_flags : SlotType = SlotType.SMALL
@export var default_properties : Dictionary
