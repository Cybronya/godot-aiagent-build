#!/usr/bin/env python3
"""Composite Scene Builder —— 把多个**已生成**的实体场景组合进同一宿主场景。

Phase 1.17（多实体场景组合）最小实现；Phase 1.18 升级为**正式管线入口**：
Scene Composer `--compose-plan` 消费 composition_plan 文档（本模块唯一权威实现）。

职责边界：

    - 输入 = 已经过 Scene Composer 生成并验证的实体 .tscn（>= 2 个），
      或一份 composition_plan 文档；
    - 组合方式 = Godot 原生场景实例化（`[node ... instance=ExtResource(...)]`），
      绝不拼接实体场景的内部文本——每个实体场景保持字节不变，
      其子节点 / 资源引用 / 脚本绑定都封装在自己的实例子树里；
    - 目标声明（Phase 1.18 运行时交互契约）= 计划里的 targets 显式声明
      「追击方实例 -> 目标实例」，宿主在对应实例节点上写
      `target_path = NodePath("../<目标实例名>")`（与 chase_movement 的既有
      相对解析契约一致：路径相对追击脚本所在节点 = 实体根）；
      目标实例不存在 → 拒绝生成（不留成功假象）；绝不遍历场景猜测目标；
    - 输入争用契约：多于一个实例场景引用 player_controller.gd（读输入）→
      拒绝生成（多个玩家实例会争用同一输入动作，契约禁止）。

不做的事（边界，见 .ai/context/CURRENT_TASK.md）：
    - 不重新解析实体场景内部结构（不引入 Scene Intent 第二套管线）；
    - 不修改任何输入场景文件；
    - 不处理同场景实例间的物理/逻辑交互（碰撞、AI 由关卡编排层负责）。

用法:
    python composite.py --scene res://Scenes/A.tscn --scene res://Scenes/B.tscn \
        --name DualHost [-o Scenes] [--json]
    python composite.py --plan plan.yaml [-o Scenes] [--json]

composition_plan 文档（契约见 .ai/context/scene_composer_schema.yaml#composition_plan）:

    document: composition_plan
    schema_version: 1
    host:
      name: DualHost
    instances:
      - entity: enemy                    # 可选：gameplay 蓝图实体身份（诊断/追溯用）
        scene: res://Scenes/Enemy.tscn   # 必填：已生成的实体场景
        instance_name: Enemy             # 可选：宿主内实例名（缺省 = 场景根名）
    targets:                             # 可选：运行时目标引用声明
      - source: Enemy                    # 追击方实例名
        target: Player                   # 目标实例名

退出码: 0 成功；1 组合失败（可诊断）；2 输入错误。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]          # game/（.ai/tools/scene_composer/ 上三级）

_ROOT_NODE_TYPE = "Node2D"                                   # 与生成实体场景根类型一致
_ROOT_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PLAYER_INPUT_MARKER = "player_controller.gd"                # 读输入组件（输入争用判定标记）

PLAN_DOCUMENT = "composition_plan"
PLAN_SCHEMA_VERSION = 1


def _res_path(path: str, project_root: Path = PROJECT_ROOT) -> str:
    """把磁盘路径转成 res:// 路径；已是 res:// 则原样返回。"""
    text = str(path).replace("\\", "/")
    if text.startswith("res://"):
        return text
    try:
        rel = Path(text).resolve().relative_to(project_root.resolve())
    except ValueError:
        raise SystemExit("FAIL: scene path is outside the project: %s" % path)
    return "res://" + rel.as_posix()


def _scene_root_name(scene_text: str, fallback: str) -> str:
    """读取实体场景的根节点名（用于诊断与缺省实例名）。"""
    match = re.search(r'^\[node name="([^"]+)"', scene_text, re.MULTILINE)
    return match.group(1) if match else fallback


def _read_instance_scene(res_path: str, project_root: Path) -> str | None:
    disk = project_root / res_path[len("res://"):]
    if not disk.is_file():
        return None
    return disk.read_text(encoding="utf-8")


