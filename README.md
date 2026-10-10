# b3d — 一句话生成电影级 3D 图像与视频

把自然语言指令变成 Cycles 光追渲染的 3D 静帧或短视频。**不需要打开 Blender 界面，不需要写任何 Blender 脚本。**

```bash
blender --background --python b3d/cli.py -- "一个金色的纳米颗粒，暗色背景，电影感灯光，高清"
```

一句话，出一张 1920×1080 的光追图。

---

## 为什么做这个

科研人员做材料 / 生物可视化时，痛点不在"会不会 Blender"，而在：

- 打开软件 → 建模 → 调材质 → 布光 → 调渲染参数 → 出图，重复劳动占 90%
- 想改个角度要重走全流程
- 结果不可复现：上次那个图的灯光参数是啥？忘了

b3d 的思路：**把渲染决策压缩成一句话，其余交给引擎**。同一句话永远出同一张图（`--seed` 固定），参数自动写进 manifest，可追溯。

---

## 快速开始

### 1. 环境要求

| 组件 | 版本 | 说明 |
|---|---|---|
| Blender | ≥ 3.0（推荐 4.x LTS） | 3.0 以下未测试 |
| GPU | NVIDIA（OptiX/CUDA） | 无 GPU 会退化为 CPU，**慢 5–7 倍** |
| ffmpeg | 任意近版 | 仅导出视频时需要 |
| NVIDIA 驱动 | ≥ 610.00 | **仅影响视频硬编速度**，低于此版本自动回退软编 |

> ⚠️ **Blender 2.83（Python 3.7）不适用。** 本引擎依赖 Cycles X 与新版 Principled BSDF 接口。
> 若你机器上装的是 2.8x，建议升级。国内镜像很快：
> `https://mirrors.tuna.tsinghua.edu.cn/blender/release/` （实测 13 MB/s）

### 2. 安装

```bash
git clone https://github.com/qianluis/blender-prompt-engine.git
```

`b3d/` 是一个纯 Python 包，无需 pip 安装。关键是让 Blender 能找到它：

```bash
# 方式一：放在 Blender 的 scripts/modules 下（永久）
cp -r b3d  "<Blender安装目录>/<版本>/scripts/modules/"

# 方式二：每次用绝对路径调用 CLI（临时，推荐先这样试）
blender --background --python /path/to/b3d/cli.py -- "你的指令"
```

### 3. 第一次运行

先不渲染，只看看引擎怎么理解你的话（秒回）：

```bash
blender --background --python b3d/cli.py -- "水凝胶网络，透明背景" --explain
```

```
  主体：1 个 ICO（材质 hydrogel）
  背景：transparent
  布光：cinematic
  镜头：中景
  质量：标准
  输出：单帧图片
```

确认理解无误，再真正出图：

```bash
blender --background --python b3d/cli.py -- "水凝胶网络，透明背景" --out-name gel.png
```

---

## 指令怎么写

引擎是**宽容解析**：多个维度可以任意组合，顺序不限，缺哪个用默认值。

```
[数量] + [主体] + [材质/颜色] + [背景] + [布光] + [镜头] + [质量] + [动画]
```

### 实际例子

```bash
# 单颗金纳米颗粒，经典暗调封面
"一个金色的纳米颗粒，暗色背景，电影感灯光，高清"

# 30 颗 PLGA 微球聚集体
"30个PLGA微球聚在一起，白色背景，棚拍，特写"

# 透明背景抠图（直接贴进 PPT / 论文）
"介孔硅纳米球，透明背景，4K"

# 5 秒环绕动画
"发光线粒体绕圈，5秒动画，标准"
```

### 支持的关键词

<details>
<summary><b>主体</b></summary>

纳米颗粒 · 纳米球 · 微球 · 介孔硅 · 二氧化硅 · 水凝胶 · 胶束 · 细胞 ·
细胞核 · 线粒体 · 多肽 · 纤维 · 胶原 · 羟基磷灰石 · 正方体 · 圆柱 · 圆环 ·
`sphere` `cube` `cylinder` `torque` 等英文
</details>

<details>
<summary><b>材质 / 颜色</b></summary>

`gold` 金色 · `silver` 银 · `titanium` 钛 · `glass` 玻璃/透明 · `chrome` 镜面 ·
`water` 水 · `silica` · `msn` 介孔 · `plga` · `hydrogel` · `collagen` ·
`hydroxyapatite` · 发光红 / 发光绿 / `dapi` 蓝 · L肽 / D肽 · 哑光白 / 哑光黑
</details>

