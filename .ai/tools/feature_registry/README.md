# Feature Registry Tool

Feature Metadata Pipeline：`feature.yaml`（Source of Truth）→ 索引生成 → 查询 → 验证。

```text
Features/*/feature.yaml          Source of Truth（手写，随 Feature 交付）
        ↓
build_feature_index.py           Feature Index Generator（自动生成）
        ↓
.ai/context/feature_index.json   Generated Data（缓存，不是 Source of Truth）
        ↓
discover_feature.py              Feature Discovery（只查询，不生成代码）
        ↓
validator/check_feature_metadata.py   校验 metadata 契约与索引同步
```

架构约束：不建 Global Feature Manager；Validator 只检查不改文件；索引永远是缓存。

## 工具

| 文件 | 职责 |
|---|---|
| `build_feature_index.py` | 扫描 `Features/*/feature.yaml` → 生成 `.ai/context/feature_index.json` |
| `discover_feature.py` | 按需求文本查询索引，输出推荐 Feature（无 LLM） |
| `tests/` | 本目录工具与 Validator 集成的回归测试 |
| `../validator/check_feature_metadata.py` | Feature Metadata Validator（独立运行或被 validate.py 集成） |

## 用法

```bash
# 1. (重新)生成索引——metadata 变更后必须执行
python .ai/tools/feature_registry/build_feature_index.py

# 2. 按需求查询
python .ai/tools/feature_registry/discover_feature.py "enemy can receive damage"
python .ai/tools/feature_registry/discover_feature.py --list

# 3. 独立校验
python .ai/tools/validator/check_feature_metadata.py

# 4. Framework 全量校验（已集成 Feature Metadata + Index Validation）
python .ai/tools/validator/validate.py
```

## 索引格式（feature_index.json）

```json
{
  "registry_version": 1,
  "generated_at": "<ISO8601>",
  "features": [
    {
      "id": "health",
      "version": "1",
      "category": "component",
      "provides": ["health_state", "damage_receiver", "heal_receiver", "death_event"],
      "requires": [],
      "interfaces": ["take_damage", "heal", "get_current_health", "is_dead", "health_changed", "died", "max_health"],
      "signals": ["health_changed", "died"],
      "validation": {"test_path": "<项目根>/Features/health/test_health.gd"}
    }
  ]
}
```

## Discovery 匹配逻辑（无 LLM）

```text
需求文本 -> 关键词提取 -> feature metadata 搜索 -> 评分 -> 排序
score = provides_match * 5 + interface_match * 3 + category_match * 1
```

工具内置同义词表（SYNONYMS）与停用词表（STOPWORDS）。

## Validator 检查项（check_feature_metadata.py）

1. **metadata 存在**：`Features/<dir>/feature.yaml` 缺失 → Error
2. **id 一致性**：`id != 目录名` → Error（如 folder=health metadata=HealthSystem）
3. **必填字段**：id/version/category/provides/requires/interfaces/validation → 缺少 Error
4. **Test 路径**：validation.test_path/self_test 指向的文件不存在 → Error
5. **Index 同步**：与 feature_index.json 比对 id/version → 不同步时 Error
   （提示运行 build_feature_index.py）

检查已集成进 Validator 主入口（执行顺序：Project Structure → Skill Registry →
Feature Metadata → Feature Index）。

## 维护约定

- **新增/修改 Feature 的 feature.yaml 后必须重跑 build_feature_index.py**，
  否则 Validator 报 "Feature index outdated"。
- 新 Feature 进入项目时不需手工登记索引——由索引生成器自动收录。
- feature.yaml 格式规范见 `Features/FEATURE_SCHEMA.md`。
