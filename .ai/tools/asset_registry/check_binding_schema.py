#!/usr/bin/env python3
"""Binding Schema Checker —— 校验 asset_bindings/*.yaml 的 schema 与记录健康度。

    python check_binding_schema.py                       # 检查默认目录
    python check_binding_schema.py --bindings-dir PATH   # 指定绑定目录
    python check_binding_schema.py --gameplay bp.yaml --bindings-dir PATH
    python check_binding_schema.py --json

检查项（只 CHECK / REPORT，禁止自动迁移或改写文件）：
    1. schema_version 存在且为整数（缺失 = ERROR）
    2. schema_version 在支持范围内（SUPPORTED_SCHEMA_VERSIONS；未知 = ERROR）
    3. 记录健康度（Phase 1.17）：
       - 输出文档：binding.entities[].bindings[] 每条记录必须有非空 str 的
         role 与 asset；可选 entity 字段若出现也必须是非空 str（entity-scoped 记录）
       - 显式绑定输入文档（顶层 bindings: []）：同上（entity 可选）
       - binding.binding_scope_errors[] 条目必须携带 entity/role/location/reason
         （与 bind_assets 的诊断契约一致）
    4. --gameplay 给出 Gameplay Blueprint 时：entity-scoped 记录的 entity 必须
       在蓝图实体清单里（未知实体 = ERROR，与 bind_assets 的
       binding_scope_errors 语义一致）
    5. 未给出 --gameplay 时：无法判断实体存在性 —— 记入 note（信息不足），
       绝不推断绑定有效或无效

与 bind_assets 的分工：bind_assets 在解析/应用时产出 binding_scope_errors
（业务规则唯一权威）；本工具只做 schema 层面的静态健康检查，不重复实现优先级/
推断等业务规则。合法的旧格式（role-level 记录，无 entity 字段）完全兼容。

退出码: 0 = 全部通过；1 = 存在违规；2 = 输入错误。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_TOOL_DOTAI = Path(__file__).resolve().parents[2]          # .ai
PROJECT_ROOT = _TOOL_DOTAI.parent
DEFAULT_BINDINGS_DIR = _TOOL_DOTAI / "context" / "asset_bindings"

# 支持的实例版本（与 bind_assets.BINDING_SCHEMA_VERSION / schema 文档 version 一致）
SUPPORTED_SCHEMA_VERSIONS = (2,)

_SCOPE_ERROR_KEYS = ("entity", "role", "location", "reason")

try:
    import yaml
except ImportError:  # pragma: no cover
    print("FAIL: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)


def _is_non_empty_str(value) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def _check_record(record, where: str, entity_ids, violations: list) -> None:
    """检查单条绑定记录（输出文档与显式输入文档共用同一套字段规则）。"""
    if not isinstance(record, dict):
        violations.append({"file": where.split(":")[0], "kind": "invalid_record",
                           "detail": "%s: expected a mapping, got %s"
                                     % (where, type(record).__name__)})
        return
    for field in ("role", "asset"):
        value = record.get(field)
        if not _is_non_empty_str(value):
            violations.append({
                "file": where.split(":")[0], "kind": "invalid_%s" % field,
                "detail": "%s.%s: must be a non-empty string, got %r" % (where, field, value)})
    entity = record.get("entity")
    if entity is None:
        return                                     # 旧格式 role-level 记录：兼容
    if not _is_non_empty_str(entity):
        violations.append({
            "file": where.split(":")[0], "kind": "invalid_entity_scope",
            "detail": "%s.entity: entity-scoped binding needs a non-empty string, got %r"
                      % (where, entity)})
        return
    if entity_ids is not None and entity not in entity_ids:
        violations.append({
            "file": where.split(":")[0], "kind": "unknown_entity_scope",
            "detail": ("%s.entity: scoped to unknown entity %r (blueprint entities: %s); "
                       "bind_assets reports the same condition as binding_scope_errors"
                       % (where, entity, ", ".join(sorted(entity_ids)) or "<none>"))})


def _check_scope_errors(scope_errors, file_name: str, violations: list) -> None:
    """binding_scope_errors 契约一致性（bind_assets 诊断字段的映射检查）。"""
    if not isinstance(scope_errors, list):
        violations.append({"file": file_name, "kind": "invalid_binding_scope_errors",
                           "detail": "binding.binding_scope_errors: must be a list"})
        return
    for index, entry in enumerate(scope_errors):
        if not isinstance(entry, dict):
            violations.append({"file": file_name, "kind": "invalid_binding_scope_errors",
                               "detail": "binding.binding_scope_errors[%d]: expected a "
                                         "mapping" % index})
            continue
        missing = [key for key in _SCOPE_ERROR_KEYS if not entry.get(key)]
        if missing:
            violations.append({
                "file": file_name, "kind": "incomplete_binding_scope_error",
                "detail": "binding.binding_scope_errors[%d]: missing %s (contract: %s)"
                          % (index, ", ".join(missing), ", ".join(_SCOPE_ERROR_KEYS))})


def check_bindings(bindings_dir: str | os.PathLike,
                   supported: tuple = SUPPORTED_SCHEMA_VERSIONS,
                   gameplay_blueprint=None) -> dict:
    """扫描绑定目录，返回 {checked, violations, entries, notes}。

    entries 形如 [{file, schema_version, records}]（可读格式便于 PASS 报告）。
    gameplay_blueprint：可选 dict；给出时对 entity-scoped 记录做实体存在性检查，
    否则记入 notes（信息不足，不推断结论）。
    """
    directory = Path(bindings_dir)
    entries: list[dict] = []
    violations: list[dict] = []
    notes: list[str] = []
    if not directory.is_dir():
        return {"checked": 0, "violations": [], "entries": [], "notes": [],
                "note": "binding directory not found: %s" % directory}

    entity_ids = None
    if gameplay_blueprint is not None:
        entities = (gameplay_blueprint or {}).get("entities") or {}
        if isinstance(entities, dict) and entities:
            entity_ids = {str(key) for key in entities}
        else:
            notes.append("gameplay blueprint has no usable entities mapping; "
                         "entity existence cannot be validated (information "
                         "insufficient, no verdict implied)")
    else:
        notes.append("no gameplay blueprint provided; entity existence of entity-scoped "
                     "bindings cannot be validated (information insufficient, no "
                     "verdict implied)")

    yaml_files = sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml"))
    for path in yaml_files:
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            violations.append({"file": path.name, "kind": "unreadable", "detail": str(exc)})
            continue
        if not isinstance(doc, dict) or not isinstance(doc.get("binding"), dict):
            violations.append({"file": path.name, "kind": "not_a_binding_document",
                               "detail": "missing 'binding:' mapping"})
            continue
        if "schema_version" not in doc:
            violations.append({"file": path.name, "kind": "missing_schema_version",
                               "detail": "add top-level 'schema_version: <int>'"})
            continue
        version = doc.get("schema_version")
        if isinstance(version, bool) or not isinstance(version, int):
            violations.append({"file": path.name, "kind": "invalid_schema_version",
                               "detail": "schema_version must be an integer, got %r" % version})
            continue
        if version not in supported:
            violations.append({"file": path.name, "kind": "unsupported_schema_version",
                               "detail": "schema_version=%s not supported (supported: %s); "
                                         "migration is a separate task"
                                         % (version, sorted(supported))})
            continue

        binding = doc["binding"]
        record_count = 0
        # 输出文档：binding.entities[].bindings[]（bind_assets --out 的产物形状）
        for block in binding.get("entities") or []:
            if not isinstance(block, dict):
                violations.append({"file": path.name, "kind": "invalid_entity_block",
                                   "detail": "binding.entities: expected mappings, got %s"
                                             % type(block).__name__})
                continue
            entity_id = block.get("entity")
            if not _is_non_empty_str(entity_id):
                violations.append({
                    "file": path.name, "kind": "invalid_entity_block",
                    "detail": "binding.entities[].entity: must be a non-empty string, "
                              "got %r" % (entity_id,)})
            for index, record in enumerate(block.get("bindings") or []):
                _check_record(record, "%s:binding.entities[%s].bindings[%d]"
                              % (path.name, entity_id, index), entity_ids, violations)
                record_count += 1
        # 显式绑定输入文档（bind_assets --binding FILE 的形状）
        for index, record in enumerate(binding.get("bindings") or []):
            _check_record(record, "%s:binding.bindings[%d]" % (path.name, index),
                          entity_ids, violations)
            record_count += 1
        if binding.get("binding_scope_errors") is not None:
            _check_scope_errors(binding["binding_scope_errors"], path.name, violations)
        entries.append({"file": path.name, "schema_version": version,
                        "records": record_count})
    return {"checked": len(yaml_files), "violations": violations, "entries": entries,
            "notes": notes}


def load_gameplay_blueprint(path: str | os.PathLike):
    """读取 Gameplay Blueprint（--gameplay）；结构错误 = 输入错误（exit 2）。"""
    blueprint_path = Path(path)
    if not blueprint_path.is_file():
        raise SystemExit("FAIL: gameplay blueprint not found: %s" % blueprint_path)
    doc = yaml.safe_load(blueprint_path.read_text(encoding="utf-8")) or {}
    if not isinstance(doc, dict):
        raise SystemExit("FAIL: gameplay blueprint must be a YAML mapping: %s"
                         % blueprint_path)
    return doc                                    # 无 entities 时按「信息不足」处理（note）


def print_report(result: dict) -> None:
    print("Binding Schema Check")
    print("Checked: %d" % result["checked"])
    for entry in result["entries"]:
        print("PASS:   %s  schema_version=%d records=%d"
              % (entry["file"], entry["schema_version"], entry.get("records", 0)))
    for note in result.get("notes") or []:
        print("Note:   %s" % note)
    if result.get("note"):
        print("Note:   %s" % result["note"])
    for violation in result["violations"]:
        print("ERROR:  %s  (%s)" % (violation["file"], violation["kind"]))
        print("        %s" % violation.get("detail") or "")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check asset binding schema and record health.")
    parser.add_argument("--bindings-dir", default=str(DEFAULT_BINDINGS_DIR))
    parser.add_argument("--gameplay", default="",
                        help="optional gameplay blueprint; when given, entity-scoped "
                             "bindings are checked against its entities (Phase 1.17)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    blueprint = None
    if args.gameplay:
        try:
            blueprint = load_gameplay_blueprint(args.gameplay)
        except SystemExit as exc:
            print(exc.code or exc, file=sys.stderr)
            return 2
    result = check_bindings(args.bindings_dir, gameplay_blueprint=blueprint)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_report(result)
    return 1 if result["violations"] else 0


if __name__ == "__main__":
    sys.exit(main())
