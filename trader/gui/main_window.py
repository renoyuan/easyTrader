"""
easyTrader 主窗口
=================
负责整体布局、左侧操作面板、右侧结果展示区、
历史记录标签页以及状态栏。
"""
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk


# ──────────────────────────────────────────────
#  主题配色（与原有保持一致）
# ──────────────────────────────────────────────
COLOR_BG = "#f0f2f5"
COLOR_PRIMARY = "#1a73e8"
COLOR_SUCCESS = "#34a853"
COLOR_WARNING = "#fbbc04"
COLOR_DANGER = "#ea4335"
COLOR_CARD_BG = "#ffffff"
COLOR_TEXT = "#202124"
COLOR_TEXT_SECONDARY = "#5f6368"

FONT_TITLE = ("微软雅黑", 14, "bold")
FONT_NORMAL = ("微软雅黑", 10)
FONT_MONO = ("Consolas", 10)


class EasyTraderGUI:
    """easyTrader 图形界面主类"""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("easyTrader · 价值评分系统")
        self.root.geometry("850x700")
        self.root.configure(bg=COLOR_BG)
        self.root.minsize(750, 600)

        # 股票代码
        self.symbol: str | None = None

        # ── 延迟导入子面板（避免循环依赖） ──
        from .scorer_panel import ScorerPanel
        from .settings_panel import SettingsPanel
        from .reviewer_panel import ReviewerPanel

        # ── 先初始化子面板（被 _build_widgets 引用） ──
        self.scorer = ScorerPanel(
            status_callback=self._set_status,
            info_callback=self._info,
            tree_callback=self._update_tree,
            history_callback=self._add_history,
            notebook_select_callback=lambda i: self.notebook.select(i),
        )
        self.settings = SettingsPanel(
            parent=self.root,
            status_callback=self._set_status,
            info_callback=self._info,
        )
        self.reviewer = ReviewerPanel(
            status_callback=self._set_status,
            info_callback=self._info,
            tree_callback=self._update_tree,
            notebook_select_callback=lambda i: self.notebook.select(i),
        )

        # ── 构建界面（此时 self.scorer / self.settings / self.reviewer 已就绪） ──
        self._build_widgets()

        # ── 初始提示 ──
        self._info("欢迎使用 easyTrader 价值评分系统\n请点击「输入股票代码」开始分析")

    # ==========================================
    #  界面构建
    # ==========================================
    def _build_widgets(self) -> None:
        # ── 顶部标题栏 ──
        header = tk.Frame(self.root, bg=COLOR_PRIMARY, height=56)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header, text="📊  easyTrader · 股神模拟器",
            fg="white", bg=COLOR_PRIMARY,
            font=("微软雅黑", 16, "bold")
        ).pack(side=tk.LEFT, padx=20, pady=12)

        self.stock_label = tk.Label(
            header, text="未选择股票",
            fg="#e8eaed", bg=COLOR_PRIMARY,
            font=("微软雅黑", 10)
        )
        self.stock_label.pack(side=tk.RIGHT, padx=20, pady=12)

        # ── 主内容区（左右分栏） ──
        main_panel = tk.Frame(self.root, bg=COLOR_BG)
        main_panel.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        # ======== 左栏：操作区 ========
        left = tk.Frame(main_panel, bg=COLOR_CARD_BG, relief=tk.RIDGE, bd=1)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10), pady=0)
        left.pack_propagate(False)
        left.configure(width=220)

        tk.Label(
            left, text="操 作 面 板", bg=COLOR_CARD_BG,
            font=FONT_TITLE, fg=COLOR_TEXT
        ).pack(pady=(16, 10))

        # 按钮组
        btn_frame = tk.Frame(left, bg=COLOR_CARD_BG)
        btn_frame.pack(pady=5, padx=12, fill=tk.X)

        # ═══════════ 股神评分 ═══════════
        tk.Label(
            btn_frame, text="══════ 股神评分 ══════",
            bg=COLOR_CARD_BG, fg=COLOR_TEXT_SECONDARY,
            font=("微软雅黑", 9, "bold")
        ).pack(fill=tk.X, pady=(6, 4))

        # ── 输入股票代码 ──
        tk.Button(
            btn_frame, text="📥 输入代码",
            command=self.input_code,
            bg=COLOR_PRIMARY, fg="white",
            font=("微软雅黑", 9, "bold"),
            relief=tk.FLAT, bd=0,
            cursor="hand2",
            activebackground=COLOR_PRIMARY,
            activeforeground="white",
            padx=6, pady=4,
        ).pack(fill=tk.X, pady=2)

        # 评分体系下拉框（在此处创建，渲染在按钮组内部）
        self.scorer.build_selector(btn_frame)

        # ═══════ 并排两个按钮：开始评分 + 扫描市场 ═══════
        action_frame = tk.Frame(btn_frame, bg=COLOR_CARD_BG)
        action_frame.pack(fill=tk.X, pady=2)

        tk.Button(
            action_frame, text="🌟 开始评分",
            command=self.scorer.run_scoring,
            bg=COLOR_SUCCESS, fg="white",
            font=("微软雅黑", 9, "bold"),
            relief=tk.FLAT, bd=0,
            cursor="hand2",
            activebackground=COLOR_SUCCESS,
            activeforeground="white",
            padx=4, pady=5,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Button(
            action_frame, text="🔍 扫描市场",
            command=lambda: self.scorer.run_market_scan(self.root),
            bg="#ff6d00", fg="white",
            font=("微软雅黑", 9, "bold"),
            relief=tk.FLAT, bd=0,
            cursor="hand2",
            activebackground="#ff6d00",
            activeforeground="white",
            padx=4, pady=5,
        ).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))

        # ═══════════ 股神复盘 ═══════════
        tk.Label(
            btn_frame, text="══════ 股神复盘 ══════",
            bg=COLOR_CARD_BG, fg=COLOR_TEXT_SECONDARY,
            font=("微软雅黑", 9, "bold")
        ).pack(fill=tk.X, pady=(10, 2))

        self._create_styled_button(
            btn_frame, "📈  市场复盘",
            self.reviewer.run_market_review, "#0f9d58"
        ).pack(fill=tk.X, pady=4)

        self._create_styled_button(
            btn_frame, "📋  个股复盘",
            self.input_stock_review_code, "#ab47bc"
        ).pack(fill=tk.X, pady=4)

        # ═══════════ 分隔 + 工具 ═══════════
        ttk.Separator(btn_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        self._create_styled_button(
            btn_frame, "⚙  设置 Tushare Token",
            self.settings.setup_tushare, "#5f6368"
        ).pack(fill=tk.X, pady=4)

        self._create_styled_button(
            btn_frame, "🤖  设置 DeepSeek Key",
            self.settings.setup_deepseek, "#5f6368"
        ).pack(fill=tk.X, pady=4)

        self._create_styled_button(
            btn_frame, "🗑  清空结果",
            self.clear_output, COLOR_DANGER
        ).pack(fill=tk.X, pady=4)

        # 状态指示
        self.status_var = tk.StringVar(value="就绪 ✅")
        tk.Label(
            left, textvariable=self.status_var,
            bg=COLOR_CARD_BG, fg=COLOR_TEXT_SECONDARY,
            font=FONT_NORMAL
        ).pack(pady=(20, 10))

        # ======== 右栏：结果区 ========
        right = tk.Frame(main_panel, bg=COLOR_CARD_BG, relief=tk.RIDGE, bd=1)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # 结果标签页
        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # ---- Tab 1: 文本结果 ----
        text_tab = tk.Frame(self.notebook, bg=COLOR_CARD_BG)
        self.notebook.add(text_tab, text="📋 详细报告")

        self.text = tk.Text(
            text_tab, font=FONT_MONO,
            bg="#fafafa", fg=COLOR_TEXT,
            wrap=tk.WORD, relief=tk.FLAT,
            padx=10, pady=10,
            highlightthickness=1,
            highlightcolor="#dadce0"
        )
        self.text.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(self.text, command=self.text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.config(yscrollcommand=scrollbar.set)

        # ---- Tab 2: 评分摘要（表格） ----
        table_tab = tk.Frame(self.notebook, bg=COLOR_CARD_BG)
        self.notebook.add(table_tab, text="📊 评分摘要")

        self.tree = ttk.Treeview(
            table_tab,
            columns=("项目", "分值", "评级"),
            show="headings",
            height=12
        )
        self.tree.heading("项目", text="评分项目")
        self.tree.heading("分值", text="分值")
        self.tree.heading("评级", text="评级 / 说明")
        self.tree.column("项目", width=160, anchor=tk.W)
        self.tree.column("分值", width=100, anchor=tk.CENTER)
        self.tree.column("评级", width=200, anchor=tk.W)

        vsb = tk.Scrollbar(table_tab, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # ---- Tab 3: 历史记录 ----
        history_tab = tk.Frame(self.notebook, bg=COLOR_CARD_BG)
        self.notebook.add(history_tab, text="📜 历史记录")

        self.history_tree = ttk.Treeview(
            history_tab,
            columns=("股票", "评分体系", "总分", "评级"),
            show="headings",
            height=12
        )
        self.history_tree.heading("股票", text="股票代码")
        self.history_tree.heading("评分体系", text="评分体系")
        self.history_tree.heading("总分", text="总分")
        self.history_tree.heading("评级", text="评级")
        self.history_tree.column("股票", width=100, anchor=tk.CENTER)
        self.history_tree.column("评分体系", width=120, anchor=tk.CENTER)
        self.history_tree.column("总分", width=80, anchor=tk.CENTER)
        self.history_tree.column("评级", width=280, anchor=tk.W)

        h_vsb = tk.Scrollbar(history_tab, orient=tk.VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=h_vsb.set)
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        h_vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # ── 底部状态栏 ──
        status_bar = tk.Frame(self.root, bg="#e8eaed", height=28)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        status_bar.pack_propagate(False)

        tk.Label(
            status_bar, text="v1.0 | 数据来源: akshare / tushare",
            bg="#e8eaed", fg=COLOR_TEXT_SECONDARY,
            font=("微软雅黑", 8)
        ).pack(side=tk.LEFT, padx=12)

    @staticmethod
    def _create_styled_button(parent: tk.Frame, text: str,
                               command, color: str) -> tk.Button:
        return tk.Button(
            parent, text=text, command=command,
            bg=color, fg="white",
            font=("微软雅黑", 10, "bold"),
            relief=tk.FLAT, bd=0,
            cursor="hand2",
            activebackground=color,
            activeforeground="white",
            padx=10, pady=8
        )

    # ==========================================
    #  工具方法
    # ==========================================
    def _set_status(self, msg: str, is_ok: bool = True) -> None:
        icon = "✅" if is_ok else "⚠️"
        self.status_var.set(f"{icon} {msg}")

    def _info(self, msg: str) -> None:
        self.text.insert(tk.END, msg + "\n")
        self.text.see(tk.END)

    def _update_tree(self, rows: list[tuple]) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in rows:
            self.tree.insert("", tk.END, values=row)

    def _add_history(self, code: str, system: str, score: int, rating: str) -> None:
        self.history_tree.insert("", 0, values=(code, system, f"{score}/100", rating))

    # ==========================================
    #  输入股票代码
    # ==========================================
    def input_code(self) -> None:
        code = simpledialog.askstring(
            "股票代码",
            "请输入 6 位股票代码：\n例如：600519（贵州茅台）",
            parent=self.root
        )
        if code is None:
            return
        code = code.strip()
        if code.isdigit() and len(code) == 6:
            self.symbol = code
            self.scorer.symbol = code
            self.stock_label.config(text=f"当前股票: {code}")
            self._set_status(f"已选择股票 {code}")
            self._info(f"\n{'='*50}\n📌 已选择股票: {code}\n{'='*50}\n")
        else:
            messagebox.showerror("输入错误", "请输入 6 位数字股票代码！")
            self._set_status("输入格式错误", False)

    # ==========================================
    #  个股复盘（独立弹窗输入）
    # ==========================================
    def input_stock_review_code(self) -> None:
        code = simpledialog.askstring(
            "个股复盘",
            "请输入要复盘的 6 位股票代码：\n例如：600519（贵州茅台）",
            parent=self.root
        )
        if code is None:
            return
        code = code.strip()
        if code.isdigit() and len(code) == 6:
            self.reviewer.run_stock_review(code)
        else:
            messagebox.showerror("输入错误", "请输入 6 位数字股票代码！")

    # ==========================================
    #  清空结果
    # ==========================================
    def clear_output(self) -> None:
        self.text.delete(1.0, tk.END)
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._set_status("已清空")
