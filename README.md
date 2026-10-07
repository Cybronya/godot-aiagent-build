# godot-aiagent-build

Godot AI Agent Development Framework —— 探索 AI Agent 如何理解、扩展、验证 Godot 项目的实验框架。

> 本项目不是一个普通的 Godot 游戏。核心目标：让 Agent 具备类似专业 Godot 开发者的能力——理解已有架构、复用已有 Feature、安全修改、自动验证。

## Agent 入口

**Agent 必须从以下入口进入，不得绕过：**

1. `AI_ENTRY.md` —— 机器入口协议（Framework 加载链、Skill 发现规则）
2. `AGENT_ONBOARDING.md` —— 上手指南（项目定位、核心概念、工作规则）
3. `.ai/config/agent.yaml` —— Framework 唯一机器配置入口

## 目录结构

| 目录 | 职责 |
|---|---|
| `.ai/config/` | Framework contract、Schema、Skill Registry |
| `.ai/skills/` | Agent 专业能力（含 godot-official-docs 官方文档导航层） |
| `.ai/tools/` | 基础设施工具（validator、run_tests、art-assets scanner） |
| `.ai/context/` | 当前任务 / 工程状态 |
| `.ai/memory/` | 长期项目知识（决策记录、实验档案） |
| `Features/` | 可复用游戏功能模块（组件 + 场景 + README + 测试） |
| `Scenes/` | 场景组合实验 |
| `Tests/` | 场景级集成测试 |
| `addons/godot_mcp/` | Godot 编辑器 MCP 插件——Agent 与引擎交互的工具通道（第三方组件，按第三方依赖对待，不在本项目 Feature/Skill 体系内演化） |

## 常用命令

```bash
# 统一测试入口（Features 组件测试 + Tests 集成测试）
python .ai/tools/run_tests.py

# Framework Validator（仅按需执行：检查 Registry/Skill 结构完整性）
python .ai/tools/validator/validate.py

# 官方文档导航层维护（离线重建 Generated 索引并校验引用）
python .ai/skills/foundation/godot-official-docs/tools/update_docs.py --from-sources --version 4.7
```

## 更多说明

- Art Asset 管理 skill 的使用说明：`.ai/tools/godot-art-assets/README.md`
- 项目当前进度与实验记录：`.ai/context/WORK_STATE.md`、`.ai/memory/HISTORY.md`
