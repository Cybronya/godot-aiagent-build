# Source:  https://github.com/foxssake/netfox/blob/main/test/netfox/serializers/snapshot-serializer-test.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
extends VestTest
class_name SnapshotSerializerTest

func before_case(__):
	# Makes sure local peer is 1, otherwise identifiers get random local IDs
	Vest.get_tree().root.multiplayer.multiplayer_peer = OfflineMultiplayerPeer.new()

func to_buffer(data: PackedByteArray) -> StreamPeerBuffer:
	var buffer := StreamPeerBuffer.new()
	buffer.data_array = data
	return buffer

func get_subject() -> Node3D:
	var subject := Node3D.new()

	Vest.get_tree().root.add_child.call_deferred(subject)
	await subject.ready

	return subject
