# -*- coding: utf-8 -*-
"""
b3d 命令行入口

用法:
    blender --background --python cli.py -- "一个金色的纳米颗粒，电影感灯光"
    blender --background --python cli.py -- "水凝胶网络，4K" --out-name gel.png
    blender --background --python cli.py -- "..." --quality 预览 --seed 7
"""
import sys
import os
import json

# 把包所在目录（cli.py 的上一级）加入路径，保证能 import b3d
_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG_ROOT = os.path.dirname(_HERE)
for p in (_PKG_ROOT, _HERE):
    if p not in sys.path:
        sys.path.insert(0, p)


def _split_argv():
    """
    Blender 会吞掉 -- 之后的参数，我们直接从 sys.argv 里手动切。
    Blender 传参惯例: blender [args] --python cli.py -- <ours>
    """
    argv = sys.argv
    ours = []
    if "--" in argv:
        i = argv.index("--")
        # 取最后一个 -- 之后的内容（防止 Blender 自身参数干扰）
        while i < len(argv):
            seg = argv[i + 1:]
            if seg:
                ours = seg
            i = argv.index("--", i + 1) if "--" in argv[i + 1:] else len(argv)
    if not ours and len(argv) > 1:
        ours = argv[1:]
    return ours


def parse_args(parts):
    """极简参数解析：位置参数为 prompt，其余为 --key value"""
    positional = []
    opts = {}
    i = 0
    while i < len(parts):
        p = parts[i]
        if p.startswith("--"):
            key = p[2:]
            # 支持 --key=value 和 --key value
            if "=" in key:
                k, v = key.split("=", 1)
                opts[k] = v
                i += 1
                continue
            if i + 1 < len(parts) and not parts[i + 1].startswith("--"):
                opts[key] = parts[i + 1]
                i += 2
            else:
                opts[key] = True
                i += 1
        else:
            positional.append(p)
            i += 1
    return positional, opts


def main():
    parts = _split_argv()
    positional, opts = parse_args(parts)

    import b3d

    # 纯解析模式（不需要 Blender 场景）
    if opts.get("explain") or opts.get("dry-run"):
        if not positional:
            print("错误: 缺少指令。用法: b3d \"指令\" --explain")
            return 2
        print(b3d.explain(" ".join(positional)))
        if opts.get("json"):
            print(json.dumps(b3d.spec_from_prompt(" ".join(positional)),
                             ensure_ascii=False, indent=2))
        return 0

    if not positional:
        print(__doc__)
        print("\n可用参数:")
        print("  --out-name NAME    输出文件名")
        print("  --out-dir DIR      输出目录")
        print("  --quality 档位      预览/草稿/标准/高清/2k/4k/出版级")
        print("  --seed N           随机种子（保证可复现）")
        print("  --dof F            景深光圈值，如 2.8")
        print("  --no-ground        不加地面板")
        print("  --keep-frames      保留序列帧")
        print("  --explain          只解析指令，不渲染")
        return 1

    prompt = " ".join(positional)

    kwargs = {}
    if opts.get("out-name"):
        kwargs["output"] = opts["out-name"]
    if opts.get("out-dir"):
        kwargs["out_dir"] = opts["out-dir"]
    if opts.get("quality"):
        kwargs["quality"] = opts["quality"]
    if opts.get("seed"):
        kwargs["seed"] = int(opts["seed"])
    if opts.get("dof"):
        kwargs["dof"] = float(opts["dof"])
    if opts.get("no-ground"):
        kwargs["ground"] = False
    if opts.get("keep-frames"):
        kwargs["keep_frames"] = True
    if opts.get("ffmpeg-dir"):
        kwargs["ffmpeg_dir"] = opts["ffmpeg-dir"]

    try:
        r = b3d.make(prompt, **kwargs)
    except Exception as e:
        print("[b3d] FAILED: %s" % e)
        import traceback
        traceback.print_exc()
        return 1

    print("\n" + "=" * 62)
    print("[b3d] 成功 (%s)" % r["kind"])
    print("  文件: %s" % r["path"])
    print("  耗时: %.1f 秒" % r["seconds"])
    if r["kind"] == "video":
        print("  帧数: %d @ %d fps (%.1f 秒)" %
              (r["frames"], r["fps"], r["duration_sec"]))
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
else:
    # 被 --python 直接执行时 __name__ 是 __main__；
    # 兜底：某些调用方式下直接跑一次
    try:
        sys.exit(main())
    except SystemExit:
        pass
