# Source:  https://github.com/peter-kish/gloot/blob/master/addons/gloot/core/prototree/proto_tree_cache.gd
# Repo:    peter-kish/gloot (star 989) | License: MIT | Collected: 2026-10-29
# Commit:  6b09b87ac07a
@tool

static var _cache: Dictionary = {}
static var _empty: ProtoTree = ProtoTree.new()


static func get_cached(key: JSON) -> ProtoTree:
    if Engine.is_editor_hint():
        var result := ProtoTree.new()
        result.deserialize(key)
        return result

    if _cache.has(key):
        return _cache[key]
    else:
        _cache[key] = ProtoTree.new()
        _cache[key].deserialize(key)
        return _cache[key]


static func get_empty() -> ProtoTree:
    return _empty
