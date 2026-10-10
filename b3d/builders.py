# -*- coding: utf-8 -*-
"""
b3d.builders - 语义化的场景构件工厂

把"我要一个发光的金色纳米颗粒"翻译成 Cycles 材质节点网络。
所有版本差异通过 compat.set_float 屏蔽。
"""
try:
    import bpy
    from mathutils import Vector
except ImportError:
    bpy = None
    Vector = None

from . import compat


# ==================== 预设材质库 ====================
# 命名遵循科研可视化直觉：nano / hydro / cyto / glass / metal
PRESET_MATERIALS = {
    # --- 金属 ---
    "gold":      dict(base=(1.00, 0.77, 0.34), metallic=1.0, roughness=0.18),
    "silver":    dict(base=(0.95, 0.95, 0.97), metallic=1.0, roughness=0.10),
    "titanium":  dict(base=(0.62, 0.64, 0.68), metallic=1.0, roughness=0.32),
    "platinum":  dict(base=(0.89, 0.89, 0.90), metallic=1.0, roughness=0.22),

    # --- 生物 / 发光 ---
    "membrane":  dict(base=(0.35, 0.55, 0.85), roughness=0.45, transmission=0.25, ior=1.36),
    "cytoplasm": dict(base=(0.55, 0.75, 0.90), roughness=0.30, transmission=0.45, ior=1.35, subsurface=0.35),
    "nucleus":   dict(base=(0.45, 0.25, 0.65), roughness=0.35, subsurface=0.40),
    "mitoEmit":  dict(base=(1.00, 0.35, 0.25), emission=(1.00, 0.32, 0.18), emission_strength=2.6, roughness=0.5),
    "mitoGreen": dict(base=(0.25, 1.00, 0.45), emission=(0.20, 1.00, 0.40), emission_strength=2.2, roughness=0.5),
    "dapi":      dict(base=(0.15, 0.35, 1.00), emission=(0.15, 0.30, 1.00), emission_strength=1.8, roughness=0.6),
    "peptideL":  dict(base=(0.95, 0.42, 0.28), roughness=0.35, subsurface=0.25),
    "peptideD":  dict(base=(0.30, 0.52, 0.95), roughness=0.35, subsurface=0.25),

    # --- 纳米材料 ---
    "silica":    dict(base=(0.85, 0.88, 0.92), roughness=0.15, transmission=0.85, ior=1.46),
    "msn":       dict(base=(0.80, 0.85, 0.90), roughness=0.22, transmission=0.75, ior=1.45),
    "plga":      dict(base=(0.90, 0.88, 0.82), roughness=0.40, subsurface=0.20, transmission=0.15),
    "hydrogel":  dict(base=(0.70, 0.88, 0.95), roughness=0.12, transmission=0.92, ior=1.40, subsurface=0.10),
    "collagen":  dict(base=(0.92, 0.78, 0.72), roughness=0.42, subsurface=0.45),
    "hydroxyapatite": dict(base=(0.94, 0.93, 0.88), roughness=0.28, subsurface=0.30),

    # --- 通用 ---
    "glass":     dict(base=(0.90, 0.95, 1.00), roughness=0.03, transmission=1.0, ior=1.50),
    "water":     dict(base=(0.75, 0.90, 1.00), roughness=0.02, transmission=1.0, ior=1.333),
    "matteDark": dict(base=(0.04, 0.04, 0.05), roughness=0.85),
    "matteWhite":dict(base=(0.92, 0.92, 0.92), roughness=0.80),
    "chrome":    dict(base=(1.00, 1.00, 1.00), metallic=1.0, roughness=0.02),
    "emissiveWhite": dict(base=(1, 1, 1), emission=(1, 1, 1), emission_strength=3.0),
}


def make_material(name, spec=None, preset=None, **kwargs):
    """
    创建 Cycles 材质。
    spec: dict，键为语义名（见 PRESET_MATERIALS），也接受 base/metallic/roughness 等
    preset: 使用预设名
    """
    if preset:
        base_kwargs = dict(PRESET_MATERIALS.get(preset, {}))
    else:
        base_kwargs = {}
    merged = dict(base_kwargs)
    if spec:
        merged.update(spec)
    merged.update(kwargs)

    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = compat.principled(mat)

    setf = compat.set_float
    if "base" in merged and merged["base"] is not None:
        rgba = merged["base"]
        if len(rgba) == 3:
            rgba = (*rgba, 1.0)
        setf(bsdf, "base_color", rgba)
    if merged.get("metallic") is not None:
        setf(bsdf, "metallic", merged["metallic"])
    if merged.get("roughness") is not None:
        setf(bsdf, "roughness", merged["roughness"])
    if merged.get("transmission") is not None:
        setf(bsdf, "transmission", merged["transmission"])
    if merged.get("ior") is not None:
        setf(bsdf, "ior", merged["ior"])
    if merged.get("subsurface") is not None:
        setf(bsdf, "subsurface", merged["subsurface"])
    if merged.get("subsurface_radius") is not None:
        vec = merged["subsurface_radius"]
        setf(bsdf, "subsurface_radius",
             vec if len(vec) == 3 else (vec[0], vec[0], vec[0]))
    if merged.get("emission") is not None:
        em = merged["emission"]
        if len(em) == 3:
            em = (*em, 1.0)
        setf(bsdf, "emission", em)
    if merged.get("emission_strength") is not None:
        setf(bsdf, "emission_strength", merged["emission_strength"])
    if merged.get("specular") is not None:
        setf(bsdf, "specular", merged["specular"])
    if merged.get("coat") is not None:
        setf(bsdf, "coat", merged["coat"])
    if merged.get("sheen") is not None:
        setf(bsdf, "sheen", merged["sheen"])
    if merged.get("alpha") is not None:
        setf(bsdf, "alpha", merged["alpha"])
        try:
            mat.blend_method = "BLEND" if merged["alpha"] < 1.0 else "OPAQUE"
        except Exception:
            pass

    return mat


