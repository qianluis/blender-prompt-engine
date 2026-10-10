#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
b3d 环境自检

不需要打开 Blender，直接用系统 Python 跑：
    python check_env.py

会检查：
  1. 本机 Blender 版本是否达标
  2. GPU 渲染能否启用（最关键，静默退化会让渲染慢 6 倍）
  3. ffmpeg 是否可用
  4. 中文指令解析是否正常

任何一项不通过都会给出修复建议。
"""
import os
import sys
import shutil
import subprocess
import platform

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

OK = "[OK]  "
BAD = "[X]   "
WARN = "[!]   "

# 常见 Blender 安装位置
CANDIDATE_PATHS = [
    r"D:\_blender_lab\blender\blender-4.5.12-windows-x64\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 2.83\blender.exe",
    "/Applications/Blender.app/Contents/MacOS/Blender",
    "/usr/bin/blender",
    "/snap/bin/blender",
]


def find_blender():
    """找 Blender：环境变量 → PATH → 常见路径"""
    env = os.environ.get("BLENDER_EXE")
    if env and os.path.exists(env):
        return env, "环境变量 BLENDER_EXE"
    which = shutil.which("blender")
    if which:
        return which, "PATH"
    for p in CANDIDATE_PATHS:
        if os.path.exists(p):
            return p, "常见安装路径"
    return None, None


def run_blender_expr(exe, code, timeout=180):
    """在 Blender 后台执行一段 Python，返回 (stdout+stderr, returncode)"""
    cmd = [exe, "--background", "--factory-startup", "--python-expr", code]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, errors="ignore")
        return (r.stdout or "") + (r.stderr or ""), r.returncode
    except subprocess.TimeoutExpired:
        return "TIMEOUT", -1
    except Exception as e:
        return "EXC: %s" % e, -1


def main():
    print("=" * 62)
    print("b3d 环境自检")
    print("=" * 62)
    print("系统: %s %s" % (platform.system(), platform.release()))
    print()

    results = []

    # ---------- 1. Blender ----------
    print("--- 1. Blender ---")
    exe, src = find_blender()
    if not exe:
        print(BAD + "未找到 Blender")
        print("     建议：从清华镜像下载（实测 13 MB/s，远快于官方源 128 KB/s）")
        print("     https://mirrors.tuna.tsinghua.edu.cn/blender/release/")
        print("     或直接设置环境变量 BLENDER_EXE 指向 blender.exe")
        results.append(("Blender", False))
        blender_exe = None
    else:
        print(OK + "找到: %s" % exe)
        print("     来源: %s" % src)
        out, rc = run_blender_expr(exe, "import bpy; print('VER|'+bpy.app.version_string)")
        ver = None
        for line in out.splitlines():
            if line.startswith("VER|"):
                ver = line.split("|", 1)[1].strip()
        if ver:
            print(OK + "版本: %s" % ver)
            major = int(ver.split(".")[0])
            minor = int(ver.split(".")[1]) if "." in ver else 0
            if (major, minor) < (3, 0):
                print(WARN + "版本过低。b3d 需要 >= 3.0，2.8x 缺少新版材质接口")
                print("     本机 2.83 用的是 Python 3.7 且材质 socket 名不同，不建议")
                results.append(("Blender", False))
            else:
                results.append(("Blender", True))
            blender_exe = exe
        else:
            print(BAD + "无法获取版本，Blender 可能启动失败")
            print("     输出片段: %s" % out[-400:])
            results.append(("Blender", False))
            blender_exe = None
    print()

    # ---------- 2. GPU（最关键）----------
    print("--- 2. GPU 渲染 ---")
    if not blender_exe:
        print(BAD + "跳过（无 Blender）")
        results.append(("GPU", False))
    else:
        # 完整走一遍引擎的 GPU 启用逻辑，确认端到端生效
        code = (
            "import bpy, addon_utils\n"
            "addon_utils.enable('cycles')\n"
            "p = bpy.context.preferences.addons['cycles'].preferences\n"
            "try:\n"
            "    p.compute_device_type = 'OPTIX'\n"
            "except TypeError:\n"
            "    try: p.compute_device_type = 'CUDA'\n"
            "    except TypeError: pass\n"
            "try: p.refresh_devices()\n"
            "except Exception: pass\n"
            "gpus = [d.name for d in p.devices if d.type in ('OPTIX','CUDA','HIP','METAL','ONEAPI')]\n"
            "print('GPULIST|' + ';'.join(gpus))\n"
            "sc = bpy.context.scene\n"
            "sc.render.engine = 'CYCLES'\n"
            "addon_utils.enable('cycles')\n"
            "try:\n"
            "    sc.cycles.device = 'GPU'\n"
            "except Exception:\n"
            "    pass\n"
            "print('DEV|' + str(sc.cycles.device))\n"
        )
        out, rc = run_blender_expr(blender_exe, code, timeout=240)
        gpus = []
        dev = None
        for line in out.splitlines():
            if line.startswith("GPULIST|"):
                gpus = [g for g in line.split("|", 1)[1].split(";") if g]
            if line.startswith("DEV|"):
                dev = line.split("|", 1)[1].strip()

        if gpus:
            for g in dict.fromkeys(gpus):
                print(OK + "检测到 GPU: %s" % g)
        else:
            print(WARN + "未检测到 GPU 渲染设备，将使用 CPU")
            print("     CPU 渲染比 GPU 慢约 5-7 倍（实测 1080p/192smp: 94s vs 14s）")

        if dev == "GPU":
            print(OK + "场景已启用 GPU 渲染 (cycles.device=GPU)")
            results.append(("GPU", True))
        else:
            print(BAD + "场景未启用 GPU！cycles.device=%s" % dev)
            print("     这是最隐蔽的性能问题：偏好里选了后端，但场景没切 GPU")
            print("     渲染会静默退回 CPU")
            results.append(("GPU", False))
    print()

    # ---------- 3. ffmpeg ----------
    print("--- 3. ffmpeg（导出视频需要）---")
    ff = None
    env_ff = os.environ.get("FFMPEG_DIR")
    candidates = [
        r"C:\Users\%s\AppData\Local\Microsoft\WinGet\Packages"
        r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
        r"\ffmpeg-9.0.2-full_build\bin" % os.environ.get("USERNAME", ""),
    ]
    if env_ff and os.path.isdir(env_ff):
        candidates.insert(0, env_ff)

    which_ff = shutil.which("ffmpeg")
    if which_ff:
        ff = which_ff
        print(OK + "PATH 中找到: %s" % ff)
    else:
        for d in candidates:
            exe_ff = os.path.join(d, "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg")
            if os.path.exists(exe_ff):
                ff = exe_ff
                print(OK + "在默认位置找到: %s" % ff)
                break

    if ff:
        # WinGet 在 PATH 放的 Links\ffmpeg.EXE 是符号链接桩，
        # subprocess 直接调用会 [WinError 193]。用引擎同款解析逻辑。
        real = None
        try:
            from b3d.renderer import resolve_ffmpeg
            real = resolve_ffmpeg(ff)
        except Exception:
            real = ff

        if real != ff and real:
            print("     （符号链接桩，已解析真实路径: %s）" % real)
        try:
            r = subprocess.run([real or ff, "-version"], capture_output=True, text=True, timeout=20)
            first = (r.stdout or "").splitlines()[0] if r.stdout else "?"
            print("     %s" % first[:78])
            r2 = subprocess.run([real or ff, "-hide_banner", "-encoders"], capture_output=True,
                                text=True, timeout=30)
            nvenc = "h264_nvenc" in (r2.stdout or "")
            if nvenc:
                # 编码器"存在"不等于"能用"。ffmpeg 9.x 要求 NVENC API 13.1 /
                # 驱动 >= 610，驱动 592.x 只有 API 13.0，encoder 根本打不开。
                # 必须实跑一次才知道。
                try:
                    from b3d.renderer import probe_nvenc
                    usable, why = probe_nvenc(real or ff)
                    if usable:
                        print(OK + "H.264 硬编 (NVENC): 可用，视频导出走 GPU 加速")
                    else:
                        print(WARN + "H.264 硬编 (NVENC): 编译支持但当前不可用")
                        print("     原因: %s" % why[:150])
                        print("     影响: 视频导出会回退 libx264 软件编码（慢，但能出片）")
                        print("     修复: 升级 NVIDIA 驱动到 610.00 以上")
                except Exception as pe:
                    print(WARN + "NVENC 预检失败: %s" % pe)
            else:
                print(WARN + "H.264 硬编 (NVENC): ffmpeg 未编译此编码器，将回退 libx264")
            results.append(("ffmpeg", True))
        except Exception as e:
            print(WARN + "ffmpeg 存在但调用失败: %s" % e)
            results.append(("ffmpeg", False))
    else:
        print(WARN + "未找到 ffmpeg（只影响视频导出，静态图不受影响）")
        print("     安装: winget install Gyan.FFmpeg")
        results.append(("ffmpeg", False))
    print()

    # ---------- 4. 中文解析 ----------
    print("--- 4. 中文指令解析 ---")
    try:
        from b3d import parser
        cases = [
            ("一个金色的纳米颗粒，暗色背景，电影感灯光", dict(count=1, mat="gold")),
            ("30个PLGA微球聚在一起，白色背景", dict(count=30, mat="plga")),
            ("一簇金纳米棒旋转，8秒动画", dict(count=18, anim="orbit")),
        ]
        all_ok = True
        for text, want in cases:
            s = parser.parse(text)
            got = dict(count=s["count"], mat=s["objects"][0]["material"],
                       anim=s.get("animation"))
            hit = all(got.get(k) == v for k, v in want.items())
            all_ok = all_ok and hit
            print("  %s %s" % (OK if hit else BAD, text))
            if not hit:
                print("       期望 %s 实得 %s" % (want, got))
        results.append(("解析", all_ok))
        if all_ok:
            print(OK + "全部通过")
    except Exception as e:
        print(BAD + "解析器导入失败: %s" % e)
        results.append(("解析", False))
    print()

    # ---------- 汇总 ----------
    print("=" * 62)
    print("自检汇总")
    print("=" * 62)
    for name, ok in results:
        print("  %s %s" % (OK if ok else BAD, name))

    critical = [n for n, ok in results if n in ("Blender", "GPU", "解析") and not ok]
    print()
    if not critical:
        print("核心功能全部就绪，可以开始渲染：")
        print('    python "%s" -- "一个金色的纳米颗粒，电影感灯光"' % os.path.join(HERE, "b3d", "cli.py"))
        print()
        print("或直接（Windows）：")
        print('    b3d.bat "一个金色的纳米颗粒，电影感灯光"')
        return 0
    else:
        print("以下项目需要修复: %s" % ", ".join(critical))
        return 1


if __name__ == "__main__":
    sys.exit(main())
