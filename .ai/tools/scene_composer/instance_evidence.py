#!/usr/bin/env python3
"""Feature Instance Evidence Reconciliation (Phase 1.38) —— 声明 vs 真实 .tscn 对账。

问题（Phase 1.37 留下的结构性缺口）：

    `template.yaml` 的 `instance:` 只被当作**声明证据**喂给能力契约。若模板声称
    「我的入口场景是 Area2D + CollisionShape2D」而场景实际没有该节点，契约照样放行。

本模块补上**独立**的第二份证据：读取真实 `.tscn`，逐条核对声明。

三级证据（严格区分，不得互相顶替）：

    declaration   —— `template.yaml` 声称需要什么实例。来源：模板文件本身。
                     只能定义**预期**，不证明实例存在。
    static_scene  —— `.tscn` 文本里实际写着的节点 / 场景实例 / 资源引用。来源：
                     `external_artifact_resolver.parse_scene_text`（单一解析实现）。
                     证明「场景文件里有什么」，不证明「运行时场景树长什么样」。
    runtime       —— 场景加载后真实存在的对象与行为。来源：Godot 探针 / 运行时验证。
                     本模块**不产生**运行时证据；动态创建的节点只能标 INSUFFICIENT。

结论状态（互斥，优先级 INVALID > MISMATCH > INSUFFICIENT > PASS）：

    PASS         声明与静态场景一致。
    MISMATCH     静态场景**已证实**与声明矛盾（根类型不符 / 子节点缺失 / 层级错误 /
                 数量不符 / 重复节点路径）。
    INSUFFICIENT 静态解析无法确认（声明为运行时创建的节点、解析器不认识的节点头部）。
                 → 必须如实上报为「证据不足」，不得当成 PASS，也不得当成失败。
    INVALID      声明本身非法，或场景不可读 / 无根节点（证据链断裂）。

本模块 MUST NOT：
    - 读 Scene Intent / 生成产物 / Blueprint：核对对象是 Feature 自己的入口场景。
    - 让「生成器的预期」充当证据（生成器与验证器不得共享唯一证据对象）。
    - 启动 Godot、import Godot、加载 PackedScene、写文件。
    - 把无法解析的结构直接判成无效（→ INSUFFICIENT）。

契约：.ai/context/scene_composer_schema.yaml#feature_instance_evidence_reconciliation

用法（诊断 CLI）：
    python .ai/tools/scene_composer/instance_evidence.py --feature collect_pickup
    python .ai/tools/scene_composer/instance_evidence.py --all
    python .ai/tools/scene_composer/instance_evidence.py --blueprint <bp.yaml> --scene <host.tscn>

退出码：0 = 全部 PASS/NOT_DECLARED；1 = 存在 MISMATCH/INVALID；2 = 输入错误。
"""

import os
import sys
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
for _path in (_HERE, _TOOLS):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import component_instance_resolver                            # noqa: E402
import external_artifact_resolver                             # noqa: E402
import template_loader                                        # noqa: E402

MODULE_VERSION = 1

STATUS_PASS = "PASS"
STATUS_MISMATCH = "MISMATCH"
STATUS_INSUFFICIENT = "INSUFFICIENT"
STATUS_INVALID = "INVALID"
STATUS_NOT_DECLARED = "NOT_DECLARED"

EVIDENCE_DECLARATION = "declaration"
EVIDENCE_STATIC = "static_scene"
EVIDENCE_RUNTIME = "runtime"

SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"

FEATURES_DIR = template_loader.FEATURES_DIR

# 声明里本模块认识的键（其余键由 resolver / 其它层负责，不在这里猜测）
DECLARATION_FIELDS = ("node_type", "children", "runtime_children", "parent", "id", "resources")


