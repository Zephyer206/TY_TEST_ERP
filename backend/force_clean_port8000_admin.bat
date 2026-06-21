@echo off
chcp 65001 >nul
title 强制清理 8000 端口（管理员权限）
echo ========================================
echo    管理员权限强制清理 8000 端口
echo ========================================
echo.
echo [!] 正在请求管理员权限...
echo.

:: 检查是否已经是管理员
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] 当前不是管理员权限，请右键此脚本选择"以管理员身份运行"
    echo.
    pause
    exit /b 1
)

echo [1/5] 查找占用 8000 端口的所有进程...
netstat -ano | findstr ":8000" | findstr "LISTENING" > "%TEMP%\port8000.txt"
type "%TEMP%\port8000.txt"
echo.

echo [2/5] 使用 taskkill /F /T 强制终止...
for /f "tokens=5" %%a in ('type "%TEMP%\port8000.txt"') do (
    echo 终止 PID: %%a
    taskkill /PID %%a /F /T 2>nul
    if !errorlevel! equ 0 (
        echo   [成功] %%a 已终止
    ) else (
        echo   [失败] %%a 无法终止
    )
)
echo.

echo [3/5] 使用 PowerShell 强制停止...
powershell -Command "Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { try { Stop-Process -Id \$_.OwningProcess -Force -ErrorAction Stop; Write-Host \"[成功] 已停止 PID: \$(\$_.OwningProcess)\" -ForegroundColor Green } catch { Write-Host \"[失败] PID: \$(\$_.OwningProcess) - \$(\$_.Exception.Message)\" -ForegroundColor Red } }" 2>nul
echo.

echo [4/5] 等待端口释放...
timeout /t 5 /nobreak >nul
echo.

echo [5/5] 验证端口状态...
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul
if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo    [警告] 8000 端口仍被占用
    echo ========================================
    echo.
    echo 最终占用的进程：
    netstat -ano | findstr ":8000" | findstr "LISTENING"
    echo.
    echo 建议方案：
    echo 1. 重启计算机
    echo 2. 在任务管理器中手动结束进程
    echo 3. 检查是否有杀毒软件拦截
) else (
    echo.
    echo ========================================
    echo    [成功] 8000 端口已释放！
    echo ========================================
)

del "%TEMP%\port8000.txt" 2>nul
echo.
pause
