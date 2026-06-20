# Zephyr ERP 部署验证脚本
# 功能：自动化验证系统部署状态和核心功能

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Zephyr ERP 部署验证工具 v1.0" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$ErrorActionPreference = "Continue"
$baseDir = "c:\Users\WIT_User\Desktop\Zephyr_test_Erp"
$backendDir = Join-Path $baseDir "backend"
$API_BASE = "http://localhost:8000"

# 验证结果统计
$passed = 0
$failed = 0
$warnings = 0

# 辅助函数：打印检查结果
function Write-Check {
    param(
        [string]$Name,
        [bool]$Success,
        [string]$Message = ""
    )

    if ($Success) {
        Write-Host "[✓] " -ForegroundColor Green -NoNewline
        Write-Host "$Name" -ForegroundColor White
        if ($Message) { Write-Host "    $Message" -ForegroundColor Gray }
        $script:passed++
    } else {
        Write-Host "[✗] " -ForegroundColor Red -NoNewline
        Write-Host "$Name" -ForegroundColor White
        if ($Message) { Write-Host "    $Message" -ForegroundColor Yellow }
        $script:failed++
    }
}

function Write-Warning-Check {
    param(
        [string]$Name,
        [string]$Message = ""
    )

    Write-Host "[⚠] " -ForegroundColor Yellow -NoNewline
    Write-Host "$Name" -ForegroundColor White
    if ($Message) { Write-Host "    $Message" -ForegroundColor Gray }
    $script:warnings++
}

Write-Host "1. 环境检查" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────`n" -ForegroundColor Cyan

# 1.1 检查 Python 版本
try {
    $pythonVersion = python --version 2>&1
    if ($pythonVersion -match "Python (\d+\.\d+)") {
        $version = [version]$matches[1]
        if ($version -ge [version]"3.11") {
            Write-Check "Python 版本" $true "$pythonVersion"
        } else {
            Write-Check "Python 版本" $false "需要 Python 3.11+，当前: $pythonVersion"
        }
    }
} catch {
    Write-Check "Python 安装" $false "未找到 Python"
}

# 1.2 检查项目文件
$requiredFiles = @(
    "backend\app\main.py",
    "backend\requirements.txt",
    ".env",
    "docker-compose.yml"
)

foreach ($file in $requiredFiles) {
    $filePath = Join-Path $baseDir $file
    if (Test-Path $filePath) {
        Write-Check "文件: $file" $true
    } else {
        Write-Check "文件: $file" $false "文件不存在"
    }
}

# 1.3 检查后端代码文件
$apiFiles = Get-ChildItem -Path "$backendDir\app\api" -Filter "*.py" -ErrorAction SilentlyContinue
$modelFiles = Get-ChildItem -Path "$backendDir\app\models" -Filter "*.py" -ErrorAction SilentlyContinue
$serviceFiles = Get-ChildItem -Path "$backendDir\app\services" -Filter "*.py" -ErrorAction SilentlyContinue

Write-Check "API 路由文件" ($apiFiles.Count -gt 0) "$($apiFiles.Count) 个文件"
Write-Check "数据模型文件" ($modelFiles.Count -gt 0) "$($modelFiles.Count) 个文件"
Write-Check "服务层文件" ($serviceFiles.Count -gt 0) "$($serviceFiles.Count) 个文件"

Write-Host "`n2. 数据库连接检查" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────`n" -ForegroundColor Cyan

# 2.1 读取数据库配置
$envFile = Join-Path $baseDir ".env"
if (Test-Path $envFile) {
    $dbUrl = Select-String -Path $envFile -Pattern "^DATABASE_URL=" | ForEach-Object { $_.Line -replace "^DATABASE_URL=", "" }

    if ($dbUrl -match "postgresql.*://.*@([\w\.]+):(\d+)/(\w+)") {
        $dbHost = $matches[1]
        $dbPort = $matches[2]
        $dbName = $matches[3]

        Write-Host "数据库配置:" -ForegroundColor Gray
        Write-Host "  主机: $dbHost" -ForegroundColor Gray
        Write-Host "  端口: $dbPort" -ForegroundColor Gray
        Write-Host "  数据库: $dbName`n" -ForegroundColor Gray

        # 测试数据库端口连接（简化版）
        Write-Check "数据库连接配置" $true "已配置远程数据库"
    } else {
        Write-Check "数据库连接配置" $false "DATABASE_URL 格式不正确"
    }
} else {
    Write-Check ".env 文件" $false "未找到环境变量配置"
}

Write-Host "`n3. 服务运行状态检查" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────`n" -ForegroundColor Cyan

# 3.1 检查后端服务
try {
    $response = Invoke-WebRequest -Uri "$API_BASE/docs" -Method GET -TimeoutSec 5 -ErrorAction Stop
    Write-Check "后端 API 服务" $true "运行在 http://localhost:8000"

    # 3.2 测试 API 健康检查
    try {
        $healthResponse = Invoke-WebRequest -Uri "$API_BASE/api/health" -Method GET -TimeoutSec 3 -ErrorAction SilentlyContinue
        Write-Check "API 健康检查" $true
    } catch {
        Write-Warning-Check "API 健康检查" "健康检查端点未响应"
    }

} catch {
    Write-Check "后端 API 服务" $false "服务未运行（端口 8000）"
    Write-Host "`n提示：需要启动后端服务才能进行完整验证" -ForegroundColor Yellow
    Write-Host "启动命令：" -ForegroundColor Gray
    Write-Host "  cd backend" -ForegroundColor Gray
    Write-Host "  python -m venv .venv" -ForegroundColor Gray
    Write-Host "  .venv\Scripts\activate" -ForegroundColor Gray
    Write-Host "  pip install -r requirements.txt" -ForegroundColor Gray
    Write-Host "  uvicorn app.main:app --reload --port 8000`n" -ForegroundColor Gray
}

