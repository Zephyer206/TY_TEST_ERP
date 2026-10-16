#!/usr/bin/env python3
"""Verify backend repairs: py_compile + AST checks."""

import ast
import py_compile
import sys
from pathlib import Path

files = [
    "backend/app/main.py",
    "backend/app/models/price.py",
    "backend/app/schemas/customer_price.py",
    "backend/app/api/customer_prices.py",
]

exit_code = 0

# py_compile all files
for file in files:
    try:
        py_compile.compile(file, doraise=True)
        print(f"py_compile {file}: OK")
    except py_compile.PyCompileError as e:
        print(f"py_compile {file}: FAILED - {e}")
        exit_code = 1

# AST check for PriceYear model
try:
    with open("backend/app/models/price.py", "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    found_price_year = False
    has_price_id = False
    has_customer_id = False
    has_part_id = False

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "PriceYear":
            found_price_year = True
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    field_name = item.target.id
                    if field_name == "price_id":
                        has_price_id = True
                    elif field_name == "customer_id":
                        has_customer_id = True
                    elif field_name == "part_id":
                        has_part_id = True

    if not found_price_year:
        print("AST check: PriceYear class not found")
        exit_code = 1
    elif not has_price_id:
        print("AST check: PriceYear missing price_id field")
        exit_code = 1
    elif has_customer_id:
        print("AST check: PriceYear has forbidden customer_id field")
        exit_code = 1
    elif has_part_id:
        print("AST check: PriceYear has forbidden part_id field")
        exit_code = 1
    else:
        print("AST check PriceYear: OK (has price_id, no customer_id, no part_id)")

except Exception as e:
    print(f"AST check failed: {e}")
    exit_code = 1

sys.exit(exit_code)
