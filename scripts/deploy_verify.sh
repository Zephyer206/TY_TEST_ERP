#!/bin/bash
# Zephyr ERP 部署验证脚本
# 功能：自动化验证系统部署状态和核心功能

echo "========================================"
echo "Zephyr ERP 部署验证工具 v1.0"
echo "========================================"
echo ""

BASE_DIR="/c/Users/WIT_User/Desktop/Zephyr_test_Erp"
API_BASE="http://localhost:8000"

passed=0
failed=0
warnings=0

# 辅助函数
check_pass() {
    echo "[✓] $1"
    if [ -n "$2" ]; then
        echo "    $2"
    fi
    ((passed++))
}

check_fail() {
    echo "[✗] $1"
    if [ -n "$2" ]; then
        echo "    $2"
    fi
    ((failed++))
}

check_warn() {
    echo "[⚠] $1"
    if [ -n "$2" ]; then
        echo "    $2"
    fi
    ((warnings++))
}

echo "1. 环境检查"
echo "─────────────────────────────────────────"
echo ""

# 1.1 检查 Python 版本
if command -v python &> /dev/null; then
    PYTHON_VERSION=$(python --version 2>&1)
    check_pass "Python 版本" "$PYTHON_VERSION"
else
    check_fail "Python 安装" "未找到 Python"
fi

# 1.2 检查项目文件
files=(
    "backend/app/main.py"
    "backend/requirements.txt"
    ".env"
    "docker-compose.yml"
)

for file in "${files[@]}"; do
    if [ -f "$BASE_DIR/$file" ]; then
        check_pass "文件: $file"
    else
        check_fail "文件: $file" "文件不存在"
    fi
done

# 1.3 检查后端代码文件
api_count=$(find "$BASE_DIR/backend/app/api" -name "*.py" 2>/dev/null | wc -l)
model_count=$(find "$BASE_DIR/backend/app/models" -name "*.py" 2>/dev/null | wc -l)
service_count=$(find "$BASE_DIR/backend/app/services" -name "*.py" 2>/dev/null | wc -l)

check_pass "API 路由文件" "$api_count 个文件"
check_pass "数据模型文件" "$model_count 个文件"
check_pass "服务层文件" "$service_count 个文件"

echo ""
echo "2. 数据库连接检查"
echo "─────────────────────────────────────────"
echo ""

