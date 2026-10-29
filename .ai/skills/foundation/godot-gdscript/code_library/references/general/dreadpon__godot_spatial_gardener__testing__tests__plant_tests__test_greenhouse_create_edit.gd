# Source:  https://github.com/dreadpon/godot_spatial_gardener/blob/master/testing/tests/plant_tests/test_greenhouse_create_edit.gd
# Repo:    dreadpon/godot_spatial_gardener (star 1319) | License: MIT | Collected: 2026-10-29
# Commit:  77b822f50ded
@tool
extends "test_plant_base.gd"




func execute():
	super.execute()
	
	var greenhouses := load_greenhouses()
	
	var morphs_gone_wrong := 0
	logger.info("Executing test for '%d' greenhouses\n" % [greenhouses.size()])
	
	var curr_greenhouse:Greenhouse = greenhouses[0]
	for i in range(1, greenhouses.size()):
		var morph_actions = PlantUtils.get_morph_actions(greenhouses[i-1], greenhouses[i])
		PlantUtils.perform_morph_actions(curr_greenhouse, morph_actions)
		
		if find_discrepancies(-1, curr_greenhouse, greenhouses[i], "during morphing '%d'->'%d'" % [i - 1, i]):
			morphs_gone_wrong += 1
	
	var results = print_and_get_result(-1, {"morph discrepancies": morphs_gone_wrong})
	finish_execution(results)
