# -*- coding: utf-8 -*-
"""
b3d.scene - SceneSpec → Blender 场景装配

把结构化的 SceneSpec 翻译成真实的物体、材质、灯光、相机、动画。
"""
import math
import random

try:
    import bpy
    from mathutils import Vector
except ImportError:
    bpy = None
    Vector = None

from . import compat, builders


# ==================== 布局 ====================
def layout_cluster(n, radius=2.2, seed=42, jitter=0.35, min_dist=0.85):
    """
    生成 n 个互不穿插的球面分布坐标（泊松盘近似的抖动采样）
    避免直接用 random 导致颗粒重叠穿模
    """
    rnd = random.Random(seed)
    pts = []
    attempts = 0
    max_attempts = n * 300
    while len(pts) < n and attempts < max_attempts:
        attempts += 1
        # 球面均匀分布
        u = rnd.uniform(-1, 1)
        theta = rnd.uniform(0, 2 * math.pi)
        r = radius * (rnd.random() ** (1 / 3))  # 体积均匀，不是壳层
        s = math.sqrt(1 - u * u)
        p = Vector((r * s * math.cos(theta),
                    r * s * math.sin(theta),
                    r * u))
        # 碰撞剔除
        ok = True
        for q in pts:
            if (p - q).length < min_dist:
                ok = False
                break
        if ok or attempts > max_attempts * 0.8:
            pts.append(p)
    return pts


def layout_fibonacci_sphere(n, radius=2.2):
    """黄金角螺旋分布：视觉上最均匀规整，适合封面图"""
    pts = []
    golden = math.pi * (3 - math.sqrt(5))
    for i in range(n):
        y = 1 - (i / max(n - 1, 1)) * 2
        r = math.sqrt(max(1 - y * y, 0))
        theta = golden * i
        pts.append(Vector((math.cos(theta) * r * radius,
                           math.sin(theta) * r * radius,
                           y * radius)))
    return pts


def layout_grid(nx=4, ny=4, nz=1, spacing=2.0):
    """规则阵列，适合展示对比或规模化制备"""
    pts = []
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                pts.append(Vector(((i - (nx - 1) / 2) * spacing,
                                   (j - (ny - 1) / 2) * spacing,
                                   (k - (nz - 1) / 2) * spacing)))
    return pts


# ==================== 灯光风格 ====================
def apply_lighting(style, center=(0, 0, 1), radius=8.0, **kw):
    """按风格布光"""
    from . import templates

    style = (style or "cinematic").lower()
    if style == "scientific":
        return templates.scientific_lighting(center, distance=radius,
                                            key_energy=kw.get("key_energy", 1000))
    if style == "darkfield":
        return templates.darkfield_style(center, distance=radius * 0.9)

    if style in ("cinematic", "three_point", "三点光"):
        return builders.three_point_rig(center, distance=radius,
                                       key_energy=kw.get("key_energy", 900))
    if style == "studio":
        return builders.three_point_rig(center, distance=radius,
                                       key_energy=kw.get("key_energy", 700),
                                       fill_ratio=0.55, rim_ratio=0.45)
    if style == "rim":
        k = builders.three_point_rig(center, distance=radius, key_energy=250,
                                     fill_ratio=0.15, rim_ratio=1.6)
        return k
    if style == "soft":
        # 大面积柔和顶光 + 弱补光
        a = builders.add_light("SoftTop", "AREA", (0, 0, radius * 1.2),
                               energy=600, size=radius * 1.6)
        b = builders.add_light("SoftFill", "AREA", (radius, 0, radius * 0.4),
                               energy=200, size=radius * 1.4, target=center)
        return {"key": a, "fill": b, "rim": None}
    if style == "dramatic":
        return builders.three_point_rig(center, distance=radius,
                                       key_energy=kw.get("key_energy", 1300),
                                       fill_ratio=0.10, rim_ratio=1.2,
                                       key_color=(1.0, 0.88, 0.72))
    # 默认
    return builders.three_point_rig(center, distance=radius)


