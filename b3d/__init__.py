# -*- coding: utf-8 -*-
"""
b3d - 一句话 3D 渲染引擎

把自然语言指令变成电影级 3D 图像 / 短视频。
面向科研人员：不要求你会 Blender，但你得能说清楚要什么。

用法（在 Blender 里）：
    import b3d
    b3d.make("一个金色的纳米颗粒，暗色背景，电影感灯光，高清")

命令行：
    blender --background --python cli.py -- "你的指令"
"""

__version__ = "0.1.0"
__author__ = "Luis"

try:
    import bpy  # noqa: F401
    _HAS_BPY = True
except ImportError:
    _HAS_BPY = False

# 纯 Python 层不依赖 bpy，任何环境下都能导入。
# 必须放在最前面：如果先导入 engine（顶层 import bpy），
# 系统 Python 会在包初始化阶段就炸掉，连降级分支都跑不到。
from . import parser  # noqa: F401,E402
from .engine import spec_from_prompt, explain  # noqa: F401,E402

__all__ = ["spec_from_prompt", "explain", "parser", "__version__"]

if _HAS_BPY:
    # 只有在 Blender 里才导出真正的渲染入口
    from .engine import make, make_batch  # noqa: F401,E402
    __all__ += ["make", "make_batch"]
