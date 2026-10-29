# Source:  https://github.com/mhgolkar/Arrow/blob/main/nodes/sequencer/shared.gd
# Repo:    mhgolkar/Arrow (star 1363) | License: MIT | Collected: 2026-10-29
# Commit:  5c0291c72e0f
# Arrow
# Game Narrative Design Tool
# Mor. H. Golkar

# Sequencer Node Type Shared Class
# (shared functionalities and constants)
class_name SequencerSharedClass

# sequencers are by definition, to run all of connected outputs in their slot order;
# so there must be at least two outgoing slots for any sequencer otherwise its just a link.
const SEQUENCER_MINIMUM_ACCEPTABLE_OUT_SLOTS = 2
# and there can be a limit for the sake of tidiness
const SEQUENCER_MAXIMUM_ACCEPTABLE_OUT_SLOTS = 10

# Note: the one incoming slot is always there in the `.tscn`
