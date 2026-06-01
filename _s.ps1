$ErrorActionPreference = 'SilentlyContinue'
$proc = Start-Process -FilePath 'C:\Users\AppData\Local\Programs\Python\Python313\python.exe' -ArgumentList '-X utf8', '_run_server.py' -WorkingDirectory 'C:\Users\Administrator\Desktop\Cloud-Stamping' -PassThru -NoNewWindow
Start-Sleep -Seconds 4
if ($proc -and -not $proc.HasExited) {
    Write-Host "OK PID: $($proc.Id)"
} else {
    Write-Host "FAIL"
}
