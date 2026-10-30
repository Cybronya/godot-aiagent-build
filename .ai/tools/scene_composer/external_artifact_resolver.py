#!/usr/bin/env python3
"""External Artifact Resolver (Phase 1.8.16) —— ExtResource 指向的组件场景静态解析。

定位（Complete Artifact Evidence 的证据来源之一）：

    Host .tscn（Scene Builder 生成物）
        |  ext_resource type="PackedScene" path="res://Features/<id>/<Scene>.tscn"
        ↓  resolve_external_artifact / resolve_external_artifacts（本模块）
    Feature Component .tscn（组件入口场景）
        ↓  合并 Evidence（artifact_evidence_validator）
    Complete Artifact Evidence = Host Artifact + External Component Artifacts

本模块只做**静态文本解析**：

    读取：节点 name / type / parent / ExtResource 引用、ext_resource 表（type / path / id）
    禁止读取：sub_resource 内容、script、animation、资源文件内容
    禁止：启动 Godot、import Godot、加载 PackedScene、Editor / Runtime SceneTree、写文件

路径解析（不猜测）：

    res://Features/<id>/<Scene>.tscn
        ↓  以宿主 .tscn 所在项目（含 project.godot 的目录）为根
    <project>/Features/<id>/<Scene>.tscn
    不存在 / 非 res://Features/ → \"External artifact unavailable: <path>\"（BLOCKED）

循环引用（递归解析）：

    A.tscn ⇄ B.tscn 之类可达环 → \"External artifact recursion detected: <path>\"（BLOCKED）
    判定口径（Phase 1.37 修正）：**回溯祖先链**——只有再次遇到当前解析路径上的文件才是环；
    菱形引用（Host → A、Host → B → A）是合法的 Godot 组合结构，只解析一次、复用证据。
    宿主 .tscn 本身也在祖先链上。

契约：.ai/context/scene_composer_schema.yaml#external_artifact_evidence
"""

import os
import re

STATUS_PASS = "PASS"
STATUS_BLOCKED = "BLOCKED"

RESOURCE_PREFIX = "res://"
FEATURES_SEGMENT = "Features/"
SCENE_SUFFIX = ".tscn"
PROJECT_FILE = "project.godot"
SCENE_RESOURCE_TYPE = "PackedScene"

# 递归深度上限（循环由 visited 集合拦截；这只是防御性兜底）
MAX_DEPTH = 8

# 目录定位：本文件位于 <root>/.ai/tools/scene_composer/ 下
_TOOL_DOTAI = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .ai
PROJECT_ROOT = os.path.dirname(_TOOL_DOTAI)

_NODE_HEADER_RE = re.compile(r'^\[node\s+(?P<attrs>.*)\]$')
_EXT_RESOURCE_RE = re.compile(r'^\[ext_resource\s+(?P<attrs>.*)\]$')
_ATTR_RE = re.compile(r'(?P<key>[A-Za-z_]+)=(?:"(?P<quoted>[^"]*)"|(?P<bare>[^\s\]]+))')
_INSTANCE_REF_RE = re.compile(r'instance\s*=\s*ExtResource\(\s*"(?P<ref>[^"]*)"\s*\)')


# ---------------------------------------------------------------- 路径工具（共用）

