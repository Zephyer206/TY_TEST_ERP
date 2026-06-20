#!/bin/bash
# Zephyr ERP API 测试脚本
# 功能：自动化测试所有 API 端点

echo "========================================"
echo "Zephyr ERP API 测试工具 v1.0"
echo "========================================"
echo ""

API_BASE="http://127.0.0.1:8000"
TOKEN=""

passed=0
failed=0

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 测试函数
test_endpoint() {
    local name="$1"
    local method="$2"
    local endpoint="$3"
    local data="$4"
    local expected_code="$5"

    echo -n "Testing: $name ... "

    if [ "$method" = "GET" ]; then
        if [ -n "$TOKEN" ]; then
            response=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer $TOKEN" "$API_BASE$endpoint")
        else
            response=$(curl -s -w "\n%{http_code}" "$API_BASE$endpoint")
        fi
    elif [ "$method" = "POST" ]; then
        if [ -n "$TOKEN" ]; then
            response=$(curl -s -w "\n%{http_code}" -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "$data" "$API_BASE$endpoint")
        else
            response=$(curl -s -w "\n%{http_code}" -X POST -H "Content-Type: application/json" -d "$data" "$API_BASE$endpoint")
        fi
    fi

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" = "$expected_code" ]; then
        echo -e "${GREEN}✓ PASS${NC} (HTTP $http_code)"
        ((passed++))
        if [ -n "$body" ] && [ "$body" != "null" ]; then
            echo "    Response: $(echo $body | cut -c1-100)"
        fi
    else
        echo -e "${RED}✗ FAIL${NC} (Expected $expected_code, got $http_code)"
        ((failed++))
        if [ -n "$body" ]; then
            echo "    Error: $(echo $body | cut -c1-150)"
        fi
    fi
}

echo "1. 基础端点测试"
echo "─────────────────────────────────────────"
echo ""

# 1.1 根路径
test_endpoint "根路径" "GET" "/" "" "200"

# 1.2 API 文档
test_endpoint "Swagger UI" "GET" "/docs" "" "200"

# 1.3 OpenAPI 规范
test_endpoint "OpenAPI JSON" "GET" "/openapi.json" "" "200"

echo ""
echo "2. 认证端点测试"
echo "─────────────────────────────────────────"
echo ""

# 2.1 登录（无效凭据）
test_endpoint "登录 - 无效凭据" "POST" "/api/auth/login" '{"username":"invalid","password":"wrong"}' "401"

# 2.2 登录（需要先创建用户）
# test_endpoint "登录 - 有效凭据" "POST" "/api/auth/login" '{"username":"admin","password":"admin123"}' "200"

echo ""
echo "3. 用户端点测试"
echo "─────────────────────────────────────────"
echo ""

# 3.1 获取用户列表（未认证）
test_endpoint "获取用户列表 - 未认证" "GET" "/api/users" "" "401"

echo ""
echo "4. 报价端点测试"
echo "─────────────────────────────────────────"
echo ""

# 4.1 获取报价列表（未认证）
test_endpoint "获取报价列表 - 未认证" "GET" "/api/quotes" "" "401"

echo ""
echo "5. 零件端点测试"
echo "─────────────────────────────────────────"
echo ""

# 5.1 获取零件列表（未认证）
test_endpoint "获取零件列表 - 未认证" "GET" "/api/parts" "" "401"

echo ""
echo "6. 生产端点测试"
echo "─────────────────────────────────────────"
echo ""

# 6.1 获取生产计划（未认证）
test_endpoint "获取生产计划 - 未认证" "GET" "/api/production/plans" "" "401"

echo ""
echo "7. 质量管控端点测试"
echo "─────────────────────────────────────────"
echo ""

# 7.1 获取质检报告（未认证）
test_endpoint "获取质检报告 - 未认证" "GET" "/api/quality/iqc-reports" "" "401"

echo ""
echo "8. 仓库端点测试"
echo "─────────────────────────────────────────"
echo ""

# 8.1 获取原料批次（未认证）
test_endpoint "获取原料批次 - 未认证" "GET" "/api/warehouse/material-batches" "" "401"

echo ""
echo "9. 二维码端点测试"
echo "─────────────────────────────────────────"
echo ""

# 9.1 扫码查询（需要 QR code）
# test_endpoint "扫码查询" "GET" "/api/qr/scan/MAT-20260101-001" "" "200"

echo ""
echo "========================================"
echo "测试结果汇总"
echo "========================================"
echo ""

echo -e "${GREEN}通过: $passed${NC}"
echo -e "${RED}失败: $failed${NC}"

total=$((passed + failed))
if [ $total -gt 0 ]; then
    success_rate=$(( (passed * 100) / total ))
    echo ""
    echo "成功率: $success_rate%"
fi

echo ""
echo "========================================"
echo ""

if [ $failed -eq 0 ]; then
    echo -e "${GREEN}✓ 所有测试通过！${NC}"
else
    echo -e "${YELLOW}⚠ 有 $failed 个测试失败${NC}"
fi

echo ""
echo "详细信息："
echo "- API 文档: http://127.0.0.1:8000/docs"
echo "- API 规范: http://127.0.0.1:8000/openapi.json"
echo ""
echo "下一步："
echo "1. 创建初始管理员账号"
echo "2. 测试完整的认证流程"
echo "3. 执行 quickstart.md 验证场景"
echo ""
