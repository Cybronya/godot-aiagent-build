# Godot 测试用 devcontainer 基础镜像。
# Codespaces 的默认镜像是 Alpine，Godot 官方 Linux 二进制依赖 glibc，跑不起来，
# 所以这里显式用 Debian，让 setup-godot.sh 的 apt 分支可用。
FROM debian:bookworm-slim

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git unzip \
        python3 python3-venv python3-pip python3-yaml \
        sudo procps less \
    && rm -rf /var/lib/apt/lists/*

# devcontainer 约定的非 root 用户，带免密 sudo（setup-godot.sh 需要装系统库）
RUN useradd -m -s /bin/bash vscode \
    && echo 'vscode ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/vscode \
    && chmod 0440 /etc/sudoers.d/vscode

USER vscode
WORKDIR /workspaces
