# Source:  https://github.com/dreadpon/godot_spatial_gardener/blob/master/testing/checks/plant_snapshot_check.gd
# Repo:    dreadpon/godot_spatial_gardener (star 1319) | License: MIT | Collected: 2026-10-29
# Commit:  77b822f50ded
@tool


const GenericUtils = preload("../utility/generic_utils.gd")
const PlantUtils = preload("../utility/plant_utils.gd")
const Greenhouse = preload("res://addons/dreadpon.spatial_gardener/greenhouse/greenhouse.gd")




static func check_snapshots(list_index:int, given:Greenhouse, ref:Greenhouse, logger, text):
	return GenericUtils.find_discrepancies(
		list_index, PlantUtils.snapshot_greenhouse(given), PlantUtils.snapshot_greenhouse(ref), logger, text)
