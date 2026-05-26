"""
easyTrader 全局配置模块
=======================
管理 Tushare Token 等用户配置，
配置保存在 {项目根目录}/config.json 中。
"""
import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")


def load_config() -> dict:
    """加载本地配置"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_config(config: dict) -> None:
    """保存配置到本地"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_tushare_token() -> str:
    """获取 Tushare Token"""
    cfg = load_config()
    return cfg.get("tushare_token", "")


def set_tushare_token(token: str) -> None:
    """设置 Tushare Token"""
    cfg = load_config()
    cfg["tushare_token"] = token
    save_config(cfg)
