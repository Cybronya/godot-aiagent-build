# Workflow

标准：

```text
init
  ↓
scan
  ↓
new / changed / deleted
  ↓
review
  ↓
human confirmation
  ↓
apply
  ↓
check
```

快捷：

```text
sync = scan + review
```

不确定时进入 pending。
