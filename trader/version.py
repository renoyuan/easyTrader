# -*- coding: utf-8 -*-
"""
easyTrader 版本信息
集中管理版本号，所有地方从此读取
"""

VERSION = "2026.06.12"
VERSION_TAG = f"v{VERSION}"
VERSION_DESC = f"v {VERSION}"

__version__ = VERSION
__version_tag__ = VERSION_TAG


def get_version() -> str:
    """获取版本号字符串"""
    return VERSION


def get_version_tag() -> str:
    """获取版本标签（如 v2026.06.12）"""
    return VERSION_TAG
