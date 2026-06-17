#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME: easyTrader
# CREATE_TIME: 2026-05-25
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# note:  

"""
easyTrader 全局配置模块
=======================
管理 Tushare Token、DeepSeek Key、数据库连接等用户配置，
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


# ── DeepSeek ──


def get_deepseek_token() -> str:
    """获取 DeepSeek API Key"""
    cfg = load_config()
    return cfg.get("deepseek_token", "")


def set_deepseek_token(token: str) -> None:
    """设置 DeepSeek API Key"""
    cfg = load_config()
    cfg["deepseek_token"] = token
    save_config(cfg)


# ════════════════════════════════════════
#  数据库配置
# ════════════════════════════════════════

def get_db_config() -> dict:
    """
    获取数据库配置，返回格式：
    {
        "type": "sqlite",       # "sqlite" 或 "mysql"
        # SQLite 无需额外参数
        # MySQL 需要以下参数
        "host": "localhost",
        "port": 3306,
        "user": "root",
        "password": "",
        "database": "easytrader",
    }
    """
    cfg = load_config()
    db_cfg = cfg.get("db", {})
    if not db_cfg:
        db_cfg = {"type": "sqlite"}
    return db_cfg


def set_db_config(db_cfg: dict) -> None:
    """设置数据库配置"""
    cfg = load_config()
    cfg["db"] = db_cfg
    save_config(cfg)
