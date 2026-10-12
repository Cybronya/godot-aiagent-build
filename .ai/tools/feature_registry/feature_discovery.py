#!/usr/bin/env python3
"""Feature Discovery (v1) —— 需求文本/角色 -> Feature 候选 + 资源槽位 + 资产候选。

    python feature_discovery.py "enemy" ["follows player"] [--role enemy] [--json]
    python feature_discovery.py "slime enemy" --top-n 3 --json

定位（Phase 1.8.1）：
    - 一站式「发现」接口：把 Feature Registry（feature_index.json）、
      实体槽位配置（.ai/context/entity_asset_slots.yaml）与
      Asset Registry（asset_index.json + query_assets）连接起来；
    - 复用现有实现：角色词表与 Feature 匹配内核来自 compose_features.py /
      discover_feature.py；槽位数据来自 entity_asset_slots.yaml；
      资产候选来自 query_assets.query（无第二套评分）；
    - 只读发现：不创建资源、不写绑定、不改场景。真正绑定由 bind_assets.py
      （显式 > 推断）执行，本工具输出可直接作为其 --binding 显式候选参考。

JSON 契约（--json；命名与错误语义对齐 asset_query_schema.yaml）：
    schema_version     整数（本文件 SCHEMA_VERSION）
    query              归一后的查询文本
    role               实体角色（显式 --role 或需求词推断；未知输入用 "*default*" 兜底并被报告）
    features           [feature id, ...]（按 discover_feature 确定性排序）
    feature_capabilities  {feature_id: [provides 标签]}（供 Agent 区分能力与槽位）
    requirements       结构/逻辑需求的占位（当前数据不足以表达 → 恒为空 dict + diagnostics）
    asset_slots        [资源 role, ...]（从槽位配置读出；结构需求的
                       scene/collision/stats 等不当成可检索资产槽位）
    asset_candidates   {slot: [{id, path, type, score, ...}]}（Asset Query 契约字段）
    missing            [{slot, kind: required, reason}]（仅必填槽位无候选）
    diagnostics        [{reason, message}]（index_missing / input_not_parsed /
                       config_error 等；balls-out 输入错误直接非 0 退出退出码 2）

退出码: 0 有结果（含部分候选缺失）；1 输入已解析但无有效候选；
        2 输入错误 / 索引缺失 / 配置损坏（与 asset_query_schema 错误语义一致）。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("FAIL: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)

_TOOL_DOTAI = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .ai
sys.path.insert(0, os.path.join(_TOOL_DOTAI, "tools", "feature_registry"))
sys.path.insert(0, os.path.join(_TOOL_DOTAI, "tools", "asset_registry"))

import compose_features as composer        # noqa: E402
import discover_feature as discovery       # noqa: E402

# Asset Query 复用（Phase 1.8.1 原则：无第二套评分）
from query_assets import query as asset_query       # noqa: E402
from asset_metadata import index_assets, load_index  # noqa: E402

SCHEMA_VERSION = 1

FEATURE_INDEX_PATH = os.path.join(_TOOL_DOTAI, "context", "feature_index.json")
ASSET_INDEX_PATH = os.path.join(_TOOL_DOTAI, "context", "asset_index.json")
SLOTS_PATH = os.path.join(_TOOL_DOTAI, "context", "entity_asset_slots.yaml")

# 结构/逻辑需求 → 不可作为资源槽位检索（Phase 1.8.1 任务明确要求区分）。
STRUCTURAL_REQUIREMENTS = ("scene", "collision", "stats", "script", "physics")
# 判定实体角色的优先词表（复用 compose_features.ROLE_KEYWORDS 的键语义）
ROLE_PATTERNS = dict(composer.ROLE_KEYWORDS)   # {"enemy": "enemy", "player": ..., ...}
ROLE_FALLBACK = "*default*"

# 角色级种子能力（查询词不含有效 Feature 语义时的最小可玩集）。
# 与 compose_features.ROLE_SEEDS 同源（enemy -> movement+damage 等），并补
# health_state：实测 compose_features 的敌方蓝图经 requires 链补齐后必然
# 含 health（test_composition 断言三件套）；seed 检索无 requires 展开，
# 因此在此显式并入，保持发现结果与实际组合行为一致。
def _seed_caps(role: str, caps: list) -> list:
    return list(caps) + (["health_state"] if role == "enemy" and "health_state" not in caps else [])


ROLE_SEEDS = {role: _seed_caps(role, caps) for role, caps in composer.ROLE_SEEDS.items()}


def load_slots(path: str = SLOTS_PATH) -> dict:
    """读取 entity_asset_slots.yaml，返回 {role: {"required": [...], "optional": [...]}}。

    与 bind_assets.load_entity_slots 同一校验集合（Phase 1.8.1 一致性补丁）：
    schema.id / schema.version / roles / required / optional / default_required。
    缺文件 / 非 mapping / schema 不符 / 不支持的版本 → RuntimeError。
    """
    file = Path(path)
    if not file.is_file():
        raise RuntimeError("entity asset slots config not found: %s" % path)
    try:
        data = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:   # Phase 1.8.1 收尾：解析错误 → 稳定的 config_error
        raise RuntimeError("entity asset slots config is not valid YAML: %s (%s)"
                           % (path, str(exc).splitlines()[0][:120])) from exc
    if not isinstance(data, dict):
        raise RuntimeError("entity asset slots config must be a mapping: %s" % path)
    schema = data.get("schema") or {}
    if not isinstance(schema, dict) or schema.get("id") != "entity_asset_slots":
        raise RuntimeError("entity asset slots config missing schema.id == entity_asset_slots: %s" % path)
    _SUPPORTED_VERSION = 1   # 与 bind_assets.load_entity_slots 同一支持集
    version = schema.get("version")
    if version is None:
        raise RuntimeError("entity asset slots config missing schema.version: %s" % path)
    try:
        version_ok = int(version) == _SUPPORTED_VERSION
    except (TypeError, ValueError):
        version_ok = False
    if not version_ok:
        raise RuntimeError("entity asset slots config unsupported schema.version %r (supported: %d): %s"
                           % (version, _SUPPORTED_VERSION, path))
    roles = data.get("roles")
    if not isinstance(roles, dict):
        raise RuntimeError("entity asset slots config missing 'roles:' mapping: %s" % path)
    parsed: dict = {}
    for role, block in roles.items():
        if not isinstance(block, dict):
            raise RuntimeError("entity asset slots roles.%s must be a mapping" % role)
        required = block.get("required")
        optional = block.get("optional")
        if (not isinstance(required, list) or not required
                or not all(isinstance(r, str) and r.strip() for r in required)):
            raise RuntimeError(
                "entity asset slots roles.%s.required must be a non-empty list of strings" % role)
        optional = optional or []
        if not isinstance(optional, list) or not all(isinstance(r, str) and r.strip() for r in optional):
            raise RuntimeError(
                "entity asset slots roles.%s.optional must be a list of strings" % role)
        parsed[str(role)] = {"required": [str(r) for r in required],
                             "optional": [str(r) for r in optional]}
    default = data.get("default_required")
    if default is None:
        default = ["idle"]
    if (not isinstance(default, list) or not default
            or not all(isinstance(r, str) and r.strip() for r in default)):
        raise RuntimeError("entity asset slots config default_required must be a non-empty list")
    parsed[ROLE_FALLBACK] = {"required": [str(r) for r in default], "optional": []}
    return parsed


def infer_role(query_text: str) -> str:
    """需求词 -> 实体角色（first match wins，与 compose_features.ROLE_KEYWORDS 顺序一致）。"""
    lower = str(query_text or "").lower()
    for word, role in ROLE_PATTERNS.items():
        if word and word.lower() in lower.split(",") or (" " + word + " ") in (" %s " % lower) \
                or lower.startswith(word + " ") or lower.endswith(" " + word) \
                or (" " + word + " ") in lower:
            return role
    return ROLE_FALLBACK


def discover(query_text: str, role: str = "", top_n: int = 3,
             feature_index_path: str = FEATURE_INDEX_PATH,
             asset_index_path: str = ASSET_INDEX_PATH,
             slots_path: str = SLOTS_PATH) -> tuple[dict, list]:
    """核心发现流程。返回 (payload, diagnostics)。"""
    diagnostics: list[dict] = []

    # 1) Feature index（复用 compose_features.load_index —— 缺失直接 SystemExit 2）
    feature_records = composer.load_index(feature_index_path)

    # 2) 实体槽位配置
    slots_table = load_slots(slots_path)

    # 3) 角色判定（infer_role 是词边界语义："zzz_monster" 不算匹配 monster）
    resolved_role = role or infer_role(query_text)
    explicit_role_match = bool(role) or resolved_role != ROLE_FALLBACK
    block = slots_table.get(resolved_role) or slots_table.get(ROLE_FALLBACK)
    if not explicit_role_match:
        diagnostics.append({
            "reason": "unknown_role",
            "message": "no recognized entity role in query %r; using fallback slots %s"
                       % (query_text, block["required"]),
        })
    required_slots = list(block["required"])
    optional_slots = list(block.get("optional") or [])

    # 4) Feature 候选（复用 discover_feature 内核：确定性评分）
    terms = discovery.extract_terms(query_text)
    features: list[str] = []
    feature_capabilities: dict[str, list] = {}
    if terms:
        for record in feature_records:
            score, _reasons = discovery.match_feature(record, terms)
            # 角色强匹配加分：entity_roles 命中该角色时纳入
            role_hit = resolved_role in ((record.get("relations") or {}).get("entity_roles") or [])
            if score > 0 or (role_hit and (set(record.get("provides") or []) & terms)):
                features.append(record["id"])
                feature_capabilities[record["id"]] = list(record.get("provides") or [])
        features.sort()
    else:
        diagnostics.append({
            "reason": "input_not_parsed",
            "message": "no usable terms extracted from query %r" % query_text,
        })
    if not features:
        # 4b) 角色种子：查询无有效 Feature 语义时给出该角色的最小可玩 Feature 集
        # （复用 compose_features.ROLE_SEEDS 的能力标签；不引入新评分，纯数据连桥）。
        # 反混淆（与 compose_features.plan 一致）：非 player 角色不将仅提供
        # player 专属能力的 Feature 拖进组合。
        seed_caps = set(ROLE_SEEDS.get(resolved_role, []))
        seed_hits: dict[str, list] = {}
        for record in feature_records:
            provides = set(record.get("provides") or [])
            if not provides & seed_caps:
                continue
            if resolved_role != "player" and provides & {"player_control", "input_driven_movement"}:
                continue   # 仅提供玩家专属能力的组件，不进非玩家角色
            features.append(record["id"])
            feature_capabilities[record["id"]] = list(record.get("provides") or [])
        features.sort()
        if features:
            diagnostics.append({
                "reason": "seeded_by_role",
                "message": "no explicit feature terms matched; using role seeds %r" % sorted(seed_caps),
            })
    if not features:
        diagnostics.append({
            "reason": "no_feature_match",
            "message": "no feature matched terms %r; role seeds unavailable" % (sorted(terms) if terms else []),
        })

    # 5) 资产候选（仅资源槽位；结构需求不计）
    asset_candidates: dict[str, list] = {}
    missing: list[dict] = []
    index = load_index(asset_index_path)
    if not index_assets(index):
        diagnostics.append({
            "reason": "index_missing",
            "message": "asset index is empty or missing: %s "
                       "(run: python .ai/tools/asset_registry/build_asset_index.py)"
                       % asset_index_path,
        })
        for slot in required_slots + optional_slots:
            asset_candidates[slot] = []
            if slot in required_slots:
                missing.append({"slot": slot, "kind": "required",
                                "reason": "asset index unavailable"})
    else:
        for slot in required_slots + optional_slots:
            # 槽位名即资源 role：直接按 role 精确过滤 + 查询词加权
            results = asset_query(index, query_text, limit=top_n, role=slot)
            if not results:
                # role 过滤过严时，退化为 unfiltered 查询 + role token 命中
                results = asset_query(index, "%s %s" % (query_text, slot), limit=top_n)
            asset_candidates[slot] = results
            if not results and slot in required_slots:
                missing.append({"slot": slot, "kind": "required",
                                "reason": "no asset candidate for role %r" % slot})
        if not any(asset_candidates.values()):
            diagnostics.append({
                "reason": "no_asset_match",
                "message": "no asset candidates matched query %r for slots %r"
                           % (query_text, required_slots),
            })

    payload = {
        "schema_version": SCHEMA_VERSION,
        "query": query_text,
        "role": resolved_role,
        "features": features,
        "feature_capabilities": feature_capabilities,
        "requirements": {},          # 结构/逻辑需求声明未定数据化 → 明确留空（见诊断补充）
        "asset_slots": required_slots,
        "optional_slots": optional_slots,
        "asset_candidates": asset_candidates,
        "missing": missing,
        "diagnostics": diagnostics,
    }
    return payload, diagnostics


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Discover features and asset candidates for an entity role.",
        epilog="JSON keys: schema_version/query/role/features/feature_capabilities/"
               "requirements/asset_slots/asset_candidates/missing/diagnostics")
    parser.add_argument("query", nargs="*", help="Requirement or role keywords")
    parser.add_argument("--role", default="", help="Explicit entity role (overrides inference)")
    parser.add_argument("--top-n", type=int, default=3, dest="top_n",
                        help="Max asset candidates per slot (0 = unlimited)")
    parser.add_argument("--project", default=os.path.dirname(_TOOL_DOTAI))
    parser.add_argument("--slots", default="",
                        help="Explicit entity_asset_slots.yaml path (highest priority; "
                             "overrides ENTITY_ASSET_SLOTS and the project default)")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)

    text = " ".join(args.query).strip()
    if not text and not args.role:
        parser.error("provide a query or --role (nothing to discover)")

    from asset_metadata import DEFAULT_PROJECT_ROOT        # noqa: E402
    project = Path(args.project).resolve() if args.project else DEFAULT_PROJECT_ROOT

    # 路径锚定到 project
    feature_index_path = str(project / ".ai" / "context" / "feature_index.json")
    asset_index_path = str(project / ".ai" / "context" / "asset_index.json")
    # 槽位配置来源优先级（与 bind_assets 一致，Phase 1.8.1 一致性补丁）：
    #   1) 显式 --slots            2) env ENTITY_ASSET_SLOTS    3) project 默认
    slots_path = (str(args.slots)
                  or os.environ.get("ENTITY_ASSET_SLOTS", "")
                  or str(project / ".ai" / "context" / "entity_asset_slots.yaml"))

    query_text = text or str(args.role)
    try:
        payload, _diagnostics = discover(
            query_text, role=args.role, top_n=args.top_n,
            feature_index_path=feature_index_path,
            asset_index_path=asset_index_path,
            slots_path=slots_path)
    except SystemExit as exc:          # composer.load_index 缺索引
        payload = {"schema_version": SCHEMA_VERSION, "query": query_text,
                   "role": "", "features": [], "feature_capabilities": {},
                   "requirements": {}, "asset_slots": [], "optional_slots": [],
                   "asset_candidates": {}, "missing": [],
                   "diagnostics": [{"reason": "feature_index_missing",
                                    "message": str(exc)}]}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2
    except RuntimeError as exc:        # 槽位配置损坏
        payload = {"schema_version": SCHEMA_VERSION, "query": query_text,
                   "role": "", "features": [], "feature_capabilities": {},
                   "requirements": {}, "asset_slots": [], "optional_slots": [],
                   "asset_candidates": {}, "missing": [],
                   "diagnostics": [{"reason": "config_error", "message": str(exc)}]}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_human(payload)
    return 0 if (payload["features"] or any(payload["asset_candidates"].values())) else 1


def _print_human(payload: dict) -> None:
    print("Feature Discovery")
    print()
    print("Query: %s" % payload["query"])
    print("Role:  %s" % payload["role"])
    print()
    print("Features:")
    for fid in payload["features"]:
        print("- %s (provides: %s)" % (fid, ", ".join(payload["feature_capabilities"].get(fid, []))))
    if not payload["features"]:
        print("(none)")
    print()
    print("Asset slots (required): %s" % ", ".join(payload["asset_slots"]))
    if payload["optional_slots"]:
        print("Asset slots (optional): %s" % ", ".join(payload["optional_slots"]))
    print()
    print("Asset candidates:")
    for slot, entries in payload["asset_candidates"].items():
        print("  %s:" % slot)
        if not entries:
            print("    (none)")
        for entry in entries:
            print("    %s [%s] score=%.2f  %s" % (
                entry.get("id"), entry.get("type"), entry.get("score") or 0.0, entry.get("path")))
    if payload["missing"]:
        print()
        print("Missing:")
        for item in payload["missing"]:
            print("  - %s (%s): %s" % (item["slot"], item["kind"], item["reason"]))
    if payload["diagnostics"]:
        print()
        print("Diagnostics:")
        for d in payload["diagnostics"]:
            print("  - [%s] %s" % (d["reason"], d["message"]))


if __name__ == "__main__":
    sys.exit(main())
