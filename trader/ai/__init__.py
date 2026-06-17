#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME: easyTrader
# CREATE_TIME: 2026-05-25
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# note:  

"""
AI 模块
=======
统一管理大语言模型（DeepSeek）的 API 调用、提示词模板和工具类。
"""
from .client import (
    DeepSeekClient,
    STOCK_REVIEW_SYSTEM_PROMPT,
    SCORE_COMMENT_SYSTEM_PROMPT,
    DEFAULT_MODEL,
)

__all__ = [
    "DeepSeekClient",
    "STOCK_REVIEW_SYSTEM_PROMPT",
    "SCORE_COMMENT_SYSTEM_PROMPT",
    "DEFAULT_MODEL",
]
