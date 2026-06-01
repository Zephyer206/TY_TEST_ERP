import ast
with open(r'C:\Users\Administrator\Desktop\Cloud-Stamping\app\api\sales.py', encoding='utf-8') as f:
    src = f.read()
try:
    ast.parse(src)
    print("Syntax OK")
except SyntaxError as e:
    print(f"SyntaxError: {e}")
