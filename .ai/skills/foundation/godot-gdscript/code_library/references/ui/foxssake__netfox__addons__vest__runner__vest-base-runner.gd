# Source:  https://github.com/foxssake/netfox/blob/main/addons/vest/runner/vest-base-runner.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
extends RefCounted

signal on_partial_result(result: VestResult.Suite)

func run_script(_script: Script, _only_mode: int = Vest.__.ONLY_DEFAULT) -> VestResult.Suite:
	# OVERRIDE
	return VestResult.Suite.new()

func run_glob(_p_glob: String, _only_mode: int = Vest.__.ONLY_DEFAULT) -> VestResult.Suite:
	# OVERRIDE
	return VestResult.Suite.new()

func run_script_at(path: String, only_mode: int = Vest.__.ONLY_DEFAULT) -> VestResult.Suite:
	var test_script := load(path)

	if not test_script or not test_script is Script:
		return null

	return await run_script(test_script, only_mode)
