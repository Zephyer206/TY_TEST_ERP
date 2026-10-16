[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$TaskName = 'Zephyr Shipping Draft Cleanup',
    [string]$ProjectRoot,
    [string]$PythonPath,
    [string]$RunAt = '02:00'
)

if (-not $ProjectRoot) { $ProjectRoot = Split-Path -Parent $PSScriptRoot }
if (-not $PythonPath) { $PythonPath = Join-Path $ProjectRoot 'backend\.runtime312\Scripts\python.exe' }
$cleanupScript = Join-Path $ProjectRoot 'scripts\cleanup_shipping_drafts.py'
if (-not (Test-Path -LiteralPath $PythonPath)) { throw "Python runtime not found: $PythonPath" }
if (-not (Test-Path -LiteralPath $cleanupScript)) { throw "Cleanup script not found: $cleanupScript" }

if ($PSCmdlet.ShouldProcess($TaskName, 'Register daily shipping draft cleanup task')) {
    $action = New-ScheduledTaskAction -Execute $PythonPath -Argument "-u `"$cleanupScript`"" -WorkingDirectory $ProjectRoot
    $trigger = New-ScheduledTaskTrigger -Daily -At ([datetime]::ParseExact($RunAt, 'HH:mm', $null))
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Description 'Remove shipping-order drafts unchanged for more than seven days.' -Force | Out-Null
    Write-Output "Registered: $TaskName ($RunAt daily)"
}
