"""Behavior Dependency Analysis（Phase 1.65）。

从**真实源码**与**正式契约**建立 Behavior 之间的依赖边，并显式区分：

- `SOURCE_OBSERVED`：边来自源码（函数调用 / 信号连接 / 状态写入 / 文件访问），带 `file:line`。
- `CONTRACT_DERIVED`：边只来自契约（`requires` / precondition 引用别的 Feature），未在源码确认。
- `UNRESOLVED`：契约要求依赖，但既没有源码边也没有可归属目标——单独列出，不伪装成边。

禁止按 Behavior 名字建依赖；循环依赖不自动判错，分类为事件环（合理）或状态环（需评审）。

用法：
    python .ai/tools/learning/dependencies.py --build
    python .ai/tools/learning/dependencies.py --query upstream --behavior i_frames/iframes_block_damage_within_window
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import time

import gd_parse
import paths
import source_analysis

GRAPH_PATH = os.path.join(paths.LEARNING_STATE, "behavior_dependency_graph.json")
SCHEMA = "behavior_dependency_graph"
SCHEMA_VERSION = 1

DEPENDENCY_TYPES = ("CALLS", "READS_STATE_FROM", "WRITES_STATE_TO", "EMITS_EVENT_TO",
                    "RECEIVES_EVENT_FROM", "USES_RESOURCE", "PERSISTS_DATA_TO",
                    "RESTORES_DATA_FROM", "REQUIRES_PRECONDITION", "SHARES_STATE_WITH")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _analyses() -> dict[tuple[str, str], dict]:
    found = {}
    for path in glob.glob(os.path.join(source_analysis.OUTPUT_DIR, "*", "*.json")):
        with open(path, encoding="utf-8") as handle:
            record = json.load(handle)
        found[(record["feature_id"], record["behavior_id"])] = record
    return found


def _class_index() -> dict[str, tuple[str, gd_parse.Script]]:
    """class_name → (feature_id, script)。用于把 `var _health: Health` 归属到 Feature。"""
    index: dict[str, tuple[str, gd_parse.Script]] = {}
    for feature_id in sorted(os.listdir(paths.FEATURES_DIR)):
        for path in paths.implementation_files(feature_id):
            try:
                script = gd_parse.parse_file(path)
            except gd_parse.ParseError:
                continue
            if script.class_name:
                index.setdefault(script.class_name, (feature_id, script))
    return index


def _function_index(classes: dict[str, tuple[str, gd_parse.Script]]) -> dict[tuple[str, str], tuple[str, gd_parse.Script, gd_parse.Function]]:
    index = {}
    for feature_id, script in classes.values():
        for function in script.functions:
            index.setdefault((feature_id, function.name), (feature_id, script, function))
    return index


def _typed_receivers(script: gd_parse.Script) -> dict[str, str]:
    """实例变量名 → 声明的类型名（`var _health: Health` → `_health: Health`）。"""
    return {item["name"]: item["type"] for item in script.variables + script.exports
            if item.get("type")}


def _behavior_for_function(analyses: dict, feature_id: str, function_name: str) -> str | None:
    for (candidate_feature, behavior_id), record in analyses.items():
        if candidate_feature != feature_id:
            continue
        for entry in record.get("entry_points") or []:
            if entry["name"] == function_name:
                return behavior_id
    return None


def _anchors(analyses: dict) -> dict[str, list[dict]]:
    """feature_id → 该 Feature 的 Behavior 入口表（用于把函数归属到 Behavior）。"""
    anchors: dict[str, list[dict]] = {}
    for (feature_id, behavior_id), record in analyses.items():
        for entry in record.get("entry_points") or []:
            anchors.setdefault(feature_id, []).append(
                {"behavior_id": behavior_id, "name": entry["name"],
                 "file": entry["file"], "line": entry["line"]})
    return anchors


def build() -> dict:
    behaviors = paths.supported_behaviors()
    analyses = _analyses()
    classes = _class_index()
    functions = _function_index(classes)
    anchors = _anchors(analyses)
    class_to_feature = {name: feature for name, (feature, _script) in classes.items()}

    nodes = []
    for item in behaviors:
        key = (item["feature_id"], item["behavior_id"])
        record = analyses.get(key) or {}
        nodes.append({
            "behavior": "%s/%s" % (item["feature_id"], item["behavior_id"]),
            "feature_id": item["feature_id"],
            "behavior_id": item["behavior_id"],
            "behavior_category": paths.category_of(item["feature_id"], item["behavior_id"]),
            "analysis_status": record.get("analysis_status", "SOURCE_NOT_ANALYZED"),
        })

    edges: list[dict] = []
    seen = set()

    def add(source: str, target: str, kind: str, reference: str, evidence_kind: str,
            confidence: str, status: str, detail: str = "") -> None:
        key = (source, target, kind, reference)
        if source == target and kind != "SHARES_STATE_WITH":
            return
        if key in seen:
            return
        seen.add(key)
        edges.append({"id": "dep-%04d" % (len(edges) + 1), "source_behavior": source,
                      "target_behavior": target, "dependency_type": kind,
                      "source_reference": reference, "evidence_kind": evidence_kind,
                      "confidence": confidence, "verification_status": status,
                      "detail": detail})

    # ---- 源码边：调用 / 信号 / 状态写入 / 持久化 ------------------------
    for (feature_id, behavior_id), record in sorted(analyses.items()):
        source = "%s/%s" % (feature_id, behavior_id)
        for entry in record.get("entry_points") or []:
            path = os.path.join(paths.ROOT, entry["file"])
            if not os.path.isfile(path):
                continue
            script = gd_parse.parse_file(path)
            function = script.function(entry["name"])
            if function is None:
                continue
            receivers = _typed_receivers(script)
            for call in gd_parse.calls(function):
                declared = receivers.get(call["receiver"], "")
                if declared not in class_to_feature:
                    continue
                target_feature = class_to_feature[declared]
                if target_feature == feature_id:
                    continue
                target_behavior = _behavior_for_function(analyses, target_feature, call["method"])
                if target_behavior is None:
                    target_behavior = next(
                        (node["behavior_id"] for node in nodes
                         if node["feature_id"] == target_feature), None)
                    confidence = "MEDIUM"
                else:
                    confidence = "HIGH"
                if target_behavior is None:
                    continue
                target_record = analyses.get((target_feature, target_behavior)) or {}
                writes = any(item["write_count"] for item in target_record.get("state_variables") or [])
                kind = "WRITES_STATE_TO" if writes else "CALLS"
                reference = "%s:%d#call=%s.%s" % (entry["file"], call["line"],
                                                  call["receiver"], call["method"])
                add(source, "%s/%s" % (target_feature, target_behavior), kind, reference,
                    "SOURCE_REFERENCE", confidence, "SOURCE_OBSERVED",
                    "receiver %s: %s" % (call["receiver"], declared))
            for connect in gd_parse.connects(script.function("_ready") or function):
                declared = receivers.get(connect["emitter"], "")
                if declared not in class_to_feature:
                    continue
                target_feature = class_to_feature[declared]
                if target_feature == feature_id:
                    continue
                target_behavior = None
                for (candidate_feature, candidate_behavior), candidate in analyses.items():
                    if candidate_feature != target_feature:
                        continue
                    if any(item.get("signal") == connect["signal"]
                           and item.get("kind") == "emit"
                           for item in candidate.get("events") or []):
                        target_behavior = candidate_behavior
                        break
                if target_behavior is None:
                    continue
                reference = "%s:%d#connect=%s.%s" % (entry["file"], connect["line"],
                                                     connect["emitter"], connect["signal"])
                add(source, "%s/%s" % (target_feature, target_behavior),
                    "RECEIVES_EVENT_FROM", reference, "SOURCE_REFERENCE", "HIGH",
                    "SOURCE_OBSERVED", "signal %s" % connect["signal"])
                add("%s/%s" % (target_feature, target_behavior), source,
                    "EMITS_EVENT_TO", reference, "SOURCE_REFERENCE", "HIGH",
                    "SOURCE_OBSERVED", "signal %s" % connect["signal"])

    # ---- 契约边：precondition 引用别的 Feature 的状态 ---------------------
    feature_ids = {item["feature_id"] for item in behaviors}
    for item in behaviors:
        feature_id, behavior_id = item["feature_id"], item["behavior_id"]
        source = "%s/%s" % (feature_id, behavior_id)
        for precondition in item["behavior"].get("preconditions") or []:
            alias = str(precondition.get("check") or "").split(".")[0]
            if alias not in feature_ids or alias == feature_id:
                continue
            targets = [node for node in nodes if node["feature_id"] == alias]
            if not targets:
                continue
            symbol = str(precondition.get("check") or "").split(".")[-1]
            preferred = None
            for (candidate_feature, candidate_behavior), record in analyses.items():
                if candidate_feature != alias:
                    continue
                if any(symbol in json.dumps(step, ensure_ascii=False)
                       for step in (item["behavior"].get("expected") or [])):
                    preferred = candidate_behavior
            target = preferred or targets[0]["behavior_id"]
            reference = "%s#behavior=%s.preconditions[%s]" % (item["contract_path"],
                                                              behavior_id,
                                                              precondition.get("check"))
            add(source, "%s/%s" % (alias, target), "REQUIRES_PRECONDITION", reference,
                "CONTRACT_REFERENCE", "MEDIUM", "CONTRACT_DERIVED",
                "precondition %s" % precondition.get("check"))

    # ---- 持久化边：同 Feature 内「写入者 → 读取者」 ---------------------
    for feature_id, items in {}.items():
        break
    writers: dict[str, list[str]] = {}
    readers: dict[str, list[str]] = {}
    for (feature_id, behavior_id), record in analyses.items():
        for effect in record.get("side_effects") or []:
            if effect.get("kind") != "file_access":
                continue
            behavior = "%s/%s" % (feature_id, behavior_id)
            bucket = writers if str(effect.get("mode", "")).upper().startswith(("WRITE", "APPEND")) \
                else readers
            bucket.setdefault(feature_id, []).append(behavior)
            reference = "%s:%d#file_access=%s" % (effect["file"], effect["line"],
                                                  effect.get("path", ""))
            record.setdefault("persistence", []).append({"mode": effect.get("mode"),
                                                          "reference": reference})
    for feature_id in sorted(set(writers) | set(readers)):
        for writer in sorted(set(writers.get(feature_id, []))):
            for reader in sorted(set(readers.get(feature_id, []))):
                if writer == reader:
                    continue
                add(writer, reader, "PERSISTS_DATA_TO", "analysis:%s#file_write" % writer,
                    "SOURCE_REFERENCE", "HIGH", "SOURCE_OBSERVED", "同 Feature 写→读")
                add(reader, writer, "RESTORES_DATA_FROM", "analysis:%s#file_read" % reader,
                    "SOURCE_REFERENCE", "HIGH", "SOURCE_OBSERVED", "同 Feature 读→写")

    # ---- 同 Feature 共享状态 -------------------------------------------
    by_feature: dict[str, list[tuple[str, dict]]] = {}
    for (feature_id, behavior_id), record in analyses.items():
        by_feature.setdefault(feature_id, []).append((behavior_id, record))
    for feature_id, items in by_feature.items():
        for index, (behavior_a, record_a) in enumerate(items):
            state_a = {item["variable"] for item in record_a.get("state_variables") or []}
            for behavior_b, record_b in items[index + 1:]:
                state_b = {item["variable"] for item in record_b.get("state_variables") or []}
                shared = sorted(state_a & state_b)
                if not shared:
                    continue
                add("%s/%s" % (feature_id, behavior_a), "%s/%s" % (feature_id, behavior_b),
                    "SHARES_STATE_WITH", "analysis:%s/%s#state=%s" % (
                        feature_id, behavior_a, ",".join(shared)),
                    "SOURCE_REFERENCE", "MEDIUM", "SOURCE_OBSERVED", ",".join(shared))

    # ---- 未解析的契约依赖 ----------------------------------------------
    unresolved = []
    covered_features = {edge["source_behavior"].split("/")[0] for edge in edges}
    for feature_id in sorted(feature_ids):
        meta = paths.feature_meta(feature_id)
        for requirement in meta.get("requires") or []:
            if feature_id in covered_features:
                continue
            unresolved.append({"feature_id": feature_id, "requirement": requirement,
                               "reason": "契约声明 requires，但源码中没有任何可归属的出边"})

    # ---- 循环检测（不判错，只分类） -------------------------------------
    adjacency: dict[str, list[dict]] = {}
    for edge in edges:
        adjacency.setdefault(edge["source_behavior"], []).append(edge)
    cycles = []
    for component in _cycles(adjacency):
        kinds = {edge["dependency_type"] for edge in component["edges"]}
        event_only = kinds <= {"EMITS_EVENT_TO", "RECEIVES_EVENT_FROM"}
        persistence = bool(kinds & {"PERSISTS_DATA_TO", "RESTORES_DATA_FROM"})
        size = len(component["nodes"])
        if event_only:
            classification, action = "event_loop", "expected"
        elif persistence:
            classification, action = "persistence_pair", "expected"
        elif size > 6:
            # 大型 SCC：共享状态的辐辏（如 Health 生态系统），是架构事实而非错误
            classification, action = "hub_component", "note"
        else:
            classification, action = "state_cycle", "review"
        cycles.append({
            "nodes": component["nodes"],
            "length": size,
            "edge_count": len(component["edges"]),
            "dependency_types": sorted(kinds),
            "classification": classification,
            "action": action,
            "sample_edges": [{"source": edge["source_behavior"],
                              "type": edge["dependency_type"],
                              "target": edge["target_behavior"]}
                             for edge in component["edges"][:4]],
        })

    status_distribution: dict[str, int] = {}
    type_distribution: dict[str, int] = {}
    for edge in edges:
        status_distribution[edge["verification_status"]] = \
            status_distribution.get(edge["verification_status"], 0) + 1
        type_distribution[edge["dependency_type"]] = \
            type_distribution.get(edge["dependency_type"], 0) + 1

    return {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        "nodes": nodes,
        "edges": edges,
        "cycles": cycles,
        "unresolved_requirements": unresolved,
        "summary": {
            "nodes": len(nodes),
            "edges": len(edges),
            "source_observed_edges": status_distribution.get("SOURCE_OBSERVED", 0),
            "contract_derived_edges": status_distribution.get("CONTRACT_DERIVED", 0),
            "cycle_count": len(cycles),
            "event_loops": sum(1 for cycle in cycles if cycle["classification"] == "event_loop"),
            "state_cycles": sum(1 for cycle in cycles if cycle["classification"] == "state_cycle"),
            "dependency_types": type_distribution,
            "behaviors_with_outgoing": len({edge["source_behavior"] for edge in edges}),
        },
    }


def _cycles(adjacency: dict[str, list[dict]]) -> list[list[dict]]:
    """Tarjan SCC + 自环；返回每个环的边序列（简单 DFS 取环）。"""
    index_of: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    result: list[list[dict]] = []
    counter = [0]

    def strongconnect(node: str) -> None:
        index_of[node] = low[node] = counter[0]
        counter[0] += 1
        stack.append(node)
        on_stack.add(node)
        for edge in adjacency.get(node, []):
            target = edge["target_behavior"]
            if target not in index_of:
                strongconnect(target)
                low[node] = min(low[node], low[target])
            elif target in on_stack:
                low[node] = min(low[node], index_of[target])
        if low[node] == index_of[node]:
            component = []
            while True:
                item = stack.pop()
                on_stack.discard(item)
                component.append(item)
                if item == node:
                    break
            if len(component) > 1:
                members = set(component)
                cycle_edges = [edge for member in component
                               for edge in adjacency.get(member, [])
                               if edge["target_behavior"] in members]
                if cycle_edges:
                    result.append({"nodes": sorted(component), "edges": cycle_edges})
            elif component and any(edge["target_behavior"] == component[0]
                                   for edge in adjacency.get(component[0], [])):
                result.append({"nodes": [component[0]],
                               "edges": [edge for edge in adjacency[component[0]]
                                         if edge["target_behavior"] == component[0]]})

    for node in sorted(adjacency):
        if node not in index_of:
            strongconnect(node)
    return result


def load(path: str = GRAPH_PATH) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save(graph: dict, path: str = GRAPH_PATH) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(graph, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def _queries(graph: dict, behavior: str, direction: str) -> list[dict]:
    key = "source_behavior" if direction == "downstream" else "target_behavior"
    match = "target_behavior" if direction == "downstream" else "source_behavior"
    return [edge for edge in graph["edges"] if edge[key] == behavior
            or edge[match] == behavior and False]


def query(graph: dict, behavior: str, kind: str = "downstream") -> list[dict]:
    if kind == "downstream":
        return [edge for edge in graph["edges"] if edge["source_behavior"] == behavior]
    if kind == "upstream":
        return [edge for edge in graph["edges"] if edge["target_behavior"] == behavior]
    if kind == "events":
        return [edge for edge in graph["edges"] if edge["dependency_type"] in
                ("EMITS_EVENT_TO", "RECEIVES_EVENT_FROM")]
    if kind == "shared_state":
        return [edge for edge in graph["edges"] if edge["dependency_type"] == "SHARES_STATE_WITH"]
    if kind == "resources":
        return [edge for edge in graph["edges"] if edge["dependency_type"] == "USES_RESOURCE"]
    if kind == "persistence":
        return [edge for edge in graph["edges"] if edge["dependency_type"] in
                ("PERSISTS_DATA_TO", "RESTORES_DATA_FROM")]
    raise ValueError("unknown query kind: %s" % kind)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Behavior dependency graph")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--query", choices=["upstream", "downstream", "events",
                                            "shared_state", "resources", "persistence"])
    parser.add_argument("--behavior")
    parser.add_argument("--out", default=GRAPH_PATH)
    args = parser.parse_args(argv)

    if args.build:
        graph = build()
        save(graph, args.out)
        print(json.dumps(graph["summary"], ensure_ascii=False))
        return 0
    if args.query:
        if not args.behavior and args.query in ("upstream", "downstream"):
            parser.error("--behavior is required for upstream/downstream")
        graph = load(args.out)
        for edge in query(graph, args.behavior or "", args.query):
            print("%-26s %-22s %s" % (edge["source_behavior"], edge["dependency_type"],
                                      edge["target_behavior"]))
        return 0
    parser.error("either --build or --query is required")


if __name__ == "__main__":
    raise SystemExit(main())
