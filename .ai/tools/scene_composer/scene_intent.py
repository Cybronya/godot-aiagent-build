#!/usr/bin/env python3
"""Scene Intent Builder (Phase 1.8.6) —— 内部规整形态 → Scene Intent Document。

链路（本模块是 Scene Composer 的**正式输出计划层**）：

    Asset Binding Document
        ↓  asset_nodes.nodes_for_blueprint（只读 Binding）
    resource_nodes + normalize_scene_blueprint() 的内部 dict
        ↓  SceneIntentBuilder（本模块）
    Scene Intent Document
        ↓  compatibility_gate（Phase 1.8.9/1.8.10：消费 capabilities.required + components）
        ↓  scene_builder（Phase 1.8.7：Scene Intent 是 Scene 层唯一输入）
    .tscn
        ↓  scene_validator / test_generator（Phase 1.8.8：同样只吃 Scene Intent）

本模块只负责「投影 + 承载 + 输入边界」；生成规则与 .tscn 文本格式归 scene_builder
（Scene Intent 契约不定义 .tscn 文本，见 scene_schema.yaml）。

输入边界（唯一实现的强制点，所有消费者共用）：
    intent_document()   —— 接受 SceneIntent 对象或契约文档 mapping；旧规整内部 dict 一律拒绝
    intent_components() —— components[].component → feature id 列表
    intent_component_instances() —— components[].instance → 实例计划声明（Phase 1.8.14）
    intent_root()       —— root 段（mapping）
    intent_capabilities() —— capability metadata（Phase 1.8.10）：`{"required": [...]}`
    intent_from_blueprint() —— 原始 Blueprint（scene_schema.yaml）→ SceneIntent（CLI 入口用）

契约（唯一权威）：.ai/context/scene_composer_schema.yaml 的 `scene_intent` 段。

边界（与契约 Contract Freeze / Scene Intent rules 同源）：
    - **只读投影**：不计算、不升级、不改写 Binding 提供的事实；不修改输入 dict。
    - provenance（resolved_from / compatibility / confidence / runners_up / note）
      契约状态为 **PLANNED** → 当前**不携带、不发明**（缺失是正确行为，不是缺陷）。
    - metadata / components[].node / components[].scene / scripts / animations
      契约状态为 **PLANNED** → 不产出（禁止发明）。
    - components[].instance（Phase 1.8.14）契约状态为 **CURRENT 但可选**：只携带调用方 /
      Blueprint 声明的实例计划（Blueprint.components[].instance 或成员 Feature template.yaml
      的 instance: 块，经 template_loader 汇总）；未声明 → 不产出该键（旧 Intent 行为不变）。
      本层只投影字段（含 Phase 1.8.17 的可选 `id`），合法性判定归 component_instance_resolver。
    - persistence = memory_only → 对象只在 compose 执行期存在，**不落盘**。
    - 禁止在本层搜索 / 选择 / 替换资源（top1、打分、补选一律禁止）。
"""

import warnings

SCENE_INTENT_DOCUMENT = "scene_intent"
SCENE_INTENT_VERSION = 1                    # 与契约 scene_intent.version 一致

# 契约 internal_to_document 映射的落地表（document 字段 <- 内部键）
_ROOT_FIELDS = (("name", "root_name"), ("type", "root_type"))
_ROOT_EXTRA_FIELDS = ("scene", "properties", "groups")
_RESOURCE_FIELDS = ("name", "type", "property", "path", "role", "roles", "asset",
                    "animation", "hframes", "vframes")

# 契约 scene_intent.provenance.fields —— CURRENT 状态为「不读取」，
# PLANNED 才允许原样携带。此处仅作声明用途，本层不读写它们。
PROVENANCE_FIELDS = ("resolved_from", "compatibility", "confidence", "runners_up", "note")

# scene_builder 在构建期间写入的私有标记，禁止泄漏进 Scene Intent。
_BUILDER_INTERNAL_PREFIX = "_"


