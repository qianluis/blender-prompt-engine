# -*- coding: utf-8 -*-
"""
b3d.parser - 中文/英文自然语言 → SceneSpec

设计原则：宽容解析。
用户说"一个金色的纳米球，暗色背景，电影感灯光"，
就应该得到一张像样的图，而不是报错要求重新输入。

不做 LLM 调用（离线可用），规则 + 词典驱动，确定性可复现。
"""
import re
import json
from typing import Dict, Any, List


# ==================== 词典 ====================
# 主体 → (几何类型, 默认材质预设)
SUBJECT_DICT = {
    # 中文
    "纳米颗粒": ("SPHERE", "gold"),
    "纳米粒":   ("SPHERE", "gold"),
    "纳米球":   ("SPHERE", "gold"),
    "纳米粒子": ("SPHERE", "silica"),
    "微球":     ("SPHERE", "plga"),
    "微纳米球": ("SPHERE", "plga"),
    "介孔硅":   ("SPHERE", "msn"),
    "二氧化硅": ("SPHERE", "silica"),
    "水凝胶":   ("ICO", "hydrogel"),
    "凝胶":     ("ICO", "hydrogel"),
    "胶束":     ("SPHERE", "hydrogel"),
    "细胞":     ("ICO", "cytoplasm"),
    "细胞核":   ("ICO", "nucleus"),
    "线粒体":   ("SPHERE", "mitoEmit"),
    "线粒体红色": ("SPHERE", "mitoEmit"),
    "线粒体绿色": ("SPHERE", "mitoGreen"),
    "肽":       ("CYLINDER", "peptideL"),
    "多肽":     ("CYLINDER", "peptideL"),
    "自组装肽": ("CYLINDER", "peptideL"),
    "纤维":     ("CYLINDER", "collagen"),
    "胶原":     ("CYLINDER", "collagen"),
    "羟基磷灰石": ("SPHERE", "hydroxyapatite"),
    "球":       ("SPHERE", "gold"),
    "正方体":   ("CUBE", "matteWhite"),
    "立方体":   ("CUBE", "matteWhite"),
    "方块":     ("CUBE", "matteWhite"),
    "圆柱":     ("CYLINDER", "matteWhite"),
    "圆环":     ("TORUS", "chrome"),
    "平面":     ("PLANE", "matteWhite"),
    "猴头":     ("MONKEY", "chrome"),
    # 英文
    "nanoparticle": ("SPHERE", "gold"),
    "microsphere":  ("SPHERE", "plga"),
    "hydrogel":     ("ICO", "hydrogel"),
    "cell":         ("ICO", "cytoplasm"),
    "mitochondria": ("SPHERE", "mitoEmit"),
    "sphere":       ("SPHERE", "gold"),
    "cube":         ("CUBE", "matteWhite"),
    "cylinder":     ("CYLINDER", "matteWhite"),
}

# 材质/颜色词
MATERIAL_DICT = {
    "金色": "gold", "金": "gold", "gold": "gold", "golden": "gold",
    "银色": "silver", "银": "silver", "silver": "silver",
    "钛": "titanium", "titanium": "titanium",
    "铂": "platinum", "platinum": "platinum",
    "玻璃": "glass", "玻璃质感": "glass", "glassy": "glass",
    "透明": "glass", "transparent": "glass",
    "铬": "chrome", "镜面": "chrome", "chrome": "chrome",
    "水": "water", "water": "water",
    "二氧化硅胶体": "silica", "silica": "silica",
    "介孔": "msn", "mesoporous": "msn",
    "PLGA": "plga", "plga": "plga", "聚乳酸": "plga",
    "水凝胶": "hydrogel", "hydrogel": "hydrogel",
    "胶原": "collagen", "collagen": "collagen",
    "羟基磷灰石": "hydroxyapatite",
    "发光红": "mitoEmit", "红色发光": "mitoEmit", "荧光红": "mitoEmit",
    "发光绿": "mitoGreen", "绿色发光": "mitoGreen", "荧光绿": "mitoGreen",
    "蓝色核": "dapi", "DAPI": "dapi", "dapi": "dapi",
    "L肽": "peptideL", "D肽": "peptideD",
    "白色哑光": "matteWhite", "哑光白": "matteWhite", "matte white": "matteWhite",
    "黑色哑光": "matteDark", "哑光黑": "matteDark",
}

