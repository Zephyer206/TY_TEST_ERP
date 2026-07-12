"""
通过FastAPI清理错误的客户数据
"""

import requests
import json

BASE_URL = "http://127.0.0.1:8000"

# 获取token
def login():
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"username": "admin", "password": "123456"}
    )
    return response.json()["access_token"]

def get_customers(token, skip=0, limit=100):
    """获取客户列表"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/api/v1/customers",
        headers=headers,
        params={"skip": skip, "limit": limit}
    )
    return response.json()

def analyze_customers():
    """分析客户数据"""
    token = login()
    print("=" * 60)
    print("客户数据分析报告")
    print("=" * 60)

    # 获取所有客户
    all_customers = []
    skip = 0
    limit = 100

    while True:
        customers = get_customers(token, skip, limit)
        if not customers:
            break
        all_customers.extend(customers)
        skip += limit
        if len(customers) < limit:
            break

    print(f"\n📊 总客户数: {len(all_customers)}")

    # 查找可疑记录
    suspicious = []
    for customer in all_customers:
        name = customer.get('name', '')
        sheet_key = customer.get('sheet_key', '')

        # 检查是否是表头或分类标签
        if any(keyword in name for keyword in ['连续模', 'T 模', '吨', '模具']) or \
           (sheet_key and sheet_key.endswith('T') and sheet_key[:-1].isdigit()):
            suspicious.append(customer)

    print(f"\n🔍 可疑的客户记录（{len(suspicious)} 条）:")
    for cust in suspicious[:20]:  # 只显示前20条
        print(f"  ID={cust['id']:3d} | name={cust['name']!r:40s} | sheet_key={cust['sheet_key']}")

    if len(suspicious) > 20:
        print(f"  ... 还有 {len(suspicious) - 20} 条")

    # 分析sheet_key分布
    print(f"\n🔑 Sheet Key 分布:")
    sheet_key_counts = {}
    for cust in all_customers:
        key = cust.get('sheet_key')
        if key:
            sheet_key_counts[key] = sheet_key_counts.get(key, 0) + 1

    for key, count in sorted(sheet_key_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {key:10s} : {count} 个客户")

    print("\n" + "=" * 60)
    print("问题总结:")
    print("=" * 60)
    print(f"1. 发现 {len(suspicious)} 条可疑记录")
    print("2. 这些记录可能是Excel的表头或分类标签被导入了")
    print("3. 建议手动检查并删除这些记录")
    print("\n可疑ID列表:")
    suspicious_ids = [c['id'] for c in suspicious]
    print(f"  {suspicious_ids}")

    return suspicious

if __name__ == '__main__':
    analyze_customers()