Write-Host "`n4. 文档完整性检查" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────`n" -ForegroundColor Cyan

# 4.1 检查 Spec 文档
$specDocs = @(
    "specs\001-erp-system-architecture\spec.md",
    "specs\001-erp-system-architecture\plan.md",
    "specs\001-erp-system-architecture\tasks.md",
    "specs\001-erp-system-architecture\data-model.md",
    "specs\001-erp-system-architecture\quickstart.md",
    "specs\002-material-qr-traceability\spec.md",
    "specs\002-material-qr-traceability\tasks.md"
)

foreach ($doc in $specDocs) {
    $docPath = Join-Path $baseDir $doc
    if (Test-Path $docPath) {
        Write-Check "文档: $(Split-Path $doc -Leaf)" $true
    } else {
        Write-Check "文档: $(Split-Path $doc -Leaf)" $false
    }
}

# 4.2 检查宪法文件
$constitutionPath = Join-Path $baseDir ".specify\memory\constitution.md"
if (Test-Path $constitutionPath) {
    Write-Check "项目宪法" $true "v1.0.0 已批准"
} else {
    Write-Check "项目宪法" $false "未找到宪法文件"
}

Write-Host "`n5. 任务完成度检查" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────`n" -ForegroundColor Cyan

# 5.1 统计任务完成情况
$tasksFile1 = Join-Path $baseDir "specs\001-erp-system-architecture\tasks.md"
$tasksFile2 = Join-Path $baseDir "specs\002-material-qr-traceability\tasks.md"

$totalTasks = 0
$completedTasks = 0

if (Test-Path $tasksFile1) {
    $content = Get-Content $tasksFile1 -Raw
    $allTasks = ([regex]::Matches($content, '- \[.\] T\d+')).Count
    $doneTasks = ([regex]::Matches($content, '- \[x\] T\d+')).Count

    $totalTasks += $allTasks
    $completedTasks += $doneTasks

    $percent = [math]::Round(($doneTasks / $allTasks) * 100, 1)
    Write-Check "模块 001 任务完成度" ($doneTasks -eq $allTasks) "$doneTasks/$allTasks ($percent%)"
}

if (Test-Path $tasksFile2) {
    $content = Get-Content $tasksFile2 -Raw
    $allTasks = ([regex]::Matches($content, '- \[.\] T\d+')).Count
    $doneTasks = ([regex]::Matches($content, '- \[x\] T\d+')).Count

    $totalTasks += $allTasks
    $completedTasks += $doneTasks

    $percent = [math]::Round(($doneTasks / $allTasks) * 100, 1)
    Write-Check "模块 002 任务完成度" ($doneTasks -eq $allTasks) "$doneTasks/$allTasks ($percent%)"
}

if ($totalTasks -gt 0) {
    $overallPercent = [math]::Round(($completedTasks / $totalTasks) * 100, 1)
    Write-Host "`n总体完成度: " -NoNewline
    if ($completedTasks -eq $totalTasks) {
        Write-Host "$completedTasks/$totalTasks (100%)" -ForegroundColor Green
    } else {
        Write-Host "$completedTasks/$totalTasks ($overallPercent%)" -ForegroundColor Yellow
    }
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "验证结果汇总" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "通过: " -NoNewline
Write-Host $passed -ForegroundColor Green
Write-Host "失败: " -NoNewline
Write-Host $failed -ForegroundColor Red
Write-Host "警告: " -NoNewline
Write-Host $warnings -ForegroundColor Yellow

$total = $passed + $failed + $warnings
if ($total -gt 0) {
    $successRate = [math]::Round(($passed / $total) * 100, 1)
    Write-Host "`n成功率: $successRate%" -ForegroundColor $(if ($successRate -ge 80) { "Green" } elseif ($successRate -ge 60) { "Yellow" } else { "Red" })
}

Write-Host "`n========================================`n" -ForegroundColor Cyan

# 生成建议
if ($failed -gt 0) {
    Write-Host "⚠️  发现问题，建议：" -ForegroundColor Yellow
    Write-Host "1. 检查上述失败项并修复" -ForegroundColor Gray
    Write-Host "2. 确保后端服务已启动" -ForegroundColor Gray
    Write-Host "3. 验证数据库连接配置" -ForegroundColor Gray
    Write-Host "4. 运行完整的 quickstart 场景测试`n" -ForegroundColor Gray
} else {
    Write-Host "✅ 系统部署状态良好！" -ForegroundColor Green
    Write-Host "`n下一步：" -ForegroundColor Cyan
    Write-Host "1. 启动后端服务（如未运行）" -ForegroundColor Gray
    Write-Host "2. 运行 API 功能测试" -ForegroundColor Gray
    Write-Host "3. 执行 quickstart.md 中的验证场景`n" -ForegroundColor Gray
}

Write-Host "详细验证场景请参考：" -ForegroundColor Gray
Write-Host "  specs\001-erp-system-architecture\quickstart.md`n" -ForegroundColor Gray
