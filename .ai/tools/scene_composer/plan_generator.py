#!/usr/bin/env python3
"""Composition Plan Generator（Phase 1.19）—— Gameplay Blueprint -> composition_plan。

定位（职责边界，见 .ai/context/CURRENT_TASK.md）：

    Gameplay Blueprint   —— 声明实体及其逻辑关系（entity id 是实体身份的唯一来源）
    Entity scene         —— Scene Composer 的生成物（每个实体一个 .tscn）
    composition_plan     —— 声明「已生成场景如何组合 + 实例间显式目标关系」
    composite.py         —— 组合的唯一实现（本模块只**生成声明**，不组合场景）

本模块只做「声明生成 + 校验」，绝不重新实现组合逻辑：

    blueprint + 实体->场景映射
      -> plan 文档（document/schema_version/host/instances/targets）
      -> composite.compose_from_plan 在临时目录试组合（复用既有校验，失败即拒绝）
      -> 原子写入 plan 文件（失败绝不留下看似成功的产物）

实体 -> 场景映射来源（按优先级，均可追溯，绝不扫描目录模糊匹配）：

    1. --entity-scene <entity>=<path>   调用方显式映射（source: override）
    2. blueprint entities.<entity>.scene 蓝图声明复用（source: declared）
    3. Scenes/<Pascal(entity)>.tscn     既有生成命名约定（source: convention）

目标关系来源（绝不推断，绝不按 role 猜）：

    --target <source_entity>:<target_entity>      调用方显式配置
    --relations <entity_graph.json> --relation <name>
        消费 blueprint 派生的关系图（planner.py 写出的 entity_graph.json）；
        只使用**显式点名**的 relation，且要求 source 实体确有输出 target_path 的
        Feature（feature.yaml interfaces），否则拒绝 —— 不产生无意义的 target_path。

用法:
    python .ai/tools/scene_composer/plan_generator.py <blueprint.yaml> \
        --host DualHost --out Plans/dual.yaml \
        [--entity-scene enemy=res://Scenes/Enemy.tscn] \
        [--target enemy:player] \
        [--relations .ai/context/entity_graph.json --relation attack] \
        [--dry-run] [--json]

退出码: 0 成功；1 失败（可诊断）；2 输入/用法错误。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import shutil
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]          # game/（.ai/tools/scene_composer/ 上三级）
_FEATURE_INDEX = Path(".ai") / "context" / "feature_index.json"

import composite                                            # noqa: E402  同目录（唯一组合实现）
PLAN_DOCUMENT = composite.PLAN_DOCUMENT
PLAN_SCHEMA_VERSION = composite.PLAN_SCHEMA_VERSION

_ROOT_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TARGET_EXPORT = "target_path"                               # 运行时目标引用的唯一入口属性
COMPOSITION_MIN_ENTITIES = 2                                 # composite 契约：>= 2 个实例


def _pascal(name: str) -> str:
    return "".join(part[:1].upper() + part[1:]
                   for part in str(name).replace("-", "_").split("_") if part)


def _res_path(raw: str, project_root: Path):
    """显式映射路径 -> (res:// 路径, 磁盘路径)；越界或非法返回 (None, reason)。"""
    text = str(raw or "").strip()
    if not text:
        return None, "empty scene path"
    if text.startswith("res://"):
        disk = project_root / text[len("res://"):]
        return text.replace("\\", "/"), None
    candidate = Path(text)
    if candidate.is_absolute():
        try:
            rel = candidate.resolve().relative_to(project_root.resolve())
        except ValueError:
            return None, "scene path is outside the project: %s" % text
        return "res://" + rel.as_posix(), None
    normalized = text.replace("\\", "/").lstrip("/")
    return "res://" + normalized, None


def _load_feature_index(project_root: Path):
    path = project_root / _FEATURE_INDEX
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    features = data.get("features") if isinstance(data, dict) else None
    return features if isinstance(features, list) else None


def _exports_of(feature_id: str, feature_index) -> list:
    for entry in feature_index or []:
        if isinstance(entry, dict) and entry.get("id") == feature_id:
            return [str(item) for item in entry.get("interfaces") or []]
    return []


def _can_consume_target(entity_id: str, entry: dict, feature_index) -> tuple:
    """实体的 Feature 是否声明了 target_path 输出（数据驱动，不按 role 推断）。"""
    features = [str(f) for f in (entry or {}).get("features") or [] if str(f).strip()]
    capable = [fid for fid in features if _TARGET_EXPORT in _exports_of(fid, feature_index)]
    return bool(capable), features, capable


def resolve_entity_scene(entity_id: str, entry: dict, project_root: Path,
                         overrides: dict | None = None):
    """实体 -> {scene|None, source, reason}（override > declared > convention）。

    只做存在性解析：解析不到返回 None + 可定位原因（预期路径），绝不猜测。
    """
    override = (overrides or {}).get(entity_id)
    if override:
        res, reason = _res_path(override, project_root)
        if res is None:
            return {"scene": None, "source": "override",
                    "reason": "entities.%s.scene: %s" % (entity_id, reason)}
        if not (project_root / res[len("res://"):]).is_file():
            return {"scene": None, "source": "override",
                    "reason": "entities.%s.scene: override scene not found: %s"
                              % (entity_id, res)}
        return {"scene": res, "source": "override", "reason": ""}

    declared = str((entry or {}).get("scene") or "").strip()
    if declared:
        res, reason = _res_path(declared, project_root)
        if res is None:
            return {"scene": None, "source": "declared",
                    "reason": "entities.%s.scene: %s" % (entity_id, reason)}
        if not (project_root / res[len("res://"):]).is_file():
            return {"scene": None, "source": "declared",
                    "reason": "entities.%s.scene: declared scene not found: %s"
                              % (entity_id, res)}
        return {"scene": res, "source": "declared", "reason": ""}

    generated = "Scenes/%s.tscn" % _pascal(entity_id)
    if (project_root / generated).is_file():
        return {"scene": "res://" + generated, "source": "convention", "reason": ""}
    return {"scene": None, "source": "convention",
            "reason": "entities.%s.scene: no scene mapping for entity %r "
                      "(expected %s, or declare entities.%s.scene / use --entity-scene)"
                      % (entity_id, entity_id, "res://" + generated, entity_id)}


def _plan_document(host: str, instances: list, targets: list) -> dict:
    plan = {
        "document": PLAN_DOCUMENT,
        "schema_version": PLAN_SCHEMA_VERSION,
        "host": {"name": host},
        "instances": [{"entity": item["entity"], "scene": item["scene"],
                       "instance_name": item["instance_name"]} for item in instances],
    }
    if targets:
        plan["targets"] = [{"source": item["source_instance"],
                            "target": item["target_instance"]} for item in targets]
    return plan


def _relations_targets(relations_doc, relation_names, pascal_to_entity: dict,
                       failures: list):
    """entity_graph.json 的显式 relation -> [(source_entity, target_entity, origin)]。

    只使用调用方点名的 relation；名称解析失败 / 实体不在蓝图里 → 可定位失败。
    """
    wanted = [str(name).strip() for name in relation_names or [] if str(name).strip()]
    if not wanted:
        failures.append("--relations: at least one --relation <name> is required "
                        "(relations are never applied implicitly)")
        return []
    if not isinstance(relations_doc, dict):
        failures.append("--relations: expected an entity graph object, got %s"
                        % type(relations_doc).__name__)
        return []
    edges = relations_doc.get("edges")
    if not isinstance(edges, list):
        failures.append("--relations: entity graph has no 'edges' list: %s"
                        % sorted(relations_doc))
        return []
    available = sorted({str(edge.get("relation") or "") for edge in edges
                        if isinstance(edge, dict)})
    unknown = [name for name in wanted if name not in available]
    if unknown:
        failures.append("--relation: unknown relation(s) %s (graph declares: %s)"
                        % (", ".join(repr(name) for name in unknown),
                           ", ".join(repr(name) for name in available) or "<none>"))
        return []
    resolved = []
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            continue
        relation = str(edge.get("relation") or "")
        if relation not in wanted:
            continue
        source_node = str(edge.get("from") or "")
        target_node = str(edge.get("to") or "")
        for node, role in ((source_node, "from"), (target_node, "to")):
            if node not in pascal_to_entity:
                failures.append("--relations: edges[%d].%s: entity graph node %r does not "
                                "match any blueprint entity (nodes: %s)"
                                % (index, role, node,
                                   ", ".join(sorted(pascal_to_entity)) or "<none>"))
        source_entity = pascal_to_entity.get(source_node)
        target_entity = pascal_to_entity.get(target_node)
        if source_entity and target_entity:
            resolved.append((source_entity, target_entity,
                             "relation:%s" % relation))
    return resolved


def generate_plan(blueprint, project_root: Path = PROJECT_ROOT, host: str = "",
                  entity_scenes: dict | None = None, targets=None,
                  relations_doc=None, relation_names=(), feature_index=None) -> dict:
    """Gameplay Blueprint -> composition_plan（生成 + 复用 compose_from_plan 校验）。

    返回 {ok, plan, failures, mappings, targets, dry_checked}。
    只有全部校验通过才返回 ok=True；调用方负责写盘（见 write_plan）。
    """
    failures: list = []
    mappings: list = []
    resolved_targets: list = []
    if not isinstance(blueprint, dict):
        return {"ok": False, "plan": {}, "mappings": [], "targets": [],
                "failures": ["blueprint: expected a mapping, got %s"
                             % type(blueprint).__name__]}
    entities = blueprint.get("entities")
    if not isinstance(entities, dict) or not entities:
        return {"ok": False, "plan": {}, "mappings": [], "targets": [],
                "failures": ["entities: blueprint declares no entities "
                             "(a composition plan needs at least %d)"
                             % COMPOSITION_MIN_ENTITIES]}

    game_id = ""
    gameplay = blueprint.get("gameplay")
    if isinstance(gameplay, dict):
        game_id = str(gameplay.get("id") or "")
    host_name = str(host or "").strip() or ("%sHost" % _pascal(game_id or "composed"))
    if not _ROOT_NAME_RE.match(host_name):
        failures.append("host.name: %r is not a valid Godot node name" % host_name)

    ordered = [str(entity_id) for entity_id in entities if str(entity_id).strip()]
    for unknown in sorted(set(entity_scenes or {}) - set(ordered), key=str):
        failures.append("entities.%s: --entity-scene names an entity that does not exist "
                        "in the blueprint (entities: %s)"
                        % (unknown, ", ".join(ordered) or "<none>"))
    if len(ordered) < COMPOSITION_MIN_ENTITIES:
        failures.append("entities: composition requires at least %d entities, "
                        "blueprint declares %d" % (COMPOSITION_MIN_ENTITIES, len(ordered)))
        return {"ok": False, "plan": {}, "mappings": [], "targets": [],
                "failures": failures}

    instances: list = []
    used_names: dict = {}
    for entity_id in ordered:
        entry = entities.get(entity_id)
        if not isinstance(entry, dict):
            failures.append("entities.%s: expected an object with 'features'/'scene'"
                            % entity_id)
            continue
        resolution = resolve_entity_scene(entity_id, entry, project_root, entity_scenes)
        if resolution["scene"] is None:
            failures.append(resolution["reason"])
            continue
        instance_name = _pascal(entity_id)
        if not _ROOT_NAME_RE.match(instance_name):
            failures.append("entities.%s: derived instance name %r is not a valid "
                            "Godot node name" % (entity_id, instance_name))
            continue
        if instance_name in used_names:
            failures.append("entities.%s: instance name %r collides with entity %r "
                            "(entity ids must derive unique instance names; rename one "
                            "entity rather than relying on silent disambiguation)"
                            % (entity_id, instance_name, used_names[instance_name]))
            continue
        used_names[instance_name] = entity_id
        instances.append({"entity": entity_id, "scene": resolution["scene"],
                          "instance_name": instance_name,
                          "root_name": "", "source": resolution["source"]})

    if not failures and len(instances) < COMPOSITION_MIN_ENTITIES:
        failures.append("instances: only %d entity scene(s) resolved; composition "
                        "requires at least %d" % (len(instances), COMPOSITION_MIN_ENTITIES))

    # ---- 目标关系：只接受显式调用方配置 / 显式点名的蓝图派生关系 ----
    declared_targets = []
    for index, spec in enumerate(targets or []):
        source = target = ""
        if isinstance(spec, (tuple, list)) and len(spec) == 2:
            source, target = spec
        elif isinstance(spec, str) and ":" in spec:
            source, target = spec.split(":", 1)
        elif isinstance(spec, dict):
            source, target = spec.get("source"), spec.get("target")
        source = str(source or "").strip()
        target = str(target or "").strip()
        if not source or not target:
            failures.append("targets[%d]: expected '<source_entity>:<target_entity>', "
                            "got %r" % (index, spec))
            continue
        declared_targets.append((source, target, "explicit"))

    pascal_to_entity = {_pascal(entity_id): entity_id for entity_id in ordered}
    if relations_doc is not None:
        declared_targets.extend(_relations_targets(relations_doc, relation_names,
                                                   pascal_to_entity, failures))

    if declared_targets:
        if feature_index is None:
            feature_index = _load_feature_index(project_root)
        if feature_index is None:
            failures.append("targets: feature index unavailable (%s); cannot verify that "
                            "target consumers export %s"
                            % ((project_root / _FEATURE_INDEX).as_posix(), _TARGET_EXPORT))
        else:
            by_entity = {item["entity"]: item for item in instances}
            claimed: dict = {}
            for index, (source, target, origin) in enumerate(declared_targets):
                if source not in entities:
                    failures.append("targets[%d].source: unknown entity %r (blueprint "
                                    "entities: %s)" % (index, source,
                                                       ", ".join(ordered)))
                    continue
                if target not in entities:
                    failures.append("targets[%d].target: unknown entity %r (blueprint "
                                    "entities: %s)" % (index, target,
                                                       ", ".join(ordered)))
                    continue
                if source == target:
                    failures.append("targets[%d]: an entity cannot target itself (%r)"
                                    % (index, source))
                    continue
                capable, features, capable_features = _can_consume_target(
                    source, entities.get(source), feature_index)
                if not capable:
                    failures.append("targets[%d].source: entity %r cannot consume a runtime "
                                    "target (no feature exporting %s; features: %s)"
                                    % (index, source, _TARGET_EXPORT,
                                       ", ".join(features) or "<none>"))
                    continue
                if source in claimed:
                    failures.append("targets[%d]: entity %r already declares a target (%r); "
                                    "one target per source"
                                    % (index, source, claimed[source]))
                    continue
                source_instance = by_entity.get(source, {}).get("instance_name", "")
                target_instance = by_entity.get(target, {}).get("instance_name", "")
                if not source_instance or not target_instance:
                    failures.append("targets[%d]: entity %r/%r has no resolved instance"
                                    % (index, source, target))
                    continue
                claimed[source] = target
                resolved_targets.append({"source_entity": source,
                                         "target_entity": target,
                                         "source_instance": source_instance,
                                         "target_instance": target_instance,
                                         "origin": origin,
                                         "capability": capable_features[0]})

    if failures:
        return {"ok": False, "plan": {}, "mappings": instances, "targets": resolved_targets,
                "failures": failures}

    plan = _plan_document(host_name, instances, resolved_targets)
    # 复用组合器的既有校验（不是第二套规则）：真实试组合到临时目录后删除。
    probe_dir = tempfile.mkdtemp(prefix="plan_generator_probe_")
    try:
        result = composite.compose_from_plan(plan, project_root=project_root,
                                             out_dir=probe_dir)
    finally:
        shutil.rmtree(probe_dir, ignore_errors=True)
    if not result.get("ok"):
        failures.extend("composition: %s" % failure
                        for failure in result.get("failures") or [])
        return {"ok": False, "plan": {}, "mappings": instances,
                "targets": resolved_targets, "failures": failures}

    return {"ok": True, "plan": plan, "mappings": instances,
            "targets": resolved_targets, "failures": [],
            "validation": "composition validated (%d instances, %d target(s))"
                          % (len(result.get("instances") or []),
                             len(result.get("targets") or []))}


def write_plan(plan: dict, out_path: str | Path, project_root: Path = PROJECT_ROOT) -> Path:
    """原子写入 plan（同目录临时文件 + os.replace）；异常时不留半成品。"""
    path = Path(out_path)
    if not path.is_absolute():
        path = project_root / path
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(plan, sort_keys=False, allow_unicode=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8", newline="\n")
        os.replace(str(tmp), str(path))
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    return path


def _parse_entity_scenes(values) -> tuple:
    overrides, errors = {}, []
    for raw in values or []:
        if "=" not in str(raw):
            errors.append("--entity-scene: expected <entity>=<scene>, got %r" % (raw,))
            continue
        entity, scene = str(raw).split("=", 1)
        entity, scene = entity.strip(), scene.strip()
        if not entity or not scene:
            errors.append("--entity-scene: expected <entity>=<scene>, got %r" % (raw,))
            continue
        overrides[entity] = scene
    return overrides, errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a composition_plan document from a gameplay blueprint "
                    "and its generated entity scenes.")
    parser.add_argument("blueprint", help="Gameplay Blueprint yaml path")
    parser.add_argument("--host", default="", help="host scene / root node name "
                                                   "(default: <Pascal(gameplay id)>Host)")
    parser.add_argument("--out", default="", help="composition plan output yaml path")
    parser.add_argument("--entity-scene", action="append", default=[],
                        metavar="ENTITY=PATH", help="explicit entity -> scene mapping")
    parser.add_argument("--target", action="append", default=[], metavar="SRC:DST",
                        help="explicit target relation between blueprint entities")
    parser.add_argument("--relations", default="",
                        help="entity_graph.json (blueprint-derived relations)")
    parser.add_argument("--relation", action="append", default=[],
                        metavar="NAME", help="relation name to consume from --relations")
    parser.add_argument("--dry-run", action="store_true", help="validate only, write nothing")
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    args = parser.parse_args(argv)

    if not args.out and not args.dry_run:
        print("FAIL: either --out <path> or --dry-run is required", file=sys.stderr)
        return 2
    blueprint_path = Path(args.blueprint)
    if not blueprint_path.is_file():
        print("FAIL: blueprint not found: %s" % args.blueprint, file=sys.stderr)
        return 2
    try:
        blueprint = yaml.safe_load(blueprint_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        print("FAIL: cannot read blueprint %s: %s" % (args.blueprint, exc), file=sys.stderr)
        return 2
    overrides, override_errors = _parse_entity_scenes(args.entity_scene)
    if override_errors:
        for error in override_errors:
            print("FAIL: %s" % error, file=sys.stderr)
        return 2

    relations_doc = None
    if args.relations:
        graph_path = Path(args.relations)
        if not graph_path.is_file():
            print("FAIL: relations graph not found: %s" % args.relations, file=sys.stderr)
            return 2
        try:
            relations_doc = yaml.safe_load(graph_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            print("FAIL: cannot read relations graph %s: %s" % (args.relations, exc),
                  file=sys.stderr)
            return 2

    result = generate_plan(blueprint, host=args.host, entity_scenes=overrides,
                          targets=list(args.target), relations_doc=relations_doc,
                          relation_names=list(args.relation))

    if args.json:
        print(json.dumps({"ok": result["ok"], "failures": result["failures"],
                          "mappings": result["mappings"], "targets": result["targets"],
                          "plan": result.get("plan") or {}},
                         ensure_ascii=False, indent=2))
    else:
        print("Composition Plan Generator")
        print()
        if result["mappings"]:
            print("Instances:")
            for item in result["mappings"]:
                print("  %-20s <- %s  (entity: %s, scene: %s)"
                      % (item["instance_name"], item["scene"], item["entity"],
                         item["source"]))
        if result["targets"]:
            print("Targets:")
            for item in result["targets"]:
                print("  %s -> %s  (%s -> %s, %s)"
                      % (item["source_entity"], item["target_entity"],
                         item["source_instance"], item["target_instance"],
                         item["origin"]))
        if not result["ok"]:
            print()
            print("FAILURES")
            for failure in result["failures"]:
                print("  - " + failure)
            return 1
        print()
        print("Validation: PASS (%s)" % result.get("validation", ""))
        if args.dry_run:
            print("Dry run: plan is valid, no plan written")
        else:
            written = write_plan(result["plan"], args.out)
            print("Artifact: %s" % written)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
