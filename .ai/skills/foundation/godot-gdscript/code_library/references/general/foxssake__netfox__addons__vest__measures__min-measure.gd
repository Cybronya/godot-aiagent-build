# Source:  https://github.com/foxssake/netfox/blob/main/addons/vest/measures/min-measure.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
extends VestMeasure

## Measures the minimum of a metric.

var _min: Variant
var _has: bool = false

func _init(p_metric: StringName):
  super(p_metric)

func get_measure_name() -> String:
  return "min"

func get_value() -> Variant:
  return _min

func ingest(value: Variant) -> void:
  _min = min(_min, value) if _has else value
  _has = true

