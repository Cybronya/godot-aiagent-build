# Source:  https://github.com/gdquest-demos/godot-open-rpg/blob/main/src/field/gameboard/debug/debug_pathfinder_map.gd
# Repo:    gdquest-demos/godot-open-rpg (star 3028) | License: MIT | Collected: 2026-10-26
# Commit:  d59f2f71bc04
extends TileMapLayer

@onready var _occupancy: TileMapLayer = $OccupancyGrid


func _ready() -> void:
	_occupancy.tile_set = tile_set

	Gameboard.pathfinder_changed.connect(
		func _on_pathfinder_changed(added_cells: Array[Vector2i], 
				removed_cells: Array[Vector2i]) -> void:
			for cell in added_cells:
				set_cell(cell, 0, Vector2i(0, 0), 0)
			
			for cell in removed_cells:
				set_cell(cell) # Flag the cell as blocked.
	)
	
	GamepieceRegistry.gamepiece_moved.connect(
		func _on_gp_moved(_gp: Gamepiece, new_cell: Vector2i, old_cell: Vector2i) -> void:
			_occupancy.set_cell(old_cell)
			_occupancy.set_cell(new_cell, 0, Vector2i(1, 0), 0)
	)
