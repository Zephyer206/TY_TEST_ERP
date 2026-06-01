$ErrorActionPreference = 'Continue'
$p = Start-Process -FilePath 'C:\Users\AppData\Local\Programs\Python\Launcher\py.exe' -ArgumentList '-3.13', '-X utf8', '_run_server.py' -WorkingDirectory 'C:\Users\Administrator\Desktop\Cloud-Stamping' -PassThru -NoNewWindow
Start-Sleep -Seconds 5
if ($p -and -not $p.HasExited) {
    Write-Host "OK PID: $($p.Id)"
} else {
    Write-Host "CRASHED"
}
