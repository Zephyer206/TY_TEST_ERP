import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "finished_goods_cross_customer_review_2026-09-24.csv"
OUTPUT = ROOT / "docs" / "finished_goods_warehouse_check_2026-09-24.csv"


def main():
    with SOURCE.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    columns = [
        "导入记录ID", "工作表", "源行号", "当前客户", "当前客户ID", "件号",
        "源零件名", "结存数量", "库位", "候选内部零件", "系统当前判定",
        "仓库核对项目", "仓库确认结果", "确认后的客户/零件", "备注",
    ]
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "导入记录ID": row.get("导入记录ID", ""),
                    "工作表": row.get("工作表", ""),
                    "源行号": row.get("源行号", ""),
                    "当前客户": row.get("当前客户", ""),
                    "当前客户ID": row.get("当前客户ID", ""),
                    "件号": row.get("件号", ""),
                    "源零件名": row.get("源零件名", ""),
                    "结存数量": row.get("结存数量", ""),
                    "库位": row.get("库位", ""),
                    "候选内部零件": row.get("候选内部零件", ""),
                    "系统当前判定": "待仓库现场核对，暂不入正式库存",
                    "仓库核对项目": "核对实物标签、包装客户标识、库区/库位和零件外观；确认是否属于当前客户",
                    "仓库确认结果": "",
                    "确认后的客户/零件": "",
                    "备注": "",
                }
            )
    print({"rows": len(rows), "output": str(OUTPUT)})


if __name__ == "__main__":
    main()
