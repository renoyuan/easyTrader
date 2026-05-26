import os
import pathlib

def get_db_path():
    """
    返回统一的数据库路径 db/stock_data.sqlite
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_dir = os.path.join(base_dir, "db")
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, "stock_data.sqlite")
