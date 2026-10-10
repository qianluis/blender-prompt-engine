# -*- coding: utf-8 -*-
"""
b3d.templates - 科研专用场景模板

通用生成器解决了"从 0 到 1"，但科研可视化有它自己的套路：
  - 肽 / 蛋白要给球棍模型，不是光溜溜一个球
  - 自组装要看螺旋 / 纤维的周期性
  - 水凝胶要看内部网络和多孔结构
  - 对比图要求风格严格一致（同一批 Fig 不能有的亮有的暗）

这里提供的是"半结构化模板"：参数化，但保留科研语义。
"""
import math
import random
import bpy
from mathutils import Vector
from . import compat, builders
from .builders import make_material


# ==================== 肽 / 分子：球棍模型 ====================
# 常用氨基酸的 CPK 着色（简化为元素色）
ELEMENT_COLORS = {
    "C":  (0.30, 0.30, 0.32),   # 碳 - 深灰
    "N":  (0.20, 0.35, 0.90),   # 氮 - 蓝
    "O":  (0.90, 0.20, 0.15),   # 氧 - 红
    "H":  (0.95, 0.95, 0.95),   # 氢 - 白
    "S":  (0.95, 0.85, 0.25),   # 硫 - 黄
    "P":  (1.00, 0.55, 0.15),   # 磷 - 橙
}

ELEMENT_RADII = {"H": 0.32, "C": 0.48, "N": 0.52, "O": 0.50,
                 "S": 0.60, "P": 0.62}


def build_ball_stick(atoms, bonds, name="Molecule",
                     stick_radius=0.12, ball_scale=1.0,
                     stick_material=None, emissive_atoms=None):
    """
    球棍模型。

    atoms: [(元素符号, (x,y,z)), ...]
    bonds: [(索引i, 索引j), ...]
    emissive_atoms: 需要发光标记的原子索引列表（如标记某个功能位点）

    这是分子可视化的通用底座：PDB 解析完后直接喂进来。
    """
    objs = []
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)

    if stick_material is None:
        stick_material = make_material(
            name + "_Stick",
            base=(0.55, 0.57, 0.60), roughness=0.35, metallic=0.0)

    # --- 球（原子）---
    for i, (elem, pos) in enumerate(atoms):
        r = ELEMENT_RADII.get(elem, 0.45) * ball_scale
        is_emit = emissive_atoms and i in emissive_atoms
        mat_name = "%s_%s_%d" % (name, elem, i) if is_emit else "%s_%s" % (name, elem)
        mat = bpy.data.materials.get(mat_name)
        if mat is None:
            mat = make_material(
                mat_name, base=ELEMENT_COLORS.get(elem, (0.5, 0.5, 0.5)) + (1.0,),
                roughness=0.28,
                emission=ELEMENT_COLORS.get(elem, (0.5, 0.5, 0.5)) + (1.0,) if is_emit else None,
                emission_strength=2.2 if is_emit else 0.0)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=r, location=pos)
        obj = bpy.context.object
        obj.name = "%s_atom_%03d_%s" % (name, i, elem)
        builders.apply_material(obj, mat)
        compat.smooth(obj)
        # 从原 collection 移到分子组
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        collection.objects.link(obj)
        objs.append(obj)

    # --- 棍（化学键）---
    for (i, j) in bonds:
        if i >= len(atoms) or j >= len(atoms):
            continue
        p1 = Vector(atoms[i][1])
        p2 = Vector(atoms[j][1])
        mid = (p1 + p2) / 2
        direction = p2 - p1
        length = direction.length
        if length < 1e-6:
            continue

        bpy.ops.mesh.primitive_cylinder_add(
            vertices=16, radius=stick_radius, depth=length, location=mid)
        stick = bpy.context.object
        stick.name = "%s_bond_%03d_%03d" % (name, i, j)
        # 圆柱默认沿 Z 轴，旋转到键方向
        stick.rotation_mode = 'QUATERNION'
        stick.rotation_quaternion = direction.to_track_quat('Z', 'Y')
        builders.apply_material(stick, stick_material)
        compat.smooth(stick)
        for c in list(stick.users_collection):
            c.objects.unlink(stick)
        collection.objects.link(stick)
        objs.append(stick)

    return {"collection": collection, "objects": objs}


def build_alpha_helix(n_residues=10, radius=0.55, rise=0.15,
                      turn_per_residue=100.0, name="Helix",
                      palette=None, show_stick=True):
    """
    α-螺旋骨架。用于展示肽二级结构 / 胶原三螺旋的单链。

    参数按真实螺旋几何：
      rise = 每残基沿轴上升 ~1.5 Å（这里单位任意，按比例）
      turn_per_residue = 每残基转角 ~100°
    """
    atoms = []
    bonds = []
    for i in range(n_residues):
        ang = math.radians(i * turn_per_residue)
        x = radius * math.cos(ang)
        y = radius * math.sin(ang)
        z = i * rise
        # 主链简化为 CA 原子
        atoms.append(("C", (x, y, z)))
        if i > 0:
            bonds.append((i - 1, i))

    return build_ball_stick(atoms, bonds, name=name,
                           stick_radius=0.09, ball_scale=1.0)


