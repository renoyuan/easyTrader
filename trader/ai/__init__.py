"""
AI 模块
=======
统一管理大语言模型（DeepSeek）的 API 调用、提示词模板和工具类。
"""
from .client import DeepSeekClient, STOCK_REVIEW_SYSTEM_PROMPT, DEFAULT_MODEL

__all__ = ["DeepSeekClient", "STOCK_REVIEW_SYSTEM_PROMPT", "DEFAULT_MODEL"]
