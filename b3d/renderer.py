# -*- coding: utf-8 -*-
"""
b3d.renderer - 渲染输出层

职责：把装配好的场景变成 PNG / MP4 文件，并给出明确的耗时与产物校验。
关键：Windows 下必须把 ffmpeg 注入 PATH（否则 Blender 合成osal -->
又失败（WinError 2）。这是本机实测踩过的坑。
"""
import os
import sys
import time
import json
import subprocess

try:
    import bpy
except ImportError:
    bpy = None

from . import compat


def inject_ffmpeg(ffmpeg_dir):
    """把 ffmpeg 目录放进 PATH（进程内注入，避免 WinError 2）"""
    if not ffmpeg_dir or not os.path.isdir(ffmpeg_dir):
        return False
    if ffmpeg_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
    return True


DEFAULT_FFMPEG_DIR = r"C:\Users\qqp66\AppData\Local\Microsoft\WinGet\Packages" \
                     r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe" \
                     r"\ffmpeg-9.0.2-full_build\bin"


def setup_gpu(disable_cpu=True):
    """调用 compat.enable_gpu 并打印实际使用设备"""
    info = compat.enable_gpu()
    print("[render] GPU backend=%s gpu=%s devices=%s"
          % (info["backend"], info["gpu"], info["devices"]))
    return info


def render_still(filepath, res=(1920, 1080), samples=256, denoise=True,
                 transparent=False, exposure=0.0, ffmpeg_dir=DEFAULT_FFMPEG_DIR):
    """渲染单帧 PNG"""
    inject_ffmpeg(ffmpeg_dir)
    scene = bpy.context.scene
    compat.set_render_defaults(scene, res=res, samples=samples,
                               denoise=denoise, transparent=transparent,
                               exposure=exposure)
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_depth = "8"
    if transparent:
        scene.render.image_settings.color_mode = "RGBA"
    else:
        scene.render.image_settings.color_mode = "RGB"

    scene.render.filepath = filepath
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    # 渲染前自检：GPU 没生效就明确报警，而不是默默用 CPU 跑 5 倍时间
    gpu_ok, gpu_msg = compat.assert_gpu_active(scene)
    if not gpu_ok:
        print("[render][警告] 未启用 GPU 渲染: %s" % gpu_msg)

    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    dt = time.time() - t0

    ok = os.path.exists(filepath) and os.path.getsize(filepath) > 1024
    size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
    print("[render] STILL done sec=%.1f path=%s ok=%s bytes=%d" % (dt, filepath, ok, size))
    return {"path": filepath, "seconds": round(dt, 2), "ok": ok, "bytes": size}


def render_sequence(output_dir, frame_start=1, frame_end=48, fps=24,
                    res=(1920, 1080), samples=192, denoise=True,
                    exposure=0.0, file_format="PNG", ffmpeg_dir=DEFAULT_FFMPEG_DIR):
    """渲染序列帧（动画）"""
    inject_ffmpeg(ffmpeg_dir)
    scene = bpy.context.scene
    compat.set_render_defaults(scene, res=res, samples=samples,
                               denoise=denoise, exposure=exposure)
    scene.frame_start = frame_start
    scene.frame_end = frame_end
    scene.frame_step = 1
    scene.render.fps = fps
    scene.render.fps_base = 1.0
    scene.render.image_settings.file_format = file_format

    os.makedirs(output_dir, exist_ok=True)
    scene.render.filepath = os.path.join(output_dir, "frame_")

    t0 = time.time()
    bpy.ops.render.render(animation=True, write_still=False)
    dt = time.time() - t0

    frames = sorted([f for f in os.listdir(output_dir)
                     if f.startswith("frame_") and f.lower().endswith(".png")])
    print("[render] SEQ done sec=%.1f frames=%d dir=%s" % (dt, len(frames), output_dir))
    return {"dir": output_dir, "frames": len(frames), "seconds": round(dt, 2), "fps": fps}


