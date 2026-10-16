from sqlalchemy import create_engine

from app.api.parts import _customer_name_search_part_ids


def test_customer_name_search_returns_only_parts_linked_to_matching_customer():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, customer_code TEXT, short_name TEXT)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE part_customer_aliases (id INTEGER PRIMARY KEY, part_id INTEGER, customer_id INTEGER, is_active BOOLEAN, data_quality_status TEXT)"
        )
        connection.exec_driver_sql(
            "INSERT INTO customers (id, name, customer_code, short_name) VALUES (10, '芜湖伯特利', NULL, NULL), (11, '其他客户', NULL, NULL)"
        )
        connection.exec_driver_sql(
            "INSERT INTO part_customer_aliases (id, part_id, customer_id, is_active, data_quality_status) VALUES (1, 101, 10, 1, 'approved'), (2, 102, 11, 1, 'approved'), (3, 103, 10, 1, 'pending_review')"
        )

        part_ids = connection.execute(
            _customer_name_search_part_ids("伯特利")
        ).scalars().all()

    assert part_ids == [101]
