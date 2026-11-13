extends GdUnitTestSuite


func test_guess_name_stable() -> void:
	_assert_bulk([
		["Godot_v4.1-stable_linux.x86_64",        "Godot v4.1 stable"],
		["Godot_v4.1.1-stable_linux.x86_64",      "Godot v4.1.1 stable"],
		["Godot_v4.1.1.1-stable_linux.x86_64",    "Godot v4.1.1.1 stable"],
		["Godot_v4.1.1.1.1-stable_linux.x86_64",  "Godot v4.1.1.1.1 stable"],
		["godot-3.5.3-stable-win64.exe",          "Godot v3.5.3 stable"],
		["Godot_v4.3-stable_macos.universal.dmg", "Godot v4.3 stable"],
		["godot-4.5-stable.tar.xz",               "Godot v4.5 stable"],
		["godot-4.5-stable.tar.xz.sha256",        "Godot v4.5 stable"],
	])


func test_guess_name_prereleases() -> void:
	_assert_bulk([
		["Godot_v4.2-rc3_mono_win64.exe",  "Godot v4.2 rc3 mono"],
		["godot-4.0-beta2-linux.x86_64",   "Godot v4.0 beta2"],
		["godot_4.0-alpha1_osx.zip",       "Godot v4.0 alpha1"],
		["GODOT-V4.2-RC1-WIN64.EXE",       "Godot v4.2 rc1"],
		["godot-v1.0.0.0.0-rc10-win64.exe", "Godot v1.0.0.0.0 rc10"],
		["Godot_v4.0-pre-alpha1_win64.exe", "Godot v4.0 pre-alpha1"],
	])


func test_guess_name_dev_releases() -> void:
	_assert_bulk([
		["Godot_v4.7-dev3_win64.exe",       "Godot v4.7 dev3"],
		["Godot_v4.7-dev3_mono_win64.exe",  "Godot v4.7 dev3 mono"],
		["Godot_v4.7-dev3_mono_win64",      "Godot v4.7 dev3 mono"],
		["Godot_v4.7-dev1_linux.x86_64",    "Godot v4.7 dev1"],
		["Godot_v4.7-dev_win64.exe",        "Godot v4.7 dev"],
	])


func test_guess_name_mono() -> void:
	_assert_bulk([
		["Godot_v4.2_mono_win64.exe",                  "Godot v4.2 mono"],
		["Godot_v4.5-stable_mono_win64.zip",           "Godot v4.5 stable mono"],
		["Godot_v4.5-stable_mono_win64",               "Godot v4.5 stable mono"],
		["Godot_v4.5-stable_mono_linux.x86_64",        "Godot v4.5 stable mono"],
		["Godot_v4.6-stable_mono_linux.x86_64",        "Godot v4.6 stable mono"],
		["Godot_v4.6.1-stable_mono_linux.x86_64",      "Godot v4.6.1 stable mono"],
		["Godot_v4.7-dev3_mono_win64.exe",             "Godot v4.7 dev3 mono"],
		["Godot_v4.5-stable_mono_win64.exe.zip",       "Godot v4.5 stable mono"],
		["Godot_v4.5-stable_mono_export_templates.tpz", "Godot v4.5 stable mono"],
		["godot-lib.4.5.stable.mono.template_release.aar", "Godot v4.5 mono"],
	])


func test_guess_name_godot_4_5_release_assets() -> void:
	_assert_bulk([
		# Dot style: channel not detected (works as designed)
		["godot-lib.4.5.stable.template_release.aar",         "Godot v4.5"],
		["Godot_native_debug_symbols.4.5.stable.editor.android.zip",           "Godot v4.5"],
		["Godot_native_debug_symbols.4.5.stable.template_release.android.zip", "Godot v4.5"],

		# Android editor builds
		["Godot_v4.5-stable_android_editor.aab",              "Godot v4.5 stable"],
		["Godot_v4.5-stable_android_editor.apk",              "Godot v4.5 stable"],
		["Godot_v4.5-stable_android_editor_horizonos.apk",    "Godot v4.5 stable"],
		["Godot_v4.5-stable_android_editor_picoos.apk",       "Godot v4.5 stable"],

		# Export templates
		["Godot_v4.5-stable_export_templates.tpz",            "Godot v4.5 stable"],

		# Desktop editors
		["Godot_v4.5-stable_linux.arm32.zip",                 "Godot v4.5 stable"],
		["Godot_v4.5-stable_linux.arm64.zip",                 "Godot v4.5 stable"],
		["Godot_v4.5-stable_linux.x86_32.zip",                "Godot v4.5 stable"],
		["Godot_v4.5-stable_linux.x86_64.zip",                "Godot v4.5 stable"],
		["Godot_v4.5-stable_macos.universal.zip",             "Godot v4.5 stable"],
		["Godot_v4.5-stable_win32.exe.zip",                   "Godot v4.5 stable"],
		["Godot_v4.5-stable_win64.exe.zip",                   "Godot v4.5 stable"],
		["Godot_v4.5-stable_windows_arm64.exe.zip",           "Godot v4.5 stable"],

		# Mono desktop editors
		["Godot_v4.5-stable_mono_linux_arm32.zip",            "Godot v4.5 stable mono"],
		["Godot_v4.5-stable_mono_linux_arm64.zip",            "Godot v4.5 stable mono"],
		["Godot_v4.5-stable_mono_linux_x86_32.zip",           "Godot v4.5 stable mono"],
		["Godot_v4.5-stable_mono_linux_x86_64.zip",           "Godot v4.5 stable mono"],
		["Godot_v4.5-stable_mono_macos.universal.zip",        "Godot v4.5 stable mono"],
		["Godot_v4.5-stable_mono_win32.zip",                  "Godot v4.5 stable mono"],
		["Godot_v4.5-stable_mono_win64.zip",                  "Godot v4.5 stable mono"],
		["Godot_v4.5-stable_mono_windows_arm64.zip",          "Godot v4.5 stable mono"],

		# Web editor
		["Godot_v4.5-stable_web_editor.zip",                  "Godot v4.5 stable"],
	])


