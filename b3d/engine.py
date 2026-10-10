# -*- coding: utf-8 -*-
"""
b3d.engine - 对外唯一入口

用户只需要一句话，不需要理解 JSON，也不需要写 Blender 脚本：
    from b3d import make
    make("一个金色的纳米颗粒，暗色背景，电影感灯光")
"""
import os
import json
import time
from . import compat, parser, scene as bscene, renderer
from typing import Dict, Any, Optional

try:
    import bpy
except ImportError:
    # 允许在系统 Python 下导入本模块做纯解析（CLI --explain）
    bpy = None


def spec_from_prompt(prompt: str) -> Dict[str, Any]:
    """指令 → SceneSpec（纯 Python，不需要 Blender）"""
    return parser.parse(prompt)


def explain(prompt: str) -> str:
    """看看引擎是怎么理解这句话的，用于确认/调试"""
    return parser.explain(parser.parse(prompt))


def _resolve_quality(spec):
    q = parser.quality_to_params(spec.get("quality", "标准"))
    return q


def make(prompt: str,
         output: Optional[str] = None,
         out_dir: Optional[str] = None,
         quality: Optional[str] = None,
         seed: int = 42,
         ground: bool = True,
         dof: Optional[float] = None,
         keep_frames: bool = False,
         ffmpeg_dir: Optional[str] = None,
         verbose: bool = True) -> Dict[str, Any]:
    """
    一句话出图 / 出片。

    参数
    ----
    prompt    : 中文或英文自然语言指令
    output    : 输出文件名（不含目录）。默认按时间戳生成
    out_dir   : 输出目录，默认 D:/_blender_lab/outputs
    quality   : 覆盖质量档位（预览/草稿/标准/高清/2k/4k/出版级）
    seed      : 随机种子，保证结果可复现
    ground    : 是否添加地面板（接触阴影）
    dof       : 景深光圈值，如 2.8 —— 数值越小背景越虚
    """
    compat.require((3, 0, 0))
    if bpy is None:
        raise RuntimeError(
            "make() 需要 Blender 环境。请通过 Blender 调用：\n"
            "  blender --background --python b3d/cli.py -- \"你的指令\"\n"
            "若只想查看指令解析结果，用 spec_from_prompt() 或 --explain。"
        )
    t_start = time.time()

    spec = parser.parse(prompt)
    if quality:
        spec["quality"] = quality

    q = _resolve_quality(spec)
    res = q["res"]
    samples = q["samples"]

    out_dir = out_dir or r"D:\_blender_lab\outputs"
    os.makedirs(out_dir, exist_ok=True)

    stamp = time.strftime("%Y%m%d_%H%M%S")
    is_video = bool(spec.get("animation"))
    if output:
        if not output.lower().endswith((".mp4", ".mov")) and is_video:
            output += ".mp4"
        elif not output.lower().endswith((".png", ".jpg")) and not is_video:
            output += ".png"
    else:
        output = ("anim_%s.mp4" if is_video else "img_%s.png") % stamp
    out_path = os.path.join(out_dir, output)

    if verbose:
        print("=" * 62)
        print("[b3d] 指令: %s" % prompt)
        print(parser.explain(spec))
        print("[b3d] 输出: %s" % out_path)
        print("=" * 62)

    # 1) GPU
    gpu = renderer.setup_gpu()

    # 2) 装配场景
    built = bscene.assemble(spec, seed=seed, ground=ground, dof=dof)

    # 3) 渲染
    ffdir = ffmpeg_dir or renderer.DEFAULT_FFMPEG_DIR
    if is_video:
        fps = int(spec.get("fps", 24))
        dur = float(spec.get("duration_sec", 6.0))
        frame_end = max(int(dur * fps), 2)
        work = os.path.join(out_dir, "_frames_%s" % stamp)
        result = renderer.render_animation(
            out_path, frame_start=1, frame_end=frame_end, fps=fps,
            res=res, samples=samples, denoise=q.get("denoise", True),
            codec="h264_nvenc", work_dir=work, ffmpeg_dir=ffdir,
            keep_frames=keep_frames)
        media = {"kind": "video", "path": out_path,
                 "frames": result["sequence"]["frames"],
                 "fps": fps, "duration_sec": dur}
    else:
        transparent = spec.get("background") == "transparent"
        info = renderer.render_still(
            out_path, res=res, samples=samples,
            denoise=q.get("denoise", True), transparent=transparent,
            ffmpeg_dir=ffdir)
        if not info["ok"]:
            raise RuntimeError("渲染失败，未产出有效文件: %s" % out_path)
        media = {"kind": "image", "path": out_path, "bytes": info["bytes"]}

    total = time.time() - t_start
    media["seconds"] = round(total, 2)
    media["spec"] = spec
    media["gpu"] = gpu

    if verbose:
        print("[b3d] DONE total=%.1fs -> %s" % (total, out_path))

    # 4) 写 manifest（可追溯 / 可复现）
    try:
        renderer.write_manifest(
            os.path.join(out_dir, "_manifest_%s.json" % stamp),
            {"prompt": prompt, "output": out_path, "spec": spec,
             "gpu": gpu, "seconds": media["seconds"]})
    except Exception as e:
        print("[b3d] manifest 写入跳过: %s" % e)

    return media


def make_batch(prompts, out_dir=None, **kw):
    """批量出图"""
    results = []
    for i, p in enumerate(prompts):
        print("\n>>> [%d/%d] %s" % (i + 1, len(prompts), p))
        try:
            r = make(p, out_dir=out_dir, **kw)
            results.append({"ok": True, "prompt": p, "result": r})
        except Exception as e:
            print("[b3d] 失败: %s" % e)
            results.append({"ok": False, "prompt": p, "error": str(e)})
    return results
