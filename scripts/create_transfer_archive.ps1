$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$output = Join-Path (Split-Path $root -Parent) 'Zephyr_test_Erp_transfer_20260826.zip'
if (Test-Path -LiteralPath $output) { Remove-Item -LiteralPath $output -Force }
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$excludedDirectories = @('node_modules', '.venv', '.runtime312', '__pycache__', '.pytest_cache', '.playwright-mcp', 'logs')
$excludedNames = @('NUL', 'CON', 'PRN', 'AUX')
$excludedExtensions = @('.log', '.db', '.pyc', '.pyo')
$includedCount = 0
$excludedCount = 0

$archive = [System.IO.Compression.ZipFile]::Open($output, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    Get-ChildItem -LiteralPath $root -Recurse -File -Force | ForEach-Object {
        $relative = $_.FullName.Substring($root.Length + 1) -replace '\\', '/'
        $segments = $relative -split '/'
        $skip = ($segments | Where-Object { $excludedDirectories -contains $_ }).Count -gt 0
        $skip = $skip -or ($excludedNames -contains $_.Name)
        $skip = $skip -or ($excludedExtensions -contains $_.Extension.ToLowerInvariant())
        if ($skip) { $excludedCount++; return }

        $entry = $archive.CreateEntry($relative, [System.IO.Compression.CompressionLevel]::Optimal)
        $source = [System.IO.File]::OpenRead($_.FullName)
        try {
            $target = $entry.Open()
            try { $source.CopyTo($target) } finally { $target.Dispose() }
        } finally { $source.Dispose() }
        $includedCount++
    }
} finally { $archive.Dispose() }

$item = Get-Item -LiteralPath $output
$hash = (Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash
Write-Output "ARCHIVE=$($item.FullName)"
Write-Output "INCLUDED_FILES=$includedCount"
Write-Output "EXCLUDED_FILES=$excludedCount"
Write-Output "ARCHIVE_BYTES=$($item.Length)"
Write-Output "ARCHIVE_SHA256=$hash"
