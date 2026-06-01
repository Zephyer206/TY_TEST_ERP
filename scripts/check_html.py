import urllib.request

url = 'http://127.0.0.1:8000/sales/quotes/15/edit'
try:
    with urllib.request.urlopen(url, timeout=5) as resp:
        print(f'Status: {resp.status}')
        print(f'Redirect: {resp.url}')
        content = resp.read().decode('utf-8', errors='replace')
        for keyword in ['dispLifecyclePcs', 'moldDiscountMode', 'doCalc', '_formatChinese']:
            if keyword in content:
                print(f'FOUND: {keyword}')
            else:
                print(f'MISSING: {keyword}')
        # Show lines around doCalc
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'function doCalc' in line:
                print(f'\ndoCalc at line {i+1}:')
                for j in range(max(0, i-2), min(len(lines), i+5)):
                    print(f'  {j+1}: {lines[j][:120]}')
                break
        else:
            print('\nNo doCalc found. First 500 chars:')
            print(content[:500])
except Exception as e:
    print(f'Error: {e}')