# ==================== 背景 ====================
def apply_background(kind, color=(0.02, 0.02, 0.03, 1.0)):
    """设置世界背景"""
    scene = bpy.context.scene
    kind = (kind or "studio_dark").lower()
    if kind == "transparent":
        scene.render.film_transparent = True
        compat.set_world_background((0, 0, 0, 0), strength=0.0)
        return None
    compat.set_world_background(color, strength=1.0)
    return None


def add_backdrop(size=60, location=(0, 0, -0.001), color=(0.02, 0.02, 0.03)):
    """
    加一块地面板。
    很多"电影感"其实来自地面接触阴影 —— 没有地面，物体像飘在空中。
    """
    bpy.ops.mesh.primitive_plane_add(size=size, location=location)
    obj = bpy.context.object
    obj.name = "Backdrop"
    mat = builders.make_material("BackdropMat",
                                 base=color + (1.0,), roughness=0.55, metallic=0.0)
    builders.apply_material(obj, mat)
    return obj


# ==================== 主体 ====================
def _build_geometry(geo, name, scale=(1, 1, 1)):
    """按几何类型生成网格"""
    geo = geo.upper()
    common = dict(name=name, scale=scale)
    if geo == "SPHERE":
        obj = builders.add_mesh("ICO", **common, subdivisions=5, radius=1.0)
        compat.smooth(obj)
    elif geo == "UVSPHERE":
        obj = builders.add_mesh("SPHERE", **common, segments=64, ring_count=32, radius=1.0)
        compat.smooth(obj)
    elif geo == "CYLINDER":
        obj = builders.add_mesh("CYLINDER", **common, vertices=32, radius=0.22,
                                depth=3.0)
        compat.smooth(obj)
    elif geo in ("CUBE", "PLANE", "TORUS", "MONKEY", "CONE", "ICO"):
        obj = builders.add_mesh(geo, **common, size=2.0 if geo in ("CUBE", "PLANE") else None)
        compat.smooth(obj)
    else:
        obj = builders.add_mesh("ICO", **common, subdivisions=5, radius=1.0)
        compat.smooth(obj)
    return obj


def build_subjects(spec, seed=42):
    """按 SceneSpec 生成主体群"""
    objs = []
    n = int(spec.get("count", 1))
    ospec = spec["objects"][0]
    geo = ospec["geometry"]
    mat_preset = ospec["material"]
    layout = spec.get("layout", "single")

    # 科研模板优先：由 templates.py 生成专用几何
    tpl = spec.get("template")
    if tpl or geo == "TEMPLATE":
        return build_template_subject(spec, seed=seed)

    mat = builders.make_material("SubjectMat_%s" % mat_preset, preset=mat_preset)

    rnd = random.Random(seed)
    if n <= 1 or layout == "single":
        obj = _build_geometry(geo, "Subject", scale=(1.0, 1.0, 1.0))
        obj.location = (0, 0, 1.0)
        builders.apply_material(obj, mat)
        compat.smooth(obj)
        objs.append(obj)
        return objs

    # 多体：先用斐波那契保证均匀，再轻微抖动打破机械感
    base = layout_fibonacci_sphere(n, radius=1.6 + 0.12 * n ** 0.5)
    for i, p in enumerate(base):
        jitter_scale = 1.0 / (1 + math.sqrt(i))
        loc = (
            p.x + rnd.uniform(-0.18, 0.18) * jitter_scale,
            p.y + rnd.uniform(-0.18, 0.18) * jitter_scale,
            p.z + 1.6 + rnd.uniform(-0.12, 0.12),
        )
        s = tuple(rnd.uniform(0.62, 1.0) for _ in range(3))
        obj = _build_geometry(geo, "P_%03d" % i, scale=s)
        obj.location = loc
        obj.rotation_euler = (rnd.uniform(0, 6.28), rnd.uniform(0, 6.28),
                              rnd.uniform(0, 6.28))
        builders.apply_material(obj, mat)
        compat.smooth(obj)
        objs.append(obj)
    return objs


