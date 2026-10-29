# Source:  https://github.com/foxssake/netfox/blob/main/examples/snippets/network-schemas/example-node-serializer.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
extends NetworkSchemaSerializer
class_name ExampleNodeSerializer

# Needs to be set from the outside
static var scene_tree: SceneTree

func encode(value: Variant, buffer: StreamPeerBuffer) -> void:
	var node := value as Node
	buffer.put_utf8_string(node.get_path())

func decode(buffer: StreamPeerBuffer) -> Variant:
	var path := buffer.get_utf8_string()
	return scene_tree.root.get_node(path)