def build_triple_helix(n_residues=12, chain_radius=0.55,
                       helix_radius=0.35, name="CollagenTripleHelix",
                       chain_colors=None):
    """
    胶原三螺旋：三条 α 链互相缠绕。
    对应 IVDD 课题里的胶原三螺旋 / FFFKTTKS 缀合物场景。
    """
    if chain_colors is None:
        chain_colors = [(0.92, 0.78, 0.72),   # 链1 - 胶原米色
                        (0.85, 0.60, 0.45),   # 链2
                        (0.70, 0.72, 0.85)]   # 链3

    all_objs = []
    rnd = random.Random(7)
    for c in range(3):
        offset = c * (2 * math.pi / 3)
        atoms = []
        bonds = []
        for i in range(n_residues):
            ang = math.radians(i * 100.0) + offset
            x = (chain_radius + 0.1 * math.sin(i * 0.7)) * math.cos(ang)
            y = (chain_radius + 0.1 * math.sin(i * 0.7)) * math.sin(ang)
            z = i * 0.16
            atoms.append(("C", (x, y, z)))
            if i > 0:
                bonds.append((i - 1, i))

        mat = make_material("%s_chain%d" % (name, c),
                            base=chain_colors[c] + (1.0,), roughness=0.30)
        stick_mat = make_material("%s_stick%d" % (name, c),
                                  base=tuple(v * 0.82 for v in chain_colors[c]) + (1.0,),
                                  roughness=0.40)
        r = build_ball_stick(atoms, bonds, name="%s_c%d" % (name, c),
                            stick_radius=0.07, stick_material=stick_mat)
        # 覆盖球材质为链色
        for o in r["objects"]:
            if o.name.endswith("_atom_0_C") or "_atom_" in o.name:
                builders.apply_material(o, mat)
        all_objs.extend(r["objects"])

    return {"objects": all_objs}


# ==================== 自组装：纤维网络 ====================
def build_fibril_network(n_fibrils=14, length=8.0, radius=0.09,
                         spread=3.2, seed=11, name="FibrilNetwork",
                         material_preset="collagen"):
    """
    纳米纤维网络 —— 肽自组装 / 水凝胶支架的典型形貌。
    用随机取向的细长圆柱编织成交联网络。
    """
    rnd = random.Random(seed)
    mat = make_material(name + "_Mat", preset=material_preset)
    objs = []
    for i in range(n_fibrils):
        L = length * rnd.uniform(0.65, 1.0)
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=12, radius=radius * rnd.uniform(0.8, 1.3),
            depth=L, location=(rnd.uniform(-spread, spread),
                               rnd.uniform(-spread, spread),
                               rnd.uniform(0.2, spread * 0.8)))
        f = bpy.context.object
        f.name = "%s_%03d" % (name, i)
        f.rotation_euler = (rnd.uniform(0, math.pi),
                            rnd.uniform(0, math.pi),
                            rnd.uniform(0, math.pi))
        builders.apply_material(f, mat)
        compat.smooth(f)
        objs.append(f)
    return objs


# ==================== 水凝胶：多孔网络 ====================
def build_porous_network(n_nodes=26, box=4.0, link_dist=1.9,
                         seed=23, name="Hydrogel",
                         node_material="hydrogel", strut_radius=0.055):
    """
    多孔水凝胶网络：节点 + 连通支柱。
    比单纯一个半透明球更能表达"网络结构"这个信息。
    """
    rnd = random.Random(seed)
    pts = []
    for _ in range(n_nodes):
        pts.append(Vector((rnd.uniform(-box / 2, box / 2),
                           rnd.uniform(-box / 2, box / 2),
                           rnd.uniform(-box / 2, box / 2))))

    node_mat = make_material(name + "_Node", preset=node_material)
    strut_mat = make_material(name + "_Strut", preset=node_material)
    objs = []

    # 节点
    for i, p in enumerate(pts):
        r = rnd.uniform(0.14, 0.24)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=r, location=p)
        n = bpy.context.object
        n.name = "%s_node_%03d" % (name, i)
        builders.apply_material(n, node_mat)
        compat.smooth(n)
        objs.append(n)

    # 支柱：距离小于阈值的节点相连
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            d = (pts[i] - pts[j]).length
            if d < link_dist:
                mid = (pts[i] + pts[j]) / 2
                direction = pts[j] - pts[i]
                bpy.ops.mesh.primitive_cylinder_add(
                    vertices=10, radius=strut_radius, depth=d, location=mid)
                s = bpy.context.object
                s.name = "%s_strut_%03d_%03d" % (name, i, j)
                s.rotation_mode = 'QUATERNION'
                s.rotation_quaternion = direction.to_track_quat('Z', 'Y')
                builders.apply_material(s, strut_mat)
                compat.smooth(s)
                objs.append(s)
    return objs