def _resolve_instances(scene_specs, project_root: Path,
                       failures: list[str]) -> list[dict]:
    """把实例声明解析成 {entity, scene(res://), instance_name, root_name, text}。

    scene_specs：str（= scene 路径）或 {scene, instance_name?, entity?}。
    """
    instances: list[dict] = []
    used_names: set[str] = set()
    seen_paths: set[str] = set()
    player_claimants: list[str] = []
    for index, spec in enumerate(scene_specs):
        if isinstance(spec, dict):
            scene_raw = spec.get("scene")
            wanted_name = spec.get("instance_name") or ""
            entity = spec.get("entity") or ""
        else:
            scene_raw, wanted_name, entity = spec, "", ""
        if not scene_raw or not isinstance(scene_raw, str):
            failures.append("instances[%d]: 'scene' is required (got %r)" % (index, scene_raw))
            continue
        res_path = _res_path(scene_raw, project_root)
        if res_path in seen_paths:
            failures.append("duplicate entity scene in one host: %s" % res_path)
            continue
        seen_paths.add(res_path)
        text = _read_instance_scene(res_path, project_root)
        if text is None:
            failures.append("entity scene not found: %s" % res_path)
            continue
        root_name = _scene_root_name(text, Path(res_path).stem)
        instance_name = str(wanted_name) or root_name
        if not _ROOT_NAME_RE.match(instance_name):
            failures.append("instances[%d]: instance name %r is not a valid Godot node name"
                            % (index, instance_name))
            continue
        if instance_name in used_names:
            failures.append("instance name conflict: %r is used by more than one instance"
                            % instance_name)
            continue
        used_names.add(instance_name)
        if _PLAYER_INPUT_MARKER in text:
            player_claimants.append(instance_name)
        instances.append({"entity": str(entity), "scene": res_path,
                          "instance_name": instance_name, "root_name": root_name,
                          "text": text})
    if len(player_claimants) > 1:
        failures.append(
            "input claim conflict: %d instance scenes contain %s (multiple player "
            "instances would contend for the same input actions); at most one is allowed"
            % (len(player_claimants), _PLAYER_INPUT_MARKER))
    return instances


def _resolve_targets(target_specs, instances: list[dict],
                     failures: list[str]) -> list[dict]:
    """解析 targets 声明：{source, target} -> 追击方实例携带 NodePath 覆盖。"""
    by_name = {instance["instance_name"]: instance for instance in instances}
    resolved: list[dict] = []
    for index, spec in enumerate(target_specs or []):
        if not isinstance(spec, dict):
            failures.append("targets[%d]: expected a mapping" % index)
            continue
        source = str(spec.get("source") or "")
        target = str(spec.get("target") or "")
        if source not in by_name:
            failures.append("targets[%d].source: unknown instance %r (instances: %s)"
                            % (index, source, ", ".join(sorted(by_name)) or "<none>"))
            continue
        if target not in by_name:
            failures.append("targets[%d].target: unknown instance %r (instances: %s)"
                            % (index, target, ", ".join(sorted(by_name)) or "<none>"))
            continue
        if source == target:
            failures.append("targets[%d]: an instance cannot target itself (%r)" % (index, source))
            continue
        # chase_movement 契约：target_path 相对追击脚本节点（= 实体根）解析，
        # 因此宿主兄弟实例 = "../<实例名>"。
        resolved.append({"source": source, "target": target,
                         "target_path": NodePath_Text("../%s" % target)})
    return resolved


def NodePath_Text(path: str) -> str:                         # noqa: N802 - 供 .tscn 文本使用
    return 'NodePath("%s")' % path


def compose_entities(scene_paths, host_name: str,
                     project_root: Path = PROJECT_ROOT,
                     out_dir: str | Path = "",
                     targets=None) -> dict:
    """把 >= 2 个实体场景实例化进同一宿主场景（Godot 原生 instancing）。

    targets：可选 [{source, target}]（实例名）；写进宿主后，追击方实例根的
    target_path 指向目标实例（运行时交互契约，Phase 1.18）。

    返回 {ok, scene_path, instances, targets, failures}。
    """
    failures: list[str] = []
    if not _ROOT_NAME_RE.match(host_name or ""):
        failures.append("host name %r is not a valid Godot node name" % host_name)
    if not failures:
        specs = [str(p) for p in scene_paths]
        if len(specs) < 2:
            failures.append("composition requires at least 2 entity scenes, got %d"
                            % len(specs))
        if not failures:
            instances = _resolve_instances(specs, project_root, failures)
            resolved_targets = _resolve_targets(targets or [], instances, failures)
            if not failures:
                return _write_host(instances, resolved_targets, host_name,
                                   project_root, out_dir)
    return {"ok": False, "scene_path": "", "instances": [], "targets": [],
            "failures": failures}