def build_template_subject(spec, seed=42):
    """
    按科研模板生成几何。返回统一格式的 list[Object]，
    让上层不必区分"模板"和"通用几何"。
    """
    from . import templates
    tpl = spec.get("template") or "porous_network"
    mat_preset = spec["objects"][0].get("material")

    builder_map = {
        "helix":          lambda: templates.build_alpha_helix(
                              n_residues=spec.get("count", 10) if spec.get("count", 1) > 3 else 12),
        "triple_helix":   lambda: templates.build_triple_helix(n_residues=12),
        "fibril_network": lambda: templates.build_fibril_network(
                              n_fibrils=24, seed=seed,
                              material_preset=mat_preset or "collagen"),
        "porous_network": lambda: templates.build_porous_network(
                              n_nodes=28, seed=seed,
                              node_material=mat_preset or "hydrogel"),
        "core_shell":     lambda: templates.build_core_shell(
                              core_preset=mat_preset or "gold"),
        "mesoporous":     lambda: templates.build_mesoporous_sphere(
                              body_preset=mat_preset or "msn", seed=seed),
    }
    fn = builder_map.get(tpl, builder_map["porous_network"])
    result = fn()

    # templates 里部分函数返回 dict，统一规约为 Object 列表
    if isinstance(result, dict):
        objs = result.get("objects", [])
    elif isinstance(result, (list, tuple)):
        objs = list(result)
    else:
        objs = [result]
    # build_ball_stick 返回 {"collection":..., "objects":[...]}
    if not objs and isinstance(result, dict) and "collection" in result:
        objs = list(result["collection"].objects)
    print("[scene] 使用科研模板: %s -> %d 个对象" % (tpl, len(objs)))
    return objs


# ==================== 相机 ====================
def setup_camera(spec, target=(0, 0, 1.2), dof=None):
    """按镜头语言放置相机"""
    from . import parser
    cam_cfg = parser.CAMERA_DICT.get(spec.get("camera", "中景"),
                                     parser.CAMERA_DICT["中景"])
    pos = builders.orbit_position(target=target,
                                  radius=cam_cfg["radius"],
                                  azimuth_deg=38,
                                  elevation_deg=cam_cfg["elevation_deg"])
    cam = builders.add_camera("MainCam", location=pos, target=target,
                             lens=cam_cfg["lens"])
    if dof:
        cam.data.dof.use_dof = True
        cam.data.dof.aperture_fstop = dof
        cam.data.dof.focus_distance = cam_cfg["radius"]
    bpy.context.scene.camera = cam
    return cam