class SceneIntent:
    """Scene Intent Document 的运行时载体。

    document —— 契约文档形态（Scene 层唯一合法消费形态）
    internal —— 归一化内部 dict（**弃用视图**：仅供诊断 / 兼容，任何生成或校验链路
                都禁止消费它；见 to_legacy_dict）
    """

    def __init__(self, document: dict, internal: dict):
        self._document = document
        self._internal = internal

    @property
    def document(self) -> dict:
        return self._document

    @property
    def internal(self) -> dict:
        return self._internal

    def to_dict(self) -> dict:
        """返回契约文档形态的**深拷贝**（调用方修改不影响本体）。"""
        import copy
        return copy.deepcopy(self._document)

    def to_legacy_dict(self) -> dict:
        """**已弃用**（Phase 1.8.7）—— 兼容访问器，返回内部规整形态。

        Phase 1.8.7 起 Scene Builder 的唯一合法输入是 Scene Intent 本身
        （本对象或其 document mapping）；旧内部 dict 传入 builder 会 ValueError。
        本方法保留只为诊断 / 对比既有内部键，**不是**运行时生成路径，
        任何生成链路都禁止再用它旁路 Scene Intent 边界。
        """
        warnings.warn("SceneIntent.to_legacy_dict() is deprecated since Phase 1.8.7: "
                      "scene_builder consumes the Scene Intent itself",
                      DeprecationWarning, stacklevel=2)
        return self._internal

    def counts(self) -> dict:
        """摘要计数（供 CLI 报告）。"""
        return {
            "components": len(self._document.get("components") or []),
            "nodes": len(self._document.get("nodes") or []),
            "resources": len(self._document.get("resources") or []),
        }

    def __repr__(self) -> str:  # pragma: no cover - 便于调试
        counts = self.counts()
        return "<SceneIntent scene=%s components=%d nodes=%d resources=%d>" % (
            (self._document.get("scene") or {}).get("id", ""),
            counts["components"], counts["nodes"], counts["resources"])


class SceneIntentBuilder:
    """把归一化内部 dict + resource_nodes 投影为 Scene Intent Document。

    纯函数式：不修改输入，不读写文件，不访问 Asset Registry / 资源目录。
    """

    def build(self, blueprint: dict, resource_nodes=None, capabilities=None) -> SceneIntent:
        """blueprint + resource_nodes + capabilities -> Scene Intent Document。

        capabilities —— 可选的能力声明（Phase 1.8.10）：`["Node", "Sprite"]` 或
        `{"required": [...]}`；缺省/空 → `{"required": []}`（旧 Intent 仍合法）。
        本层只做**声明与规范化**：不判断能力是否支持（那是 compatibility_gate 的职责）。
        """
        if not isinstance(blueprint, dict):
            raise ValueError(
                "SceneIntentBuilder.build expects the normalized blueprint mapping, got %s"
                % type(blueprint).__name__)
        nodes = blueprint.get("resource_nodes") if resource_nodes is None else resource_nodes
        # 能力声明（Phase 1.8.11）：规整 Blueprint 携带的声明（Feature 汇总 + 作者声明）
        # 与调用方显式传入的声明取**并集** —— 需求只能叠加，任何一方不得削弱另一方。
        required = _merge_capabilities(blueprint.get("capabilities"), capabilities)
        document = {
            # 文档身份与版本（契约 scene_intent.document / version）
            "document": SCENE_INTENT_DOCUMENT,
            "schema_version": SCENE_INTENT_VERSION,
            "scene": {"id": str(blueprint.get("scene_id") or "")},
            "root": self._root(blueprint),
            "components": self._components(blueprint),
            "nodes": self._nodes(blueprint),
            "resources": self._resources(nodes or []),
            # 能力声明（CURRENT；默认 required=[]，向后兼容旧 Intent）
            "capabilities": {"required": required},
            "validation": {
                "required_tests": [str(t) for t in (blueprint.get("required_tests") or [])],
            },
            # metadata / scripts / animations：契约状态 PLANNED → 不产出。
        }
        return SceneIntent(document=document, internal=blueprint)

    # ---------- 各段投影 ----------

    @staticmethod
    def _root(blueprint: dict) -> dict:
        root = {}
        for document_key, internal_key in _ROOT_FIELDS:
            value = blueprint.get(internal_key)
            if value:
                root[document_key] = str(value)
        root_extra = blueprint.get("root_extra") or {}
        for key in _ROOT_EXTRA_FIELDS:
            if key in root_extra:
                value = root_extra[key]
                root[key] = value if key == "properties" else (
                    [str(g) for g in value] if key == "groups" else str(value))
        return root

    @staticmethod
    def _components(blueprint: dict) -> list:
        # CURRENT：features[] -> components[].component
        # Phase 1.8.14：可选的组件实例计划（components[].instance）——只携带声明，
        # 不派生、不猜测（模板派生的是 node / scene，仍为 PLANNED）。
        # PLANNED：components[].node / .scene（由 template 派生，本层禁止发明）
        declared = blueprint.get("component_instances") or {}
        components = []
        for fid in (blueprint.get("features") or []):
            entry = {"component": str(fid)}
            instance = declared.get(str(fid)) if isinstance(declared, dict) else None
            if isinstance(instance, dict):
                entry["instance"] = _component_instance(instance)
            elif instance is not None:
                entry["instance"] = instance      # 非法形态原样携带 → resolver 报错（不静默丢弃）
            components.append(entry)
        return components

    @staticmethod
    def _nodes(blueprint: dict) -> list:
        # CURRENT：extra_nodes[] -> nodes[]（保留 name / type / parent / shape /
        # properties 等一切非 builder 私有键；不新增、不改写）
        nodes = []
        for entry in blueprint.get("extra_nodes") or []:
            if not isinstance(entry, dict):
                continue
            node = {k: entry[k] for k in entry
                    if not str(k).startswith(_BUILDER_INTERNAL_PREFIX)}
            nodes.append(node)
        return nodes

    @staticmethod
    def _resources(nodes) -> list:
        # CURRENT：resource_nodes[] -> resources[]（字段白名单，与契约列表一致）
        # 排除 ext_type 等构建期派生值；provenance 为 PLANNED → 不携带。
        resources = []
        for entry in nodes or []:
            if not isinstance(entry, dict):
                continue
            resource = {key: entry[key] for key in _RESOURCE_FIELDS if key in entry}
            if resource:
                resources.append(resource)
        return resources