def compose_from_plan(plan, project_root: Path = PROJECT_ROOT,
                      out_dir: str | Path = "") -> dict:
    """composition_plan 文档 -> 宿主场景（正式管线入口，Phase 1.18）。

    结构非法 = {ok: False, failures: [...]}（绝不写盘）；
    实体场景缺失 / 实例名冲突 / 目标实例未知 → 可定位失败（exit 1 由 CLI 映射）。
    """
    failures: list[str] = []
    if not isinstance(plan, dict):
        return {"ok": False, "scene_path": "", "instances": [], "targets": [],
                "failures": ["composition plan must be a mapping, got %s"
                             % type(plan).__name__]}
    if plan.get("document") != PLAN_DOCUMENT:
        failures.append("plan.document: expected %r, got %r"
                        % (PLAN_DOCUMENT, plan.get("document")))
    version = plan.get("schema_version")
    if version != PLAN_SCHEMA_VERSION:
        failures.append("plan.schema_version: expected %r, got %r"
                        % (PLAN_SCHEMA_VERSION, version))
    host = plan.get("host") or {}
    host_name = str((host or {}).get("name") or "")
    if not _ROOT_NAME_RE.match(host_name):
        failures.append("host.name: %r is not a valid Godot node name" % host_name)
    instances_spec = plan.get("instances") or []
    if not isinstance(instances_spec, list) or len(instances_spec) < 2:
        failures.append("instances: composition requires at least 2 instance entries, "
                        "got %d" % (len(instances_spec) if isinstance(instances_spec, list)
                                    else 0))
        return {"ok": False, "scene_path": "", "instances": [], "targets": [],
                "failures": failures}
    if not failures:
        instances = _resolve_instances(instances_spec, project_root, failures)
        resolved_targets = _resolve_targets(plan.get("targets") or [], instances, failures)
        if not failures:
            return _write_host(instances, resolved_targets, host_name,
                               project_root, out_dir)
    return {"ok": False, "scene_path": "", "instances": [], "targets": [],
            "failures": failures}


def _write_host(instances: list[dict], targets: list[dict], host_name: str,
                project_root: Path, out_dir: str | Path) -> dict:
    """生成宿主 .tscn 文本并落盘（只在全部校验通过后调用）。"""
    ext_resources = []
    for index, instance in enumerate(instances):
        ext_resources.append(("%d_%s" % (index + 1, instance["instance_name"].lower()),
                              instance["scene"]))
    target_by_source = {t["source"]: t for t in targets}
    lines = ["[gd_scene load_steps=%d format=3]" % (len(ext_resources) + 1), ""]
    for ext_id, res_path in ext_resources:
        lines.append('[ext_resource type="PackedScene" path="%s" id="%s"]' % (res_path, ext_id))
    lines.append("")
    lines.append('[node name="%s" type="%s"]' % (host_name, _ROOT_NODE_TYPE))
    for instance, (ext_id, _res) in zip(instances, ext_resources):
        lines.append("")
        lines.append('[node name="%s" parent="." instance=ExtResource("%s")]'
                     % (instance["instance_name"], ext_id))
        override = target_by_source.get(instance["instance_name"])
        if override:
            lines.append("target_path = %s" % override["target_path"])
    document = "\n".join(lines) + "\n"

    out_directory = Path(out_dir) if out_dir else (project_root / "Scenes")
    out_directory.mkdir(parents=True, exist_ok=True)
    out_path = out_directory / ("%s.tscn" % host_name)
    out_path.write_text(document, encoding="utf-8", newline="\n")
    public_instances = [{k: v for k, v in instance.items() if k != "text"}
                        for instance in instances]
    return {"ok": True, "scene_path": str(out_path), "instances": public_instances,
            "targets": targets, "failures": []}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Compose generated entity scenes into one host scene (native instancing).")
    parser.add_argument("--scene", action="append", default=[],
                        help="entity scene to instance (repeatable, >= 2)")
    parser.add_argument("--plan", default="",
                        help="composition plan yaml (formal pipeline entry, Phase 1.18)")
    parser.add_argument("--name", default="", help="host scene / root node name (--scene mode)")
    parser.add_argument("-o", "--out", default=str(PROJECT_ROOT / "Scenes"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.plan:
        import yaml
        plan_path = Path(args.plan)
        if not plan_path.is_file():
            print("FAIL: composition plan not found: %s" % plan_path, file=sys.stderr)
            return 2
        result = compose_from_plan(
            yaml.safe_load(plan_path.read_text(encoding="utf-8")), out_dir=args.out)
    elif args.scene and args.name:
        result = compose_entities(args.scene, args.name, out_dir=args.out)
    else:
        parser.error("--plan, or --scene (repeatable) together with --name")
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for failure in result["failures"]:
            print("FAIL: %s" % failure, file=sys.stderr)
        if result["ok"]:
            print("Composite scene: %s" % result["scene_path"])
            for instance in result["instances"]:
                print("  %-20s <- %s (root=%s)" % (instance["instance_name"],
                                                   instance["scene"],
                                                   instance["root_name"]))
            for target in result.get("targets") or []:
                print("  target: %s -> %s (%s)" % (target["source"], target["target"],
                                                   target["target_path"]))
            print("Validation: instances=%d conflicts=0" % len(result["instances"]))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
