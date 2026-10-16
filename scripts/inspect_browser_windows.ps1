<#
.SYNOPSIS
    Lists visible Google Chrome and Microsoft Edge windows by their actual Windows process.

.DESCRIPTION
    This is an application-identity check only. It does not read browser cookies,
    passwords, profiles, local storage, or session files.
#>

param(
    [switch]$AsJson
)

Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;

public static class BrowserWindowInspector {
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool EnumWindows(EnumWindowsProc callback, IntPtr lParam);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int maxLength);

    [DllImport("user32.dll")]
    public static extern int GetWindowTextLength(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
'@

$foregroundWindow = [BrowserWindowInspector]::GetForegroundWindow()
$browserWindows = [System.Collections.Generic.List[object]]::new()

$callback = [BrowserWindowInspector+EnumWindowsProc]{
    param([IntPtr]$hWnd, [IntPtr]$lParam)

    if (-not [BrowserWindowInspector]::IsWindowVisible($hWnd)) {
        return $true
    }

    $length = [BrowserWindowInspector]::GetWindowTextLength($hWnd)
    if ($length -le 0) {
        return $true
    }

    $titleBuilder = [System.Text.StringBuilder]::new($length + 1)
    [void][BrowserWindowInspector]::GetWindowText($hWnd, $titleBuilder, $titleBuilder.Capacity)

    [uint32]$processId = 0
    [void][BrowserWindowInspector]::GetWindowThreadProcessId($hWnd, [ref]$processId)

    try {
        $process = Get-Process -Id $processId -ErrorAction Stop
    }
    catch {
        return $true
    }

    if ($process.ProcessName -notin @('chrome', 'msedge')) {
        return $true
    }

    $application = if ($process.ProcessName -eq 'chrome') { 'Google Chrome' } else { 'Microsoft Edge' }
    $browserWindows.Add([pscustomobject]@{
        Application = $application
        Executable = "$($process.ProcessName).exe"
        ProcessId = $process.Id
        Foreground = ($hWnd -eq $foregroundWindow)
        WindowTitle = $titleBuilder.ToString()
    })

    return $true
}

[void][BrowserWindowInspector]::EnumWindows($callback, [IntPtr]::Zero)
$result = $browserWindows | Sort-Object Application, WindowTitle

if ($AsJson) {
    $result | ConvertTo-Json -Depth 3
}
else {
    $result | Format-Table -AutoSize
}