def _component_instance(instance: dict) -> dict:
    """组件实例声明 -> 文档形态（只复制已声明字段，不补默认值、不发明）。

    允许字段：id / node_type / children / resources / parent（见契约
    component_instance_materialization 与 component_instance_ownership）。
    `id`（Phase 1.8.17 可选）= 声明方给出的**节点身份**（ownership 唯一映射依据）。
    声明为空 mapping → 返回 {}（保留「已声明」这一事实；无法识别由 resolver 报错，不静默丢弃）。
    """
    document = {}
    instance_id = instance.get("id")
    if isinstance(instance_id, str) and instance_id.strip():
        document["id"] = instance_id.strip()
    node_type = instance.get("node_type")
    if isinstance(node_type, str) and node_type.strip():
        document["node_type"] = node_type.strip()
    for key in ("children", "resources"):
        raw = instance.get(key)
        if not isinstance(raw, (list, tuple)):
            continue
        values = [str(item).strip() for item in raw if str(item or "").strip()]
        if values:
            document[key] = values
    parent = instance.get("parent")
    if isinstance(parent, str) and parent.strip():
        document["parent"] = parent.strip()
    return document


def _normalize_capabilities(capabilities) -> list:
    """能力声明 -> 去空、去重（保序）的字符串列表。

    接受 None / list[str] / `{"required": [...]}`；其它形态 → ValueError（不猜测）。
    """
    if capabilities is None:
        return []
    if isinstance(capabilities, dict):
        if "required" in capabilities:
            capabilities = capabilities["required"]
        elif not capabilities:
            return []
        else:
            raise ValueError("capabilities mapping must contain 'required', got keys %s"
                             % sorted(str(key) for key in capabilities))
    if isinstance(capabilities, str):
        capabilities = [capabilities]
    if not isinstance(capabilities, (list, tuple)):
        raise ValueError("capabilities must be a list of names or {'required': [...]}, got %s"
                         % type(capabilities).__name__)
    required = []
    for entry in capabilities:
        name = str(entry or "").strip()
        if name and name not in required:
            required.append(name)
    return required


def _merge_capabilities(*sources) -> list:
    """多个能力声明源 -> 并集（去空、去重、保序）。

    需求语义是叠加而非覆盖：Blueprint（Feature 汇总）与显式声明都不得削弱对方
    （否则调用方可以透过显式声明隐藏成员 Feature 的能力需求）。
    """
    merged = []
    for source in sources:
        for name in _normalize_capabilities(source):
            if name not in merged:
                merged.append(name)
    return merged


def build_scene_intent(blueprint: dict, resource_nodes=None,
                       capabilities=None) -> SceneIntent:
    """便捷入口：SceneIntentBuilder().build(...) 的模块级封装。"""
    return SceneIntentBuilder().build(blueprint, resource_nodes, capabilities)


# ---------------------------------------------------------------- 输入边界（唯一实现）

