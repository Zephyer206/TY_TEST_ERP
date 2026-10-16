param(
    [switch]$FailOnViolation,
    [string]$FrontendRoot = "$(Join-Path $PSScriptRoot '..\frontend\src')",
    [string]$MobileRoot = "$(Join-Path $PSScriptRoot '..\mobile-h5\src')",
    [string]$SharedApiRoot = "$(Join-Path $PSScriptRoot '..\shared\api')"
)

$ErrorActionPreference = 'Stop'

$sourceRoots = @($FrontendRoot, $MobileRoot) | ForEach-Object { [IO.Path]::GetFullPath($_) }
$sourceRoots = $sourceRoots | Select-Object -Unique
foreach ($sourceRoot in $sourceRoots) {
    if (-not (Test-Path -LiteralPath $sourceRoot)) {
        throw "Frontend source directory not found: $sourceRoot"
    }
}

$sharedApiPath = [IO.Path]::GetFullPath($SharedApiRoot)
if (-not (Test-Path -LiteralPath $sharedApiPath)) {
    throw "Shared API registry directory not found: $sharedApiPath"
}

$allowedRoots = @($sourceRoots | ForEach-Object { Join-Path $_ 'api' }) + @(
    (Join-Path $FrontendRoot 'utils\request.ts')
    $sharedApiPath
)

$files = foreach ($sourceRoot in $sourceRoots) {
    Get-ChildItem -LiteralPath $sourceRoot -Recurse -File |
        Where-Object { $_.Extension -in @('.vue', '.ts', '.tsx', '.js', '.jsx') }
}

$ruleNames = @(
    "direct-http-client",
    "native-fetch",
    "hardcoded-api-prefix",
    "hardcoded-business-path"
)
$rulePatterns = @(
    "(?m)\b(apiClient|axios)\s*\.\s*(get|post|put|patch|delete)\s*\(",
    "(?m)\bfetch\s*\(",
    "(?m)\/api\/v1\/",
    "(?m)\/(parts|customers|toolings|quotes|production|warehouse|packaging|coating|price|sampling|shipping-orders|after-sales)(\/|\b)"
)
$ruleMessages = @(
    "Direct Axios client call outside API layer",
    "Native fetch call outside API layer",
    "Hardcoded /api/v1 prefix outside API layer",
    "Hardcoded business API path outside API layer"
)

$violations = New-Object System.Collections.Generic.List[object]

foreach ($file in $files) {
    $fullPath = [IO.Path]::GetFullPath($file.FullName)
    $isAllowed = $false
    foreach ($root in $allowedRoots) {
        $allowedPath = [IO.Path]::GetFullPath($root)
        if ($fullPath.Equals($allowedPath, [StringComparison]::OrdinalIgnoreCase) -or $fullPath.StartsWith($allowedPath + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
            $isAllowed = $true
            break
        }
    }
    if ($isAllowed) { continue }

    $lines = Get-Content -LiteralPath $file.FullName
    for ($lineIndex = 0; $lineIndex -lt $lines.Count; $lineIndex++) {
        $line = $lines[$lineIndex]
        for ($ruleIndex = 0; $ruleIndex -lt $ruleNames.Count; $ruleIndex++) {
            if (($ruleNames[$ruleIndex] -eq "hardcoded-api-prefix" -or $ruleNames[$ruleIndex] -eq "hardcoded-business-path") -and $line -notmatch "\b(get|post|put|patch|delete|fetch|request)\s*\(") {
                continue
            }
            if ($line -match $rulePatterns[$ruleIndex]) {
                $violations.Add([pscustomobject]@{
                    rule = $ruleNames[$ruleIndex]
                    file = $fullPath
                    line = $lineIndex + 1
                    message = $ruleMessages[$ruleIndex]
                    text = $line.Trim()
                })
            }
        }
    }
}

Write-Host "API usage scan: $($violations.Count) violation(s) found."
if ($violations.Count -gt 0) {
    $violations | Sort-Object file, line, rule | Format-Table -AutoSize rule, file, line, message
}

if ($FailOnViolation -and $violations.Count -gt 0) {
    exit 1
}

exit 0