# ==================== 灯光 ====================
def add_light(name, kind="AREA", location=(0, 0, 5), energy=500,
              size=4.0, color=(1, 1, 1), rotation=None, target=(0, 0, 0)):
    """添加灯光，返回 Object"""
    light_data = bpy.data.lights.new(name=name, type=kind)
    light_data.energy = energy
    light_data.color = color
    if kind in ("AREA",) and hasattr(light_data, "size"):
        light_data.size = size
    elif kind in ("POINT", "SPOT") and hasattr(light_data, "shadow_soft_size"):
        light_data.shadow_soft_size = size

    obj = bpy.data.objects.new(name=name, object_data=light_data)
    obj.location = location
    bpy.context.collection.objects.link(obj)

    if rotation is not None:
        obj.rotation_euler = rotation
    else:
        # 默认朝向目标点
        aim_at(obj, target)
    return obj


def aim_at(obj, target=(0, 0, 0), axis="-Z", up="Y"):
    """让物体 -Z 轴（Blender 相机/面光默认朝向）对准目标"""
    loc = Vector(obj.location)
    tgt = Vector(target)
    direction = tgt - loc
    if direction.length == 0:
        return obj
    obj.rotation_euler = direction.to_track_quat(axis, up).to_euler()
    return obj


def three_point_rig(center=(0, 0, 1), distance=8.0, height=6.0,
                    key_energy=900, fill_ratio=0.35, rim_ratio=0.7,
                    key_color=(1.0, 0.96, 0.90), rim_color=(0.55, 0.75, 1.0)):
    """
    电影级三点布光：Key（主光）+ Fill（补光）+ Rim（轮廓光）
    这是让画面脱离"塑料感"的关键一步
    """
    import math
    cx, cy, cz = center

    key_pos = (cx + distance * 0.8, cy - distance * 0.9, cz + height)
    fill_pos = (cx - distance * 1.0, cy - distance * 0.4, cz + height * 0.5)
    rim_pos = (cx - distance * 0.7, cy + distance * 1.0, cz + height * 0.9)

    key = add_light("Key_Light", "AREA", key_pos, energy=key_energy,
                    size=distance * 0.9, color=key_color, target=center)
    fill = add_light("Fill_Light", "AREA", fill_pos,
                     energy=key_energy * fill_ratio, size=distance * 1.2,
                     color=(0.85, 0.90, 1.0), target=center)
    rim = add_light("Rim_Light", "AREA", rim_pos,
                    energy=key_energy * rim_ratio, size=distance * 0.7,
                    color=rim_color, target=center)
    return {"key": key, "fill": fill, "rim": rim}


# ==================== 相机 ====================
def add_camera(name="Camera", location=(8, -8, 5), target=(0, 0, 1),
               lens=50, sensor_width=36, fstop=None, focus_target=None):
    """添加并瞄准相机"""
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = lens
    cam_data.sensor_width = sensor_width
    cam = bpy.data.objects.new(name, cam_data)
    cam.location = location
    bpy.context.collection.objects.link(cam)
    aim_at(cam, target)

    # 景深（虚化）：拉开近处/远处 Powell 感
    if fstop:
        cam_data.dof.use_dof = True
        cam_data.dof.focus_object = focus_target
        cam_data.dof.aperture_fstop = fstop
    return cam


def orbit_position(target=(0, 0, 1), radius=10, azimuth_deg=45,
                   elevation_deg=25, unit="deg"):
    """由球坐标计算环绕机位"""
    import math
    az = math.radians(azimuth_deg)
    el = math.radians(elevation_deg)
    x = radius * math.cos(el) * math.cos(az)
    y = radius * math.cos(el) * math.sin(az)
    z = radius * math.sin(el)
    tx, ty, tz = target
    return (tx + x, ty + y, tz + z)


# ==================== 基础几何 ====================
def add_mesh(kind="CUBE", name=None, location=(0, 0, 0), rotation=(0, 0, 0),
             scale=(1, 1, 1), **kwargs):
    """统一的基本体入口"""
    name = name or kind.capitalize()
    kind = kind.upper()
    ops_map = {
        "CUBE":    lambda: bpy.ops.mesh.primitive_cube_add(**kwargs),
        "SPHERE":  lambda: bpy.ops.mesh.primitive_uv_sphere_add(**kwargs),
        "ICO":     lambda: bpy.ops.mesh.primitive_ico_sphere_add(**kwargs),
        "CYLINDER":lambda: bpy.ops.mesh.primitive_cylinder_add(**kwargs),
        "CONE":    lambda: bpy.ops.mesh.primitive_cone_add(**kwargs),
        "PLANE":   lambda: bpy.ops.mesh.primitive_plane_add(**kwargs),
        "TORUS":   lambda: bpy.ops.mesh.primitive_torus_add(**kwargs),
        "MONKEY":  lambda: bpy.ops.mesh.primitive_monkey_add(**kwargs),
    }
    if kind not in ops_map:
        raise ValueError("不支持的基本体: %s" % kind)
    ops_map[kind]()
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    obj.location = location
    obj.rotation_euler = rotation
    obj.scale = scale
    return obj


def apply_material(obj, mat):
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    return obj


def link_new(obj):
    """确保物体已链接到场景集合"""
    if obj.name not in bpy.context.collection.objects:
        bpy.context.collection.objects.link(obj)
    return obj