func test_guess_name_from_full_path() -> void:
	_assert_bulk([
		[
			"C:/Users/maxim/Versions/Godot_v4.7-dev3_mono_win64.exe",
			"Godot v4.7 dev3 mono",
		],
		[
			"D:\\Godot\\Godot_v4.7-dev3_win64.exe",
			"Godot v4.7 dev3",
		],
		[
			"/home/user/.local/share/godot/Godot_v4.5-stable_mono_linux.x86_64",
			"Godot v4.5 stable mono",
		],
	])


func test_guess_name_zip_basenames_without_extension() -> void:
	var cases := [
		["Godot_v4.7-dev3_mono_win64",           "Godot v4.7 dev3 mono"],
		["Godot_v4.7-dev3_win64",                "Godot v4.7 dev3"],
		["Godot_v4.6-stable_mono_linux",         "Godot v4.6 stable mono"],
		["Godot_v4.6.1-stable_mono_linux",       "Godot v4.6.1 stable mono"],
		["Godot_v4.5-stable_mono_win64",         "Godot v4.5 stable mono"],
		["Godot_v4.5-stable_win64",              "Godot v4.5 stable"],
		["Godot_v4.2-rc3_mono_win64",            "Godot v4.2 rc3 mono"],
	]
	_assert_bulk(cases)
	for c: Array in cases:
		assert_str(utils.guess_editor_name(c[0] as String)).is_not_equal("Godot_v4")


func test_guess_name_from_downloaded_zip_filename() -> void:
	var zip_names := [
		"Godot_v4.7-dev3_mono_win64.zip",
		"Godot_v4.6.1-stable_mono_linux.x86_64.zip",
		"Godot_v4.6-stable_mono_linux.x86_64.zip",
		"Godot_v4.5-stable_mono_win64.exe.zip",
	]
	var expected := [
		"Godot v4.7 dev3 mono",
		"Godot v4.6.1 stable mono",
		"Godot v4.6 stable mono",
		"Godot v4.5 stable mono",
	]
	for i in len(zip_names):
		var basename := (zip_names[i] as String).replace(".zip", "")
		_assert_name(basename, expected[i] as String)


func test_guess_name_preserves_version_dots() -> void:
	_assert_bulk([
		["Godot_v4.6.1-stable_mono_linux.x86_64",  "Godot v4.6.1 stable mono"],
		["Godot_v4.1.1.1-stable_linux.x86_64",     "Godot v4.1.1.1 stable"],
		["Godot_v10.20.30.40.50-stable_linux.x86_64", "Godot v10.20.30.40.50 stable"],
		["godot-3.5.3-stable-win64",               "Godot v3.5.3 stable"],
	])


func test_guess_name_ignores_mono_in_parent_path() -> void:
	# Only the basename should affect mono detection.
	_assert_name(
		"C:/Projects/mono/Godot_v4.5-stable_win64.exe",
		"Godot v4.5 stable"
	)
	_assert_name(
		"C:/Projects/mono/Godot_v4.5-stable_mono_win64.exe",
		"Godot v4.5 stable mono"
	)


func test_guess_name_misc() -> void:
	_assert_bulk([
		["Godot_4.3-linux.x86_64",                "Godot v4.3"],
		["custom-godot-build-4.3.0.official",     "Godot v4.3.0"],
		["Godot_v10.20.30.40.50-stable_linux.x86_64", "Godot v10.20.30.40.50 stable"],
		["godot_v4.2-rc1.tar.xz",                 "Godot v4.2 rc1"],
		["editor",                                "editor"],
	])


func _assert_name(file_name: String, expected: String) -> void:
	assert_str(utils.guess_editor_name(file_name)).is_equal(expected)


func _assert_bulk(cases: Array) -> void:
	for c: Array in cases:
		_assert_name(c[0] as String, c[1] as String)
