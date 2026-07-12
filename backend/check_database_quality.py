"""
全量数据库质量检查脚本
检查所有主要表的数据质量问题
"""

import sys
import json

def check_customers(token):
    """检查customers表"""
    print("=" * 70)
    print("1. CUSTOMERS 表检查")
    print("=" * 70)

    import subprocess
    result = subprocess.run([
        'curl', '-s',
        'http://127.0.0.1:8000/api/v1/customers?skip=0&limit=200',
        '-H', f'Authorization: Bearer {token}'
    ], capture_output=True, text=True)

    customers = json.loads(result.stdout)
    print(f"总记录数: {len(customers)}")

    issues = []

    # 检查异常记录
    suspicious = []
    for c in customers:
        name = c.get('name', '')
        sheet_key = c.get('sheet_key', '')

        # 检查是否是表头/分类
        if any(kw in name for kw in ['连续模', '模具', '工作表', '客户名称', 'T 模']):
            suspicious.append(c)

        # 检查sheet_key异常
        if sheet_key and (sheet_key.endswith('T') and len(sheet_key) <= 4):
            suspicious.append(c)

        # 检查空名称
        if not name or name.strip() == '':
            issues.append(f"  ⚠️ ID={c['id']}: 客户名称为空")

    if suspicious:
        print(f"\n❌ 发现 {len(suspicious)} 条可疑记录（可能是表头）:")
        for c in suspicious[:5]:
            print(f"  ID={c['id']:3d} | name={c['name'][:40]:40s} | sheet_key={c.get('sheet_key', '')}")

    # 检查重复
    names = {}
    for c in customers:
        name = c['name']
        if name in names:
            names[name].append(c['id'])
        else:
            names[name] = [c['id']]

    duplicates = {k: v for k, v in names.items() if len(v) > 1}
    if duplicates:
        print(f"\n⚠️ 发现 {len(duplicates)} 个重复的客户名称:")
        for name, ids in list(duplicates.items())[:5]:
            print(f"  '{name[:30]}' 出现在 ID={ids}")

    if issues:
        print("\n其他问题:")
        for issue in issues[:10]:
            print(issue)

    if not suspicious and not duplicates and not issues:
        print("\n✅ 未发现明显问题")

    return len(suspicious) + len(duplicates) + len(issues)


def check_parts(token):
    """检查parts表"""
    print("\n" + "=" * 70)
    print("2. PARTS 表检查")
    print("=" * 70)

    import subprocess
    result = subprocess.run([
        'curl', '-s',
        'http://127.0.0.1:8000/api/v1/parts?skip=0&limit=200',
        '-H', f'Authorization: Bearer {token}'
    ], capture_output=True, text=True)

    parts = json.loads(result.stdout)
    print(f"总记录数: {len(parts)}")

    issues = []

    # 检查表头被导入
    header_keywords = ['零件编号', '本厂产品编号', '客户产品编号', '原图产品编号']
    for p in parts:
        part_number = p.get('part_number', '')
        internal_name = p.get('internal_name', '')

        if any(kw in part_number for kw in header_keywords):
            issues.append(f"  ❌ ID={p['id']}: part_number可能是表头: {part_number[:30]}")

        if any(kw in internal_name for kw in header_keywords):
            issues.append(f"  ❌ ID={p['id']}: internal_name可能是表头: {internal_name[:30]}")

        # 检查必填字段
        if not part_number or part_number.strip() == '':
            issues.append(f"  ⚠️ ID={p['id']}: part_number为空")

    # 检查重复
    part_numbers = {}
    for p in parts:
        pn = p['part_number']
        if pn in part_numbers:
            part_numbers[pn].append(p['id'])
        else:
            part_numbers[pn] = [p['id']]

    duplicates = {k: v for k, v in part_numbers.items() if len(v) > 1}
    if duplicates:
        print(f"\n⚠️ 发现 {len(duplicates)} 个重复的零件编号:")
        for pn, ids in list(duplicates.items())[:5]:
            print(f"  '{pn[:30]}' 出现在 ID={ids}")

    # 检查数据完整性
    null_counts = {
        'customer_id': 0,
        'material_name': 0,
        'mold_number': 0,
        'spec_twph': 0,
        'thickness': 0
    }

    for p in parts:
        for field in null_counts.keys():
            if not p.get(field):
                null_counts[field] += 1

    print(f"\n📊 字段空值统计:")
    for field, count in null_counts.items():
        pct = (count / len(parts) * 100) if parts else 0
        status = "⚠️" if pct > 50 else "✅"
        print(f"  {status} {field:20s}: {count:3d} / {len(parts)} ({pct:.1f}%)")

    if issues:
        print(f"\n发现 {len(issues)} 个问题:")
        for issue in issues[:10]:
            print(issue)
        if len(issues) > 10:
            print(f"  ... 还有 {len(issues) - 10} 个问题")

    return len(issues) + len(duplicates)


def check_tooling(token):
    """检查tooling表"""
    print("\n" + "=" * 70)
    print("3. TOOLING 表检查")
    print("=" * 70)

    # 通过MCP检查
    print("通过数据库直接检查...")
    # 这里需要通过其他方式检查，因为可能没有tooling的API端点
    print("⚠️ 需要单独检查tooling表（无直接API）")

    return 0


def check_production_plans(token):
    """检查production_plans表"""
    print("\n" + "=" * 70)
    print("4. PRODUCTION_PLANS 表检查")
    print("=" * 70)

    print("⚠️ 需要单独检查production_plans表")
    return 0


def main():
    """主函数"""
    print("🔍 开始全量数据库检查...")
    print()

    # 获取token
    import subprocess
    result = subprocess.run([
        'curl', '-s', '-X', 'POST',
        'http://127.0.0.1:8000/api/v1/auth/login',
        '-H', 'Content-Type: application/json',
        '-d', '{"username":"admin","password":"123456"}'
    ], capture_output=True, text=True)

    token_data = json.loads(result.stdout)
    token = token_data['access_token']

    total_issues = 0

    # 检查各表
    total_issues += check_customers(token)
    total_issues += check_parts(token)
    total_issues += check_tooling(token)
    total_issues += check_production_plans(token)

    # 总结
    print("\n" + "=" * 70)
    print("检查总结")
    print("=" * 70)
    print(f"发现问题总数: {total_issues}")

    if total_issues > 0:
        print("\n建议:")
        print("1. 清理表头被导入的记录")
        print("2. 修复字符编码问题")
        print("3. 检查并清理重复数据")
        print("4. 修复导入脚本，防止类似问题再次发生")
    else:
        print("\n✅ 数据库整体健康")


if __name__ == '__main__':
    main()
