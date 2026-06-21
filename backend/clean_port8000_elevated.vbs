' clean_port8000_elevated.vbs
' Self-elevating script: triggers UAC for user to confirm admin privileges
' Usage: Double-click this file

Option Explicit

Dim shell, fso, tempDir, ps1Path

' Get temp directory
Set fso = CreateObject("Scripting.FileSystemObject")
tempDir = fso.GetSpecialFolder(2) ' 2 = TemporaryFolder
ps1Path = tempDir & "\clean_port8000.ps1"

' Write PowerShell script to temp file
Dim psFile
Set psFile = fso.CreateTextFile(ps1Path, True, True) ' Unicode
psFile.WriteLine "$ErrorActionPreference = 'SilentlyContinue'"
psFile.WriteLine "Write-Host '========================================' -ForegroundColor Cyan"
psFile.WriteLine "Write-Host '  管理员模式: 清理 8000 端口' -ForegroundColor Cyan"
psFile.WriteLine "Write-Host '========================================' -ForegroundColor Cyan"
psFile.WriteLine "Write-Host ''"
psFile.WriteLine "Write-Host '[1/4] 查找占用 8000 端口的进程...' -ForegroundColor Yellow"
psFile.WriteLine "$conns = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue"
psFile.WriteLine "if ($conns) { $conns | Format-Table LocalAddress, LocalPort, OwningProcess -AutoSize | Out-String | Write-Host }"
psFile.WriteLine "Write-Host '[2/4] 强制终止占用进程...' -ForegroundColor Yellow"
psFile.WriteLine "if ($conns) {"
psFile.WriteLine "  foreach ($c in $conns) {"
psFile.WriteLine "    $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue"
psFile.WriteLine "    if ($proc) {"
psFile.WriteLine "      Write-Host (\"  终止 PID \" + $c.OwningProcess + \" (\" + $proc.ProcessName + \")\") -ForegroundColor White"
psFile.WriteLine "      Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue"
psFile.WriteLine "    }"
psFile.WriteLine "  }"
psFile.WriteLine "}"
psFile.WriteLine "Start-Sleep -Seconds 3"
psFile.WriteLine "Write-Host '[3/4] 验证端口状态...' -ForegroundColor Yellow"
psFile.WriteLine "$remaining = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue"
psFile.WriteLine "if ($remaining) {"
psFile.WriteLine "  Write-Host '[失败] 8000 端口仍被占用:' -ForegroundColor Red"
psFile.WriteLine "  $remaining | Format-Table -AutoSize | Out-String | Write-Host"
psFile.WriteLine "  Write-Host '建议重启计算机后再试' -ForegroundColor Red"
psFile.WriteLine "} else {"
psFile.WriteLine "  Write-Host '[成功] 8000 端口已释放！' -ForegroundColor Green"
psFile.WriteLine "}"
psFile.WriteLine "Write-Host ''"
psFile.WriteLine "Write-Host '清理临时文件...' -ForegroundColor Gray"
psFile.WriteLine "Remove-Item -Path $PSCommandPath -Force -ErrorAction SilentlyContinue"
psFile.WriteLine "Write-Host '按任意键关闭...' -ForegroundColor Gray"
psFile.WriteLine "$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')"
psFile.Close

' Launch PowerShell with UAC elevation
Set shell = CreateObject("Shell.Application")
shell.ShellExecute "powershell.exe", "-NoProfile -ExecutionPolicy Bypass -File """ & ps1Path & """", "", "runas", 1

Set shell = Nothing
Set fso = Nothing