def resolve_ffmpeg(ffmpeg_exe="ffmpeg"):
    """
    解析出真正可执行的 ffmpeg。

    Windows 坑：WinGet 在 PATH 里放的是 %LOCALAPPDATA%\\Microsoft\\WinGet\\Links\\ffmpeg.EXE，
    那是个符号链接/转发桩，Python subprocess 直接调用会报
    `[WinError 193] %1 不是有效的 Win32 应用程序`。
    必须先探测一次，失败则回落到真实安装目录里的 exe。
    """
    try:
        r = subprocess.run([ffmpeg_exe, "-version"], capture_output=True,
                           text=True, timeout=15)
        if r.returncode == 0:
            return ffmpeg_exe
    except Exception:
        pass

    # 回落：默认安装目录
    for cand in (os.path.join(DEFAULT_FFMPEG_DIR, "ffmpeg.exe"),
                 os.path.join(DEFAULT_FFMPEG_DIR, "ffmpeg")):
        if os.path.exists(cand):
            try:
                r = subprocess.run([cand, "-version"], capture_output=True,
                                   text=True, timeout=15)
                if r.returncode == 0:
                    return cand
            except Exception:
                continue
    return None


_NVENC_CACHE = {"checked": False, "ok": False, "reason": ""}


def probe_nvenc(ffmpeg_exe="ffmpeg"):
    """
    预检 NVENC 是否真的可用（结果缓存，避免每条指令都试一遍）。

    失败根因常见于版本门槛：ffmpeg 9.x 要求 NVENC API 13.1 / 驱动 ≥ 610，
    本机驱动 592.27 只提供 API 13.0，于是 encoder 根本打不开，
    只能回退 libx264。与其每次都试错，不如先查清楚。
    """
    if _NVENC_CACHE["checked"]:
        return _NVENC_CACHE["ok"], _NVENC_CACHE["reason"]

    _NVENC_CACHE["checked"] = True
    ff = resolve_ffmpeg(ffmpeg_exe)
    if ff is None:
        _NVENC_CACHE.update(ok=False, reason="找不到 ffmpeg")
        return False, _NVENC_CACHE["reason"]

    # 用极短的黑场源试编码，成本 <1 秒
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", "color=c=black:s=320x240:d=0.1",
           "-frames:v", "1", "-c:v", "h264_nvenc",
           "-pix_fmt", "yuv420p", "-f", "null", "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
        if r.returncode == 0:
            _NVENC_CACHE.update(ok=True, reason="NVENC 可用")
            return True, "NVENC 可用"
        err = (r.stderr or "").strip().replace("\n", " ")[:200]
        _NVENC_CACHE.update(ok=False, reason=err or "未知错误")
        return False, err
    except Exception as e:
        _NVENC_CACHE.update(ok=False, reason=str(e))
        return False, str(e)


