import sys
sys.path.insert(0, r"c:\Users\Administrator\Desktop\Cloud-Stamping")
from app.services.db_service import upsert_treatment, get_all_treatments
import time

name = f"FixTest_{int(time.time())}"
print(f"1. Insert: {name}")
r = upsert_treatment(name, "manual", 2.22, "Yuan/Pc")
print(f"   code={r.get('code')} msg={r.get('message')}")
d = r.get("data")
print(f"   data={d}")
if d:
    print(f"   data.rate type={type(d.get('rate')).__name__} value={d.get('rate')}")

print("2. Verify GET")
rows = get_all_treatments()
found = [x for x in rows if x["name"] == name]
print(f"   Found: {bool(found)}, total={len(rows)}")
if found:
    print(f"   id={found[0]['id']} rate={found[0]['rate']}")

print("DONE - result:", "OK" if r.get("code") == 0 else "FAIL")
