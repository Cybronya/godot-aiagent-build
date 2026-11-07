#!/usr/bin/env python3
"""Knowledge-Driven Test Scenario Generator（Phase 1.66）。

从**真实知识**（Phase 1.65 Knowledge Store）+ 正式契约 + 源码分析 + 依赖图生成可执行场景。

设计约束：

- 不在代码里写死 Behavior 名单；支持集合始终由 `paths.supported_behaviors()` 动态读取，
  CLI 只是选择子集。
- 场景的动作/期望使用 **Phase 1.41 行为协议**（`behavior_protocol.yaml`）的同一套词汇，
  因此能被现有真实 Runner 执行，不需要第二套执行器。
- 规则匹配基于**知识事实**（守卫条件、依赖边），不是 Behavior 名字：新增 Behavior 只要产生
  同类知识就会被覆盖。
- 生成的知识来源必须可追溯：每条场景记录 `knowledge_refs` / `source_refs` / `dependency_refs`，
  并把「哪个守卫、哪条依赖」写进 `derivation`。
- 只生成候选；`execution_status = NOT_EXECUTED`、`validation_status = PENDING`。
  生成成功不等于执行成功，更不等于通过。

用法：
    python .ai/tools/learning/scenario_generator.py --behaviors openable_door/open,health/damage
    python .ai/tools/learning/scenario_generator.py --all
    python .ai/tools/learning/scenario_generator.py --from-plan .ai/learning/learning_plan.json --limit 20
退出码：0 生成完成（可能 0 条）；1 输入错误。
"""

from __future__ import annotations

