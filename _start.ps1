$ErrorActionPreference = 'SilentlyContinue'
$old = Get-Process -Id 8052 -ErrorAction SilentlyContinue
if ($old) {
    Stop-Process -Id 8052 -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}
$proc = Start-Process -FilePath 'C:\Users\AppData\Local\Programs\Python\Python313\python.exe' -ArgumentList '-X utf8', '_run_server.py' -WorkingDirectory 'C:\Users\Administrator\Desktop\Cloud-Stamping' -PassThru -NoNewWindow
Start-Sleep -Seconds 3
if ($proc -and -not $proc.HasExited) {
    Write-Host "Server started PID: $($proc.Id)"
} else {
    Write-Host "Server failed to start or crashed"
}