def encode_video(frame_dir, output_path, fps=24, codec="h264_nvenc",
                 preset="p4", crf=18, audio=None, pattern="frame_%04d.png",
                 ffmpeg_exe="ffmpeg"):
    """
    序列帧 → MP4。优先 NVENC 硬编（本机 RTX 3070 Ti 支持），失败自动回退 libx264。
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    frames = [f for f in os.listdir(frame_dir) if f.lower().endswith(".png")]
    if not frames:
        raise RuntimeError("没有找到序列帧: %s" % frame_dir)

    # 探测起始编号，避免 %04d 对不上
    import re
    nums = [int(m.group(1)) for f in frames
            for m in [re.search(r"(\d+)", f)] if m]
    start = min(nums) if nums else 1

    inp = os.path.join(frame_dir, pattern)
    if start != 1 and "%04d" in pattern:
        cmd_prefix = ["-start_number", str(start)]

    def _build(exe, c):
        base = [exe, "-y", "-framerate", str(fps)]
        base += ["-start_number", str(start)]
        base += ["-i", inp]
        if audio:
            base += ["-i", audio, "-shortest"]
        if c == "h264_nvenc":
            base += ["-c:v", "h264_nvenc", "-preset", preset,
                     "-cq", str(crf), "-pix_fmt", "yuv420p"]
        else:
            base += ["-c:v", "libx264", "-preset", "medium",
                     "-crf", str(crf), "-pix_fmt", "yuv420p"]
        base += ["-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2"]
        if audio:
            base += ["-c:a", "aac", "-b:a", "192k"]
        base += [output_path]
        return base

    # 关键：PATH 里的 ffmpeg 可能是 WinGet 符号链接桩，直接调用会 WinError 193。
    # 必须在真正编码前解析出可用的可执行文件。
    real_exe = resolve_ffmpeg(ffmpeg_exe)
    if real_exe is None:
        raise RuntimeError(
            "找不到可用的 ffmpeg。请安装（winget install Gyan.FFmpeg）"
            "或用 --ffmpeg-dir 指定目录。"
        )

    # 先探能力，再决定用哪个编码器。
    # 避免 NVENC 明明不可用还每次都跑一遍失败流程（每条视频浪费数十秒）。
    if codec == "h264_nvenc":
        ok, reason = probe_nvenc(real_exe)
        if ok:
            encoders_to_try = ["h264_nvenc"]
        else:
            print("[ffmpeg] NVENC 不可用，直接用软件编码: %s" % reason)
            encoders_to_try = ["libx264"]
    else:
        encoders_to_try = [codec]

    last_err = ""
    for encoder_name in encoders_to_try:
        try:
            cmd = _build(real_exe, encoder_name)
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
            if r.returncode == 0 and os.path.exists(output_path) \
               and os.path.getsize(output_path) > 1024:
                print("[ffmpeg] OK encoder=%s size=%d bytes"
                      % (encoder_name, os.path.getsize(output_path)))
                return {"path": output_path, "encoder": encoder_name,
                        "bytes": os.path.getsize(output_path)}
            last_err = (r.stderr or "")[-500:]
        except Exception as e:
            last_err = str(e)
        print("[ffmpeg] %s 失败，回退软件编码" % encoder_name)

    # 兜底：硬编失败再试一次软编，保证一定能出片
    if "libx264" not in encoders_to_try:
        try:
            cmd = _build(real_exe, "libx264")
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
            if r.returncode == 0 and os.path.exists(output_path) \
               and os.path.getsize(output_path) > 1024:
                print("[ffmpeg] 兜底 OK encoder=libx264 size=%d"
                      % os.path.getsize(output_path))
                return {"path": output_path, "encoder": "libx264",
                        "bytes": os.path.getsize(output_path)}
            last_err = (r.stderr or "")[-500:]
        except Exception as e:
            last_err = str(e)
        print("[ffmpeg] %s 失败" % encoder_name)

    raise RuntimeError("视频编码全部失败: %s" % last_err)


def render_animation(output_path, frame_start=1, frame_end=48, fps=24,
                     res=(1920, 1080), samples=192, denoise=True,
                     exposure=0.0, codec="h264_nvenc", work_dir=None,
                     ffmpeg_dir=DEFAULT_FFMPEG_DIR, keep_frames=False):
    """一站式：渲染序列帧 + 编码成 MP4"""
    work_dir = work_dir or os.path.join(os.path.dirname(output_path), "_frames")
    seq = render_sequence(work_dir, frame_start, frame_end, fps,
                          res, samples, denoise, exposure,
                          ffmpeg_dir=ffmpeg_dir)
    real_exe = resolve_ffmpeg(os.path.join(ffmpeg_dir, "ffmpeg.exe")
                             if os.path.isdir(ffmpeg_dir) else "ffmpeg")
    vid = encode_video(work_dir, output_path, fps=fps, codec=codec,
                       ffmpeg_exe=real_exe or "ffmpeg")
    if not keep_frames:
        import shutil
        try:
            shutil.rmtree(work_dir)
        except Exception:
            pass
    return {"video": vid, "sequence": seq}


def write_manifest(path, payload):
    """写出渲染元数据，便于追溯参数（科研可复现性）"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = dict(payload)
    payload["blender_version"] = compat.bl_version_str()
    payload["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path
