"""
杀掉占用 8000 端口的旧服务器进程
"""
import subprocess, sys

result = subprocess.run(
    ["powershell", "-Command",
     "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | "
     "Select-Object -ExpandProperty OwningProcess | "
     "ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue; "
     "Write-Host \"Killed PID: $_\" }"],
    capture_output=True, text=True, timeout=15
)
print(result.stdout)
print(result.stderr)
print("Done.")
