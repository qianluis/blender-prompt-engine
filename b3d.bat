@echo off
REM ============================================================
REM  b3d 快捷入口 (Windows)
REM
REM  用法:
REM    b3d.bat "一个金色的纳米颗粒，电影感灯光"
REM    b3d.bat "水凝胶网络，4K" --out-name gel.png
REM    b3d.bat "微球环绕，8秒动画" --quality 草稿
REM
REM  如果 Blender 不在下面的默认路径，改 BLENDER_EXE 即可。
REM ============================================================
setlocal

set "PKG_DIR=%~dp0"

REM ---- Blender 路径：按你的实际情况修改这一行 ----
set "BLENDER_EXE=D:\_blender_lab\blender\blender-4.5.12-windows-x64\blender.exe"

if not exist "%BLENDER_EXE%" (
    set "BLENDER_EXE=C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"
)
if not exist "%BLENDER_EXE%" (
    set "BLENDER_EXE=C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"
)

if not exist "%BLENDER_EXE%" (
    echo.
    echo [错误] 找不到 Blender。
    echo 请编辑本文件，把 BLENDER_EXE 改成你机器上的真实路径。
    echo.
    echo 当前尝试过的路径见脚本顶部注释。
    exit /b 1
)

"%BLENDER_EXE%" --background --python "%PKG_DIR%b3d\cli.py" -- %*

endlocal
