#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON_CMD=${PYTHON_CMD:-python3}

printf '%s\n' '========================================'
printf '%s\n' '  会打岔的学术速递 - 环境初始化'
printf '%s\n' '========================================'

if ! "$PYTHON_CMD" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
    printf '%s\n' "[ERROR] 需要 Python 3.9+（当前命令: $PYTHON_CMD）。" >&2
    exit 1
fi

if [ ! -x "$ROOT/.venv/bin/python" ]; then
    printf '%s\n' '[1/4] 创建虚拟环境 .venv ...'
    "$PYTHON_CMD" -m venv "$ROOT/.venv"
else
    printf '%s\n' '[1/4] 虚拟环境已存在。'
fi

VENV_PYTHON="$ROOT/.venv/bin/python"
printf '%s\n' '[2/4] 安装依赖 ...'
"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install -r "$ROOT/requirements.txt"

printf '%s\n' '[3/4] 准备本地配置与数据目录 ...'
if [ ! -f "$ROOT/.env" ]; then
    cp "$ROOT/.env.example" "$ROOT/.env"
    printf '%s\n' '  已创建 .env，请按需填写 SMTP 配置。'
fi
mkdir -p "$ROOT/data" "$ROOT/archive"

printf '%s\n' '[4/4] 运行本地体检 ...'
if ! "$VENV_PYTHON" "$ROOT/scripts/project_doctor.py" --root "$ROOT" --target manual; then
    printf '%s\n' '[WARN] 体检发现阻断项，请按上方 NEXT 提示处理。'
fi

printf '%s\n' '初始化完成。接下来可让 agent 读取 AGENTS.md/config.md 并运行当天速递。'
