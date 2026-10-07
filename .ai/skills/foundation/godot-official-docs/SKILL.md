# SKILL: godot-official-docs

```text
Skill:    godot-official-docs
Version:  1.1
Category: foundation
Purpose:  Godot 4.7 official reference（Official Reference Skill）
Source:   .ai/skills/godot-official-docs_sources/4.7/  （只读 Source of Truth）
```

## Use this Skill when

- 查询 Godot 官方 API（Class / Method / Property / Signal / Enum / Constant）
- 查询 Godot 官方行为、概念说明、官方教程
- 查询版本差异与迁移（4.x upgrade / breaking change）

## Do NOT use this Skill for

- 项目架构（→ godot-project-architecture）
- 项目编码规范（→ godot-development-standard、godot-gdscript）
- Feature implementation / 项目具体实现（→ 对应 Domain / systems Skill）
- 项目目录设计
- 社区/项目介绍类内容：Source 中的 `about/`、`community/` 明确**不纳入本 Skill 导航范围**，路由未命中时不要因此判定 FAIL，直接按文档缺失处理并说明

职责边界：本 Skill 回答「**Godot 官方是什么**」；项目里「**应该怎么用**」由对应 Domain Skill 负责。

# Skill Identity

## Skill ID

godot-official-docs

## Skill Name

Godot Official Docs

## Version

1.1

## Category

foundation

# Registry Metadata

本章节是本 Skill 的 Canonical Metadata。Registry 仅索引本 Skill，不重复维护这些字段。

## Load Policy

conditional

> 不设为 required：文档规模大，仅在任务匹配 Trigger 时加载，避免污染所有任务的上下文。

## Dependencies

### Required

[]

### Related

- godot-gdscript
- godot-development-standard
- godot-character-system

## Ownership

- official_docs_source_of_truth（只读 Source 的引用与追溯）
- docs_navigation_layer（routing / api index）
- docs_update_tool（tools/update_docs.py）

# Description

Godot Official Documentation / Reference Knowledge Skill。

本 Skill 是**导航层**，不是文档镜像：它把用户问题路由到只读 Source（`.ai/skills/godot-official-docs_sources/4.7/`）中的具体官方文档文件。references/ 保存索引与路由：Hand-authored 层（routing / api/INDEX / categories）保持极小；Generated 层（classes / tutorials-index / keywords-suggested / members-index 全量数据表）约 2.7 MB，由 update_docs.py 重建。不复制文档正文。

```text
godot-official-docs（官方定义）
        ↓
CharacterBody3D 官方 API
        ↓
godot-character-system（项目实现）
```

# Purpose

Agent 的训练记忆对 Godot API 可能过时或不准确。本 Skill 保证所有 Godot 官方事实都有本地 Source 依据，并以最低阅读成本（少量导航文件 → 一个 Source 文件）完成查询。

# Responsibility

## 负责

- 维护官方文档导航层（routing / api index / metadata）
- 把用户问题路由到只读 Source 中的具体官方文档
- 通过 update tool 保持导航层与 Source 同步
- 作为其他 Godot Skill 的官方事实来源

## 不负责

- 不定义项目开发规范（→ godot-development-standard）
- 不管理 GDScript 代码风格（→ godot-gdscript）
- 不决定项目架构或具体实现（→ 对应 Domain / systems Skill）
- 不验证项目结构或运行时行为
- 不修改只读 Source（`.ai/skills/godot-official-docs_sources/`）
- 不复制文档正文进本 Skill

# Trigger Conditions

- 用户询问某个 Godot API 的行为、参数、返回值、signal
- 用户询问引擎特性、概念或版本差异
- 需要确认 4.x 迁移 / 破坏性变更
- 用户明确要求「查官方文档」

# Input Contract

需要输入：问题主题（或涉及的类 / 方法 / 特性）+ 目标版本。

版本判断：用户已明确 → 用之；否则查项目 `project.godot`；仍无法判断 → 请求确认，或明确声明使用 Godot 4.7 reference。禁止混用其他版本文档。

# Workflow

## DEFAULT QUERY FLOW

```text
1. Read SKILL.md（本文件）
2. Read references/4.7/INDEX.md
3. Check routing/intents.md → keywords.md → topics.md
4. API 问题：查 api/INDEX.md（→ api/categories.md / api/classes.md）
5. Resolve exact Source path（前缀：../../../../godot-official-docs_sources/4.7/）
6. Read only the required Source file / section
7. Answer using official documentation，注明引用路径
```

**Read-Source Rule：不要先读整个 Source tree。** 先导航定位，再读取定位到的单个文件或片段。

