# Registry Rules v2

## 作用

Registry负责Skill发现和管理。

它不是Skill知识库。

Skill实际内容存放在：

.ai/skills/

------------------------------------------------------------------------

# 修改权限

## Agent可以：

-   读取Registry
-   检查Registry完整性
-   提出新增Skill建议

## Agent不能：

-   自动新增Skill
-   自动删除Skill
-   自动修改Registry

除非用户确认。

------------------------------------------------------------------------

# 新Skill注册流程

1.  创建：

.ai/skills/{skill-id}/

2.  创建：

SKILL.md

3.  定义：

-   category
-   dependencies
-   ownership
-   trigger_conditions

4.  更新：

skill_registry.yaml

5.  检查：

-   id唯一
-   path正确
-   dependency存在

------------------------------------------------------------------------

# Skill关系规则

同级Skill默认独立。

不要通过priority解决冲突。

通过：

-   dependencies
-   ownership

定义关系。

------------------------------------------------------------------------

# 数据职责

Registry:

负责发现。

SKILL.md:

负责能力定义。

references:

负责知识补充。

tools:

负责执行。