import argparse
import copy
import glob
import hashlib
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
for _p in (_HERE, _TOOLS, os.path.join(_TOOLS, "scene_composer"),
           os.path.join(_TOOLS, "validator")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paths                                    # noqa: E402
import knowledge_v2 as kv                       # noqa: E402
import dependencies                             # noqa: E402
import feature_behavior_evidence as fbe         # noqa: E402
import behavior_protocol                        # noqa: E402

SCENARIO_DIR = os.path.join(paths.LEARNING_STATE, "scenarios")
INDEX_PATH = os.path.join(paths.LEARNING_STATE, "scenarios.json")
SCHEMA = "behavior_test_scenario"
SCHEMA_VERSION = 1
FOREIGN_GROUP = "p166_foreign"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _digest(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _dump(path: str, document) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _load(path: str, default):
    if not os.path.isfile(path):
        return default
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


# ---------------------------------------------------------------- 知识索引


def approved_records(feature_id: str, behavior_id: str) -> list[dict]:
    return [record for record in kv.all_records()
            if record["feature_id"] == feature_id and record["behavior_id"] == behavior_id
            and record["verification_status"] == "APPROVED"]


def _record_of(records: list[dict], knowledge_type: str, key: str = "") -> list[dict]:
    return [record for record in records
            if record["knowledge_type"] == knowledge_type and (not key or record["key"] == key)]


def _guards(records: list[dict]) -> list[tuple[dict, dict]]:
    """(record, condition) 对；只返回带真实 file/line 的守卫。"""
    found = []
    for record in _record_of(records, "SOURCE_OBSERVATION", "guards"):
        for condition in (record["content"] or {}).get("conditions") or []:
            if isinstance(condition, dict) and condition.get("condition"):
                found.append((record, condition))
    return found


def _signal_expectations(contract: dict) -> list[dict]:
    return [check for check in contract["expected"] if check.get("check") == "signal"]


def _expected_count(contract: dict, entry: str) -> int:
    for check in _signal_expectations(contract):
        if check.get("entry") == entry:
            return int(check.get("count") or 0)
    return 0


def _check_key(check: dict) -> tuple:
    return (check.get("check"), check.get("entry", ""), check.get("target", "."))


def _without(checks: list[dict], keys: set[tuple]) -> list[dict]:
    return [check for check in checks if _check_key(check) not in keys]


def _with_checks(checks: list[dict], additions: list[dict]) -> list[dict]:
    """新检查替换同键旧检查（避免同一 (check, entry, target) 出现互相矛盾的期望）。"""
    keys = {_check_key(item) for item in additions}
    return _without(checks, keys) + additions


# ---------------------------------------------------------------- 规则目录
#
# 每条规则 = 知识事实的通用匹配器 + 由**基础契约**参数化的场景构造器。
# 没有 Behavior 名字；规则只依赖契约里真实存在的 action/expected 形状。

def _rule_idempotent_repeat(contract, records, guards, graph):
    for record, condition in guards:
        if "== value" not in str(condition.get("condition")):
            continue
        actions = [action for action in contract["actions"] if not action.get("fixture")]
        if not actions:
            return None
        repeated = [copy.deepcopy(action) for action in actions]
        # 契约本身就已经重复了同一动作 → 这个场景不新，跳过
        if sum(1 for action in contract["actions"] if action == actions[0]) >= 2:
            return None
        return {
            "rule_id": "idempotent_repeat",
            "scenario_type": "GUARD_IDEMPOTENCE",
            "title": "重复同一动作不应产生第二次效果（守卫：%s）" % condition["condition"],
            "actions": [copy.deepcopy(action) for action in contract["actions"]] + repeated,
            "preconditions": copy.deepcopy(contract["preconditions"]),
            "expected": copy.deepcopy(contract["expected"]),
            "window_frames": contract["window_frames"],
            "knowledge_refs": [record["knowledge_id"]],
            "derivation": ("守卫 %s（%s:%s）表明重复输入是 no-op；因此重复首个行为动作后，"
                           "契约期望的终态与信号次数必须保持不变"
                           % (condition["condition"], condition.get("file"),
                              condition.get("line"))),
            "source_refs": [{"file": condition.get("file"), "line": condition.get("line"),
                             "function": condition.get("function")}],
        }
    return None


def _rule_foreign_group(contract, records, guards, graph):
    overlap = [action for action in contract["actions"]
               if action.get("type") == "physics.overlap"]
    if not overlap:
        return None
    membership = [item for item in guards
                  if "is_in_group" in str(item[1].get("condition"))]
    if not membership:
        return None
    record, condition = membership[0]
    actions = []
    for action in contract["actions"]:
        copied = copy.deepcopy(action)
        if copied.get("type") == "physics.overlap":
            params = dict(copied.get("params") or {})
            params["group"] = FOREIGN_GROUP
            copied["params"] = params
        actions.append(copied)
    expected = []
    for check in contract["expected"]:
        if check.get("check") == "signal":
            inverted = {key: value for key, value in check.items() if key != "last_args"}
            inverted["count"] = 0
            expected.append(inverted)
        elif isinstance(check.get("equals"), bool):
            inverted = dict(check)
            inverted["equals"] = not check["equals"]
            expected.append(inverted)
    if not expected:
        return None
    return {
        "rule_id": "foreign_group_ignored",
        "scenario_type": "GUARD_MEMBERSHIP",
        "title": "非目标组成员不得触发行为（守卫：%s）" % condition["condition"],
        "actions": actions,
        "preconditions": copy.deepcopy(contract["preconditions"]),
        "expected": expected,
        "window_frames": contract["window_frames"],
        "knowledge_refs": [record["knowledge_id"]],
        "derivation": ("守卫 %s（%s:%s）按组成员过滤；把接触体放进 %r 组后，"
                       "契约期望的信号必须为 0 次、布尔终态必须保持原值"
                       % (condition["condition"], condition.get("file"),
                          condition.get("line"), FOREIGN_GROUP)),
        "source_refs": [{"file": condition.get("file"), "line": condition.get("line"),
                         "function": condition.get("function")}],
    }


def _rule_invalid_slot(contract, records, guards, graph):
    save = [action for action in contract["actions"]
            if action.get("type") == "savegame.save_slot"]
    if not save:
        return None
    validation = [item for item in guards
                  if "_is_valid_slot_name" in str(item[1].get("condition"))]
    if not validation:
        return None
    record, condition = validation[0]
    actions = []
    for action in contract["actions"]:
        copied = copy.deepcopy(action)
        if copied.get("type") == "savegame.save_slot":
            params = dict(copied.get("params") or {})
            params["slot"] = "p166/invalid:slot"
            copied["params"] = params
        actions.append(copied)
    target = save[0].get("target", ".")
    expected = [copy.deepcopy(check) for check in contract["expected"]
                if check.get("check") != "signal" and check.get("check") != "savegame.last_slot"]
    additions = []
    for check in _signal_expectations(contract):
        inverted = {key: value for key, value in check.items() if key != "last_args"}
        inverted["count"] = 0
        additions.append(inverted)
    additions.append({"check": "savegame.last_slot", "target": target, "equals": ""})
    expected = _with_checks(expected, additions)
    preconditions = copy.deepcopy(contract["preconditions"])
    preconditions.append({"check": "savegame.last_slot", "target": save[0].get("target", "."),
                          "equals": ""})
    return {
        "rule_id": "invalid_slot_rejected",
        "scenario_type": "GUARD_INPUT_VALIDATION",
        "title": "非法槽位名不得写入存档（守卫：%s）" % condition["condition"],
        "actions": actions,
        "preconditions": preconditions,
        "expected": expected,
        "window_frames": contract["window_frames"],
        "knowledge_refs": [record["knowledge_id"]],
        "derivation": ("守卫 %s（%s:%s）在写入前拒绝非法槽名；用非法槽名替换契约动作后，"
                       "存档信号必须为 0 次且 last_slot 保持空"
                       % (condition["condition"], condition.get("file"),
                          condition.get("line"))),
        "source_refs": [{"file": condition.get("file"), "line": condition.get("line"),
                         "function": condition.get("function")}],
    }


def _rule_post_terminal(contract, records, guards, graph):
    damage = [action for action in contract["actions"]
              if action.get("type") == "health.take_damage"]
    if not damage:
        return None
    terminal = [item for item in guards
                if "_is_dead" in str(item[1].get("condition"))
                or "_current_health == 0" in str(item[1].get("condition"))]
    if not terminal:
        return None
    record, condition = terminal[0]
    target = damage[0].get("target", ".")
    actions = [copy.deepcopy(action) for action in contract["actions"]]
    actions.append({"type": "health.take_damage", "target": target, "params": {"amount": 100}})
    actions.append({"type": "health.heal", "target": target, "params": {"amount": 1}})
    changed = _expected_count(contract, "health.health_changed")
    kept = [copy.deepcopy(check) for check in contract["expected"]
            if check.get("check") not in ("signal", "health.current")]
    expected = _with_checks(kept, [
        {"check": "health.current", "target": target, "equals": 0},
        {"check": "health.is_dead", "target": target, "equals": True},
        {"check": "signal", "target": target, "entry": "health.health_changed",
         "count": changed + 1},
        {"check": "signal", "target": target, "entry": "health.died", "count": 1},
    ])
    return {
        "rule_id": "post_terminal_input_ignored",
        "scenario_type": "GUARD_TERMINAL_STATE",
        "title": "死亡后的伤害与治疗不得改变状态（守卫：%s）" % condition["condition"],
        "actions": actions,
        "preconditions": copy.deepcopy(contract["preconditions"]),
        "expected": expected,
        "window_frames": max(int(contract["window_frames"]), 5),
        "knowledge_refs": [record["knowledge_id"]],
        "derivation": ("守卫 %s（%s:%s）在死亡后提前返回；追加致死伤害与治疗后，"
                       "current 必须为 0、died 恰一次、health_changed 比契约多一次"
                       % (condition["condition"], condition.get("file"),
                          condition.get("line"))),
        "source_refs": [{"file": condition.get("file"), "line": condition.get("line"),
                         "function": condition.get("function")}],
    }


DEPENDENCY_SCENARIO = {
    "rule_id": "dependency_postcondition_after_death",
    "scenario_type": "DEPENDENCY_PRECONDITION",
    "title": "依赖 Behavior 的死亡后置条件不得被破坏",
    "actions": [
        {"type": "health.take_damage", "target": "Host/Health", "params": {"amount": 10}},
        {"type": "simulation.advance_frames", "params": {"frames": 1}},
        {"type": "health.take_damage", "target": "Host/Health", "params": {"amount": 1}},
        {"type": "simulation.advance_frames", "params": {"frames": 1}},
    ],
    "expected": [
        {"check": "health.current", "target": "Host/Health", "equals": 0},
        {"check": "health.is_dead", "target": "Host/Health", "equals": True},
        {"check": "signal", "target": "Host/Health", "entry": "health.health_changed",
         "count": 1},
        {"check": "signal", "target": "Host/Health", "entry": "health.died", "count": 1},
    ],
}


def _rule_dependency_precondition(contract, records, guards, graph):
    edges = []
    for record in _record_of(records, "DEPENDENCY_KNOWLEDGE", "dependencies"):
        for edge in (record["content"] or {}).get("edges") or []:
            haystack = (str(edge.get("detail", ""))
                        + str(edge.get("target_behavior", ""))).lower()
            if edge.get("dependency_type") == "REQUIRES_PRECONDITION" and "health" in haystack:
                edges.append((record, edge))
    if not edges:
        return None
    record, edge = edges[0]
    actions = copy.deepcopy(DEPENDENCY_SCENARIO["actions"])
    targets = {action["target"] for action in contract["actions"]
               if "Host/Health" in str(action.get("target"))}
    if not targets:
        # 契约的动作目标不是 Host/Health → 依赖场景无法套用，不生成（不猜路径）。
        return None
    preconditions = [copy.deepcopy(check) for check in contract["preconditions"]
                     if check.get("check") == "health.current"]
    return {
        "rule_id": DEPENDENCY_SCENARIO["rule_id"],
        "scenario_type": DEPENDENCY_SCENARIO["scenario_type"],
        "title": DEPENDENCY_SCENARIO["title"],
        "actions": actions,
        "preconditions": preconditions,
        "expected": copy.deepcopy(DEPENDENCY_SCENARIO["expected"]),
        "window_frames": max(int(contract["window_frames"]), 5),
        "knowledge_refs": [record["knowledge_id"]],
        "derivation": ("依赖边 %s（%s）声明该 Behavior 依赖 health 的死亡后置条件；"
                       "在真实夹具上杀死宿主后继续输入，依赖方不得复活或二次结算"
                       % (edge.get("id"), edge.get("dependency_type"))),
        "source_refs": [{"edge": edge.get("id"),
                         "reference": edge.get("source_reference")}],
    }


RULES = (_rule_idempotent_repeat, _rule_foreign_group, _rule_invalid_slot,
         _rule_post_terminal, _rule_dependency_precondition)

RULE_IDS = ("idempotent_repeat", "foreign_group_ignored", "invalid_slot_rejected",
            "post_terminal_input_ignored", "dependency_postcondition_after_death")


# ---------------------------------------------------------------- 生成


def _make_scenario(feature_id: str, behavior_id: str, contract: dict, build: dict,
                   contract_version: str) -> dict:
    body = {
        "feature_id": feature_id,
        "behavior_id": behavior_id,
        "scenario_type": build["scenario_type"],
        "rule_id": build["rule_id"],
        "scene": contract["scene"],
        "actions": build["actions"],
        "preconditions": build["preconditions"],
        "expected_observations": build["expected"],
        "window_frames": build["window_frames"],
    }
    scenario_id = "s-" + _digest(body)[:16]
    return {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "scenario_id": scenario_id,
        "feature_id": feature_id,
        "behavior_id": behavior_id,
        "behavior": "%s/%s" % (feature_id, behavior_id),
        "scenario_type": build["scenario_type"],
        "rule_id": build["rule_id"],
        "title": build["title"],
        "contract_version": contract_version,
        "scene": contract["scene"],
        "knowledge_refs": sorted(set(build["knowledge_refs"])),
        "source_refs": build["source_refs"],
        "dependency_refs": [edge.get("edge") for edge in build["source_refs"]
                            if edge.get("edge")],
        "preconditions": build["preconditions"],
        "actions": build["actions"],
        "expected_observations": build["expected"],
        "window_frames": build["window_frames"],
        "cleanup": ["workspace 由 runner 逐场景销毁；user:// 使用独立 custom_user_dir"],
        "environment_requirements": ["Godot 4.7 headless", "behavior_protocol v2",
                                     "scene: %s" % contract["scene"]],
        "failure_classification_policy": {
            "BEHAVIOR_FAILURE": "执行观测与契约期望不符，且 Validator/Attestation 均通过",
            "TEST_DESIGN_FAILURE": "动作未执行、前置不成立或期望与契约矛盾",
            "ENVIRONMENT_FAILURE": "Godot/资源不可用",
            "RUNNER_FAILURE": "探针或判定器故障",
            "RESOURCE_FAILURE": "场景/夹具缺失",
            "UNKNOWN_FAILURE": "证据不足以归类",
        },
        "derivation": build["derivation"],
        "execution_status": "NOT_EXECUTED",
        "validation_status": "PENDING",
        "created_at": _now(),
    }


def generate_behavior(feature_id: str, behavior_id: str) -> dict:
    """单个 Behavior → {scenarios, skipped}；契约缺失/未知 Behavior 直接报错不猜。"""
    contracts, _reports = fbe.build_contracts(feature_id, "Features")
    contracts = [contract for contract in contracts
                 if str(contract["behavior"]) == behavior_id]
    if not contracts:
        return {"feature_id": feature_id, "behavior_id": behavior_id,
                "scenarios": [], "skipped": "CONTRACT_NOT_FOUND"}
    contract = contracts[0]
    records = approved_records(feature_id, behavior_id)
    graph = _load(dependencies.GRAPH_PATH, {"edges": []})
    guards = _guards(records)
    contract_version = paths.contract_version(feature_id, behavior_id)
    scenarios = []
    signatures = set()
    base_signature = _digest({"actions": contract["actions"],
                              "expected": contract["expected"]})
    for rule in RULES:
        build = rule(contract, records, guards, graph)
        if build is None:
            continue
        signature = _digest({"actions": build["actions"], "expected": build["expected"]})
        if signature == base_signature or signature in signatures:
            continue
        signatures.add(signature)
        scenarios.append(_make_scenario(feature_id, behavior_id, contract, build,
                                        contract_version))
    return {"feature_id": feature_id, "behavior_id": behavior_id,
            "scenarios": scenarios, "skipped": "" if scenarios else "NO_APPLICABLE_RULE"}


def selection(behaviors: list[str] | None, from_plan: str, limit: int) -> list[tuple[str, str]]:
    if behaviors:
        pairs = []
        for item in behaviors:
            if "/" not in item:
                raise SystemExit("behavior must be feature/behavior: %r" % item)
            feature_id, behavior_id = item.split("/", 1)
            pairs.append((feature_id, behavior_id))
        return pairs
    if from_plan:
        plan = _load(from_plan, None)
        if plan is None:
            raise SystemExit("plan not found: %s" % from_plan)
        pairs = []
        for task in plan.get("tasks") or []:
            if task.get("task_type") != "DESIGN_TEST_SCENARIO":
                continue
            pair = (task["feature_id"], task["behavior_id"])
            if pair not in pairs:
                pairs.append(pair)
        return pairs[:limit] if limit else pairs
    # 默认：正式支持集合全体（动态读取，不硬编码）
    return [(item["feature_id"], item["behavior_id"]) for item in paths.supported_behaviors()]


def build(behaviors: list[str] | None = None, from_plan: str = "", limit: int = 0) -> dict:
    results = []
    scenarios = []
    for feature_id, behavior_id in selection(behaviors, from_plan, limit):
        result = generate_behavior(feature_id, behavior_id)
        results.append({"behavior": "%s/%s" % (feature_id, behavior_id),
                        "generated": len(result["scenarios"]),
                        "skipped": result["skipped"]})
        scenarios.extend(result["scenarios"])
    return {
        "schema": "behavior_scenario_index",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        "note": "候选场景；execution_status=NOT_EXECUTED 表示尚未真实执行",
        "rules": list(RULE_IDS),
        "summary": {"behaviors": len(results), "scenarios": len(scenarios),
                    "with_scenarios": sum(1 for item in results if item["generated"])},
        "behaviors": results,
        "scenarios": scenarios,
    }


def write(document: dict, out_dir: str = "", prune: bool = False) -> dict:
    directory = out_dir or SCENARIO_DIR
    os.makedirs(directory, exist_ok=True)
    paths_written = []
    kept = set()
    for scenario in document["scenarios"]:
        path = os.path.join(directory, "%s.json" % scenario["scenario_id"])
        _dump(path, scenario)
        paths_written.append(path)
        kept.add(os.path.basename(path))
    removed = []
    if prune:
        for path in sorted(glob.glob(os.path.join(directory, "s-*.json"))):
            if os.path.basename(path) in kept:
                continue
            os.remove(path)
            removed.append(os.path.relpath(path, paths.ROOT).replace(os.sep, "/"))
    document = dict(document)
    document["pruned"] = removed
    index_path = INDEX_PATH if not out_dir else os.path.join(out_dir, "index.json")
    _dump(index_path, document)
    return {"index": index_path, "scenarios": paths_written, "pruned": removed}


def load_scenarios(directory: str = "") -> list[dict]:
    directory = directory or SCENARIO_DIR
    return [_load(path, None) for path in sorted(glob.glob(os.path.join(directory, "s-*.json")))]


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--behaviors", default="", help="逗号分隔的 feature/behavior")
    parser.add_argument("--all", action="store_true", help="正式支持集合全体")
    parser.add_argument("--from-plan", default="", help="从 Learning Plan 的 DESIGN_TEST_SCENARIO 取")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--prune", action="store_true",
                        help="删除本次未生成的旧场景文件（仅限 s-*.json）")
    args = parser.parse_args(argv)

    behaviors = [item.strip() for item in args.behaviors.split(",") if item.strip()]
    if not behaviors and not args.all and not args.from_plan:
        parser.print_help()
        return 1
    document = build(behaviors or None, args.from_plan, args.limit)
    written = write(document, args.out_dir, prune=args.prune)
    print(json.dumps({"behaviors": document["summary"]["behaviors"],
                      "scenarios": document["summary"]["scenarios"],
                      "index": os.path.relpath(written["index"], paths.ROOT)},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