def intent_document(scene_intent, where: str = "scene_intent") -> dict:
    """Scene Intent -> 契约文档 mapping（只读；不拷贝）。

    接受 `SceneIntent` 对象（object API）或 Scene Intent 契约文档 mapping
    （`document: scene_intent`）；**旧规整内部 dict 一律拒绝**（无隐藏转换、
    无兼容适配器）。Phase 1.8.7 起 scene_builder 拒绝，Phase 1.8.8 起
    scene_validator / test_generator 同样拒绝 —— 不存在第二入口。
    """
    document = getattr(scene_intent, "document", None)
    if isinstance(document, dict):
        return document
    if isinstance(scene_intent, dict):
        if str(scene_intent.get("document") or "") == SCENE_INTENT_DOCUMENT:
            return scene_intent
        raise ValueError(
            "%s expects a Scene Intent document (document: %r); the legacy normalized "
            "blueprint dict is rejected (Phase 1.8.7/1.8.8 input boundary). "
            "Build one with SceneIntentBuilder (or intent_from_blueprint)."
            % (where, SCENE_INTENT_DOCUMENT))
    raise ValueError("%s expects a SceneIntent or its document mapping, got %s"
                     % (where, type(scene_intent).__name__))


def intent_root(scene_intent) -> dict:
    """Scene Intent -> root 段（mapping）。"""
    root = intent_document(scene_intent, "scene_intent.intent_root").get("root") or {}
    if not isinstance(root, dict):
        raise ValueError("Scene Intent root must be a mapping")
    return root


def intent_components(scene_intent) -> list:
    """Scene Intent -> components[].component（保持声明顺序）。

    components[].node / components[].scene 为契约 PLANNED（由 Feature Scene Template
    在构建期派生），本函数不读取、不派生它们。
    """
    document = intent_document(scene_intent, "scene_intent.intent_components")
    features = []
    for entry in document.get("components") or []:
        if isinstance(entry, dict):
            fid = str(entry.get("component") or "").strip()
            if fid:
                features.append(fid)
    return features


def intent_component_instances(scene_intent) -> list:
    """Scene Intent -> 组件实例计划声明列表（Phase 1.8.14；保持声明顺序）。

    只读投影：只返回**已声明** instance 的组件（`instance: null` / 缺失 = 未声明，不出现）；
    合法性判定（节点类型词表 / 字段形态）归 component_instance_resolver —— 本函数不校验、
    不猜测、不补默认值（非法形态原样交出去，由 resolver 报错）。

    返回 [{"component": <feature id>, "instance": <声明>}, ...]
    """
    document = intent_document(scene_intent, "scene_intent.intent_component_instances")
    declared = []
    for entry in document.get("components") or []:
        if not isinstance(entry, dict):
            continue
        instance = entry.get("instance")
        if instance is None:
            continue
        component = str(entry.get("component") or "").strip()
        declared.append({"component": component, "instance": instance})
    return declared


def intent_capabilities(scene_intent) -> dict:
    """Scene Intent -> capability metadata（Phase 1.8.10）：`{"required": [...]}`。

    统一读取入口：只收 Scene Intent（旧内部 dict / 原始 Blueprint → ValueError）。
    不读 Blueprint、不读 Feature Registry、不判断能力是否被支持；
    缺字段（旧 Intent）或空声明 → `{"required": []}`。
    """
    document = intent_document(scene_intent, "scene_intent.intent_capabilities")
    return {"required": _normalize_capabilities(document.get("capabilities"))}


def intent_from_blueprint(blueprint_raw, resource_nodes=None, capabilities=None,
                          features_dir=None) -> tuple:
    """原始 Blueprint（Scene / Entity Blueprint，scene_schema.yaml）-> (SceneIntent|None, errors)。

    仅「规整 + 投影」：不解析资源、不读 Asset Registry；resource_nodes / capabilities
    由调用方（可选）传入；features_dir 指定读取 Feature 能力声明的基准目录。
    给 CLI 入口（test_generator / check_scene_composition）与 compose 使用。
    """
    from template_loader import (FEATURES_DIR, derive_scene_blueprint,
                                 normalize_scene_blueprint)

    blueprint, errors = normalize_scene_blueprint(
        derive_scene_blueprint(blueprint_raw or {}), features_dir or FEATURES_DIR)
    if errors:
        return None, list(errors)
    blueprint["resource_nodes"] = list(resource_nodes or [])
    return SceneIntentBuilder().build(blueprint, blueprint["resource_nodes"], capabilities), []
