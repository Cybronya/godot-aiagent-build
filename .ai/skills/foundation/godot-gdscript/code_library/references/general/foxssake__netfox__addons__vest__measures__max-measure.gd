# Source:  https://github.com/foxssake/netfox/blob/main/addons/vest/measures/max-measure.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
extends VestMeasure

## Measures the maximum of a metric.

var _max: Variant
var _has: bool = false

func _init(p_metric: StringName):
  super(p_metric)

func get_measure_name() -> String:
  return "max"

func get_value() -> Variant:
  return _max

func ingest(value: Variant) -> void:
  _max = max(_max, value) if _has else value
  _has = true

