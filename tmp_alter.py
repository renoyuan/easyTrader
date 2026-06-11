"""临时脚本：为已有 MySQL 表加 source / create_time 列"""
from sqlalchemy import inspect, text
from trader.db.orm import engine

with engine.connect() as conn:
    insp = inspect(engine)

    for tbl in insp.get_table_names():
        existing = {c['name'] for c in insp.get_columns(tbl)}
        for col_name, col_def in [
            ("source", "VARCHAR(30) DEFAULT NULL COMMENT '数据来源'"),
            ("create_time", "DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间'"),
        ]:
            if col_name not in existing:
                try:
                    sql = f"ALTER TABLE {tbl} ADD COLUMN {col_name} {col_def}"
                    conn.execute(text(sql))
                    conn.commit()
                    print(f"✅ {tbl}  +{col_name}")
                except Exception as e:
                    conn.rollback()
                    print(f"⚠️ {tbl}  +{col_name} 失败: {e}")

    print("\n=== 最终列检查 ===")
    for tbl in insp.get_table_names():
        cols = [c['name'] for c in insp.get_columns(tbl)]
        print(f"  {tbl}: {cols}")
