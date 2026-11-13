# Source:  https://github.com/MakovWait/godots/blob/main/addons/use-context/context_keys.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
static func by_type(type):
	return func(bucket: Array, opt):
		for x in bucket:
			if is_instance_of(x, type):
				return opt.found(x)
		return opt.not_found()
