@echo off
setlocal
chcp 65001 >nul
title Panasonic DC-S5 闪光灯实时预览 - 一键部署
cd /d "%~dp0"

set "PY_CMD="

where python >nul 2>&1
if not errorlevel 1 (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
    if not errorlevel 1 set "PY_CMD=python"
)
if defined PY_CMD goto :py_ready

where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
    if not errorlevel 1 set "PY_CMD=py -3"
)
if defined PY_CMD goto :py_ready

for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
) do (
    if exist %%P (
        %%P -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
        if not errorlevel 1 (
            set "PY_CMD=%%P"
            goto :py_ready
        )
    )
)

echo [错误] 未检测到 Python 3（需 3.9 及以上版本）。
echo 请先安装 Python 3 并勾选 "Add Python to PATH"，然后重试。
echo.
pause
exit /b 1

:py_ready
if not exist "deploy_shutter_preview.py" (
    echo [错误] 未找到 deploy_shutter_preview.py，请勿移动本脚本。
    echo.
    pause
    exit /b 1
)

set "ACTION=deploy"
if not "%~1"=="" set "ACTION=%~1"

:run_action
echo ============================================================
echo   Panasonic DC-S5 (FW 2.9) 闪光灯实时预览 - 一键部署工具
echo ============================================================
if /i "%ACTION%"=="deploy" (
    echo [操作] 正在部署闪光灯实时预览...
    echo [提示] 看到 "Installation armed" 后，请拨动机身 ISO 一格完成激活。
) else if /i "%ACTION%"=="replace" (
    echo [操作] 正在替换并重新部署...
    echo [提示] 看到 "Removal armed" / "Installation armed" 时，请分别拨动机身 ISO 一格。
) else if /i "%ACTION%"=="rollback" (
    echo [操作] 正在回滚卸载（请先确保相机已退出 Fn2 实时预览）...
    echo [提示] 看到 "Removal armed" 后，请拨动机身 ISO 一格完成卸载。
) else if /i "%ACTION%"=="status" (
    echo [操作] 正在查询相机当前状态...
) else (
    echo [操作] 正在执行: %ACTION%
)
echo ------------------------------------------------------------
echo.

%PY_CMD% -u "deploy_shutter_preview.py" %ACTION%
set "RC=%ERRORLEVEL%"

echo.
echo ------------------------------------------------------------
if "%RC%"=="0" (
    if /i "%ACTION%"=="deploy" (
        echo [成功] 部署完成并已验证运行！点按机身 Fn2 即可开启/关闭实时预览。
    ) else if /i "%ACTION%"=="replace" (
        echo [成功] 替换部署完成并已验证运行！
    ) else if /i "%ACTION%"=="rollback" (
        echo [成功] 已回滚恢复原厂入口字节。
    ) else (
        echo [完成] 状态查询成功。
    )
) else (
    echo [失败] 执行未完成（退出码 %RC%）。请检查：
    echo   1. 相机是否已进入服务模式（关机按住 回放 + AF/AE LOCK 开机）并连接 USB；
    echo   2. 设备 04DA:2370 是否已通过 Zadig 绑定 WinUSB 驱动；
    echo   3. 若提示等待超时，请确认在 20 秒内实际拨动了一格有效 ISO；
    echo   4. 若提示已安装其他版本，可选择 [3] 替换重装 或拔电池冷启动后重试。
)

if not "%~1"=="" exit /b %RC%

echo.
echo 后续操作：[1] 重新部署  [2] 查看状态  [3] 替换重装  [4] 回滚卸载  [直接回车] 退出
set "CHOICE="
set /p "CHOICE=请输入选项并回车: "
if not defined CHOICE exit /b %RC%
if "%CHOICE%"=="0" exit /b %RC%
if "%CHOICE%"=="1" (
    set "ACTION=deploy"
    echo.
    goto :run_action
)
if "%CHOICE%"=="2" (
    set "ACTION=status"
    echo.
    goto :run_action
)
if "%CHOICE%"=="3" (
    set "ACTION=replace"
    echo.
    goto :run_action
)
if "%CHOICE%"=="4" (
    set "ACTION=rollback"
    echo.
    goto :run_action
)
exit /b %RC%
