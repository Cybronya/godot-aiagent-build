# Source:  https://github.com/dialogic-godot/dialogic/blob/main/Tests/Unit/test_example.gd
# Repo:    dialogic-godot/dialogic (star 6121) | License: MIT | Collected: 2026-10-26
# Commit:  701b67bbe601
class_name GdUnitExampleTest
extends GdUnitTestSuite

func test_example() -> void:
	const EXAMPLE_STRING := "Dialogic!"

	assert_str(EXAMPLE_STRING)\
		.has_length(EXAMPLE_STRING.length())\
		.starts_with("Dia")
