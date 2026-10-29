# Source:  https://github.com/foxssake/netfox/blob/main/test/netfox/servers/testing-command-server.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
extends _NetworkCommandServer
class_name TestingCommandServer

var commands_sent := [] as Array[Array]

func send_command(idx: int, data: PackedByteArray, target_peer: int = 0, mode: MultiplayerPeer.TransferMode = MultiplayerPeer.TRANSFER_MODE_RELIABLE, channel: int = 0) -> void:
	commands_sent.append([idx, data, target_peer, mode, channel])
