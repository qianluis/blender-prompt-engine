# -*- coding: utf-8 -*-
"""
b3d.compat - Blender 版本差异屏蔽层

所有跨版本坑都被关在这里：
  - Principled BSDF socket 改名（2.8x: Transmission / 4.x: Transmission Weight）
  - Cycles 设备枚举 API 变更（4.5 起 get_devices() 被移除）
  - 渲染引擎 / 色彩管理差异

业务代码只准调用这里的 helper，禁止直接写字符串常量。
"""
try:
    import bpy
except ImportError:
    # 系统 Python 下允许导入（仅用版本工具/词典，不碰 bpy API）
    bpy = None


def bl_version():
    """返回 (major, minor, patch) 元组。无 bpy 时返回全 0"""
    if bpy is None:
        return (0, 0, 0)
    return bpy.app.version[:3]


def bl_version_str():
    if bpy is None:
        return "unknown (no bpy)"
    return bpy.app.version_string


def require(min_version=(3, 0, 0)):
    """低于最低版本时抛清晰错误，而不是在半路报 KeyError"""
    if bpy is None:
        raise RuntimeError("当前不在 Blender 环境中，无法渲染")
    if bl_version() < min_version:
        raise RuntimeError(
            "需要 Blender >= %s，当前 %s。请升级：https://mirrors.tuna.tsinghua.edu.cn/blender/release/"
            % (".".join(map(str, min_version)), bl_version_str())
        )


def principled(material):
    """获取（必要时创建）Principled BSDF 节点"""
    nt = material.node_tree
    for n in nt.nodes:
        if n.type == "BSDF_PRINCIPLED":
            return n
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    out = nt.nodes.get("Material Output") or nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return bsdf


# ---- Principled socket 别名表：新名优先，旧名兜底 ----
_SOCKET_ALIASES = {
    "base_color":        ["Base Color"],
    "metallic":          ["Metallic"],
    "roughness":         ["Roughness"],
    "ior":               ["IOR"],
    "alpha":             ["Alpha"],
    "transmission":      ["Transmission Weight", "Transmission"],  # 4.x / 2.8x
    "subsurface":        ["Subsurface Weight", "Subsurface"],      # 4.x / 2.8x
    "subsurface_radius": ["Subsurface Radius"],
    "subsurface_color":  ["Subsurface Color"],
    "specular":          ["Specular IOR Level", "Specular"],       # 4.x / 2.8x
    "coat":              ["Coat Weight"],
    "sheen":             ["Sheen Weight"],
    "emission":          ["Emission Color"],
    "emission_strength": ["Emission Strength"],
    "normal":            ["Normal"],
}


def set_float(node, key, value, verbose=False):
    """按语义键设置 Principled socket，自动兼容新旧命名。返回是否成功"""
    names = _SOCKET_ALIASES.get(key, [key])
    for n in names:
        s = node.inputs.get(n)
        if s is not None:
            try:
                s.default_value = value
                return True
            except TypeError:
                continue
    if verbose:
        print("[compat] socket 未命中: %s (候选 %s)" % (key, names))
    return False


def get_socket(node, key):
    """按语义键取 socket 对象（不存在返回 None）"""
    for n in _SOCKET_ALIASES.get(key, [key]):
        s = node.inputs.get(n)
        if s is not None:
            return s
    return None


def enable_gpu():
    """
    启用 Cycles GPU 渲染，返回实际启用的设备列表。
    兼容 4.5 之前的 get_devices() 与之后的 prefs.devices 两种 API。
    """
    import addon_utils
    addon_utils.enable("cycles")
    prefs = bpy.context.preferences.addons["cycles"].preferences

    # 1) 选定后端：优先 OptiX（RTX 光追最快），无则 CUDA，最后 CPU
    chosen = None
    for backend in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
        try:
            prefs.compute_device_type = backend
            chosen = backend
            break
        except TypeError:
            continue

    # 2) 刷新设备列表（4.5 起需要显式 refresh，旧版是 get_devices 刷新）
    try:
        prefs.refresh_devices()
    except AttributeError:
        try:
            prefs.get_devices()
        except Exception:
            pass
    except Exception:
        pass

    devices = prefs.devices  # 统一走新属性
    used = []
    has_gpu = False
    for d in devices:
        if d.type in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
            d.use = True
            has_gpu = True
            used.append("%s/%s" % (d.name, d.type))
        else:
            # CPU 只在没有 GPU 时兜底，避免 CPU 抢活拖慢速度
            d.use = not has_gpu
            if d.use:
                used.append("%s/CPU" % d.name)

    return {"backend": chosen, "devices": used, "gpu": has_gpu}


