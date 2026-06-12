"""
设置面板模块
============
负责 Tushare Token、DeepSeek API Key、数据库配置等配置项管理。
提供一个统一设置对话框，节省界面空间。
"""
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from trader.config import (
    get_tushare_token, set_tushare_token,
    get_deepseek_token, set_deepseek_token,
    get_db_config, set_db_config,
)


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

    def open_settings(self) -> None:
        """打开统一设置对话框"""
        win = tk.Toplevel(self.parent)
        win.title("⚙ 系统设置")
        win.geometry("520x480")
        win.configure(bg="#f0f2f5")
        win.resizable(False, False)
        win.transient(self.parent)
        win.grab_set()

        # ── 标题 ──
        tk.Label(
            win, text="⚙ 系统设置",
            bg="#f0f2f5", fg="#202124",
            font=("微软雅黑", 14, "bold")
        ).pack(pady=(16, 8))

        # ── 主容器 ──
        frame = tk.Frame(win, bg="#ffffff", relief=tk.RIDGE, bd=1)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 16))

        # ═══════════ 1. Tushare Token ═══════════
        self._build_section_header(frame, "🔑 Tushare Token", 0)

        token_frame = tk.Frame(frame, bg="#ffffff")
        token_frame.pack(fill=tk.X, padx=16, pady=(0, 4))

        current_tushare = get_tushare_token()
        tk.Label(
            token_frame, text="Tushare Pro Token：",
            bg="#ffffff", fg="#202124",
            font=("微软雅黑", 10)
        ).pack(side=tk.LEFT)

        self.tushare_entry = tk.Entry(
            token_frame, width=30,
            font=("Consolas", 10),
            show="*",
            relief=tk.SUNKEN, bd=1
        )
        self.tushare_entry.pack(side=tk.LEFT, padx=8)
        if current_tushare:
            # 显示部分掩码但不填满，让用户自行决定是否修改
            self.tushare_entry.insert(0, current_tushare[:12] + "****" if len(current_tushare) > 16 else current_tushare)

        # 显示/隐藏按钮
        self._toggle_tushare_btn = tk.Button(
            token_frame, text="👁", font=("微软雅黑", 9),
            bg="#e8eaed", relief=tk.FLAT, bd=0, cursor="hand2",
            command=lambda: self._toggle_show(self.tushare_entry, self._toggle_tushare_btn),
        )
        self._toggle_tushare_btn.pack(side=tk.LEFT, padx=(0, 4))

        # ═══════════ 2. DeepSeek API Key ═══════════
        self._build_section_header(frame, "🤖 DeepSeek API Key", 1)

        ds_frame = tk.Frame(frame, bg="#ffffff")
        ds_frame.pack(fill=tk.X, padx=16, pady=(0, 4))

        tk.Label(
            ds_frame, text="DeepSeek API Key：",
            bg="#ffffff", fg="#202124",
            font=("微软雅黑", 10)
        ).pack(side=tk.LEFT)

        self.deepseek_entry = tk.Entry(
            ds_frame, width=30,
            font=("Consolas", 10),
            show="*",
            relief=tk.SUNKEN, bd=1
        )
        self.deepseek_entry.pack(side=tk.LEFT, padx=8)
        current_ds = get_deepseek_token()
        if current_ds:
            self.deepseek_entry.insert(0, current_ds[:12] + "****" if len(current_ds) > 16 else current_ds)

        self._toggle_ds_btn = tk.Button(
            ds_frame, text="👁", font=("微软雅黑", 9),
            bg="#e8eaed", relief=tk.FLAT, bd=0, cursor="hand2",
            command=lambda: self._toggle_show(self.deepseek_entry, self._toggle_ds_btn),
        )
        self._toggle_ds_btn.pack(side=tk.LEFT, padx=(0, 4))

        # ═══════════ 3. 数据库配置 ═══════════
        self._build_section_header(frame, "🗄 数据库配置", 2)

        db_frame = tk.Frame(frame, bg="#ffffff")
        db_frame.pack(fill=tk.X, padx=16, pady=(0, 4))

        tk.Label(
            db_frame, text="数据库类型：",
            bg="#ffffff", fg="#202124",
            font=("微软雅黑", 10)
        ).pack(side=tk.LEFT)

        self.db_type_var = tk.StringVar()
        current_db = get_db_config()
        self.db_type_var.set(current_db.get("type", "sqlite"))

        self.db_type_combo = ttk.Combobox(
            db_frame, textvariable=self.db_type_var,
            values=("sqlite", "mysql"),
            state="readonly", width=12,
            font=("微软雅黑", 10)
        )
        self.db_type_combo.pack(side=tk.LEFT, padx=8)
        self.db_type_combo.bind("<<ComboboxSelected>>", self._on_db_type_change)

        # ── MySQL 详细参数（默认隐藏） ──
        self.mysql_frame = tk.Frame(frame, bg="#ffffff")

        mysql_fields = [
            ("主机地址：", "host", "localhost"),
            ("端口号：", "port", "3306"),
            ("用户名：", "user", "root"),
            ("密码：", "password", ""),
            ("数据库名：", "database", "easytrader"),
        ]
        self.mysql_entries = {}
        for label, key, default in mysql_fields:
            row = tk.Frame(self.mysql_frame, bg="#ffffff")
            row.pack(fill=tk.X, padx=24, pady=3)
            tk.Label(
                row, text=label, bg="#ffffff", fg="#5f6368",
                font=("微软雅黑", 9), width=10, anchor=tk.E
            ).pack(side=tk.LEFT)
            show = key == "password"
            entry = tk.Entry(
                row, width=28, font=("Consolas", 10),
                show="*" if show else "",
                relief=tk.SUNKEN, bd=1
            )
            entry.pack(side=tk.LEFT, padx=6)
            # 填入当前值
            val = current_db.get(key, default)
            entry.insert(0, str(val))
            self.mysql_entries[key] = entry

            # 密码显示/隐藏
            if key == "password":
                self._toggle_pw_btn = tk.Button(
                    row, text="👁", font=("微软雅黑", 9),
                    bg="#e8eaed", relief=tk.FLAT, bd=0, cursor="hand2",
                    command=lambda: self._toggle_show(entry, self._toggle_pw_btn),
                )
                self._toggle_pw_btn.pack(side=tk.LEFT)

        if self.db_type_var.get() == "mysql":
            self.mysql_frame.pack(fill=tk.X, pady=(4, 8))

        # ── 分割线 ──
        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=12)

        # ── 测试连接按钮 ──
        test_btn = tk.Button(
            frame, text="🔌 测试数据库连接",
            command=self._test_db_connection,
            bg="#1a73e8", fg="white",
            font=("微软雅黑", 9, "bold"),
            relief=tk.FLAT, bd=0, cursor="hand2",
            padx=16, pady=6,
        )
        test_btn.pack(pady=(0, 12))

        # ── 底部按钮 ──
        bottom_frame = tk.Frame(win, bg="#f0f2f5")
        bottom_frame.pack(fill=tk.X, padx=20, pady=(0, 16))

        tk.Button(
            bottom_frame, text="取消",
            command=win.destroy,
            bg="#e8eaed", fg="#202124",
            font=("微软雅黑", 10, "bold"),
            relief=tk.FLAT, bd=0, cursor="hand2",
            padx=20, pady=6,
        ).pack(side=tk.RIGHT, padx=(8, 0))

        tk.Button(
            bottom_frame, text="✅ 保存设置",
            command=lambda: self._save_settings(win),
            bg="#34a853", fg="white",
            font=("微软雅黑", 10, "bold"),
            relief=tk.FLAT, bd=0, cursor="hand2",
            padx=20, pady=6,
        ).pack(side=tk.RIGHT)

    # ── 内部辅助方法 ──

    @staticmethod
    def _build_section_header(parent: tk.Frame, title: str, index: int) -> None:
        """构建分区标题"""
        tk.Label(
            parent, text=title,
            bg="#ffffff", fg="#1a73e8",
            font=("微软雅黑", 11, "bold")
        ).pack(fill=tk.X, padx=16, pady=(12 if index > 0 else 8, 4))

    @staticmethod
    def _toggle_show(entry: tk.Entry, btn: tk.Button) -> None:
        """切换密码/明文显示"""
        if entry.cget("show") == "*":
            entry.config(show="")
            btn.config(text="🙈")
        else:
            entry.config(show="*")
            btn.config(text="👁")

    def _on_db_type_change(self, event=None) -> None:
        """切换数据库类型时显示/隐藏 MySQL 参数"""
        if self.db_type_var.get() == "mysql":
            self.mysql_frame.pack(fill=tk.X, pady=(4, 8))
        else:
            self.mysql_frame.pack_forget()

    def _test_db_connection(self) -> None:
        """测试数据库连接"""
        try:
            db_type = self.db_type_var.get()
            if db_type == "sqlite":
                from trader.db.orm import _get_sqlite_path
                db_path = _get_sqlite_path()
                import os
                if os.path.exists(db_path):
                    messagebox.showinfo("✅ 连接成功", f"SQLite 数据库文件存在：\n{db_path}")
                else:
                    messagebox.showinfo("ℹ️ 尚未创建", f"SQLite 数据库文件将在首次使用时创建：\n{db_path}")
                return

            # MySQL 测试
            host = self.mysql_entries["host"].get().strip()
            port = int(self.mysql_entries["port"].get().strip())
            user = self.mysql_entries["user"].get().strip()
            password = self.mysql_entries["password"].get()
            database = self.mysql_entries["database"].get().strip()

            from sqlalchemy import create_engine, text
            url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"
            engine = create_engine(url, echo=False, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            engine.dispose()

            messagebox.showinfo("✅ 连接成功", f"MySQL 数据库连接测试通过！\n{host}:{port}/{database}")
        except Exception as e:
            messagebox.showerror("❌ 连接失败", f"数据库连接测试失败：\n{e}")

    def _save_settings(self, win: tk.Toplevel) -> None:
        """保存所有设置"""
        # ── 保存 Tushare Token ──
        tushare_val = self.tushare_entry.get().strip()
        if tushare_val:
            # 如果用户输入了掩码形式（包含****），说明没改，保留原值
            if "****" in tushare_val:
                current = get_tushare_token()
            else:
                set_tushare_token(tushare_val)
                self._info("🔑 Tushare Token 已配置完成")

        # ── 保存 DeepSeek Key ──
        ds_val = self.deepseek_entry.get().strip()
        if ds_val:
            if "****" in ds_val:
                current = get_deepseek_token()
            else:
                set_deepseek_token(ds_val)
                self._info("🤖 DeepSeek API Key 已配置完成")

        # ── 保存数据库配置 ──
        db_type = self.db_type_var.get()
        db_cfg = {"type": db_type}
        if db_type == "mysql":
            for key in ("host", "port", "user", "password", "database"):
                val = self.mysql_entries[key].get().strip()
                if key == "port":
                    try:
                        val = int(val)
                    except ValueError:
                        messagebox.showwarning("参数错误", f"端口号必须为数字")
                        return
                db_cfg[key] = val
        set_db_config(db_cfg)
        self._info(f"🗄 数据库配置已保存（类型: {db_type}）")

        self._set_status("设置已保存", True)
        messagebox.showinfo("✅ 已保存", "所有设置已保存到 config.json")
        win.destroy()
