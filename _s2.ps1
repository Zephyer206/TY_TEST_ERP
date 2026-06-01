$ErrorActionPreference = 'Continue'
$out = ""
$err = ""
$p = Start-Process -FilePath 'C:\Users\AppData\Local\Programs\Python\Python313\python.exe' -ArgumentList '-X utf8', '_run_server.py' -WorkingDirectory 'C:\Users\Administrator\Desktop\Cloud-Stamping' -PassThru -NoNewWindow -RedirectStandardOutput 'C:\Users\Administrator\Desktop\Cloud-Stamping\_stdout.txt' -RedirectStandardError 'C:\Users\Administrator\Desktop\Cloud-Stamping\_stderr.txt'
Start-Sleep -Seconds 5
if ($p -and -not $p.HasExited) {
    Write-Host "OK PID: $($p.Id)"
} else {
    Write-Host "CRASHED exit code: $($p.ExitCode)"
    $errContent = Get-Content 'C:\Users\Administrator\Desktop\Cloud-Stamping\_stderr.txt' -Raw -ErrorAction SilentlyContinue
    $outContent = Get-Content 'C:\Users\Administrator\Desktop\Cloud-Stamping\_stdout.txt' -Raw -ErrorAction SilentlyContinue
    Write-Host "STDERR: $errContent"
    Write-Host "STDOUT: $outContent"
}
