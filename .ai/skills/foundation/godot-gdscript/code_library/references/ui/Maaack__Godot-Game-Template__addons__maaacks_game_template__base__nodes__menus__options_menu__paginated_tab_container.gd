# Source:  https://github.com/Maaack/Godot-Game-Template/blob/main/addons/maaacks_game_template/base/nodes/menus/options_menu/paginated_tab_container.gd
# Repo:    Maaack/Godot-Game-Template (star 1709) | License: MIT | Collected: 2026-10-26
# Commit:  5cc611f7dfcd
extends TabContainer
## Applies UI page up and page down inputs to tab switching.

func _unhandled_input(event : InputEvent) -> void:
	if (not is_visible_in_tree()) or tab_focus_mode == Control.FOCUS_NONE:
		return
	var is_first : bool = true
	if event.is_action_pressed(&"ui_page_down"):
		while is_first or get("tab_%d/hidden" % current_tab):
			is_first = false
			current_tab = (current_tab+1) % get_tab_count()
	elif event.is_action_pressed(&"ui_page_up"):
		while is_first or get("tab_%d/hidden" % current_tab):
			is_first = false
			if current_tab == 0:
				current_tab = get_tab_count()-1
			else:
				current_tab = current_tab-1