class InstanceEvidenceReport:
    """一次对账的完整结论（findings 保序；status 由 findings 派生）。"""

    def __init__(self, feature: str = "", scene_path: str = "", declaration=None):
        self.feature = feature
        self.scene_path = str(scene_path or "")
        self.declaration = dict(declaration) if isinstance(declaration, dict) else {}
        self.findings = []
        self.checked = []          # 已核对且一致的项（类型 / 节点路径），便于报告引用
        self.notes = []

    def add(self, code: str, severity: str, evidence: str, detail: str,
            node_path: str = "", resource_path: str = "") -> dict:
        finding = {"code": code, "severity": severity, "evidence": evidence,
                   "detail": detail, "node_path": node_path,
                   "resource_path": resource_path}
        self.findings.append(finding)
        return finding

    def errors(self) -> list:
        return [f for f in self.findings if f["severity"] == SEVERITY_ERROR]

    def warnings(self) -> list:
        return [f for f in self.findings if f["severity"] == SEVERITY_WARNING]

    @property
    def status(self) -> str:
        codes = {f["code"] for f in self.findings}
        if codes & {"INSTANCE_EVIDENCE_UNAVAILABLE", "INSTANCE_DECLARATION_INVALID",
                    "INSTANCE_SCENE_UNPARSEABLE"}:
            return STATUS_INVALID
        if self.errors():
            return STATUS_MISMATCH
        if self.warnings():
            return STATUS_INSUFFICIENT
        if not self.declaration:
            return STATUS_NOT_DECLARED
        return STATUS_PASS

    @property
    def ok(self) -> bool:
        """只有 PASS / NOT_DECLARED 视为无需修复；INSUFFICIENT 不算失败但也不算通过。"""
        return self.status in (STATUS_PASS, STATUS_NOT_DECLARED)

    def to_dict(self) -> dict:
        return {"feature": self.feature, "scene": self.scene_path,
                "status": self.status, "findings": [dict(f) for f in self.findings],
                "checked": list(self.checked), "notes": list(self.notes),
                "declaration": dict(self.declaration)}

    def __repr__(self) -> str:  # pragma: no cover - 调试
        return "<InstanceEvidenceReport %s %s findings=%d>" % (
            self.feature, self.status, len(self.findings))


# ---------------------------------------------------------------- 声明校验

def _validate_declaration(declaration, report: InstanceEvidenceReport) -> tuple:
    """声明形态 -> (node_type, children[list], runtime_children[list])；非法时返回 None。"""
    if not isinstance(declaration, dict):
        report.add("INSTANCE_DECLARATION_INVALID", SEVERITY_ERROR, EVIDENCE_DECLARATION,
                   "Invalid instance declaration: expected a mapping")
        return None

    node_type = declaration.get("node_type")
    node_type = node_type.strip() if isinstance(node_type, str) else ""
    if not node_type or not component_instance_resolver.is_known_instance_type(node_type):
        report.add("INSTANCE_DECLARATION_INVALID", SEVERITY_ERROR, EVIDENCE_DECLARATION,
                   "Invalid instance declaration: node_type %s"
                   % (node_type or "<missing>"))
        return None

    def _types(field: str):
        raw = declaration.get(field)
        if raw is None:
            return []
        if isinstance(raw, str):
            raw = [raw]
        if not isinstance(raw, (list, tuple)):
            return None
        values = []
        for item in raw:
            if not isinstance(item, str) or not item.strip():
                return None
            values.append(item.strip())
        return values

    children = _types("children")
    runtime = _types("runtime_children")
    if children is None or runtime is None:
        report.add("INSTANCE_DECLARATION_INVALID", SEVERITY_ERROR, EVIDENCE_DECLARATION,
                   "Invalid instance declaration: children/runtime_children must be lists "
                   "of non-empty strings")
        return None

    unknown = [name for name in children + runtime
               if not component_instance_resolver.is_known_instance_type(name)]
    if unknown:
        report.add("INSTANCE_DECLARATION_INVALID", SEVERITY_ERROR, EVIDENCE_DECLARATION,
                   "Invalid instance declaration: unknown node type %s" % unknown[0])
        return None

    # runtime_children 必须是 children 的子集：只能为「已声明需要的子节点」提供运行时豁免。
    undeclared = [name for name in runtime if name not in children]
    if undeclared:
        report.add("INSTANCE_DECLARATION_INVALID", SEVERITY_ERROR, EVIDENCE_DECLARATION,
                   "Invalid instance declaration: runtime_children %s not declared in children"
                   % undeclared[0])
        return None

    return node_type, children, runtime