# 背景词
BACKGROUND_DICT = {
    "暗色背景": ("studio_dark", (0.02, 0.02, 0.03, 1.0)),
    "黑色背景": ("studio_dark", (0.01, 0.01, 0.015, 1.0)),
    "深色背景": ("studio_dark", (0.02, 0.02, 0.03, 1.0)),
    "白色背景": ("studio_white", (0.95, 0.95, 0.96, 1.0)),
    "亮色背景": ("studio_white", (0.93, 0.93, 0.95, 1.0)),
    "渐隐背景": ("gradient", (0.05, 0.07, 0.12, 1.0)),
    "蓝色渐变": ("gradient", (0.06, 0.12, 0.25, 1.0)),
    "透明背景": ("transparent", (0.0, 0.0, 0.0, 0.0)),
    "抠图": ("transparent", (0.0, 0.0, 0.0, 0.0)),
}

# 科研模板（走 templates.py 专用几何，而非通用基本体）
TEMPLATE_DICT = {
    "三螺旋": "triple_helix",
    "胶原三螺旋": "triple_helix",
    "螺旋": "helix",
    "α螺旋": "helix",
    "纤维网络": "fibril_network",
    "自组装纤维": "fibril_network",
    "纳米纤维": "fibril_network",
    "多孔网络": "porous_network",
    "网络结构": "porous_network",
    "核壳": "core_shell",
    "核壳结构": "core_shell",
    "介孔": "mesoporous",
    "介孔硅": "mesoporous",
}

# 灯光风格
LIGHTING_DICT = {
    "科研风格": "scientific",
    "学术风格": "scientific",
    "科学布光": "scientific",
    "暗场": "darkfield",
    "荧光风格": "darkfield",
    "电影感": "cinematic",
    "电影级": "cinematic",
    "cinematic": "cinematic",
    "棚拍": "studio",
    "影棚": "studio",
    "studio": "studio",
    "三点光": "three_point",
    "三点布光": "three_point",
    "three point": "three_point",
    "侧光": "rim",
    "轮廓光": "rim",
    "柔和": "soft",
    "高对比": "dramatic",
    "戏剧性": "dramatic",
}

# 质量档位
QUALITY_DICT = {
    "预览": dict(res=(960, 540), samples=32, denoise=True),
    "草稿": dict(res=(1280, 720), samples=64, denoise=True),
    "标准": dict(res=(1920, 1080), samples=192, denoise=True),
    "高清": dict(res=(1920, 1080), samples=320, denoise=True),
    "2k":   dict(res=(2560, 1440), samples=384, denoise=True),
    "4k":   dict(res=(3840, 2160), samples=512, denoise=True),
    "出版级": dict(res=(3840, 2160), samples=768, denoise=True),
    "poster": dict(res=(3840, 2160), samples=768, denoise=True),
}

# 镜头语言
CAMERA_DICT = {
    "近景": dict(radius=4.5, elevation_deg=12, lens=85),
    "特写": dict(radius=3.2, elevation_deg=8, lens=105),
    "微距": dict(radius=2.6, elevation_deg=5, lens=120),
    "中景": dict(radius=8.0, elevation_deg=22, lens=50),
    "全景": dict(radius=14.0, elevation_deg=30, lens=35),
    "俯视": dict(radius=9.0, elevation_deg=70, lens=40),
    "仰视": dict(radius=9.0, elevation_deg=-20, lens=40),
    "平视": dict(radius=9.0, elevation_deg=2, lens=50),
    "closeup": dict(radius=3.2, elevation_deg=8, lens=105),
    "wide":   dict(radius=14.0, elevation_deg=30, lens=35),
}

