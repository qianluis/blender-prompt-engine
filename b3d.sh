#!/usr/bin/env bash
# ============================================================
#  b3d 快捷入口 (macOS / Linux / Git Bash)
#
#  用法:
#    ./b3d.sh "一个金色的纳米颗粒，电影感灯光"
#    ./b3d.sh "水凝胶网络，4K" --out-name gel.png
# ============================================================
set -euo pipefail

PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---- Blender 路径：按你的实际情况修改 ----
BLENDER_EXE="${BLENDER_EXE:-/Applications/Blender.app/Contents/MacOS/Blender}"

if [ ! -x "$BLENDER_EXE" ]; then
    if command -v blender >/dev/null 2>&1; then
        BLENDER_EXE="$(command -v blender)"
    else
        echo "[错误] 找不到 Blender。请设置环境变量 BLENDER_EXE。" >&2
        exit 1
    fi
fi

exec "$BLENDER_EXE" --background --python "$PKG_DIR/b3d/cli.py" -- "$@"
