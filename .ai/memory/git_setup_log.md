# Git 环境记录

## 一、踩过的坑与解决

### 1. Freebuff 找不到 bash
- **现象**：终端命令报 `Bash is required but was not found`
- **解决**：设置环境变量 `CODEBUFF_GIT_BASH_PATH` 指向 `bash.exe`，重启 Freebuff 生效

### 2. Git 不在系统 PATH
- **现象**：CMD 中 `git` 不是内部或外部命令
- **原因**：Git 装在非默认路径 `F:\Program Files\Git\`
- **解决**：用户变量 `Path` 添加 `F:\Program Files\Git\cmd`，重开终端生效

### 3. GitHub 连接不稳定
- **现象**：`Failed to connect to github.com:443` / `Connection was reset`，时通时断
- **解决**：多重试；持续失败则配代理：
  ```bash
  git config --global http.https://github.com.proxy http://127.0.0.1:<代理端口>
  ```

### 4. 提交身份未配置
- **现象**：`fatal: Author identity unknown`
- **解决**：
  ```bash
  git config --global user.name "cybronya"
  git config --global user.email "wangxinloo@163.com"
  ```

## 二、凭证方案（永久免密）

- **方式**：Git Credential Manager（GCM）
- **启用**：`git config --global credential.helper manager`
- **状态**：✅ 凭证（username=cybronya）已存入 Windows 凭据管理器，push/pull 全自动免密
- **验证**：
  ```bash
  echo -e "protocol=https\nhost=github.com\n" | git credential fill
  ```
- **管理位置**：控制面板 → 用户账户 → 凭据管理器 → Windows 凭据 → `git:https://github.com`
- **安全提醒**：不要在对话中明文发送 token；GCM 浏览器授权全程无需手动创建 token

## 三、日常操作速查

```bash
# 日常提交推送（凭证已缓存，直接执行）
git add <文件>
git commit -m "提交说明"
git push

# 查看状态
git status
git log --oneline
```

## 四、仓库信息

| 项目 | 值 |
|------|-----|
| 远程地址 | https://github.com/Cybronya/godot-aiagent-build.git |
| 分支 | master（已跟踪 origin/master） |
| 首次提交 | 8fefc81 |
| 排除项 | .godot/ .freebuff/ __pycache__/ |
