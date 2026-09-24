# Session Context

记录当前AI会话。

## Completed

- 实现 2D 角色方向键移动并验证通过（Player.tscn + player_controller.gd + 输入映射 + 主场景配置）
- 沉淀为第一个可复用 Feature：Features/player_movement/，记录 AD-001
- 新增 Player2（WASD）：复用移动 Feature，脚本输入动作参数化（向后兼容），游戏级验证通过
- Framework 修改执行：feature-development.md 扩充（含适用范围判定）、framework-rules 增两条 principle、AD 唯一归宿声明、AI_ENTRY 陈旧章节删除；Validator PASS
- Health Feature（Build 分支）：组件节点 + 信号接口，AD-002 记录组合边界；双角色组合、移动回归、主场景启动全部验证通过
- 伤害交互（普通任务路径）：游戏侧触发器复用 Health 接口，零 Feature 改动；首次出现「已接受 AD 直接回答新架构问题」的情形，未新增 AD

## Findings

- GDScript lambda 对局部变量按值捕获：测试中的事件计数器必须用成员变量或绑定方法，不能用 lambda 自增局部变量
- SceneTree 测试中 instantiate() 后必须 await 一帧，_ready() 才会执行（导出属性初始化依赖 _ready 时的断言会误报）
- 游戏侧胶水（如伤害路由）在单消费者阶段不 Feature 化；出现多攻击者等复用需求时再提升（AD-002 的应用而非新决策）
- 集成/交互测试的断言值从 max_health 推导；修改角色生命值配置时需同步多个测试文件中的期望值（普通任务路径首次实战：胶水检查项触发且判定不提升）
- Git Bash 下运行 Godot 必须重定向 stdin（`< /dev/null`），否则挂起
- godot_mcp 编辑器插件导致无头导入退出时出现良性 ObjectDB 泄漏警告
- 原项目未配置主场景，已在 project.godot 补充 run/main_scene

## Pending

无
