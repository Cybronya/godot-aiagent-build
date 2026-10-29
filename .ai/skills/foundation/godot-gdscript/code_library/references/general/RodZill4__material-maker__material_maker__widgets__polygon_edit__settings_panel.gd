# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/widgets/polygon_edit/settings_panel.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
extends PanelContainer


func _on_ready() -> void:
	%GridDensity.value = %PolygonEditor.axes_density - 1.0


func _on_grid_density_value_changed(value: Variant) -> void:
	%PolygonEditor.axes_density = value + 1.0
	%PolygonEditor.queue_redraw()