<details>
<summary><b>背景</b></summary>

暗色背景 · 黑色背景 · 白色背景 · 渐隐背景 · 蓝色渐变 · **透明背景**（抠图用）
</details>

<details>
<summary><b>布光</b></summary>

`cinematic` 电影感（默认，三点光） · `studio` 棚拍 · `three_point` ·
`rim` 轮廓光 · `soft` 柔和 · `dramatic` 高对比
</details>

<details>
<summary><b>镜头</b></summary>

`特写` 微距 · `近景` · `中景`（默认）· `全景` · `俯视` · `仰视` · `平视`
</details>

<details>
<summary><b>质量档位</b></summary>

| 档位 | 分辨率 | 采样 | 典型耗时¹ |
|---|---|---|---|
| 预览 | 960×540 | 32 | ~2 s |
| 草稿 | 1280×720 | 64 | ~4 s |
| 标准 | 1920×1080 | 192 | ~14 s |
| 高清 | 1920×1080 | 320 | ~24 s |
| 2k | 2560×1440 | 384 | ~45 s |
| 4k | 3840×2160 | 512 | ~90 s |
| 出版级 | 3840×2160 | 768 | ~140 s |

¹ RTX 3070 Ti Laptop（8GB）实测，单主体场景。多体簇会相应增加。
</details>

<details>
<summary><b>科研模板</b>（走专用几何，不是普通基本体）</summary>

| 关键词 | 生成内容 | 适用课题 |
|---|---|---|
| `胶原三螺旋` / `三螺旋` | 三条 α 链互缠 | IVDD / 胶原结合肽 |
| `螺旋` / `α螺旋` | α-螺旋球棍模型 | 二级结构示意 |
| `自组装纤维` / `纳米纤维` | 随机取向纤维网络 | 肽自组装水凝胶 |
| `多孔网络` / `网络结构` | 节点+连通支柱 | 水凝胶支架形貌 |
| `核壳` / `核壳结构` | 同心核壳颗粒 | 药物递送 / 多功能探针 |
| `介孔硅` / `介孔` | 表面规则孔道球 | MSN 载体表征 |
</details>

<details>
<summary><b>动画</b></summary>

`orbit` 相机环绕 · `spin` 物体自转 · `dolly_in` 推进 · `dolly_out` 拉远 · `rise` 上升

触发视频需要**同时**出现动画词和视频意图（"动画"/"视频"/"5秒"等）。
只说"旋转"而没说要视频，默认仍出静帧。

> 动画实现用的是**空物体做轨道驱动**，相机作为子级跟随。
> 不是逐帧打关键帧——后者会产生 帧数×通道数 个关键帧（72帧=432个），
> 而驱动方案只有 2 个，改速度改半径都更容易。
</details>

---

## CLI 参数

| 参数 | 说明 |
|---|---|
| `--out-name NAME` | 输出文件名 |
| `--out-dir DIR` | 输出目录（默认 `outputs/`） |
| `--quality 档位` | 覆盖指令里的质量词 |
| `--seed N` | 随机种子，**固定.seed 保证结果完全可复现** |
| `--dof F` | 景深光圈值（如 `2.8`），数值越小背景越虚 |
| `--no-ground` | 不加地面板（物体会失去接触阴影） |
| `--keep-frames` | 导出视频时保留序列帧 |
| `--explain` | 只解析不渲染，用于确认理解 |
| `--ffmpeg-dir DIR` | 手动指定 ffmpeg 目录 |

---

## 在 Python 里用

```python
import b3d

# 出图
r = b3d.make("一个金色的纳米颗粒，电影感灯光", quality="高清")
print(r["path"], r["seconds"])

# 批量
prompts = ["水凝胶网络", "介孔硅纳米球", "PLGA微球堆积"]
b3d.make_batch(prompts, quality="标准")

# 只要结构化 spec，自己接别的渲染器
spec = b3d.spec_from_prompt("30个微球")
```

---

## 架构

```
指令文本
   ↓  parser.py        规则+词典，纯 Python，离线可用
SceneSpec (JSON)
   ↓  scene.py         装配：布局/材质/灯光/相机/动画
Blender 场景
   ↓  renderer.py      Cycles + OptiX，出 PNG / 序列帧
图片 or MP4
```