# ==================== 核壳结构 ====================
def build_core_shell(core_radius=1.0, shell_thickness=0.35,
                     core_preset="gold", shell_preset="silica",
                     location=(0, 0, 1.2), name="CoreShell"):
    """
    核壳纳米颗粒 —— 药物递送 / 多功能探针的标准结构。
    """
    objs = []
    # 核
    bpy.ops.mesh.primitive_ico_sphere_add(
        subdivisions=5, radius=core_radius, location=location)
    core = bpy.context.object
    core.name = name + "_Core"
    builders.apply_material(core, make_material(name + "_CoreMat",
                                                preset=core_preset))
    compat.smooth(core)
    objs.append(core)

    # 壳（半透明）
    bpy.ops.mesh.primitive_ico_sphere_add(
        subdivisions=5, radius=core_radius + shell_thickness, location=location)
    shell = bpy.context.object
    shell.name = name + "_Shell"
    builders.apply_material(shell, make_material(name + "_ShellMat",
                                                 preset=shell_preset))
    compat.smooth(shell)
    objs.append(shell)
    return {"core": core, "shell": shell, "objects": objs}


# ==================== 介孔硅：表面孔道 ====================
def build_mesoporous_sphere(radius=1.2, n_pores=42, pore_depth=0.30,
                            seed=5, location=(0, 0, 1.2),
                            body_preset="msn", pore_preset="matteDark",
                            name="MSN"):
    """
    介孔硅纳米球：球体上挖出规则排布的孔道（用布尔或直接凹面近似）。
    这里用"深色小球嵌入表面"的方式近似，比布尔运算快且不易出错。
    """
    rnd = random.Random(seed)
    objs = []

    bpy.ops.mesh.primitive_ico_sphere_add(
        subdivisions=6, radius=radius, location=location)
    body = bpy.context.object
    body.name = name + "_Body"
    builders.apply_material(body, make_material(name + "_BodyMat",
                                                preset=body_preset))
    compat.smooth(body)
    objs.append(body)

    pore_mat = make_material(name + "_PoreMat", preset=pore_preset)
    # 斐波那契球面分布，保证孔道均匀
    golden = math.pi * (3 - math.sqrt(5))
    for i in range(n_pores):
        y = 1 - (i / max(n_pores - 1, 1)) * 2
        r = math.sqrt(max(1 - y * y, 0))
        theta = golden * i
        direction = Vector((math.cos(theta) * r, math.sin(theta) * r, y))
        pos = Vector(location) + direction * (radius - pore_depth * 0.35)

        bpy.ops.mesh.primitive_ico_sphere_add(
            subdivisions=2, radius=pore_depth * rnd.uniform(0.75, 1.15),
            location=pos)
        p = bpy.context.object
        p.name = "%s_pore_%03d" % (name, i)
        builders.apply_material(p, pore_mat)
        compat.smooth(p)
        objs.append(p)
    return {"body": body, "objects": objs}


# ==================== 科研专用布光 ====================
def scientific_lighting(target=(0, 0, 1.2), distance=9.0,
                       key_energy=1000, bg=(0.015, 0.017, 0.022, 1.0)):
    """
    科研图布光：比"电影感"更克制。
    目标是准确还原形态与材质，而不是制造情绪。
    特点是补光更足、轮廓光更弱，暗部细节保留更多。
    """
    compat.set_world_background(bg, strength=1.0)
    return builders.three_point_rig(
        center=target, distance=distance, key_energy=key_energy,
        fill_ratio=0.55, rim_ratio=0.45,
        key_color=(1.0, 0.98, 0.95), rim_color=(0.75, 0.85, 1.0))


def darkfield_style(target=(0, 0, 1.2), distance=7.0):
    """
    暗场风格：主体自发光 + 极暗环境。
    适合荧光标记 / 发光探针的表达（对应线粒体检测课题）。
    """
    compat.set_world_background((0.0, 0.0, 0.005, 1.0), strength=1.0)
    k = builders.add_light("DF_Key", "AREA", (distance * 0.5, -distance, distance * 0.6),
                           energy=350, size=distance * 0.5, target=target)
    r = builders.add_light("DF_Rim", "AREA", (-distance, distance * 0.6, distance * 0.7),
                           energy=180, size=distance * 0.4,
                           color=(0.6, 0.8, 1.0), target=target)
    return {"key": k, "rim": r}