# 动画
ANIMATION_DICT = {
    "绕圈": "orbit",
    "绕着转": "orbit",
    "旋转": "orbit",
    "环绕": "orbit",
    "自旋": "spin",
    "自转": "spin",
    "推进": "dolly_in",
    "推近": "dolly_in",
    "拉远": "dolly_out",
    "上升": "rise",
    "飘浮": "float",
    "orbit": "orbit",
    "spin": "spin",
}


# ==================== 解析 ====================
def _match_first(text: str, table: Dict[str, Any]):
    """按 key 长度降序匹配，优先命中更具体的词（如'纳米颗粒' > '球'）"""
    keys = sorted(table.keys(), key=len, reverse=True)
    text_l = text.lower()
    for k in keys:
        if k.lower() in text_l:
            return k, table[k]
    return None, None


def _find_all(text: str, table: Dict[str, Any]) -> List:
    """找出所有命中的关键词"""
    keys = sorted(table.keys(), key=len, reverse=True)
    text_l = text.lower()
    hits = []
    consumed = set()
    for k in keys:
        kl = k.lower()
        if kl in text_l and not any(kl in c or c in kl for c in consumed):
            # 避免短词已被长词覆盖
            hits.append((k, table[k]))
            consumed.add(kl)
    return hits


def parse(prompt: str) -> Dict[str, Any]:
    """
    自然语言 → SceneSpec dict
    """
    spec: Dict[str, Any] = {
        "prompt": prompt,
        "objects": [],
        "background": "studio_dark",
    "bg_color": (0.02, 0.02, 0.03, 1.0),
    "lighting": "cinematic",
    "quality": "标准",
    "camera": "中景",
    "animation": None,
    "duration_sec": 0,
    "fps": 24,
    "count": 1,
    "layout": "single",
    "template": None,
}

    # --- 主体 ---
    subj_key, subj_val = _match_first(prompt, SUBJECT_DICT)
    if subj_val:
        geo, mat = subj_val
    else:
        geo, mat = "SPHERE", "gold"

    # --- 数量 ---
    n = _extract_count(prompt)

    # --- 材质覆盖（若明确指定了颜色/材质词）---
    mat_key, mat_preset = _match_first(prompt, MATERIAL_DICT)
    if mat_preset:
        mat = mat_preset

    # --- 布局 ---
    if n > 1:
        spec["layout"] = "cluster"
        spec["count"] = n
    else:
        spec["count"] = 1

    spec["objects"].append({
        "geometry": geo,
        "material": mat,
        "role": "subject",
        "scale": (1.0, 1.0, 1.0),
    })

    # --- 科研模板（优先于普通几何，命中后由 templates.py 接管）---
    tpl_key, tpl_val = _match_first(prompt, TEMPLATE_DICT)
    if tpl_val:
        spec["template"] = tpl_val
        # 模板自带的材质语义更准，覆盖通用匹配
        if tpl_val in ("triple_helix", "helix") and not mat_preset:
            mat = "collagen"
        spec["objects"][0]["geometry"] = "TEMPLATE"

    # --- 背景 ---
    bg_key, bg_val = _match_first(prompt, BACKGROUND_DICT)
    if bg_val:
        spec["background"], spec["bg_color"] = bg_val

    # --- 灯光 ---
    lit_key, lit_val = _match_first(prompt, LIGHTING_DICT)
    if lit_val:
        spec["lighting"] = lit_val

    # --- 质量 ---
    q_key, q_val = _match_first(prompt, QUALITY_DICT)
    if q_val:
        spec["quality"] = q_key

    # --- 镜头 ---
    cam_key, cam_val = _match_first(prompt, CAMERA_DICT)
    if cam_val:
        spec["camera"] = cam_key

    # --- 动画 ---
    anim_key, anim_val = _match_first(prompt, ANIMATION_DICT)
    if anim_val and _has_video_intent(prompt):
        spec["animation"] = anim_val
        spec["duration_sec"] = _extract_duration(prompt)

    return spec


