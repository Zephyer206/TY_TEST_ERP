"""Recover only the disposable UI database with its original journalled OID.

Refuse prefix-only deletion, business database names, changed OIDs and active
sessions. Preserve sanitized synthetic acceptance counts before cleanup.
"""
from pathlib import Path
import json
import re
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/"backend")]
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from app.core.config import settings


def main():
    journal=ROOT/"runtime/qr-ui-owned.json"
    owned=json.loads(journal.read_text(encoding="utf-8"))
    name=owned.get("database")
    source=make_url(settings.DATABASE_URL).set(drivername="postgresql+psycopg2")
    if (not isinstance(name,str) or not re.fullmatch(r"qrtmp_[a-f0-9]{32}",name)
        or name==source.database or not isinstance(owned.get("original_oid"),int)
        or owned.get("purpose")!="synthetic QR UI acceptance"):
        raise ValueError("Ownership proof invalid")
    admin=create_engine(source,echo=False,poolclass=NullPool,isolation_level="AUTOCOMMIT",connect_args={"connect_timeout":10})
    try:
        with admin.connect() as connection:
            oid=connection.scalar(text("SELECT oid FROM pg_database WHERE datname=:name"),{"name":name})
            if oid is None:
                owned["state"]="cleaned"
                journal.write_text(json.dumps(owned),encoding="utf-8")
                print("Owned UI database already absent")
                return
            if oid!=owned["original_oid"]:
                raise ValueError("Ownership changed; cleanup refused")
            active=connection.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname=:name"),{"name":name})
            if active:
                raise ValueError("Active UI sessions; stop the owned server first")
        test_engine=create_engine(source.set(database=name),echo=False,poolclass=NullPool,connect_args={"connect_timeout":10})
        try:
            with test_engine.begin() as connection:
                connection.execute(text("SET TRANSACTION READ ONLY"))
                result={"pool_count":connection.scalar(text("SELECT count(*) FROM product_qr_pool_items")),
                        "confirmed_items":connection.scalar(text("SELECT count(*) FROM qr_print_confirmations")),
                        "total_print_count":connection.scalar(text("SELECT coalesce(sum(print_count),0) FROM product_qr_pool_items")),
                        "boxes":[dict(r) for r in connection.execute(text("SELECT id,order_id,bound_by,current_qty,version FROM product_boxes ORDER BY id")).mappings()],
                        "production_states":[dict(r) for r in connection.execute(text("SELECT id,production_status,version,completed_by FROM machine_order_process_states ORDER BY id")).mappings()],
                        "allocations":[dict(r) for r in connection.execute(text("SELECT source_quantity_id,available_qty,order_qty,stock_qty,assigned_by FROM product_output_allocations ORDER BY id")).mappings()],
                        "owned_original_oid_matched":True,"synthetic_data_only":True}
                (ROOT/"runtime/qr-ui-recovered-summary.json").write_text(json.dumps(result),encoding="utf-8")
        finally:
            test_engine.dispose()
        with admin.connect() as connection:
            if connection.scalar(text("SELECT oid FROM pg_database WHERE datname=:name"),{"name":name})!=owned["original_oid"]:
                raise ValueError("Ownership changed; cleanup refused")
            connection.exec_driver_sql(f'DROP DATABASE "{name}"')
        owned["state"]="cleaned"
        journal.write_text(json.dumps(owned),encoding="utf-8")
        print(json.dumps({"owned_database_cleaned":True,"preserved_summary":result}))
    finally:
        admin.dispose()


if __name__=="__main__":
    try: main()
    except Exception as error:
        print("Owned UI cleanup incomplete: "+type(error).__name__)
        sys.exit(1)
