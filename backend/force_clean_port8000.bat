@echo off
chcp 65001 >nul
echo ========================================
echo    端口 8000 强制清理脚本
echo ========================================
echo.

echo [1/4] 查找占用 8000 端口的进程...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
    echo 发现进程 PID: %%a
    set "PIDS=%%a !PIDS!"
)

if defined PIDS (
    echo.
    echo [2/4] 终止这些进程...
    for %%p in (!PIDS!) do (
        echo 终止 PID %%p ...
        taskkill /PID %%p /F /T 2>nul
        if !errorlevel! equ 0 (
            echo   [成功] 已终止 %%p
        ) else (
            echo   [警告] 无法终止 %%p
        )
    )
) else (
    echo 没有进程占用 8000 端口
)

echo.
echo [3/4] 等待端口释放...
timeout /t 5 /nobreak >nul

echo.
echo [4/4] 验证端口状态...
netstat -ano | findstr ":8000" | findstr "LISTENING"
if %errorlevel% neq 0 (
    echo.
    echo ========================================
    echo    [成功] 端口 8000 已释放！
    echo ========================================
) else (
    echo.
    echo ========================================
    echo    [警告] 端口 8000 仍被占用
    echo    请尝试重启计算机后再运行此脚本
    echo ========================================
)

echo.
pause