## 最短使用示例

```text
Question: "Godot 4.7 CharacterBody3D 怎么移动？"

Flow:
SKILL.md
→ references/4.7/INDEX.md
→ routing/intents.md（character movement）
→ api/classes.md / api/INDEX.md
→ class_characterbody3d.rst
→ read move_and_slide section
→ answer
```

## 继承 API 示例

```text
Question: "Godot 4.7 Button 的 pressed signal 是什么？"

Flow:
routing/keywords.md
→ Button
→ BaseButton（pressed 的 canonical 定义在父类）
→ class_basebutton.rst
→ pressed signal
```

规则：目标类文档中找不到某成员时，按 `api/INDEX.md` 的 Inheritance Navigation 上溯父类，禁止回答「不存在」。

# Output Contract

- 答案或结论
- 引用的本地 Source 路径（`../../../../godot-official-docs_sources/4.7/<path>`）
- 文档缺失时明确说明，并建议运行 `tools/update_docs.py`

# Validation

## Validation Method

- 路由命中：问题可经 routing / api index 定位到具体 Source 文件
- 引用存在：引用的文件在 Source 中真实存在
- 工具校验：`update_docs.py --from-sources` 验证 categories / INDEX 中类名与 routing 路径

## Success Criteria

- 回答基于本地 Source 而非训练记忆
- 引用路径可打开且内容相关
- 查询成本：少量导航文件 → 一个 Source 文件（禁止全库搜索）

## Status Update

- PASS / WARNING（Source 缺章节但已说明）/ FAIL（引用了不存在的路径）

# References

目录：references/（导航层，全部路径基准为 `references/4.7/`）

```text
references/4.7/
├── INDEX.md                  Agent Navigation Map
├── routing/intents.md        意图 → 文档位置
├── routing/keywords.md       自然语言 → 官方 API
├── routing/topics.md         主题 → Source 路径
├── api/INDEX.md              常用类 + 继承链导航规则（Hand-authored）
├── api/categories.md         按领域分类（Hand-authored）
├── api/classes.md            全量类清单（Generated，勿手改）
├── api/tutorials-index.md    教程/引擎细节文件级索引，含标题（Generated，勿手改）
├── api/keywords-suggested.md 全量类名关键词表（Generated，勿手改）
├── api/members-index.md      成员 → 定义类反查表（Generated，勿手改）
└── metadata/source-info.md   Source 元数据（version/branch/commit）
```

文档正文不在本目录，一律从只读 Source 读取：

```text
.ai/skills/godot-official-docs_sources/4.7/
├── classes/           Class Reference（1078 类）
├── getting_started/   入门
├── tutorials/         教程（含 tutorials/migrating/ 版本迁移）
└── engine_details/    引擎细节
```

# Tool Usage

```bash
# 离线（默认）：验证 Source 完整性 + 重新生成 api/classes.md + 校验引用，不删除任何文件
python .ai/skills/foundation/godot-official-docs/tools/update_docs.py --from-sources --version 4.7

# 联网（仅显式调用，不隐式触发）：下载新版本 Source 后构建
python .ai/skills/foundation/godot-official-docs/tools/update_docs.py --download <branch>
```

文件分两类：**Hand-authored**（INDEX / routing / api/INDEX / categories / metadata，工具绝不覆盖）与 **Generated**（api/classes.md，工具可重建）。

# Failure Handling

## Source 缺失

提示运行 update tool；临时可用网络查询替代，但须声明未经本地 Source 验证。

## 路由未命中

三层 routing 均未命中 = FAIL，请求用户补充信息。

## 成员在类文档中找不到

按 api/INDEX.md 继承链上溯父类，禁止回答「不存在」。

# Permission Model

允许修改：本 Skill 目录内的导航文件与 tools/。
禁止修改：`.ai/skills/godot-official-docs_sources/`（只读 Source of Truth）。
需要确认：首次下载新版本 Source、删除旧版本文档目录、修改 Registry。

# Skill Completion Report

完成后输出：

``` text
Skill:
任务:
修改内容:
验证结果:
状态:
后续建议:
```

# Notes

- Source Metadata：godotengine/godot-docs @ 4.7，commit unknown（ZIP 下载，不伪造），详见 `references/4.7/metadata/source-info.md`
- 本文件遵循 SKILL_TEMPLATE v2.2 与 skill-schema.yaml
- 版本隔离：仅 4.7；新版本用独立 `references/<version>/`，不覆盖旧版本
- 官方文档只经本 Skill 的 references 导航访问，禁止复制到 `Features/`、`.ai/memory/`、`.ai/context/`
