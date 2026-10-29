# Source:  https://github.com/KoBeWi/Metroidvania-System/blob/master/Extensions/ModernMap/SampleProject/Scripts/GenerateAllOverlays.gd
# Repo:    KoBeWi/Metroidvania-System (star 1596) | License: MIT | Collected: 2026-10-26
# Commit:  0065ae897429
@tool
extends EditorScript

static var persist: EditorScript

func _run() -> void:
	persist = self
	
	var generator := preload("res://SampleProject/Scripts/GenerateOverlay.gd")
	for scene in MetSys.map_data.assigned_scenes:
		print("Generating %s..." % MetSys.map_data.get_room_friendly_name(scene))
		EditorInterface.open_scene_from_path(scene)
		
		await Engine.get_main_loop().process_frame
		await Engine.get_main_loop().process_frame
		
		var gen := generator.new()
		gen._run()
		
		EditorInterface.close_scene()
	
	persist = null