# ==================== 动画 ====================
def apply_animation(kind, target_obj=None, camera=None, target=(0, 0, 1.2),
                   frame_start=1, frame_end=48, radius=None):
    """给场景加动画"""
    kind = (kind or "orbit").lower()
    scene = bpy.context.scene

    if kind == "spin":
        # 物体自转
        obj = target_obj
        if obj is None:
            return None
        obj.rotation_euler = (0, 0, 0)
        obj.keyframe_insert(data_path="rotation_euler", frame=frame_start)
        obj.rotation_euler = (0, 0, math.radians(360))
        obj.keyframe_insert(data_path="rotation_euler", frame=frame_end)
        for fc in obj.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
        return obj

    if kind in ("dolly_in", "dolly_out"):
        if camera is None:
            return None
        # 同样只打首尾两个关键帧，交给 Blender 做插值。
        # 用 target 而非原点做基准，否则推镜会偏出画面外。
        tgt = Vector(target)
        p0 = Vector(camera.location) - tgt
        start_r = p0.length
        if start_r < 1e-6:
            p0 = Vector((1, 0, 0))
            start_r = 1.0
        factor = 0.42 if kind == "dolly_in" else 1.9
        end_r = start_r * factor

        camera.location = tgt + p0
        camera.keyframe_insert(data_path="location", frame=frame_start)
        camera.location = tgt + p0.normalized() * end_r
        camera.keyframe_insert(data_path="location", frame=frame_end)

        for fc in camera.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                # 平滑加减速，比线性更像真实运镜
                kp.interpolation = "BEZIER"
                kp.easing = "EASE_IN_OUT"
        return camera

    if kind == "rise":
        if camera is None:
            return None
        base_z = camera.location.z
        camera.location.z = base_z
        camera.keyframe_insert(data_path="location", frame=frame_start)
        camera.location.z = base_z + 5.0
        camera.keyframe_insert(data_path="location", frame=frame_end)
        for fc in camera.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.easing = "EASE_IN_OUT"
        return camera

    # 默认：相机环绕 (orbit)
    #
    # 不用"逐帧 keyframe_insert"的老写法：那会产生 (帧数×通道数) 个关键帧
    # （72帧 × 6通道 = 432 个），既慢又难调整。
    # 改成：建一个空物体做旋转驱动，相机作为它的子级。
    # 关键帧数量从数百降到 3 个，且随时能改速度/半径。
    if camera is None:
        return None

    from mathutils import Vector as V

    target_v = V(target)
    empty = bpy.data.objects.new("OrbitDriver", None)
    empty.location = target_v
    empty.empty_display_size = 0.5
    empty.empty_display_type = "PLAIN_AXES"
    bpy.context.collection.objects.link(empty)

    # 相机当前偏移直接作为 local 偏移。
    # 关键：此时 empty 旋转必须是 0，这样首帧相机世界位置才会和原位置精确重合，
    # 否则开场会"跳一下"。
    cam_offset = V(camera.location) - target_v
    camera.parent = empty
    camera.matrix_parent_inverse = empty.matrix_world.inverted()
    camera.location = cam_offset
    # 在 empty 的局部空间里瞄准中心的far target（即 empty 自身原点）
    camera.rotation_euler = (-cam_offset).to_track_quat("-Z", "Y").to_euler()

    # 只给 driver 的 Z 旋转打关键帧：0 → 360°
    empty.rotation_euler = (0, 0, 0)
    empty.keyframe_insert(data_path="rotation_euler", index=2, frame=frame_start)
    empty.rotation_euler = (0, 0, 2 * math.pi)
    empty.keyframe_insert(data_path="rotation_euler", index=2, frame=frame_end)

    for fc in empty.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"  # 匀速，避免起停顿挫

    scene.frame_set(frame_start)
    return empty


# ==================== 总装 ====================
def assemble(spec, seed=42, ground=True, dof=None):
    """
    SceneSpec → Blender 场景（不含渲染）
    返回 dict(obj, camera, lights)
    """
    compat.clear_scene(keep_world=True)
    scene = bpy.context.scene

    # 背景
    apply_background(spec.get("background"), tuple(spec.get("bg_color",
                                                           (0.02, 0.02, 0.03, 1.0))))

    # 地面（透明背景时不加，否则会有残留板）
    if ground and spec.get("background") != "transparent":
        add_backdrop()

    # 主体
    objs = build_subjects(spec, seed=seed)

    # 中心点：包围盒中心，保证相机/灯光对准
    center = (0, 0, 1.2)
    if objs:
        vs = []
        for o in objs:
            for c in o.bound_box:
                vs.append(Vector(o.matrix_world @ Vector(c)))
        if vs:
            mn = Vector((min(v.x for v in vs), min(v.y for v in vs),
                         min(v.z for v in vs)))
            mx = Vector((max(v.x for v in vs), max(v.y for v in vs),
                         max(v.z for v in vs)))
            center = ((mn + mx) / 2).to_tuple()

    # 灯光：距离随物体规模自适应，否则小颗体会过曝、大簇会过暗
    scale_hint = 8.0 + 0.25 * math.sqrt(max(len(objs) - 1, 0))
    lights = apply_lighting(spec.get("lighting"), center=center,
                           radius=scale_hint)

    # 相机
    cam = setup_camera(spec, target=center, dof=dof)

    # 动画
    anim = spec.get("animation")
    if anim:
        fps = int(spec.get("fps", 24))
        dur = float(spec.get("duration_sec", 6.0))
        frame_end = max(int(dur * fps), 2)
        scene.frame_start = 1
        scene.frame_end = frame_end
        apply_animation(anim, target_obj=objs[0] if objs else None,
                       camera=cam, target=center,
                       frame_start=1, frame_end=frame_end)

    return {"objects": objs, "camera": cam, "lights": lights, "center": center}
