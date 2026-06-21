' clean_port8000_elevated.vbs
' 自提权脚本：触发 UAC 弹窗让用户确认以管理员权限清理 8000 端口
' 使用方法：双击运行此 VBS 文件

Option Explicit

Dim shell, command, result

' 构建 PowerShell 清理命令
command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -Command " & _
    """$ErrorActionPreference='SilentlyContinue';" & _
    "Write-Host '========================================' -ForegroundColor Cyan;" & _
    "Write-Host '  管理员模式: 清理 8000 端口' -ForegroundColor Cyan;" & _
    "Write-Host '========================================' -ForegroundColor Cyan;" & _
    "Write-Host '';" & _
    "Write-Host '[1/4] 查找占用 8000 端口的进程...' -ForegroundColor Yellow;" & _
    "Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Format-Table LocalAddress, LocalPort, OwningProcess -AutoSize | Out-String | Write-Host;" & _
    "Write-Host '[2/4] 强制终止占用进程...' -ForegroundColor Yellow;" & _
    "Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { " & _
    "  $proc = Get-Process -Id \$_.OwningProcess -ErrorAction SilentlyContinue;" & _
    "  if (\$proc) { " & _
    "    Write-Host ('  终止 PID ' + \$_.OwningProcess + ' (' + \$proc.ProcessName + ')') -ForegroundColor White;" & _
    "    Stop-Process -Id \$_.OwningProcess -Force -ErrorAction SilentlyContinue;" & _
    "  } " & _
    "};" & _
    "Start-Sleep -Seconds 3;" & _
    "Write-Host '[3/4] 验证端口状态...' -ForegroundColor Yellow;" & _
    "\$remaining = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue;" & _
    "if (\$remaining) {" & _
    "  Write-Host '[失败] 8000 端口仍被占用:' -ForegroundColor Red;" & _
    "  \$remaining | Format-Table -AutoSize | Out-String | Write-Host;" & _
    "  Write-Host '建议重启计算机后再试' -ForegroundColor Red;" & _
    "} else {" & _
    "  Write-Host '[成功] 8000 端口已释放！' -ForegroundColor Green;" & _
    "}" & _
    "Write-Host '';" & _
    "Write-Host '按任意键关闭...' -ForegroundColor Gray;" & _
    "\$null = \$Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown');""

' 创建 Shell 对象并以管理员权限运行 PowerShell
Set shell = CreateObject("Shell.Application")

' -Verb RunAs 触发 UAC 弹窗
' 0 = 隐藏窗口
shell.ShellExecute "powershell.exe", "-NoProfile -ExecutionPolicy Bypass -Command " & Chr(34) & Replace(command, Chr(34), Chr(34) & Chr(34)) & Chr(34), "", "runas", 0

Set shell = Nothing