# ---------------------------------------------------------------- 静态场景证据

def _parse_scene(scene_path: str, report: InstanceEvidenceReport) -> dict:
    """读取真实 .tscn；不可读 -> INVALID（证据链断裂），不猜测通过。"""
    text_path = str(scene_path or "").strip()
    if not text_path or not os.path.isfile(text_path):
        report.add("INSTANCE_EVIDENCE_UNAVAILABLE", SEVERITY_ERROR, EVIDENCE_STATIC,
                   "Instance evidence unavailable: %s" % (text_path or "<missing>"),
                   resource_path=text_path)
        return {}
    try:
        scene = external_artifact_resolver.parse_scene_text(text_path)
    except OSError as exc:
        report.add("INSTANCE_EVIDENCE_UNAVAILABLE", SEVERITY_ERROR, EVIDENCE_STATIC,
                   "Instance evidence unavailable: %s (%s)" % (text_path, exc),
                   resource_path=text_path)
        return {}
    if not scene.get("root_name"):
        report.add("INSTANCE_SCENE_UNPARSEABLE", SEVERITY_ERROR, EVIDENCE_STATIC,
                   "Instance evidence unavailable: %s (no root node)" % text_path,
                   resource_path=text_path)
        return {}
    return scene


def _node_header_gap(scene_path: str, parsed: int, report: InstanceEvidenceReport) -> None:
    """`[node ...]` 行数多于解析结果 -> 解析器不认识某些结构（不判定无效，标 INSUFFICIENT）。"""
    try:
        with open(scene_path, encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return
    headers = sum(1 for line in text.splitlines() if line.strip().startswith("[node "))
    if headers > parsed:
        report.add("INSTANCE_PARSE_LIMITED", SEVERITY_WARNING, EVIDENCE_STATIC,
                   "Static parse understood %d of %d node header(s); runtime confirmation required"
                   % (parsed, headers), resource_path=scene_path)


def _direct_children(scene: dict) -> list:
    root_name = scene.get("root_name") or ""
    return [node for node in scene.get("nodes") or []
            if node.get("parent_path") == root_name]


def _script_sources(scene: dict) -> list:
    return [entry for entry in scene.get("ext_resources") or []
            if str(entry.get("type") or "").strip() == "Script"]


# ---------------------------------------------------------------- Feature 级对账

def reconcile_declaration(declaration, scene_path: str, feature: str = "",
                          project_root: str = None) -> InstanceEvidenceReport:
    """声明 + 真实 .tscn -> InstanceEvidenceReport（单条声明，纯静态）。

    规则：
        - node_type 必须等于场景根节点类型（根节点不可能由脚本动态创建）。
        - children 是「根节点的直接子节点类型」；同一类型出现 n 次 = 需要 n 个。
        - 子节点存在但层级/路径不对 -> MISMATCH（可定位到实际路径）。
        - 子节点完全不存在且未声明 runtime_children -> MISMATCH。
        - 声明了 runtime_children 但静态找不到 -> INSUFFICIENT（等待运行时证据）。
        - 声明了 runtime_children 却静态存在 -> INSUFFICIENT（声明已过期，需修正）。
    """
    report = InstanceEvidenceReport(feature=feature, scene_path=scene_path,
                                    declaration=declaration if isinstance(declaration, dict) else {})
    validated = _validate_declaration(declaration, report)
    if validated is None:
        return report
    node_type, children, runtime = validated

    scene = _parse_scene(scene_path, report)
    if not scene:
        return report
    _node_header_gap(str(scene_path), len(scene.get("nodes") or []), report)

    nodes = scene.get("nodes") or []
    root_name = scene.get("root_name") or ""
    root = next((node for node in nodes if node.get("path") == root_name), None)
    root_type = str((root or {}).get("type") or "").strip()
    if not root_type:
        report.add("INSTANCE_ROOT_TYPE_MISSING", SEVERITY_ERROR, EVIDENCE_STATIC,
                   "Instance evidence mismatch: scene root has no type (node %s)" % root_name,
                   node_path=root_name, resource_path=str(scene_path))
        return report
    if root_type != node_type:
        report.add("INSTANCE_ROOT_TYPE_MISMATCH", SEVERITY_ERROR, EVIDENCE_STATIC,
                   "Instance evidence mismatch: declared root %s, scene root %s (node %s)"
                   % (node_type, root_type, root_name),
                   node_path=root_name, resource_path=str(scene_path))
    else:
        report.checked.append("%s:%s" % (root_name, root_type))

    seen_paths = Counter(str(node.get("path") or "") for node in nodes)
    for path, count in sorted(seen_paths.items()):
        if count > 1 and path:
            report.add("INSTANCE_DUPLICATE_NODE_PATH", SEVERITY_ERROR, EVIDENCE_STATIC,
                       "Instance evidence mismatch: duplicate node path %s (%d)" % (path, count),
                       node_path=path, resource_path=str(scene_path))

    direct = _direct_children(scene)
    runtime_set = set(runtime)
    for child_type, needed in sorted(Counter(children).items()):
        found = [node for node in direct if node.get("type") == child_type]
        if len(found) >= needed:
            report.checked.append("%s:%s" % (child_type, ",".join(
                str(node.get("path") or "") for node in found)))
            continue
        elsewhere = [node for node in nodes
                     if node.get("type") == child_type and node not in found]
        if child_type in runtime_set:
            report.add("INSTANCE_RUNTIME_CHILD_UNVERIFIED", SEVERITY_WARNING, EVIDENCE_RUNTIME,
                       "Runtime-provided child not statically verifiable: %s" % child_type,
                       node_path=root_name, resource_path=str(scene_path))
            continue
        if elsewhere:
            report.add("INSTANCE_CHILD_PATH_MISMATCH", SEVERITY_ERROR, EVIDENCE_STATIC,
                       "Instance evidence mismatch: %s found at %s, expected directly under %s"
                       % (child_type, elsewhere[0].get("path") or "?",
                          root_name or "?"),
                       node_path=str(elsewhere[0].get("path") or ""),
                       resource_path=str(scene_path))
            continue
        if len(found) and needed > len(found):
            report.add("INSTANCE_CHILD_COUNT_MISMATCH", SEVERITY_ERROR, EVIDENCE_STATIC,
                       "Instance evidence mismatch: %s declared %d, found %d"
                       % (child_type, needed, len(found)),
                       node_path=root_name, resource_path=str(scene_path))
            continue
        report.add("INSTANCE_CHILD_MISSING", SEVERITY_ERROR, EVIDENCE_STATIC,
                   "Instance evidence mismatch: %s missing" % child_type,
                   node_path=root_name, resource_path=str(scene_path))

    for child_type in sorted(runtime_set):
        present = [node for node in nodes if node.get("type") == child_type]
        if present:
            report.add("INSTANCE_RUNTIME_CHILD_STALE", SEVERITY_WARNING, EVIDENCE_STATIC,
                       "Runtime-provided child is actually static: %s at %s"
                       % (child_type, present[0].get("path") or "?"),
                       node_path=str(present[0].get("path") or ""),
                       resource_path=str(scene_path))

    scripts = _script_sources(scene)
    if scripts:
        report.notes.append(
            "static evidence only: scene carries %d script resource(s); nodes created at "
            "runtime are not covered (declare them in instance.runtime_children)"
            % len(scripts))
    return report


def reconcile_feature(feature: str, features_dir: str = FEATURES_DIR,
                      project_root: str = None) -> InstanceEvidenceReport:
    """Feature -> 声明 + 入口场景 -> 对账报告（未声明实例的 Feature 返回 NOT_DECLARED）。"""
    template = template_loader.load_template(feature, features_dir)
    declaration = template_loader.feature_instance_plan(feature, features_dir)
    resource = template_loader.template_scene_path(feature, template, features_dir)
    # 场景按 features_dir 解析（支持临时 / 夹具目录），不假设项目根
    scene_path = _fs_path(resource, project_root or os.path.dirname(features_dir))
    if not declaration:
        report = InstanceEvidenceReport(feature=feature, scene_path=scene_path, declaration={})
        report.notes.append("no instance declaration: nothing to reconcile")
        return report
    return reconcile_declaration(declaration, scene_path, feature=feature,
                                 project_root=project_root)


# ---------------------------------------------------------------- 挂载级对账（生成物）

def reconcile_component_mounts(scene_path: str, feature_ids, features_dir: str = FEATURES_DIR,
                               project_root: str = None) -> dict:
    """生成物（宿主 .tscn）里的组件挂载对账。

    与 artifact_evidence 的差别（互补，不替代）：
        - 只认**恰好一个**挂载节点，且其 PackedScene 必须是该 Feature 模板声明的入口场景；
        - 声明要求的子节点必须在「该组件挂载子树 + 组件自身场景」内找到，
          不接受「别的组件恰好也有这个类型」；
        - 仍区分 INSUFFICIENT（runtime_children / 解析受限）。

    返回 {"scene", "findings", "components": {fid: report_dict}, "status"}。
    """
    findings = []
    components = {}
    scene = _parse_scene(scene_path, InstanceEvidenceReport())
    if not scene:
        return {"scene": str(scene_path), "status": STATUS_INVALID,
                "findings": [{"code": "INSTANCE_EVIDENCE_UNAVAILABLE", "severity": SEVERITY_ERROR,
                              "evidence": EVIDENCE_STATIC,
                              "detail": "Instance evidence unavailable: %s" % scene_path,
                              "node_path": "", "resource_path": str(scene_path)}],
                "components": {}}

    ext_by_id = {str(entry.get("id") or ""): str(entry.get("path") or "")
                 for entry in scene.get("ext_resources") or []}
    instance_nodes = [node for node in scene.get("nodes") or [] if node.get("instance")]
    # 先按声明预解析每个组件的入口场景：「别的组件场景里有该类型」必须可定位，
    # 不能因为扫描不到就笼统报 missing（诊断要能指向真正的来源）。
    declaration_scenes = {}
    for feature in feature_ids:
        if not template_loader.feature_instance_plan(feature, features_dir):
            continue
        template = template_loader.load_template(feature, features_dir)
        expected_scene = template_loader.template_scene_path(feature, template, features_dir)
        parsed = _parse_scene(
            _fs_path(expected_scene, project_root or os.path.dirname(features_dir)),
            InstanceEvidenceReport())
        declaration_scenes[feature] = (parsed, expected_scene)

    for feature in feature_ids:
        template = template_loader.load_template(feature, features_dir)
        declaration = template_loader.feature_instance_plan(feature, features_dir)
        expected = template_loader.template_scene_path(feature, template, features_dir)
        expected_res = expected if str(expected).startswith("res://") else _resource_path(expected)
        mounts = [node for node in instance_nodes
                  if ext_by_id.get(str(node.get("instance_ref") or "")) == expected_res]
        wrong = [node for node in instance_nodes
                 if _is_feature_scene(ext_by_id.get(str(node.get("instance_ref") or "")), feature)]

        if not declaration:
            components[feature] = reconcile_feature(feature, features_dir, project_root).to_dict()
            continue

        report = InstanceEvidenceReport(feature=feature, scene_path=scene_path,
                                        declaration=declaration)
        if not mounts:
            if wrong:
                report.add("INSTANCE_WRONG_SCENE_REFERENCE", SEVERITY_ERROR, EVIDENCE_STATIC,
                           "Instance evidence mismatch: %s mounted from %s, expected %s"
                           % (feature, ext_by_id.get(str(wrong[0].get("instance_ref") or "")),
                              expected_res),
                           node_path=str(wrong[0].get("path") or ""), resource_path=expected_res)
            else:
                report.add("INSTANCE_MOUNT_MISSING", SEVERITY_ERROR, EVIDENCE_STATIC,
                           "Instance evidence mismatch: component mount missing (%s)" % feature,
                           resource_path=expected_res)
        elif len(mounts) > 1:
            report.add("INSTANCE_MOUNT_DUPLICATED", SEVERITY_ERROR, EVIDENCE_STATIC,
                       "Instance evidence mismatch: component mounted %d times (%s)"
                       % (len(mounts), feature),
                       node_path=",".join(str(n.get("path") or "") for n in mounts),
                       resource_path=expected_res)
        else:
            others = []
            for other, (parsed, resource) in sorted(declaration_scenes.items()):
                if other == feature or not parsed:
                    continue
                others.extend(dict(node, origin=resource)
                              for node in parsed.get("nodes") or [])
            _check_mount_children(report, mounts[0], scene,
                                  _fs_path(expected,
                                           project_root or os.path.dirname(features_dir)),
                                  feature, declaration, others)
        components[feature] = report.to_dict()
        findings.extend(report.findings)

    status = STATUS_PASS
    if any(f["severity"] == SEVERITY_ERROR for f in findings):
        status = STATUS_MISMATCH
    elif any(f["severity"] == SEVERITY_WARNING for f in findings):
        status = STATUS_INSUFFICIENT
    return {"scene": str(scene_path), "status": status, "findings": findings,
            "components": components}


def _check_mount_children(report, mount, host_scene, expected_scene_path, feature,
                          declaration, others=None) -> None:
    validated = _validate_declaration(declaration, report)
    if validated is None:
        return
    node_type, children, runtime = validated
    component_scene = _parse_scene(expected_scene_path, report)
    if not component_scene:
        return

    mount_path = str(mount.get("path") or "")
    host_nodes = host_scene.get("nodes") or []
    inside = [node for node in host_nodes
              if str(node.get("parent_path") or "") == mount_path
              or str(node.get("parent_path") or "").startswith(mount_path + "/")]
    outside = [node for node in host_nodes if node not in inside]
    own_direct = [node for node in component_scene.get("nodes") or []
                  if node.get("parent_path") == component_scene.get("root_name")]

    runtime_set = set(runtime)
    for child_type, needed in sorted(Counter(children).items()):
        found = [node for node in inside + own_direct if node.get("type") == child_type]
        if len(found) >= needed:
            report.checked.append("%s:%s" % (child_type, ",".join(
                str(node.get("path") or "") for node in found)))
            continue
        stray = [node for node in outside if node.get("type") == child_type]
        stray_from_others = [node for node in (others or [])
                             if node.get("type") == child_type and node not in stray]
        if child_type in runtime_set:
            report.add("INSTANCE_RUNTIME_CHILD_UNVERIFIED", SEVERITY_WARNING, EVIDENCE_RUNTIME,
                       "Runtime-provided child not statically verifiable: %s" % child_type,
                       node_path=mount_path, resource_path=expected_scene_path)
            continue
        if stray or stray_from_others:
            source = (stray or stray_from_others)[0]
            location = str(source.get("origin") or "") + "/" + str(source.get("path") or "?")
            report.add("INSTANCE_CHILD_OUTSIDE_MOUNT", SEVERITY_ERROR, EVIDENCE_STATIC,
                       "Instance evidence mismatch: %s found at %s, outside the %s mount"
                       % (child_type, location, feature),
                       node_path=str(source.get("path") or ""),
                       resource_path=str(source.get("origin") or expected_scene_path))
            continue
        report.add("INSTANCE_CHILD_MISSING", SEVERITY_ERROR, EVIDENCE_STATIC,
                   "Instance evidence mismatch: %s missing" % child_type,
                   node_path=mount_path, resource_path=expected_scene_path)


# ---------------------------------------------------------------- 工具

def _fs_path(resource_path: str, project_root: str = None) -> str:
    """res:// 路径 -> 文件系统路径（项目根内）；其它形态原样返回（不猜测）。"""
    text = str(resource_path or "").strip()
    if not text.startswith("res://"):
        return text
    root = project_root or external_artifact_resolver.PROJECT_ROOT
    relative = text[len("res://"):].replace("\\", "/").lstrip("/")
    return os.path.join(root, *relative.split("/")) if relative else ""


def _resource_path(scene_path: str) -> str:
    """文件系统路径 -> res:// 路径（项目根内）；无法映射 -> 原样返回（不猜测）。"""
    absolute = os.path.abspath(str(scene_path or ""))
    root = os.path.abspath(external_artifact_resolver.PROJECT_ROOT)
    try:
        relative = os.path.relpath(absolute, root)
    except ValueError:
        return str(scene_path or "")
    if relative.startswith(".."):
        return str(scene_path or "")
    return "res://" + relative.replace("\\", "/")


def _is_feature_scene(resource_path, feature: str) -> bool:
    text = str(resource_path or "")
    return bool(feature) and text.startswith("res://Features/%s/" % feature)


def declared_features(features_dir: str = FEATURES_DIR) -> list:
    """声明了 instance: 的 Feature（按目录顺序；只读）。"""
    names = []
    if not os.path.isdir(features_dir):
        return names
    for name in sorted(os.listdir(features_dir)):
        template_path = os.path.join(features_dir, name, "template.yaml")
        if not os.path.isfile(template_path):
            continue
        if template_loader.feature_instance_plan(name, features_dir):
            names.append(name)
    return names


def reconcile_all(features_dir: str = FEATURES_DIR) -> list:
    """所有 Feature -> 报告列表（含未声明者，状态 NOT_DECLARED）。"""
    reports = []
    if not os.path.isdir(features_dir):
        return reports
    for name in sorted(os.listdir(features_dir)):
        if not os.path.isfile(os.path.join(features_dir, name, "template.yaml")):
            continue
        reports.append(reconcile_feature(name, features_dir))
    return reports


def summarize(reports) -> dict:
    counts = Counter(report.status for report in reports)
    return {"checked": len(reports),
            "pass": counts.get(STATUS_PASS, 0),
            "mismatch": counts.get(STATUS_MISMATCH, 0),
            "insufficient": counts.get(STATUS_INSUFFICIENT, 0),
            "invalid": counts.get(STATUS_INVALID, 0),
            "not_declared": counts.get(STATUS_NOT_DECLARED, 0)}


# ---------------------------------------------------------------- CLI

def main(argv=None) -> int:  # pragma: no cover - 诊断入口（只读）
    import argparse

    parser = argparse.ArgumentParser(description="Reconcile Feature instance declarations "
                                                 "against real .tscn files.")
    parser.add_argument("--feature", action="append", default=[], help="Feature id (repeatable)")
    parser.add_argument("--all", action="store_true", help="all Features with template.yaml")
    parser.add_argument("--blueprint", default="", help="Scene/Entity blueprint (mount mode)")
    parser.add_argument("--scene", default="", help="generated host .tscn (mount mode)")
    args = parser.parse_args(argv)

    if args.blueprint or args.scene:
        if not (args.blueprint and args.scene):
            print("FAIL: --blueprint and --scene must be used together")
            return 2
        if not os.path.isfile(args.blueprint) or not os.path.isfile(args.scene):
            print("FAIL: input not found")
            return 2
        import yaml
        from scene_intent import intent_components, intent_from_blueprint
        blueprint = yaml.safe_load(open(args.blueprint, encoding="utf-8")) or {}
        intent, errors = intent_from_blueprint(blueprint)
        if errors or intent is None:
            print("FAIL: invalid blueprint: %s" % "; ".join(errors or ["unknown"]))
            return 2
        features = list(intent_components(intent))
        result = reconcile_component_mounts(args.scene, features)
        print("Feature Instance Mounts: %s -> %s" % (args.scene, result["status"]))
        for finding in result["findings"]:
            print("  - [%s] %s" % (finding["severity"], finding["detail"]))
        return 0 if result["status"] in (STATUS_PASS, STATUS_INSUFFICIENT) else 1

    targets = args.feature or (declared_features() if args.all else [])
    if not targets:
        print("FAIL: give --feature <id>, --all, or --blueprint/--scene")
        return 2
    failed = 0
    for feature in targets:
        report = reconcile_feature(feature)
        print("%-18s %-12s %s" % (feature, report.status, report.scene_path))
        for finding in report.findings:
            print("  - [%s] %s" % (finding["severity"], finding["detail"]))
        if report.status in (STATUS_MISMATCH, STATUS_INVALID):
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
