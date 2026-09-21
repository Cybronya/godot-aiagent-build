# Skill Framework Validator

这是 Godot Agent Skill Framework 的按需机器验证器。

Validator 只检查，不自动修改 Framework 文件。第一阶段只在用户明确要求检查/验证时由 Agent 执行。

## 执行

```bash
python .ai/validator/validate.py
```

或：

```bash
python .ai/validator/validate.py --config-dir .ai/config
```

依赖：Python 3 + PyYAML（`pip install pyyaml`）。

## 检查范围

- Agent 入口与 Framework 版本
- Agent 配置路径
- Registry 注册项
- Registry 与 canonical SKILL.md 一致性
- Skill ID、目录名、必需 Metadata
- Category 与 Load Policy
- Required / Related Dependencies
- Dependency Category Direction
- Circular Required Dependencies
- Schema / Template 基础对齐
- Collaboration 中的重复 canonical metadata
- Framework 内部路径的 root-independent 约束

## 输出

- **PASS**：无错误或警告
- **WARNING**：无阻断错误，但有需要人工确认的问题
- **FAIL**：违反 Framework 契约

发现问题后由 Agent 决定如何修复，修复后再次运行 Validator。当前不接 Git hooks、GitHub Actions 或后台自动检查。