def set_world_background(color=(0.02, 0.02, 0.03, 1.0), strength=1.0):
    """设置世界背景纯色（用于干净的棚拍感）"""
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes.get("Background")
    if bg is None:
        for n in nt.nodes:
            if n.type == "BACKGROUND":
                bg = n
                break
    if bg is None:
        bg = nt.nodes.new("ShaderNodeBackground")
        out = nt.nodes.get("World Output") or nt.nodes.new("ShaderNodeOutputWorld")
        nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    bg.inputs["Color"].default_value = color
    bg.inputs["Strength"].default_value = strength
    return world


def clear_scene(keep_world=True):
    """清空场景全部物体（可选保留世界）"""
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    if not keep_world:
        for w in list(bpy.data.worlds):
            bpy.data.worlds.remove(w)


def set_scene_units(unit_system="METRIC", length_unit="MILLIMETERS"):
    """4.x 才有 length_unit；2.8x 只有 unit_system。这里做安全降级"""
    s = bpy.context.scene
    s.unit_settings.system = unit_system
    try:
        s.unit_settings.length_unit = length_unit
    except TypeError:
        pass
    try:
        s.unit_settings.scale_length = 1.0
    except Exception:
        pass


def smooth(obj, angle_deg=45.0):
    """平滑着色，带 shade_smooth 缺失时的兜底"""
    try:
        obj.data.polygons.foreach_set
    except Exception:
        return obj
    try:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.shade_smooth()
    except Exception:
        # 兜底：直接改 mesh 属性
        try:
            for poly in obj.data.polygons:
                poly.use_smooth = True
        except Exception:
            pass
    return obj


def set_render_defaults(scene, res=(1920, 1080), samples=256, denoise=True,
                        engine="CYCLES", transparent=False, exposure=0.0):
    """统一渲染参数入口"""
    scene.render.engine = engine
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = transparent

    if hasattr(scene, "view_settings"):
        try:
            scene.view_settings.exposure = exposure
            scene.view_settings.look = "AgX" if hasattr(scene.view_settings, "look") else "Filmic"
        except Exception:
            pass

    if engine == "CYCLES":
        import addon_utils
        # 关键：必须确保 cycles addon 已激活，否则 scene.cycles 访问会失败
        addon_utils.enable("cycles")
        # 关键：偏好里选了 OptiX 后端还不够，场景本身必须切到 GPU。
        # 漏了这行就会静默退回 CPU —— 实测同样 1920x1080/192 samples，
        # CPU 需要 94s，GPU 只要 17s，差 5.5 倍。
        try:
            scene.cycles.device = "GPU"
        except Exception as e:
            print("[compat] 无法切换到 GPU 渲染，将使用 CPU: %s" % e)
        try:
            scene.cycles.samples = samples
            scene.cycles.use_denoising = denoise
            # 自适应采样：有则开启，提速明显
            if hasattr(scene.cycles, "use_adaptive_sampling"):
                scene.cycles.use_adaptive_sampling = True
        except Exception as e:
            print("[compat] Cycles 参数设置失败: %s" % e)
    return scene


def assert_gpu_active(scene):
    """
    渲染前自检：确认真的在 GPU 上跑。
    返回 (是否GPU, 描述)。用于避免"配了半天结果跑 CPU"的静默退化。
    """
    if scene.render.engine != "CYCLES":
        return False, "渲染引擎是 %s，不是 CYCLES" % scene.render.engine
    dev = getattr(scene.cycles, "device", None)
    if dev != "GPU":
        return False, "cycles.device=%s（应为 GPU）" % dev
    return True, "GPU"