| 文件 | 职责 |
|---|---|
| `parser.py` | 自然语言 → SceneSpec。纯 Python，不依赖 Blender，可单测 |
| `scene.py` | SceneSpec → Blender 场景图 |
| `builders.py` | 材质库 / 灯光组 / 相机 / 几何 的语义化工厂 |
| `renderer.py` | 渲染与视频编码，含 GPU 自检 |
| `compat.py` | **屏蔽 Blender 版本差异**，所有跨版本坑关在这里 |
| `templates.py` | 科研专用几何：球棍分子 / 螺旋 / 纤维网络 / 多孔 / 核壳 / 介孔 |
| `cli.py` | 命令行入口 |
| `engine.py` | 对外 API：`make()` |
| `check_env.py` | 环境自检，不需要打开 Blender 就能跑 |

### 设计取舍

**为什么不用 LLM 来解析指令？**
规则解析是确定性的——同一句话永远得到同一张图，这对科研可复现性是硬需求。
而且离线可用，不依赖 API key，不产生费用。
代价是覆盖不了长尾表达；真遇到歧义，用 `--explain` 看理解对不对，再调整措辞。

**为什么所有版本差异都关在 `compat.py`？**
Blender 改接口名很随意（2.8x 的 `Transmission` → 4.x 的 `Transmission Weight`；
4.5 又删了 `get_devices()`）。散落各处的版本判断早晚会漏。集中在一处，升级 Blender 只改一个文件。

---

## 踩过的坑（也是这里最值钱的部分）

1. **配了 OptiX 却仍在 CPU 上跑。** 偏好里选后端 (`prefs.compute_device_type`)
   和场景用 GPU (`scene.cycles.device`) 是**两件事**。漏掉后者会静默退化。
   实测 1920×1080/192 samples：CPU 94 s vs GPU 14 s，**差 6.6 倍**。
   现在 `renderer.py` 有 `assert_gpu_active()` 自检，未生效会明确报警。

2. **`scene.render.engine = "CYCLES"` 需要 cycles addon 已激活**，否则赋值静默失败。
   已改为在 `set_render_defaults` 里显式 `addon_utils.enable("cycles")`。

3. **中文正则不能用 `\b`。** Python 里中文属于 `\w`，`"10秒动画"` 中 `秒` 和 `动`
   之间**不存在词边界**，`r"(\d+)秒\b"` 永远匹配不上。中文 NLU 里这是个高频坑。

4. **Windows 下 ffmpeg 必须注入 PATH**（`renderer.inject_ffmpeg`），
   否则 Blender 调子进程报 `WinError 2`。

5. **`\b` 之外，中文量词也别漏。** "一簇""几个""若干"要映射到具体数量，
   否则用户说"一簇金纳米棒"只会得到孤零零一颗。

6. **`--factory-startup` 会清空 addon 状态。** 每次 `--background` 调用都是干净环境，
   GPU 后端必须在脚本里每次重设，指望用户手工配好的偏好是没用的。

7. **PATH 里的 ffmpeg 可能是假的。** WinGet 装的是 `%LOCALAPPDATA%\...\WinGet\Links\ffmpeg.EXE`，
   那是个转发桩。Python `subprocess` 直接调用报
   `[WinError 193] %1 不是有效的 Win32 应用程序`，必须解析到真实 exe
   （见 `renderer.resolve_ffmpeg`）。

8. **编码器"存在"≠"能用"。** `ffmpeg -encoders` 里能看到 `h264_nvenc`，
   但实际打不开：ffmpeg 9.x 要求 NVENC API 13.1 / 驱动 ≥ 610，
   而驱动 592.x 只有 API 13.0。得**实跑一次**才能确认
   （见 `renderer.probe_nvenc`，0.6 秒出结论，结果缓存）。

---

## 路线图

- [x] 中文指令解析
- [x] Cycles + OptiX GPU 渲染
- [x] 单帧 / 序列帧 / MP4（NVENC 硬编）
- [x] 多体分布（斐波那契球面 + 抖动）
- [x] 景深（DOF）
- [ ] 分子结构渲染（PDB / 球棍模型）
- [ ] 自定义材质 Preset 与外部 HDRI 环境光
- [ ] 批量 + 多视角出图（同一场景 8 个角度）
- [ ] 可选 LLM 后端解析长尾指令

---

## License

MIT
