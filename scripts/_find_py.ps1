Get-Process python* | ForEach-Object {
    $id = $_.Id
    try {
        $wmi = Get-CimInstance Win32_Process -Filter "ProcessId=$id" -ErrorAction SilentlyContinue
        $cmd = $wmi.CommandLine
    } catch { $cmd = "?" }
    [PSCustomObject]@{Id=$id; CommandLine=$cmd}
} | Format-Table -AutoSize
