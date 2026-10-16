"""Seed the material master price library from the supplied price sheet."""

from alembic import op
import sqlalchemy as sa


revision = "20261007_material_library_seed"
down_revision = "20261006_quote_groups"
branch_labels = None
depends_on = None


MATERIALS = [
    {"code": "FE", "name": "铁", "name_cn": "铁", "density": 7.85, "default_price": 5.4, "scrap_price": 2.0, "category": "钢材", "sort_order": 10},
    {"code": "AL", "name": "铝", "name_cn": "铝", "density": 2.7, "default_price": 30.0, "scrap_price": 18.0, "category": "铝材", "sort_order": 20},
    {"code": "SUS301-304", "name": "SUS301/304", "name_cn": "SUS301/304", "density": 7.93, "default_price": 19.0, "scrap_price": 7.0, "category": "不锈钢", "sort_order": 30},
    {"code": "FORMING-SUS301-304", "name": "SUS301/304", "name_cn": "成型机 SUS301/304", "density": 7.93, "default_price": 26.0, "scrap_price": 7.0, "category": "不锈钢", "sort_order": 40},
    {"code": "SUS430", "name": "SUS430", "name_cn": "SUS430", "density": 7.75, "default_price": 11.0, "scrap_price": 3.5, "category": "不锈钢", "sort_order": 50},
    {"code": "65MN", "name": "65Mn", "name_cn": "65Mn", "density": 7.85, "default_price": 9.0, "scrap_price": 2.0, "category": "弹簧钢", "sort_order": 60},
    {"code": "51CRV4", "name": "51CrV4", "name_cn": "51CrV4", "density": 7.85, "default_price": 12.0, "scrap_price": 2.0, "category": "弹簧钢", "sort_order": 70},
    {"code": "GALVANIZED-WIRE", "name": "镀锌钢丝", "name_cn": "镀锌钢丝", "density": None, "default_price": None, "scrap_price": None, "category": "钢材", "sort_order": 80},
    {"code": "S65C-C67S", "name": "S65C OR C67S", "name_cn": "S65C OR C67S", "density": 7.85, "default_price": 11.0, "scrap_price": 2.0, "category": "弹簧钢", "sort_order": 90},
    {"code": "SPHC", "name": "SPHC", "name_cn": "SPHC", "density": 7.85, "default_price": 4.5, "scrap_price": 2.0, "category": "钢材", "sort_order": 100},
    {"code": "6061-T6", "name": "6061-T6", "name_cn": "6061-T6", "density": 2.7, "default_price": 22.0, "scrap_price": 9.0, "category": "铝材", "sort_order": 110},
    {"code": "10#", "name": "10#", "name_cn": "10#", "density": 7.85, "default_price": 5.8, "scrap_price": 2.0, "category": "钢材", "sort_order": 120},
    {"code": "SAE1074-1075", "name": "SAE 1074/1075", "name_cn": "SAE 1074/1075", "density": 7.85, "default_price": 5.8, "scrap_price": 2.0, "category": "弹簧钢", "sort_order": 130},
    {"code": "SECC-N", "name": "SECC-N", "name_cn": "SECC-N电镀耐指纹钢板", "density": 7.85, "default_price": 7.4, "scrap_price": 2.0, "category": "钢材", "sort_order": 140},
    {"code": "AL5052", "name": "5052", "name_cn": "铝5052", "density": 2.7, "default_price": 30.0, "scrap_price": 18.0, "category": "铝材", "sort_order": 150},
    {"code": "SAPH440", "name": "SAPH440", "name_cn": "SAPH440", "density": 7.85, "default_price": 5.2, "scrap_price": 2.0, "category": "钢材", "sort_order": 160},
]


def upgrade() -> None:
    material_dict = sa.table(
        "material_dict",
        sa.column("code", sa.String(50)),
        sa.column("name", sa.String(100)),
        sa.column("name_cn", sa.String(100)),
        sa.column("density", sa.Numeric(10, 4)),
        sa.column("default_price", sa.Numeric(12, 4)),
        sa.column("scrap_price", sa.Numeric(12, 4)),
        sa.column("category", sa.String(50)),
        sa.column("sort_order", sa.Integer()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(material_dict, [{**item, "is_active": True} for item in MATERIALS])


def downgrade() -> None:
    codes = [item["code"] for item in MATERIALS]
    material_dict = sa.table(
        "material_dict",
        sa.column("code", sa.String(50)),
    )
    op.execute(sa.delete(material_dict).where(material_dict.c.code.in_(codes)))