def _has_video_intent(text: str) -> bool:
    """判断是否真的想要视频，而不是恰好提到'旋转'二字"""
    video_words = ["视频", "动画", "短片", "电影", "录像", "gif",
                   "video", "animation", "movie", "clip", "mov", "mp4"]
    t = text.lower()
    if any(w in t for w in video_words):
        return True
    # 时长单位 + 数字 = 强信号。
    # 注意：中文字符在 Python re 里属于 \w，"10秒动画" 中 秒/动 之间不存在 \b，
    # 所以这里绝不能用 \b 做边界，否则中文时长识别全部失效。
    if re.search(r"(\d+)\s*(秒|秒钟|sec|secs|second|seconds)", t, re.I):
        return True
    if re.search(r"(\d+)\s*(分钟|min|minute)", t, re.I):
        return True
    return False


def _extract_count(text: str) -> int:
    """提取数量：支持中文数字与阿拉伯数字"""
    cn = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
          "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
          "十几": 12, "二十": 20, "三十": 30, "五十": 50, "一百": 100}

    # 阿拉伯数字 + 个
    m = re.search(r"(\d+)\s*个", text)
    if m:
        v = int(m.group(1))
        if 1 <= v <= 500:
            return v
    # 中文数字 + 个
    for k, v in sorted(cn.items(), key=lambda x: -len(x[0])):
        if k + "个" in text:
            return v
    # 群体词
    if re.search(r"(一群|一堆|许多|大量|很多|簇)", text):
        return 18
    if re.search(r"(若干|几个|数个)", text):
        return 6
    return 1


def _extract_duration(text: str) -> float:
    # 同样不能用 \b：中文 \w 会导致 \b 在"秒动画"之间匹配失败
    m = re.search(r"(\d+(?:\.\d+)?)\s*(秒|秒钟|sec|secs|second|seconds)", text, re.I)
    if m:
        v = float(m.group(1))
        return min(max(v, 0.5), 120.0)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(分钟|min|minute)", text, re.I)
    if m:
        return min(float(m.group(1)) * 60, 300.0)
    return 6.0


def quality_to_params(qname: str) -> Dict[str, Any]:
    """质量档位 → 渲染参数"""
    return QUALITY_DICT.get(qname, QUALITY_DICT["标准"])


def explain(spec: Dict[str, Any]) -> str:
    """把 SceneSpec 翻译回人话，便于用户确认理解是否正确"""
    o = spec["objects"][0]
    if spec.get("template"):
        parts = ["模板：%s（科研专用几何）" % spec["template"]]
    else:
        parts = ["主体：%s 个 %s（材质 %s）"
                 % (spec["count"], o["geometry"], o["material"])]
    parts += [
        "背景：%s" % spec["background"],
        "布光：%s" % spec["lighting"],
        "镜头：%s" % spec["camera"],
        "质量：%s" % spec["quality"],
    ]
    if spec["animation"]:
        parts.append("动画：%s，时长 %.1f 秒" % (spec["animation"], spec["duration_sec"]))
    else:
        parts.append("输出：单帧图片")
    return "\n".join("  " + p for p in parts)


if __name__ == "__main__":
    tests = [
        "一个金色的纳米颗粒，暗色背景，电影感灯光，高清",
        "30个PLGA微球聚在一起，白色背景，棚拍，特写",
        "发光线粒体在细胞里绕圈，10秒动画，标准质量",
    "水凝胶网络结构，透明背景，4K",
    "蓝色DAPI细胞核，近景，戏剧性布光",
    "一簇金纳米棒在溶液里旋转，做成8秒的动画，高清",
    "单个介孔硅微球，白色背景，微距，4K出版级",
    ]
    for t in tests:
        print("=" * 60)
        print("输入:", t)
        s = parse(t)
        print(json.dumps(s, ensure_ascii=False, indent=2))
        print(explain(s))
