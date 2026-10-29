# Source:  https://github.com/gdquest-demos/godot-open-rpg/blob/main/overworld/maps/town/gang_of_four_conversation.gd
# Repo:    gdquest-demos/godot-open-rpg (star 3028) | License: MIT | Collected: 2026-10-26
# Commit:  d59f2f71bc04
@tool
extends InteractionTemplateConversation


func _on_dialogic_signal_event(argument: String) -> void:
	if argument == "coin_received":
		Inventory.restore().add(Inventory.ItemTypes.COIN)