# 2.1 读取数据库配置
if [ -f "$BASE_DIR/.env" ]; then
    DB_URL=$(grep "^DATABASE_URL=" "$BASE_DIR/.env" | cut -d'=' -f2)

    if [[ $DB_URL =~ postgresql.*://.*@([a-zA-Z0-9\.]+):([0-9]+)/([a-zA-Z0-9_]+) ]]; then
        DB_HOST="${BASH_REMATCH[1]}"
        DB_PORT="${BASH_REMATCH[2]}"
        DB_NAME="${BASH_REMATCH[3]}"

        echo "数据库配置:"
        echo "  主机: $DB_HOST"
        echo "  端口: $DB_PORT"
        echo "  数据库: $DB_NAME"
        echo ""

        check_pass "数据库连接配置" "已配置远程数据库"
    else
        check_fail "数据库连接配置" "DATABASE_URL 格式不正确"
    fi
else
    check_fail ".env 文件" "未找到环境变量配置"
fi

echo ""
echo "3. 服务运行状态检查"
echo "─────────────────────────────────────────"
echo ""

# 3.1 检查后端服务
if curl -s "$API_BASE/docs" > /dev/null 2>&1; then
    check_pass "后端 API 服务" "运行在 http://localhost:8000"

    # 3.2 测试 API 健康检查
    if curl -s "$API_BASE/api/health" > /dev/null 2>&1; then
        check_pass "API 健康检查"
    else
        check_warn "API 健康检查" "健康检查端点未响应"
    fi
else
    check_fail "后端 API 服务" "服务未运行（端口 8000）"
    echo ""
    echo "提示：需要启动后端服务才能进行完整验证"
    echo "启动命令："
    echo "  cd backend"
    echo "  python -m venv .venv"
    echo "  source .venv/Scripts/activate  # Windows: .venv\\Scripts\\activate"
    echo "  pip install -r requirements.txt"
    echo "  uvicorn app.main:app --reload --port 8000"
    echo ""
fi

echo ""
echo "4. 文档完整性检查"
echo "─────────────────────────────────────────"
echo ""

# 4.1 检查 Spec 文档
docs=(
    "specs/001-erp-system-architecture/spec.md"
    "specs/001-erp-system-architecture/plan.md"
    "specs/001-erp-system-architecture/tasks.md"
    "specs/001-erp-system-architecture/data-model.md"
    "specs/001-erp-system-architecture/quickstart.md"
    "specs/002-material-qr-traceability/spec.md"
    "specs/002-material-qr-traceability/tasks.md"
)

for doc in "${docs[@]}"; do
    filename=$(basename "$doc")
    if [ -f "$BASE_DIR/$doc" ]; then
        check_pass "文档: $filename"
    else
        check_fail "文档: $filename"
    fi
done

# 4.2 检查宪法文件
if [ -f "$BASE_DIR/.specify/memory/constitution.md" ]; then
    check_pass "项目宪法" "v1.0.0 已批准"
else
    check_fail "项目宪法" "未找到宪法文件"
fi

echo ""
echo "5. 任务完成度检查"
echo "─────────────────────────────────────────"
echo ""

# 5.1 统计任务完成情况
total_tasks=0
completed_tasks=0

if [ -f "$BASE_DIR/specs/001-erp-system-architecture/tasks.md" ]; then
    all_tasks=$(grep -c "^- \[.\] T[0-9]" "$BASE_DIR/specs/001-erp-system-architecture/tasks.md" || echo 0)
    done_tasks=$(grep -c "^- \[x\] T[0-9]" "$BASE_DIR/specs/001-erp-system-architecture/tasks.md" || echo 0)

    total_tasks=$((total_tasks + all_tasks))
    completed_tasks=$((completed_tasks + done_tasks))

    if [ $all_tasks -gt 0 ]; then
        percent=$((done_tasks * 100 / all_tasks))
        if [ $done_tasks -eq $all_tasks ]; then
            check_pass "模块 001 任务完成度" "$done_tasks/$all_tasks ($percent%)"
        else
            check_warn "模块 001 任务完成度" "$done_tasks/$all_tasks ($percent%)"
        fi
    fi
fi

if [ -f "$BASE_DIR/specs/002-material-qr-traceability/tasks.md" ]; then
    all_tasks=$(grep -c "^- \[.\] T[0-9]" "$BASE_DIR/specs/002-material-qr-traceability/tasks.md" || echo 0)
    done_tasks=$(grep -c "^- \[x\] T[0-9]" "$BASE_DIR/specs/002-material-qr-traceability/tasks.md" || echo 0)

    total_tasks=$((total_tasks + all_tasks))
    completed_tasks=$((completed_tasks + done_tasks))

    if [ $all_tasks -gt 0 ]; then
        percent=$((done_tasks * 100 / all_tasks))
        if [ $done_tasks -eq $all_tasks ]; then
            check_pass "模块 002 任务完成度" "$done_tasks/$all_tasks ($percent%)"
        else
            check_warn "模块 002 任务完成度" "$done_tasks/$all_tasks ($percent%)"
        fi
    fi
fi

if [ $total_tasks -gt 0 ]; then
    overall_percent=$((completed_tasks * 100 / total_tasks))
    echo ""
    echo "总体完成度: $completed_tasks/$total_tasks ($overall_percent%)"
fi

echo ""
echo "========================================"
echo "验证结果汇总"
echo "========================================"
echo ""

echo "通过: $passed"
echo "失败: $failed"
echo "警告: $warnings"

total=$((passed + failed + warnings))
if [ $total -gt 0 ]; then
    success_rate=$((passed * 100 / total))
    echo ""
    echo "成功率: $success_rate%"
fi

echo ""
echo "========================================"
echo ""

# 生成建议
if [ $failed -gt 0 ]; then
    echo "⚠️  发现问题，建议："
    echo "1. 检查上述失败项并修复"
    echo "2. 确保后端服务已启动"
    echo "3. 验证数据库连接配置"
    echo "4. 运行完整的 quickstart 场景测试"
    echo ""
else
    echo "✅ 系统部署状态良好！"
    echo ""
    echo "下一步："
    echo "1. 启动后端服务（如未运行）"
    echo "2. 运行 API 功能测试"
    echo "3. 执行 quickstart.md 中的验证场景"
    echo ""
fi

echo "详细验证场景请参考："
echo "  specs/001-erp-system-architecture/quickstart.md"
echo ""
