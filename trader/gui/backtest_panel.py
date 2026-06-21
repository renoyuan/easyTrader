#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME: easyTrader
# CREATE_TIME: 2026-06-09
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# note:  回测 GUI 面板

"""
回测 GUI 面板
==============
嵌入在主窗口右侧 Notebook 中，提供回测参数配置、执行、结果展示功能。
"""

import tkinter as tk
from tkinter import ttk, messagebox
import traceback
from datetime import datetime
import threading


# ── 主题色（与主窗口保持一致） ──
COLOR_PRIMARY = "#1a73e8"
COLOR_SUCCESS = "#34a853"
COLOR_WARNING = "#fbbc04"
COLOR_DANGER = "#ea4335"
COLOR_BG = "#f0f2f5"
COLOR_CARD_BG = "#ffffff"
COLOR_TEXT = "#202124"
COLOR_TEXT_SECONDARY = "#5f6368"


class BacktestPanel:
    """
    回测面板
    ========
    包含回测参数配置区、执行控制、结果展示。
    以新标签页形式嵌入右侧 Notebook。
    """

    # 可选评分体系（与 SCORER_MAP 键名一致）
    SCORER_NAMES = [
        "renoyuan核心评分",
        "巴菲特价值评分",
        "格雷厄姆价值评分",
        "徐翔趋势评分",
        "xubin财报排雷评分",
        "方老哥筹码趋势评分",
        "石头姐科技成长评分",
        "葛兰医药行业评分",
    ]

    def __init__(self, notebook: ttk.Notebook,
                 status_callback, info_callback,
                 tree_callback) -> None:
        """
        :param notebook: 右侧 Notebook，用于添加回测标签页
        :param status_callback: 更新状态栏回调 (msg, is_ok)
        :param info_callback: 追加文本回调 (msg)
        :param tree_callback: 更新摘要表格回调 (rows)
        """
        self._set_status = status_callback
        self._info = info_callback
        self._update_tree = tree_callback

        # ── 回测标签页 ──
        self.tab = tk.Frame(notebook, bg=COLOR_CARD_BG)
        notebook.add(self.tab, text="📈 回测")
        self._build_ui()

        # 运行时状态（类型用字符串标注避免导入）
        self._engine = None
        self._last_stats = None
        self._is_running = False

    def _build_ui(self) -> None:
        """构建回测标签页 UI"""
        # ── 顶部参数配置区 ──
        cfg_frame = tk.Frame(self.tab, bg=COLOR_CARD_BG)
        cfg_frame.pack(fill=tk.X, padx=10, pady=(10, 4))

        tk.Label(
            cfg_frame, text="🔬 量化回测",
            bg=COLOR_CARD_BG, fg=COLOR_TEXT,
            font=("微软雅黑", 13, "bold")
        ).pack(anchor=tk.W)

        # ── 参数网格 ──
        params = tk.Frame(self.tab, bg=COLOR_BG, relief=tk.RIDGE, bd=1)
        params.pack(fill=tk.X, padx=10, pady=4)

        # 第1行：股票代码 / 评分体系 / 最低评分
        row1 = tk.Frame(params, bg=COLOR_BG)
        row1.pack(fill=tk.X, padx=10, pady=(8, 4))

        tk.Label(row1, text="股票代码：", bg=COLOR_BG,
                 font=("微软雅黑", 9), fg=COLOR_TEXT).pack(side=tk.LEFT)
        self._code_entry = tk.Entry(row1, width=10, font=("Consolas", 9),
                                    relief=tk.SUNKEN, bd=1)
        self._code_entry.pack(side=tk.LEFT, padx=(2, 12))
        self._code_entry.insert(0, "600519")

        tk.Label(row1, text="评分体系：", bg=COLOR_BG,
                 font=("微软雅黑", 9), fg=COLOR_TEXT).pack(side=tk.LEFT)
        self._scorer_var = tk.StringVar(value=self.SCORER_NAMES[0])
        scorer_combo = ttk.Combobox(row1, textvariable=self._scorer_var,
                                     values=self.SCORER_NAMES,
                                     state="readonly", width=16,
                                     font=("微软雅黑", 9))
        scorer_combo.pack(side=tk.LEFT, padx=(2, 12))

        tk.Label(row1, text="最低评分：", bg=COLOR_BG,
                 font=("微软雅黑", 9), fg=COLOR_TEXT).pack(side=tk.LEFT)
        self._min_score_var = tk.StringVar(value="70")
        tk.Spinbox(row1, from_=0, to=100, textvariable=self._min_score_var,
                   width=5, font=("Consolas", 9),
                   relief=tk.SUNKEN, bd=1).pack(side=tk.LEFT, padx=(2, 0))

        # 第2行：起始日期 / 结束日期 / 初始资金
        row2 = tk.Frame(params, bg=COLOR_BG)
        row2.pack(fill=tk.X, padx=10, pady=4)

        tk.Label(row2, text="起始日期：", bg=COLOR_BG,
                 font=("微软雅黑", 9), fg=COLOR_TEXT).pack(side=tk.LEFT)
        self._start_entry = tk.Entry(row2, width=10, font=("Consolas", 9),
                                     relief=tk.SUNKEN, bd=1)
        self._start_entry.pack(side=tk.LEFT, padx=(2, 12))
        self._start_entry.insert(0, "20230101")

        tk.Label(row2, text="结束日期：", bg=COLOR_BG,
                 font=("微软雅黑", 9), fg=COLOR_TEXT).pack(side=tk.LEFT)
        self._end_entry = tk.Entry(row2, width=10, font=("Consolas", 9),
                                   relief=tk.SUNKEN, bd=1)
        self._end_entry.pack(side=tk.LEFT, padx=(2, 12))
        self._end_entry.insert(0, "20241231")

        tk.Label(row2, text="初始资金：", bg=COLOR_BG,
                 font=("微软雅黑", 9), fg=COLOR_TEXT).pack(side=tk.LEFT)
        self._capital_entry = tk.Entry(row2, width=12, font=("Consolas", 9),
                                       relief=tk.SUNKEN, bd=1)
        self._capital_entry.pack(side=tk.LEFT, padx=(2, 0))
        self._capital_entry.insert(0, "100000")

        # 第3行：风控参数
        row3 = tk.Frame(params, bg=COLOR_BG)
        row3.pack(fill=tk.X, padx=10, pady=(4, 8))

        tk.Label(row3, text="止损比例：", bg=COLOR_BG,
                 font=("微软雅黑", 9), fg=COLOR_TEXT).pack(side=tk.LEFT)
        self._sl_var = tk.StringVar(value="7")
        tk.Spinbox(row3, from_=1, to=30, textvariable=self._sl_var,
                   width=4, font=("Consolas", 9),
                   relief=tk.SUNKEN, bd=1).pack(side=tk.LEFT, padx=(2, 12))

        tk.Label(row3, text="止盈比例：", bg=COLOR_BG,
                 font=("微软雅黑", 9), fg=COLOR_TEXT).pack(side=tk.LEFT)
        self._sp_var = tk.StringVar(value="15")
        tk.Spinbox(row3, from_=1, to=50, textvariable=self._sp_var,
                   width=4, font=("Consolas", 9),
                   relief=tk.SUNKEN, bd=1).pack(side=tk.LEFT, padx=(2, 12))

        self._filter_var = tk.BooleanVar(value=True)
        tk.Checkbutton(row3, text="启用信号过滤", variable=self._filter_var,
                       bg=COLOR_BG, font=("微软雅黑", 9),
                       fg=COLOR_TEXT, selectcolor=COLOR_BG).pack(
                           side=tk.LEFT, padx=(16, 0))

        self._bs_var = tk.BooleanVar(value=True)
        tk.Checkbutton(row3, text="黑天鹅保护", variable=self._bs_var,
                       bg=COLOR_BG, font=("微软雅黑", 9),
                       fg=COLOR_TEXT, selectcolor=COLOR_BG).pack(
                           side=tk.LEFT, padx=(8, 0))

        # ── 操作按钮区 ──
        btn_frame = tk.Frame(self.tab, bg=COLOR_CARD_BG)
        btn_frame.pack(fill=tk.X, padx=10, pady=6)

        self._run_btn = tk.Button(
            btn_frame, text="🚀 开始回测", command=self.run_backtest,
            bg=COLOR_PRIMARY, fg="white",
            font=("微软雅黑", 10, "bold"),
            relief=tk.FLAT, bd=0, cursor="hand2",
            activebackground=COLOR_PRIMARY, activeforeground="white",
            padx=16, pady=6,
        )
        self._run_btn.pack(side=tk.LEFT)

        self._progress_var = tk.StringVar(value="")
        tk.Label(btn_frame, textvariable=self._progress_var,
                 bg=COLOR_CARD_BG, fg=COLOR_TEXT_SECONDARY,
                 font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=12)

        # ── 结果展示区分栏 ──
        result_pane = tk.PanedWindow(self.tab, orient=tk.VERTICAL,
                                     bg=COLOR_BG)
        result_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # ── 上方：回测报告文本 ──
        report_frame = tk.Frame(result_pane, bg=COLOR_CARD_BG,
                                relief=tk.RIDGE, bd=1)
        result_pane.add(report_frame, height=280)

        tk.Label(report_frame, text="📋 回测报告",
                 bg=COLOR_CARD_BG, fg=COLOR_TEXT,
                 font=("微软雅黑", 10, "bold")).pack(anchor=tk.W, padx=8, pady=(6, 0))

        self._report_text = tk.Text(
            report_frame, font=("Consolas", 9),
            bg="#fafafa", fg=COLOR_TEXT,
            wrap=tk.WORD, relief=tk.FLAT,
            padx=8, pady=6,
            highlightthickness=1, highlightcolor="#dadce0"
        )
        self._report_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        report_scroll = tk.Scrollbar(self._report_text,
                                     command=self._report_text.yview)
        report_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._report_text.config(yscrollcommand=report_scroll.set)

        # ── 下方：交易记录表格 ──
        trade_frame = tk.Frame(result_pane, bg=COLOR_CARD_BG,
                               relief=tk.RIDGE, bd=1)
        result_pane.add(trade_frame, height=180)

        # 切换视图的下拉框
        view_header = tk.Frame(trade_frame, bg=COLOR_CARD_BG)
        view_header.pack(fill=tk.X, padx=8, pady=(6, 0))

        tk.Label(view_header, text="📊 回测数据",
                 bg=COLOR_CARD_BG, fg=COLOR_TEXT,
                 font=("微软雅黑", 10, "bold")).pack(side=tk.LEFT)

        self._view_var = tk.StringVar(value="交易记录")
        view_combo = ttk.Combobox(view_header, textvariable=self._view_var,
                                   values=["交易记录", "入场信号归因", "离场原因归因",
                                           "信号过滤对比"],
                                   state="readonly", width=16,
                                   font=("微软雅黑", 9))
        view_combo.pack(side=tk.RIGHT)
        view_combo.bind("<<ComboboxSelected>>", self._on_view_switch)

        # 表格
        table_container = tk.Frame(trade_frame, bg=COLOR_CARD_BG)
        table_container.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # 可滚动表格用 Treeview
        self._trade_tree = ttk.Treeview(table_container, show="headings",
                                        height=6)
        trade_vsb = tk.Scrollbar(table_container, orient=tk.VERTICAL,
                                 command=self._trade_tree.yview)
        self._trade_tree.configure(yscrollcommand=trade_vsb.set)
        self._trade_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        trade_vsb.pack(side=tk.RIGHT, fill=tk.Y)

    # ═══════════════════════════════════════════
    #  回测执行
    # ═══════════════════════════════════════════

    def run_backtest(self) -> None:
        """启动回测（异步执行，不阻塞 UI）"""
        # ── 参数校验 ──
        code = self._code_entry.get().strip()
        if not code.isdigit() or len(code) != 6:
            messagebox.showwarning("参数错误", "请输入 6 位数字股票代码！")
            return

        try:
            start_date = self._start_entry.get().strip()
            end_date = self._end_entry.get().strip()
            initial_capital = float(self._capital_entry.get().strip())
            min_score = float(self._min_score_var.get().strip())
            sl_ratio = float(self._sl_var.get().strip()) / 100.0
            sp_ratio = float(self._sp_var.get().strip()) / 100.0
        except ValueError:
            messagebox.showwarning("参数错误", "请检查数字格式参数！")
            return

        scorer_name = self._scorer_var.get()
        enable_filter = self._filter_var.get()
        enable_bs = self._bs_var.get()

        if self._is_running:
            messagebox.showinfo("提示", "回测正在运行中，请等待完成")
            return

        self._is_running = True
        self._run_btn.config(state=tk.DISABLED, text="⏳ 回测中...")
        self._progress_var.set("初始化...")
        self._report_text.delete(1.0, tk.END)
        self._report_text.insert(tk.END, "🚀 回测启动中，请稍等...\n")

        # ── 异步执行 ──
        def task():
            try:
                self._do_backtest(code, start_date, end_date, initial_capital,
                                  scorer_name, min_score,
                                  sl_ratio, sp_ratio,
                                  enable_filter, enable_bs)
            finally:
                self._is_running = False
                self._run_btn.config(state=tk.NORMAL, text="🚀 开始回测")
                self._progress_var.set("")

        threading.Thread(target=task, daemon=True).start()

    def _do_backtest(self, code: str, start_date: str, end_date: str,
                     initial_capital: float, scorer_name: str, min_score: float,
                     sl_ratio: float, sp_ratio: float,
                     enable_filter: bool, enable_bs: bool) -> None:
        """实际执行回测逻辑（异步线程）"""
        # 延迟导入 backtest 引擎，避免 GUI 启动时加载 akshare 等依赖
        from trader.backtest import BacktestEngine, PerformanceStats
        from trader.backtest.signal import ScorerSignal
        from trader.backtest.filter import TrendFilter, MACrossFilter
        try:
            self._set_status("⏳ 加载数据中...", True)
            self._append_report(f"📥 加载 {code} K 线数据 {start_date}~{end_date}...\n")

            # 创建引擎
            engine = BacktestEngine(initial_capital=initial_capital)

            # 配置风控
            engine.risk_manager.sl_fixed_ratio = sl_ratio
            engine.risk_manager.sp_target_price_pct = sp_ratio
            engine.risk_manager.bs_enabled = enable_bs

            # 配置过滤
            engine.signal_filter.enabled = enable_filter
            if enable_filter:
                engine.signal_filter.add_filter(TrendFilter(ma_period=20))
                engine.signal_filter.add_filter(MACrossFilter())

            # 注册评分信号
            engine.signal_registry.register(
                ScorerSignal(scorer_name, min_score=min_score)
            )

            # 加载 K 线
            self._set_status("⏳ 加载K线...", True)
            success = engine.load_kline_from_db(code, start_date, end_date)
            if not success:
                self._append_report("❌ 无法加载 K 线数据，请确认股票代码和日期范围\n")
                self._set_status("回测失败", False)
                return

            # 执行回测
            self._set_status("⏳ 回测执行中...", True)
            self._append_report("⚙️ 开始遍历 K 线进行仿真...\n")

            def progress(current, total, msg):
                self._progress_var.set(f"{current}/{total} {msg}")

            stats = engine.run(code, scorer_name=scorer_name,
                               min_score=min_score,
                               progress_callback=progress)

            # 保存引用
            self._engine = engine
            self._last_stats = stats

            # ── 展示结果 ──
            self._append_report("\n" + stats.print_report())

            # 展示交易记录表格
            self._update_trade_table(engine)

            # 更新主窗口摘要树
            self._update_summary_tree(stats)

            # 完成
            self._set_status(f"✅ 回测完成: {code}", True)
            self._append_report("\n✅ 回测完成\n")

        except Exception as e:
            self._append_report(f"\n❌ 回测异常: {e}\n")
            traceback.print_exc()
            self._set_status(f"回测失败: {e}", False)

    # ═══════════════════════════════════════════
    #  UI 更新
    # ═══════════════════════════════════════════

    def _append_report(self, text: str) -> None:
        """向回测报告文本区追加内容（线程安全）"""
        self._report_text.after(0, lambda: (
            self._report_text.insert(tk.END, text),
            self._report_text.see(tk.END)
        ))

    def _update_trade_table(self, engine) -> None:
        """更新交易记录表格"""
        trades_df = engine.get_trades_df()
        if trades_df.empty:
            return

        # 在主线程中更新 UI
        self._trade_tree.after(0, lambda: self._fill_trade_tree(trades_df))

    def _fill_trade_tree(self, trades_df) -> None:
        """填充交易记录表格"""
        # 清空旧数据
        for item in self._trade_tree.get_children():
            self._trade_tree.delete(item)

        # 设置列
        cols = list(trades_df.columns)
        # 限制列数，避免太宽
        display_cols = [c for c in cols if c in (
            "trade_id", "code", "entry_date", "exit_date",
            "holding_period", "entry_price", "exit_price",
            "pnl_pct", "pnl", "exit_reason", "is_win"
        )]

        self._trade_tree["columns"] = display_cols
        for col in display_cols:
            self._trade_tree.heading(col, text=col)
            width = 80 if col in ("code", "is_win", "trade_id") else 100
            if col == "exit_reason":
                width = 120
            self._trade_tree.column(col, width=width, anchor=tk.CENTER)

        # 填入数据
        for _, row in trades_df.head(200).iterrows():
            values = [row.get(c, "") for c in display_cols]
            self._trade_tree.insert("", tk.END, values=values)

    def _update_summary_tree(self, stats) -> None:
        """更新主窗口摘要树"""
        rows = []
        d = stats.to_dict()
        for category, metrics in d.items():
            rows.append((f"── {category} ──", "", ""))
            for k, v in metrics.items():
                rows.append((f"  {k}", str(v), ""))
        self._update_tree(rows)

    def _on_view_switch(self, event=None) -> None:
        """切换表格视图"""
        view = self._view_var.get()
        if not self._engine:
            return

        # 清空表格
        for item in self._trade_tree.get_children():
            self._trade_tree.delete(item)

        if view == "入场信号归因":
            self._fill_signal_analysis()
        elif view == "离场原因归因":
            self._fill_exit_reason_analysis()
        elif view == "信号过滤对比":
            self._fill_filter_comparison()
        else:
            # 默认交易记录
            trades_df = self._engine.get_trades_df()
            if not trades_df.empty:
                self._fill_trade_tree(trades_df)

    def _fill_signal_analysis(self) -> None:
        """填充入场信号归因分析表"""
        if not self._engine or not self._last_stats:
            return

        signal_stats = self._last_stats.signal_source_stats
        cols = ["信号类型", "次数", "胜率", "盈亏比", "平均盈亏", "总盈亏"]
        self._trade_tree["columns"] = cols
        for col in cols:
            self._trade_tree.heading(col, text=col)
            self._trade_tree.column(col, width=100, anchor=tk.CENTER)

        for signal_name, info in signal_stats.items():
            self._trade_tree.insert("", tk.END, values=(
                signal_name,
                info["count"],
                f"{info['win_rate']:.1f}%",
                f"{info.get('profit_factor', 0):.2f}",
                f"{info['avg_pnl']:+.2f}",
                f"{info['total_pnl']:+.2f}",
            ))

    def _fill_exit_reason_analysis(self) -> None:
        """填充离场原因归因分析表"""
        if not self._engine or not self._last_stats:
            return

        exit_stats = self._last_stats.exit_reason_stats
        # 过滤掉 _filter_stats
        exit_stats = {k: v for k, v in exit_stats.items()
                      if not k.startswith("_")}
        cols = ["离场原因", "次数", "胜率", "平均盈亏", "总盈亏"]
        self._trade_tree["columns"] = cols
        for col in cols:
            self._trade_tree.heading(col, text=col)
            self._trade_tree.column(col, width=120, anchor=tk.CENTER)

        for reason, info in exit_stats.items():
            self._trade_tree.insert("", tk.END, values=(
                reason,
                info["count"],
                f"{info['win_rate']:.1f}%",
                f"{info['avg_pnl']:+.2f}",
                f"{info['total_pnl']:+.2f}",
            ))

    def _fill_filter_comparison(self) -> None:
        """填充信号过滤对比表"""
        filter_stats = self._last_stats.exit_reason_stats.get("_filter_stats", {})
        cols = ["指标", "数值"]
        self._trade_tree["columns"] = cols
        for col in cols:
            self._trade_tree.heading(col, text=col)
            self._trade_tree.column(col, width=200, anchor=tk.CENTER)

        for k, v in filter_stats.items():
            self._trade_tree.insert("", tk.END, values=(k, v))

    # ═══════════════════════════════════════════
    #  数据加载配置
    # ═══════════════════════════════════════════

    def load_data(self, code: str) -> None:
        """外部设置股票代码"""
        self._code_entry.delete(0, tk.END)
        self._code_entry.insert(0, code)
