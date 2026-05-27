"""
设置面板模块
============
负责 Tushare Token、DeepSeek API Key 等配置项管理。
"""
import tkinter as tk
from tkinter import messagebox, simpledialog
from trader.config import get_tushare_token, set_tushare_token
from trader.config import get_deepseek_token, set_deepseek_token


class SettingsPanel:
    """设置面板——嵌入在主窗口左侧操作区"""

    def __init__(self, parent: tk.Frame, status_callback, info_callback) -> None:
        """
        :param parent: 父容器 Frame
        :param status_callback: 回调，用于更新底部状态栏，签名 (msg, is_ok)
        :param info_callback: 回调，用于向文本输出区追加消息，签名 (msg)
        """
        self.parent = parent
        self._set_status = status_callback
        self._info = info_callback

    def setup_tushare(self) -> None:
        """弹出对话框设置 Tushare Token"""
        current = get_tushare_token()
        masked = current[:8] + "****" + current[-4:] if len(current) > 12 else ""
        prompt = "请输入 Tushare Pro Token（在 tushare.pro 个人中心获取）："
        if masked:
            prompt += f"\n当前已设置: {masked}"

        token = simpledialog.askstring(
            "Tushare Token 设置",
            prompt,
            parent=self.parent
        )
        if token is None:
            return
        token = token.strip()
        if not token:
            messagebox.showwarning("提示", "Token 不能为空")
            return
        set_tushare_token(token)
        messagebox.showinfo("✅ 已保存", "Tushare Token 已保存到 config.json")
        self._set_status("Tushare Token 已更新", True)
        self._info("🔑 Tushare Token 已配置完成")

    def setup_deepseek(self) -> None:
        """弹出对话框设置 DeepSeek API Key"""
        current = get_deepseek_token()
        masked = current[:8] + "****" + current[-4:] if len(current) > 12 else ""
        prompt = "请输入 DeepSeek API Key（在 platform.deepseek.com 获取）："
        if masked:
            prompt += f"\n当前已设置: {masked}"

        token = simpledialog.askstring(
            "DeepSeek API Key 设置",
            prompt,
            parent=self.parent
        )
        if token is None:
            return
        token = token.strip()
        if not token:
            messagebox.showwarning("提示", "API Key 不能为空")
            return
        set_deepseek_token(token)
        messagebox.showinfo("✅ 已保存", "DeepSeek API Key 已保存到 config.json")
        self._set_status("DeepSeek API Key 已更新", True)
        self._info("🤖 DeepSeek API Key 已配置完成")
