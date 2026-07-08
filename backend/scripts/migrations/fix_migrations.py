import sys

files = [
    '002_create_customer_material_prices.py',
    '003_create_customer_treatment_prices.py',
    '004_create_price_adjustments.py',
    '005_migrate_material_base_prices.py',
    '006_migrate_treatment_dicts.py',
    '007_drop_legacy_tables.py'
]

for filename in files:
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Fix imports
        content = content.replace('from app.database import async_engine', 'from app.database import engine')
        # Fix usage
        content = content.replace('async_engine', 'engine')
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"OK: Fixed {filename}")
    except Exception as e:
        print(f"ERROR fixing {filename}: {e}")
        sys.exit(1)

print("\nAll migration files fixed!")
