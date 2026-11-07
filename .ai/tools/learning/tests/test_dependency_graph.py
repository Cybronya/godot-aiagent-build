#!/usr/bin/env python3
"""Phase 1.65：Dependency Analysis 测试（真实图 + 查询 + 循环分类 + 来源强制）。"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LEARNING = os.path.dirname(HERE)
sys.path[:0] = [LEARNING]

import dependencies  # noqa: E402
import paths  # noqa: E402

checks = 0
failures = 0


def ok(name: str, condition: bool, detail: str = "") -> None:
    global checks, failures
    checks += 1
    if condition:
        print("PASS: %s" % name)
    else:
        failures += 1
        print("FAIL: %s %s" % (name, detail))


def main() -> int:
    graph = dependencies.build()
    ok("D1: graph covers the dynamic supported set",
       graph["summary"]["nodes"] == len(paths.supported_behaviors()))
    ok("D2: every edge has a real source reference",
       all(edge["source_reference"].strip() for edge in graph["edges"]))
    ok("D3: every edge declares its evidence kind",
       all(edge["evidence_kind"] in ("SOURCE_REFERENCE", "CONTRACT_REFERENCE")
           for edge in graph["edges"]))
    ok("D4: every edge declares verification status",
       all(edge["verification_status"] in ("SOURCE_OBSERVED", "CONTRACT_DERIVED")
           for edge in graph["edges"]))
    ok("D5: dependency types are from the declared vocabulary",
       all(edge["dependency_type"] in dependencies.DEPENDENCY_TYPES
           for edge in graph["edges"]))
    ok("D6: contract-derived edges are not mixed into source-observed ones",
       all((edge["evidence_kind"] == "CONTRACT_REFERENCE") ==
           (edge["verification_status"] == "CONTRACT_DERIVED") for edge in graph["edges"]))
    ok("D7: at least one source-observed cross-feature call/state edge exists",
       graph["summary"]["source_observed_edges"] > 0)
    ok("D8: event propagation edges are symmetric (emit/receive)",
       sum(1 for edge in graph["edges"] if edge["dependency_type"] == "EMITS_EVENT_TO") ==
       sum(1 for edge in graph["edges"] if edge["dependency_type"] == "RECEIVES_EVENT_FROM"))

    downstream = dependencies.query(graph, "i_frames/iframes_block_damage_within_window",
                                    "downstream")
    upstream = dependencies.query(graph, "health/damage", "upstream")
    ok("D9: downstream query returns only edges from that behavior",
       all(edge["source_behavior"] == "i_frames/iframes_block_damage_within_window"
           for edge in downstream))
    ok("D10: upstream query finds consumers of a state owner",
       any(edge["source_behavior"].startswith("i_frames/") for edge in upstream))

    events = dependencies.query(graph, "", "events")
    persistence = dependencies.query(graph, "", "persistence")
    ok("D11: event query is filtered to event edge types",
       all(edge["dependency_type"] in ("EMITS_EVENT_TO", "RECEIVES_EVENT_FROM")
           for edge in events))
    ok("D12: save_game has a persistence edge with file_access reference",
       any(edge["source_behavior"].startswith("save_game/")
           for edge in persistence))

    ok("D13: cycles are classified, not treated as errors",
       all(cycle["classification"] in ("event_loop", "persistence_pair", "state_cycle",
                                        "hub_component")
           for cycle in graph["cycles"]))
    ok("D14: every cycle has a unique node list and a sample of real edges",
       all(len(set(cycle["nodes"])) == len(cycle["nodes"]) and cycle["sample_edges"]
           for cycle in graph["cycles"]))

    cyclic = {"edges": [{"source_behavior": "a/x", "target_behavior": "b/y",
                         "dependency_type": "CALLS", "source_reference": "r",
                         "evidence_kind": "SOURCE_REFERENCE",
                         "verification_status": "SOURCE_OBSERVED"}],
              "unresolved_requirements": [], "nodes": [], "cycles": [], "summary": {}}
    cycles = dependencies._cycles({"a/x": cyclic["edges"],
                                   "b/y": [dict(cyclic["edges"][0],
                                                source_behavior="b/y",
                                                target_behavior="a/x")]})
    ok("D15: cycle detector reports mutual edges", len(cycles) == 1)

    unresolved = graph["unresolved_requirements"]
    ok("D16: unresolved contract requirements are listed separately",
       isinstance(unresolved, list) and
       all({"feature_id", "requirement", "reason"} <= set(item) for item in unresolved))
    print("\n===== test_dependency_graph: %d checks, %d failures =====" % (checks, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