def normalize_path(value) -> str:
    """节点路径 / parent 声明 -> 规范相对路径（"" 表示根）。"""
    text = str(value or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    if text in (".", "/"):
        return ""
    return text.strip("/")


def parent_key(node: dict, root_name: str) -> str:
    """节点的「挂载点」（根相对形式，与声明的 parent 字段可比）：根节点 → 根名。"""
    return normalize_path(node.get("parent")) or root_name


def is_under(parent_path: str, base_path: str) -> bool:
    """parent_path 是否等于 base_path 或位于其下（逐层后代）。"""
    return parent_path == base_path or parent_path.startswith(base_path + "/")


def project_root_for(scene_path: str) -> str:
    """宿主 .tscn -> 项目根（向上找含 project.godot 的目录）；找不到退回工具所在项目根。"""
    current = os.path.dirname(os.path.abspath(str(scene_path or "")))
    while current and current != os.path.dirname(current):
        if os.path.isfile(os.path.join(current, PROJECT_FILE)):
            return current
        current = os.path.dirname(current)
    return PROJECT_ROOT


def resolve_resource_path(resource_path, project_root=None) -> str:
    """res:// 路径 -> 文件系统路径；非 res:// 路径 → ""（不猜测、不拼路径）。"""
    text = str(resource_path or "").strip()
    if not text.startswith(RESOURCE_PREFIX):
        return ""
    relative = text[len(RESOURCE_PREFIX):].replace("\\", "/").lstrip("/")
    if not relative:
        return ""
    return os.path.join(project_root or PROJECT_ROOT, *relative.split("/"))


def is_component_scene(resource_path) -> bool:
    """组件入口场景判定：res://Features/... 下的 PackedScene（本阶段解析范围）。"""
    text = str(resource_path or "").strip()
    return (text.startswith(RESOURCE_PREFIX + FEATURES_SEGMENT)
            and text.lower().endswith(SCENE_SUFFIX))


def _abs_key(scene_path, resource_path, project_root=None) -> str:
    """组件场景 -> 文件绝对路径（祖先链身份；无法解析 → ""）。

    与 resolve_external_artifact 的身份口径必须一致，否则环判定会和解析器不一致。
    """
    root = project_root or project_root_for(scene_path)
    file_path = resolve_resource_path(resource_path, root)
    return os.path.abspath(file_path) if file_path else ""


def feature_id_of(resource_path) -> str:
    """res://Features/<id>/<Scene>.tscn -> <id>；不符合形态 → ""（不猜测）。"""
    text = str(resource_path or "").strip()
    marker = RESOURCE_PREFIX + FEATURES_SEGMENT
    if not text.startswith(marker):
        return ""
    rest = text[len(marker):]
    return rest.split("/", 1)[0].strip() if "/" in rest else ""


# ---------------------------------------------------------------- 静态解析

def parse_scene_text(scene_path: str) -> dict:
    """静态解析 .tscn 文本 -> {"root_name", "nodes", "ext_resources", "scene_path"}。

    nodes[]: {"name", "type", "parent", "path", "parent_path", "instance", "instance_ref"}
      path         —— 节点全路径（含场景根名，如 "Root/Inner/Shape"；根为裸名）
      parent_path  —— 父节点全路径（根节点为 ""）；供逐层后代判定使用
      parent       —— 原始 parent 属性（根相对，如 "." / "Inner"）
      instance     —— 该节点是否为 PackedScene 实例（instance=ExtResource(...)）
      instance_ref —— ExtResource id（未实例化节点为 ""）
    ext_resources[]: {"id", "type", "path"}（type=Script / PackedScene / 资源类型都保留，
      只有 PackedScene + res://Features/ 才参与外部解析）

    只读文本；不解释属性值、不读 sub_resource / script / animation / 资源内容。
    """
    with open(scene_path, encoding="utf-8") as handle:
        text = handle.read()

    nodes, ext_resources = [], []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("[ext_resource "):
            match = _EXT_RESOURCE_RE.match(line)
            if not match:
                continue
            attrs = _attrs(match.group("attrs"))
            ext_resources.append({"id": attrs.get("id", ""), "type": attrs.get("type", ""),
                                  "path": attrs.get("path", "")})
            continue
        if not line.startswith("[node "):
            continue
        match = _NODE_HEADER_RE.match(line)
        if not match:
            continue
        attrs = _attrs(match.group("attrs"))
        name = str(attrs.get("name") or "").strip()
        if not name:
            continue
        instance_ref = _INSTANCE_REF_RE.search(match.group("attrs"))
        nodes.append({
            "name": name,
            "type": str(attrs.get("type") or "").strip(),
            "parent": str(attrs.get("parent") or "").strip(),
            "path": "",
            "parent_path": "",
            "instance": bool(instance_ref) or "instance" in attrs,
            "instance_ref": instance_ref.group("ref") if instance_ref else "",
        })

    # 根节点 = 没有 parent 属性的节点（注意：parent="." 表示「挂在场景根下」，不是根）
    root_name = ""
    for node in nodes:
        if not str(node["parent"] or "").strip():
            root_name = node["name"]
            break
    # 全路径（根名开头）：逐层后代判定需要它，否则多级子节点无法与声明节点比较。
    for node in nodes:
        raw = str(node["parent"] or "").strip()
        if not raw:
            node["parent_path"] = ""
            node["path"] = node["name"]
            continue
        relative = normalize_path(raw)
        if not relative:                          # "."：直接挂在场景根下
            node["parent_path"] = root_name
        elif relative == root_name or relative.startswith(root_name + "/"):
            node["parent_path"] = relative        # parent 已写全路径（少见但合法）
        else:
            node["parent_path"] = "%s/%s" % (root_name, relative) if root_name else relative
        node["path"] = "%s/%s" % (node["parent_path"], node["name"])
    return {"root_name": root_name, "nodes": nodes, "ext_resources": ext_resources,
            "scene_path": os.path.abspath(scene_path)}


def _attrs(header: str) -> dict:
    values = {}
    for attr in _ATTR_RE.finditer(header):
        quoted = attr.group("quoted")
        values[attr.group("key")] = quoted if quoted is not None else attr.group("bare")
    return values


def component_scene_refs(scene: dict) -> list:
    """场景 -> 其引用的组件入口场景（PackedScene + res://Features/...；保持出现顺序）。"""
    refs, seen = [], set()
    for entry in scene.get("ext_resources") or []:
        path = str(entry.get("path") or "").strip()
        if str(entry.get("type") or "").strip() != SCENE_RESOURCE_TYPE:
            continue
        if not is_component_scene(path) or path in seen:
            continue
        seen.add(path)
        refs.append(path)
    return refs


# ---------------------------------------------------------------- 单个外部产物

def resolve_external_artifact(scene_path, resource_path, project_root=None,
                              visited=None, depth: int = 0) -> dict:
    """读取并解析 ExtResource 指向的组件场景（单文件，不做递归展开）。

    scene_path    —— 宿主 .tscn（用于定位项目根）；仅作上下文，不修改。
    resource_path —— res://Features/<id>/<Scene>.tscn（来自 ext_resource 表）。
    project_root  —— 可选：显式项目根（缺省由 scene_path 向上找 project.godot）。
    visited       —— 可选：已访问文件绝对路径集合（循环检测；宿主路径应由调用方预置）。

    返回 {"status", "nodes", "errors", "path", "references"}：
        nodes      —— 该文件中的节点（origin 为该 res:// 路径；parent/path 相对该场景根）
        references —— 该文件自身引用的组件入口场景（供调用方继续递归）
    不存在的路径 → BLOCKED \"External artifact unavailable: <path>\"；重复访问 →
    BLOCKED \"External artifact recursion detected: <path>\"。
    """
    text = str(resource_path or "").strip()
    report = {"status": STATUS_PASS, "nodes": [], "errors": [], "path": text, "references": []}
    if not is_component_scene(text):
        report["status"] = STATUS_BLOCKED
        report["errors"] = ["External artifact unavailable: %s" % (text or "<missing>")]
        return report

    root = project_root or project_root_for(scene_path)
    file_path = resolve_resource_path(text, root)
    seen = visited if visited is not None else set()
    key = os.path.abspath(file_path) if file_path else ""
    if key and key in seen:
        report["status"] = STATUS_BLOCKED
        report["errors"] = ["External artifact recursion detected: %s" % text]
        return report
    if not file_path or not os.path.isfile(file_path):
        report["status"] = STATUS_BLOCKED
        report["errors"] = ["External artifact unavailable: %s" % text]
        return report
    if depth >= MAX_DEPTH:
        report["status"] = STATUS_BLOCKED
        report["errors"] = ["External artifact recursion detected: %s" % text]
        return report

    try:
        scene = parse_scene_text(file_path)
    except OSError:
        report["status"] = STATUS_BLOCKED
        report["errors"] = ["External artifact unavailable: %s" % text]
        return report

    seen.add(key)
    report["nodes"] = [dict(node, origin=text) for node in scene["nodes"]]
    report["references"] = component_scene_refs(scene)
    return report


def resolve_external_artifacts(scene_path, project_root=None) -> dict:
    """宿主 .tscn 可达的**全部**外部组件场景（递归；Complete Evidence 的外部部分）。

    返回 {"status", "artifacts", "nodes", "references", "errors"}：
        artifacts  —— 已解析的 res:// 路径（出现顺序，去重）
        nodes      —— 全部外部节点（每个带 origin）
        references —— 引用图 {res:// 路径: [其直接引用的 res:// 路径]}（供调用方计算可达闭包）
    任一环节失败（不存在 / 循环 / 非法路径）→ status BLOCKED 且 errors 非空
    （证据链不完整时不得放行）。

    环判定用**祖先链**（Phase 1.37）：同一文件经不同分支重复可达（菱形）是合法结构，
    只解析一次并复用证据；只有回到当前路径上的祖先才是真正的环。
    """
    errors, artifacts, nodes, references = [], [], [], {}
    host_key = os.path.abspath(str(scene_path)) if scene_path else ""
    host_ancestors = frozenset([host_key]) if host_key else frozenset()
    try:
        host = parse_scene_text(scene_path)
    except OSError:
        return {"status": STATUS_BLOCKED, "artifacts": [], "nodes": [], "references": {},
                "errors": ["External artifact unavailable: %s" % (scene_path or "<missing>")]}

    queue = [(ref, 0, host_ancestors) for ref in component_scene_refs(host)]
    while queue:
        resource_path, depth, ancestors = queue.pop(0)
        key = _abs_key(scene_path, resource_path, project_root)
        if key and key in ancestors:
            # 真正的环：回到当前解析路径上的祖先（先判环，再由菱形缓存复用）
            errors.append("External artifact recursion detected: %s" % resource_path)
            continue
        if resource_path in references:
            continue                          # 菱形：已解析，复用证据（不是环）
        result = resolve_external_artifact(scene_path, resource_path,
                                           project_root=project_root,
                                           visited=set(ancestors), depth=depth)
        if result["status"] != STATUS_PASS:
            errors.extend(result["errors"])
            continue
        references[resource_path] = list(result["references"])
        if resource_path not in artifacts:
            artifacts.append(resource_path)
            nodes.extend(result["nodes"])
        child_ancestors = frozenset(ancestors | {_abs_key(scene_path, resource_path,
                                                         project_root)})
        queue.extend((ref, depth + 1, child_ancestors) for ref in result["references"])

    status = STATUS_BLOCKED if errors else STATUS_PASS
    return {"status": status, "artifacts": artifacts, "nodes": nodes,
            "references": references, "errors": errors}


def main(argv=None) -> int:  # pragma: no cover - 诊断入口（只读，无副作用）
    """打印解析器版本与解析范围。"""
    print("External Artifact Resolver v1")
    print("scope: res://Features/**/*.tscn (PackedScene ext_resource); static text only")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
