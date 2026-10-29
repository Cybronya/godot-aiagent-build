# Source:  https://github.com/foxssake/netfox/blob/main/script_templates/VestMeasure/empty.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
# meta-name: Empty measure
# meta-description: Custom measure with overrideable methods implemented
# meta-default: true

extends _BASE_
class_name _CLASS_

func get_measure_name() -> String:
  return "custom"

func get_value() -> Variant:
  return 0.0

func ingest(value: Variant) -> void:
  pass

