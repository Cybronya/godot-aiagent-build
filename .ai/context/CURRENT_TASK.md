# 当前任务

## 目标

调整 Player 最大生命值为 10（Player2 保持 8），按修订后 Framework 的普通任务路径执行。

## 当前状态

已完成：场景覆写 + 两处测试期望值同步；首次验证发现残留旧期望值（5→3），修复后重验通过。胶水再评估检查项首次实际触发（attack_trigger 条件未熟，不提升）。

## 修改文件

- `Features/player_movement/Player.tscn`：Health 实例覆写 max_health=10
- `Tests/test_health_integration.gd`、`Tests/test_damage_interaction.gd`：期望值同步

## 下一步

无阻塞事项。
