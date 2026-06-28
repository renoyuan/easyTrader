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

        # ── 风控默认配置（可在弹窗中修改） ──
        # 止损
        self._risk_sl_fixed_ratio = 0.07       # 固定比例止损 7%
        self._risk_sl_atr_multiplier = 2.0      # ATR 动态止损倍数
        self._risk_sl_atr_enabled = True        # 启用 ATR 动态止损
        # 止盈模式： "graded" = 分级止盈, "target" = 目标价止盈
        self._risk_sp_mode = "graded"
        self._risk_sp_graded_levels = [
            (0.05, 0.3),
            (0.10, 0.3),
            (0.15, 0.4),
        ]
        self._risk_sp_target_price_pct = 0.15   # 目标价止盈比例

        # 时间止损（最大持股时间）
        self._risk_ts_enabled = True
        self._risk_ts_max_bars = 60
        self._risk_bs_enabled = True  # 黑天鹅默认开启

        # ── 回测标签页 ──
        self.tab = tk.Frame(notebook, bg=COLOR_CARD_BG)
        notebook.add(self.tab, text="📈 回测")
        self._build_ui()

        # 运行时状态（类型用字符串标注避免导入）
        self._engine = None
        self._last_stats = None
        self._is_running = False
        self._daily_log_enabled = True      # [新增] 每日日志开关

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
        self._min_score_var = tk.StringVar(value="80")
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
        self._capital_entry.insert(0, "1000000")

                # 第3行：仓位模式 + 设置风控按钮（独立弹窗）
        row3 = tk.Frame(params, bg=COLOR_BG)
        row3.pack(fill=tk.X, padx=10, pady=(4, 8))

        tk.Label(row3, text="仓位模式：", bg=COLOR_BG,
                 font=("微软雅黑", 9), fg=COLOR_TEXT).pack(side=tk.LEFT)
        self._pos_var = tk.StringVar(value="100% 满仓")
        pos_combo = ttk.Combobox(row3, textvariable=self._pos_var,
                                  values=["100% 满仓", "50% 中仓", "20% 轻仓", "10% 保守"],
                                  state="readonly", width=12,
                                  font=("微软雅黑", 9))
        pos_combo.pack(side=tk.LEFT, padx=(2, 12))

        tk.Button(
            row3, text="⚙ 设置止盈止损",
            command=self._open_risk_settings,
            bg="#5f6368", fg="white",
            font=("微软雅黑", 9, "bold"),
            relief=tk.FLAT, bd=0, cursor="hand2",
            activebackground="#5f6368", activeforeground="white",
            padx=12, pady=4,
        ).pack(side=tk.LEFT, padx=(0, 12))

        self._filter_var = tk.BooleanVar(value=True)
        tk.Checkbutton(row3, text="信号过滤", variable=self._filter_var,
                       bg=COLOR_BG, font=("微软雅黑", 9),
                       fg=COLOR_TEXT, selectcolor=COLOR_BG).pack(
                           side=tk.LEFT, padx=(4, 0))

        self._bs_var = tk.BooleanVar(value=True)
        # 黑天鹅移入止盈止损弹窗，此处不再显示

        self._daily_log_var = tk.BooleanVar(value=True)
        tk.Checkbutton(row3, text="日志", variable=self._daily_log_var,
                       bg=COLOR_BG, font=("微软雅黑", 9),
                       fg=COLOR_TEXT, selectcolor=COLOR_BG).pack(
                           side=tk.LEFT, padx=(6, 0))

        self._risk_status_var = tk.StringVar(value="止盈:分级 止损:7%+ATR")
        tk.Label(row3, textvariable=self._risk_status_var,
                 bg=COLOR_BG, fg=COLOR_TEXT_SECONDARY,
                 font=("微软雅黑", 8)).pack(side=tk.LEFT, padx=(8, 0))

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

        # ── 规则帮助按钮 ──
        self._help_btn = tk.Button(
            btn_frame, text="❓ 规则帮助", command=self._show_help,
            bg=COLOR_CARD_BG, fg=COLOR_PRIMARY,
            font=("微软雅黑", 9),
            relief=tk.RIDGE, bd=1, cursor="hand2",
            activebackground=COLOR_BG, activeforeground=COLOR_PRIMARY,
            padx=10, pady=4,
        )
        self._help_btn.pack(side=tk.LEFT, padx=(8, 0))

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
            pos_text = self._pos_var.get().strip()
            pos_ratio = float(pos_text.split("%")[0]) / 100.0
        except ValueError:
            messagebox.showwarning("参数错误", "请检查数字格式参数！")
            return

        scorer_name = self._scorer_var.get()
        enable_filter = self._filter_var.get()
        enable_bs = getattr(self, '_risk_bs_enabled', True)
        enable_daily_log = self._daily_log_var.get()

        # ── 风控参数（从独立配置中读取） ──
        sl_ratio = self._risk_sl_fixed_ratio
        sp_ratio = self._risk_sp_target_price_pct
        atr_multiplier = self._risk_sl_atr_multiplier if self._risk_sl_atr_enabled else 0.0

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
                                  sl_ratio, sp_ratio, atr_multiplier, pos_ratio,
                                  enable_filter, enable_bs, enable_daily_log)
            finally:
                self._is_running = False
                self._run_btn.config(state=tk.NORMAL, text="🚀 开始回测")
                self._progress_var.set("")

        threading.Thread(target=task, daemon=True).start()

    def _do_backtest(self, code: str, start_date: str, end_date: str,
                         initial_capital: float, scorer_name: str, min_score: float,
                         sl_ratio: float, sp_ratio: float, atr_multiplier: float = 2.0, pos_ratio: float = 1.0,
                         enable_filter: bool = True, enable_bs: bool = True, enable_daily_log: bool = True) -> None:
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

            # 配置仓位
            engine.fixed_position_ratio = pos_ratio

                        # 配置风控
            engine.risk_manager.sl_fixed_ratio = sl_ratio
            engine.risk_manager.sl_atr_multiplier = atr_multiplier if atr_multiplier > 0 else self._risk_sl_atr_multiplier
            engine.risk_manager.bs_enabled = enable_bs

            # 配置时间止损
            engine.risk_manager.ts_enabled = self._risk_ts_enabled
            engine.risk_manager.ts_max_bars = self._risk_ts_max_bars

            # ── 配置止盈模式（互斥） ──
            engine.risk_manager.sp_mode = self._risk_sp_mode
            if self._risk_sp_mode == "graded":
                engine.risk_manager.sp_graded_levels = self._risk_sp_graded_levels
                self._append_report(f"📌 止盈模式: 分级止盈 {self._risk_sp_graded_levels}\n")
            else:
                engine.risk_manager.sp_target_price_pct = sp_ratio
                self._append_report(f"📌 止盈模式: 目标价止盈 {sp_ratio:.0%}\n")

            # 配置过滤
            engine.signal_filter.enabled = enable_filter
            if enable_filter:
                engine.signal_filter.add_filter(TrendFilter(ma_period=20))
                engine.signal_filter.add_filter(MACrossFilter())

            # 注册评分信号
            engine.signal_registry.register(
                ScorerSignal(scorer_name, min_score=min_score)
            )

            # ── [新增] 挂载每日日志回调 ──
            if enable_daily_log:
                self._append_report("📅 每日回测日志已开启\n")
                self._append_report(f"{'日期':<12} {'本金':>10} {'总资产':>10} {'评分/持仓':<18} {'今日涨跌':>8} {'原因/浮盈':<40} {'费用':>8}\n")
                self._append_report(f"{'-'*120}\n")
                self._last_log_date = None

                def daily_log_callback(daily_info: dict) -> None:
                    # [修复] 每个交易日都输出日志，不跳过任何一天
                    # 有持仓/开平仓 → 完整日志（含浮盈）
                    # 空仓 → 精简日志（节省空间，但仍每日输出）
                    self._append_daily_log(daily_info)

                engine.on_daily_log_callback = daily_log_callback
            else:
                engine.on_daily_log_callback = None

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
    #  规则帮助弹窗
    # ═══════════════════════════════════════════

    def _show_help(self) -> None:
        """弹出规则说明窗口"""
        help_text = """📖 回测规则说明

━━━━━━━━━━━━━━━━━━━━━━━━━━━
1️⃣  入场规则（开仓条件）
━━━━━━━━━━━━━━━━━━━━━━━━━━━

必须同时满足以下条件才开仓：

① 评分达标
   所选评分体系对标的的评分 ≥ 最低评分阈值（默认 70 分）
   评分基于财务/基本面数据，非 K 线技术指标

② 信号过滤（可选，默认开启）
   勾选"启用信号过滤"时，额外检查以下条件：

   a. 趋势过滤（TrendFilter MA20）
      收盘价 ≥ MA20（20日均线），否则视为非上升趋势
      作用：避免在下跌趋势中抄底

   b. 均线多空过滤（MACrossFilter MA5>MA10>MA20）
      短期均线 > 中期 > 长期，多头排列才允许入场
      作用：过滤均线空头排列的反弹假信号

③ 资金充足
   仓位金额 = 总资金 × 仓位比例（下限 1 手=100股）
   股价过高时可能买不起整手 → 日志提示"未开仓"

━━━━━━━━━━━━━━━━━━━━━━━━━━━
2️⃣  持仓规则
━━━━━━━━━━━━━━━━━━━━━━━━━━━

开仓后每日跟踪持仓状态，实时更新：
  · 浮盈/浮亏
  · 持仓天数
  · 最高/最低价（用于止盈止损判断）

━━━━━━━━━━━━━━━━━━━━━━━━━━━
3️⃣  离场规则（平仓条件）
━━━━━━━━━━━━━━━━━━━━━━━━━━━

任一条件触发即平仓：

① 固定比例止损（默认 -7%）
   持仓亏损达到页面设定的"止损比例"时强制平仓
   计算公式：止损价 = 成本价 × (1 - 止损比例)
   特点：固定价格线，简单直接

② ATR 动态止损（默认 2.0 倍）
   基于真实波幅均值（ATR）计算动态止损位
   计算公式：止损价 = 成本价 - ATR倍数 × ATR
   特点：自动适应市场波动，波动大时止损位宽，波动小时止损位窄
   示例：成本 100 元，ATR=3，ATR倍数=2.0 → 止损价 94 元（-6%）
         成本 100 元，ATR=8，ATR倍数=2.0 → 止损价 84 元（-16%）
   提示：倍数越小止损越紧，默认 2.0 较激进；推荐 3.0~4.0 更宽松

③ 固定比例止盈（默认 +15%）
   持仓盈利达到页面设定的"止盈比例"时止盈离场
   计算公式：止盈价 = 成本价 × (1 + 止盈比例)

④ 黑天鹅保护（可选，默认开启）
   当日跌幅超过 -9% 时触发紧急平仓
   作用：防止突发利空导致大幅亏损

⑤ 时间止损（策略内嵌）
   持仓超过 120 个交易日强制平仓
   作用：避免资金长期被套

⑥ 策略结束（强制平仓）
   回测周期结束时，所有持仓强制卖出

━━━━━━━━━━━━━━━━━━━━━━━━━━━
4️⃣  仓位模式说明
━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────┬───────┬──────────────────────────┐
│ 模式       │ 比例  │ 适用场景                  │
├────────────┼───────┼──────────────────────────┤
│ 100% 满仓  │ 100%  │ 高股价标的（如茅台600519）│
│ 50% 中仓   │  50%  │ 普通个股分散配置           │
│ 20% 轻仓   │  20%  │ 小仓位试探性建仓           │
│ 10% 保守   │  10%  │ 极端保守分批建仓           │
└────────────┴───────┴──────────────────────────┘

计算方式：开仓金额 = 当前总资金 × 仓位比例
         开仓股数 = floor(开仓金额 / 股价 / 100) × 100

━━━━━━━━━━━━━━━━━━━━━━━━━━━
5️⃣  费用模型
━━━━━━━━━━━━━━━━━━━━━━━━━━━

  · 佣金：万分之三（双边）
  · 滑点：千分之一（双边）
  · 印花税：千分之一（仅卖出）

━━━━━━━━━━━━━━━━━━━━━━━━━━━
6️⃣  每日日志字段说明
━━━━━━━━━━━━━━━━━━━━━━━━━━━

  📅 日期       → 当前交易日
  💰 本金        → 当日可用资金
  📊 总资产      → 本金 + 持仓市值
  🏷 评分/持仓   → 评分(评级) 或 N股@成本价
  📈 今日涨跌    → 当日涨跌幅
  📝 原因/浮盈   → 空仓原因 或 浮盈金额(百分比)
  💸 费用        → 累计交易费用
"""

        win = tk.Toplevel(self.tab)
        win.title("📖 回测规则说明")
        win.geometry("680x600")
        win.configure(bg=COLOR_CARD_BG)
        win.transient(self.tab)
        win.grab_set()

        # 文本区域
        text = tk.Text(win, font=("Consolas", 9),
                       bg="#fafafa", fg=COLOR_TEXT,
                       wrap=tk.WORD, relief=tk.FLAT,
                       padx=12, pady=10)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text.insert(1.0, help_text)
        text.config(state=tk.DISABLED)

        # 关闭按钮
        tk.Button(win, text="关闭", command=win.destroy,
                  bg=COLOR_PRIMARY, fg="white",
                  font=("微软雅黑", 9),
                  relief=tk.FLAT, padx=20, pady=4
                  ).pack(pady=(0, 10))

    # ═══════════════════════════════════════════
    #  每日日志输出
    # ═══════════════════════════════════════════

    def _append_daily_log(self, info: dict) -> None:
        """格式化每日日志并追加到回测报告区（线程安全）

        两种模式：
        - 空仓观望 → 精简模式 + 简洁空仓原因
        - 有持仓/开平仓 → 完整模式（含浮盈、持仓明细、交易说明）
        """
        # 确定当日交易说明
        notes = []
        if info["just_opened"]:
            notes.append("🟢 开仓买入")
        if info["just_closed"]:
            notes.append("🔴 平仓卖出")
        if info["has_position"]:
            if not info["just_opened"] and not info["just_closed"]:
                notes.append("持有中")
        else:
            if not info["just_opened"] and not info["just_closed"]:
                notes.append("空仓")

        note_str = " | ".join(notes) if notes else ""

        if info["has_position"]:
            # ── 完整模式（有持仓）：含浮盈和持仓明细 ──
            unrealized_info = ""
            if info["position_unrealized_pnl"] != 0:
                pnl = info["position_unrealized_pnl"]
                pnl_pct = info["position_unrealized_pnl_pct"]
                sign = "+" if pnl > 0 else ""
                unrealized_info = f"{sign}{pnl:.2f}({pnl_pct:+.2f}%)"

            pos_info = f"{info['position_quantity']}股@{info['position_cost']}"

            line = (
                f"{info['date']:<12} "
                f"{info['capital']:>10.2f} "
                f"{info['total_value']:>10.2f} "
                f"{pos_info:<16} "
                f"{info['today_pct_chg']:>+7.2f}% "
                f"{unrealized_info:<22} "
                f"{info['total_fee']:>8.2f}  "
                f"{note_str}"
            )

            if info["just_opened"] or info["just_closed"]:
                line = f"  ▶ {line}"
        else:
            # ── 精简模式（空仓）：简洁空仓原因 ──
            score_str = f"评分={info.get('today_score', 0)}"
            score = info.get("today_score", 0)
            min_score_val = self._min_score_var.get().strip() if hasattr(self, '_min_score_var') else "80"
            if score > 0 and score < float(min_score_val):
                reason_short = f"评分{score}<阈值{min_score_val}"
            elif info.get("open_skipped_reason", ""):
                reason_short = info["open_skipped_reason"]
            elif info.get("signal_reason", ""):
                reason_short = info["signal_reason"]
            elif info.get("signal_triggered", False) and not info.get("filter_passed", False):
                reason_short = f"被过滤({info.get('filter_reason', '')})"
            else:
                reason_short = "无信号"

            line = (
                f"{info['date']:<12} "
                f"{info['capital']:>10.2f} "
                f"{info['total_value']:>10.2f} "
                f"{score_str:<18} "
                f"{info['today_pct_chg']:>+7.2f}% "
                f"{reason_short:<40} "
                f"{info['total_fee']:>8.2f}"
            )

        self._append_report(line + "\n")

    # ═══════════════════════════════════════════
    #  止盈止损独立配置弹窗
    # ═══════════════════════════════════════════

    def _open_risk_settings(self) -> None:
        """打开止盈止损独立配置弹窗"""
        win = tk.Toplevel(self.tab)
        win.title("⚙ 止盈止损配置")
        win.geometry("520x480")
        win.configure(bg=COLOR_CARD_BG)
        win.transient(self.tab)
        win.grab_set()
        win.resizable(False, False)

        # ── 止损区域 ──
        sl_frame = tk.LabelFrame(win, text="⛔ 止损配置", bg=COLOR_CARD_BG,
                                  font=("微软雅黑", 10, "bold"),
                                  fg=COLOR_TEXT,
                                  relief=tk.RIDGE, bd=1, padx=10, pady=8)
        sl_frame.pack(fill=tk.X, padx=15, pady=(12, 6))

        # 固定比例止损
        row_sl1 = tk.Frame(sl_frame, bg=COLOR_CARD_BG)
        row_sl1.pack(fill=tk.X, pady=3)

        self._risk_sl_fixed_var = tk.DoubleVar(value=self._risk_sl_fixed_ratio * 100)
        tk.Label(row_sl1, text="固定比例止损：", bg=COLOR_CARD_BG,
                 font=("微软雅黑", 9), fg=COLOR_TEXT,
                 width=14, anchor=tk.W).pack(side=tk.LEFT)
        tk.Spinbox(row_sl1, from_=0, to=30, textvariable=self._risk_sl_fixed_var,
                   width=6, font=("Consolas", 9),
                   relief=tk.SUNKEN, bd=1).pack(side=tk.LEFT, padx=(2, 4))
        tk.Label(row_sl1, text="%", bg=COLOR_CARD_BG,
                 font=("微软雅黑", 9), fg=COLOR_TEXT).pack(side=tk.LEFT)
        tk.Label(row_sl1, text="  跌超此比例 → 全仓卖出", bg=COLOR_CARD_BG,
                 font=("微软雅黑", 8), fg=COLOR_TEXT_SECONDARY).pack(side=tk.LEFT, padx=(6, 0))

        # ATR 动态止损
        row_sl2 = tk.Frame(sl_frame, bg=COLOR_CARD_BG)
        row_sl2.pack(fill=tk.X, pady=3)

        self._risk_sl_atr_enabled_var = tk.BooleanVar(value=self._risk_sl_atr_enabled)
        tk.Checkbutton(row_sl2, text="启用 ATR 动态止损", variable=self._risk_sl_atr_enabled_var,
                       bg=COLOR_CARD_BG, font=("微软雅黑", 9),
                       fg=COLOR_TEXT, selectcolor=COLOR_CARD_BG).pack(side=tk.LEFT)

        self._risk_sl_atr_var = tk.DoubleVar(value=self._risk_sl_atr_multiplier)
        tk.Spinbox(row_sl2, from_=1.0, to=6.0, increment=0.5,
                   textvariable=self._risk_sl_atr_var,
                   width=6, font=("Consolas", 9),
                   relief=tk.SUNKEN, bd=1).pack(side=tk.LEFT, padx=(6, 4))
        tk.Label(row_sl2, text="倍 ATR", bg=COLOR_CARD_BG,
                 font=("微软雅黑", 9), fg=COLOR_TEXT).pack(side=tk.LEFT)
        tk.Label(row_sl2, text="  (越大越宽松)", bg=COLOR_CARD_BG,
                 font=("微软雅黑", 8), fg=COLOR_TEXT_SECONDARY).pack(side=tk.LEFT)

        # ATR 动态止损
        row_sl3 = tk.Frame(sl_frame, bg=COLOR_CARD_BG)
        row_sl3.pack(fill=tk.X, pady=3)

        self._risk_bs_enabled_var = tk.BooleanVar(value=self._risk_bs_enabled if hasattr(self, '_risk_bs_enabled') else True)
        tk.Checkbutton(row_sl3, text="启用黑天鹅保护（单日跌超10%/大盘跌超5%/跳空击穿→市价平仓）",
                       variable=self._risk_bs_enabled_var,
                       bg=COLOR_CARD_BG, font=("微软雅黑", 9),
                       fg=COLOR_TEXT, selectcolor=COLOR_CARD_BG).pack(side=tk.LEFT)

                # ── 分隔线 ──
        ttk.Separator(win, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=15, pady=6)

        # ── 时间止损区域 ──
        ts_frame = tk.LabelFrame(win, text="⏱ 最大持股时间", bg=COLOR_CARD_BG,
                                  font=("微软雅黑", 10, "bold"),
                                  fg=COLOR_TEXT,
                                  relief=tk.RIDGE, bd=1, padx=10, pady=8)
        ts_frame.pack(fill=tk.X, padx=15, pady=6)

        row_ts1 = tk.Frame(ts_frame, bg=COLOR_CARD_BG)
        row_ts1.pack(fill=tk.X, pady=3)

        self._risk_ts_enabled_var = tk.BooleanVar(value=self._risk_ts_enabled if hasattr(self, '_risk_ts_enabled') else True)
        tk.Checkbutton(row_ts1, text="启用时间止损", variable=self._risk_ts_enabled_var,
                       bg=COLOR_CARD_BG, font=("微软雅黑", 9),
                       fg=COLOR_TEXT, selectcolor=COLOR_CARD_BG).pack(side=tk.LEFT)

        self._risk_ts_max_bars_var = tk.IntVar(value=self._risk_ts_max_bars if hasattr(self, '_risk_ts_max_bars') else 60)
        tk.Label(row_ts1, text="  持股超过", bg=COLOR_CARD_BG,
                 font=("微软雅黑", 9), fg=COLOR_TEXT).pack(side=tk.LEFT, padx=(6, 0))
        tk.Spinbox(row_ts1, from_=10, to=240, textvariable=self._risk_ts_max_bars_var,
                   width=6, font=("Consolas", 9),
                   relief=tk.SUNKEN, bd=1).pack(side=tk.LEFT, padx=(4, 2))
        tk.Label(row_ts1, text="根K线 → 强制卖出", bg=COLOR_CARD_BG,
                 font=("微软雅黑", 9), fg=COLOR_TEXT).pack(side=tk.LEFT)

        # ── 分隔线 ──
        ttk.Separator(win, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=15, pady=6)

        # ── 止盈区域 ──
        sp_frame = tk.LabelFrame(win, text="💰 止盈配置", bg=COLOR_CARD_BG,
                                  font=("微软雅黑", 10, "bold"),
                                  fg=COLOR_TEXT,
                                  relief=tk.RIDGE, bd=1, padx=10, pady=8)
        sp_frame.pack(fill=tk.X, padx=15, pady=6)

        # 止盈模式选择
        row_sp0 = tk.Frame(sp_frame, bg=COLOR_CARD_BG)
        row_sp0.pack(fill=tk.X, pady=3)

        self._risk_sp_mode_var = tk.StringVar(value=self._risk_sp_mode)
        tk.Label(row_sp0, text="止盈模式：", bg=COLOR_CARD_BG,
                 font=("微软雅黑", 9), fg=COLOR_TEXT,
                 width=14, anchor=tk.W).pack(side=tk.LEFT)
        ttk.Combobox(row_sp0, textvariable=self._risk_sp_mode_var,
                     values=["graded", "target"],
                     state="readonly", width=10,
                     font=("微软雅黑", 9)).pack(side=tk.LEFT)
        tk.Label(row_sp0, text="  graded=分级止盈  target=目标价止盈",
                 bg=COLOR_CARD_BG,
                 font=("微软雅黑", 8), fg=COLOR_TEXT_SECONDARY).pack(side=tk.LEFT, padx=(6, 0))

        # 分级止盈参数（3 档）
        row_sp1 = tk.Frame(sp_frame, bg=COLOR_CARD_BG)
        row_sp1.pack(fill=tk.X, pady=3)

        tk.Label(row_sp1, text="分级止盈档位：", bg=COLOR_CARD_BG,
                 font=("微软雅黑", 9), fg=COLOR_TEXT,
                 width=14, anchor=tk.W).pack(side=tk.LEFT)

        self._risk_sp_l1_pct_var = tk.DoubleVar(value=self._risk_sp_graded_levels[0][0] * 100)
        self._risk_sp_l1_ratio_var = tk.DoubleVar(value=self._risk_sp_graded_levels[0][1] * 100)
        tk.Label(row_sp1, text="档1:", bg=COLOR_CARD_BG,
                 font=("微软雅黑", 8), fg=COLOR_TEXT).pack(side=tk.LEFT)
        tk.Spinbox(row_sp1, from_=1, to=50, textvariable=self._risk_sp_l1_pct_var,
                   width=4, font=("Consolas", 8),
                   relief=tk.SUNKEN, bd=1).pack(side=tk.LEFT, padx=(1, 1))
        tk.Label(row_sp1, text="%→卖", bg=COLOR_CARD_BG,
                 font=("微软雅黑", 8), fg=COLOR_TEXT).pack(side=tk.LEFT)
        tk.Spinbox(row_sp1, from_=10, to=100, textvariable=self._risk_sp_l1_ratio_var,
                   width=4, font=("Consolas", 8),
                   relief=tk.SUNKEN, bd=1).pack(side=tk.LEFT, padx=(1, 1))
        tk.Label(row_sp1, text="%", bg=COLOR_CARD_BG,
                 font=("微软雅黑", 8), fg=COLOR_TEXT).pack(side=tk.LEFT)

        row_sp2 = tk.Frame(sp_frame, bg=COLOR_CARD_BG)
        row_sp2.pack(fill=tk.X, pady=3)

        self._risk_sp_l2_pct_var = tk.DoubleVar(value=self._risk_sp_graded_levels[1][0] * 100)
        self._risk_sp_l2_ratio_var = tk.DoubleVar(value=self._risk_sp_graded_levels[1][1] * 100)
        tk.Label(row_sp2, text="档2:", bg=COLOR_CARD_BG,
                 font=("微软雅黑", 8), fg=COLOR_TEXT).pack(side=tk.LEFT, padx=(14+12+2, 0))
        tk.Spinbox(row_sp2, from_=1, to=50, textvariable=self._risk_sp_l2_pct_var,
                   width=4, font=("Consolas", 8),
                   relief=tk.SUNKEN, bd=1).pack(side=tk.LEFT, padx=(1, 1))
        tk.Label(row_sp2, text="%→卖", bg=COLOR_CARD_BG,
                 font=("微软雅黑", 8), fg=COLOR_TEXT).pack(side=tk.LEFT)
        tk.Spinbox(row_sp2, from_=10, to=100, textvariable=self._risk_sp_l2_ratio_var,
                   width=4, font=("Consolas", 8),
                   relief=tk.SUNKEN, bd=1).pack(side=tk.LEFT, padx=(1, 1))
        tk.Label(row_sp2, text="%", bg=COLOR_CARD_BG,
                 font=("微软雅黑", 8), fg=COLOR_TEXT).pack(side=tk.LEFT)

        row_sp3 = tk.Frame(sp_frame, bg=COLOR_CARD_BG)
        row_sp3.pack(fill=tk.X, pady=3)

        self._risk_sp_l3_pct_var = tk.DoubleVar(value=self._risk_sp_graded_levels[2][0] * 100)
        self._risk_sp_l3_ratio_var = tk.DoubleVar(value=self._risk_sp_graded_levels[2][1] * 100)
        tk.Label(row_sp3, text="档3:", bg=COLOR_CARD_BG,
                 font=("微软雅黑", 8), fg=COLOR_TEXT).pack(side=tk.LEFT, padx=(14+12+2, 0))
        tk.Spinbox(row_sp3, from_=1, to=50, textvariable=self._risk_sp_l3_pct_var,
                   width=4, font=("Consolas", 8),
                   relief=tk.SUNKEN, bd=1).pack(side=tk.LEFT, padx=(1, 1))
        tk.Label(row_sp3, text="%→卖", bg=COLOR_CARD_BG,
                 font=("微软雅黑", 8), fg=COLOR_TEXT).pack(side=tk.LEFT)
        tk.Spinbox(row_sp3, from_=10, to=100, textvariable=self._risk_sp_l3_ratio_var,
                   width=4, font=("Consolas", 8),
                   relief=tk.SUNKEN, bd=1).pack(side=tk.LEFT, padx=(1, 1))
        tk.Label(row_sp3, text="%", bg=COLOR_CARD_BG,
                 font=("微软雅黑", 8), fg=COLOR_TEXT).pack(side=tk.LEFT)

        # 目标价止盈
        row_sp4 = tk.Frame(sp_frame, bg=COLOR_CARD_BG)
        row_sp4.pack(fill=tk.X, pady=3)

        self._risk_sp_target_var = tk.DoubleVar(value=self._risk_sp_target_price_pct * 100)
        tk.Label(row_sp4, text="目标价止盈：", bg=COLOR_CARD_BG,
                 font=("微软雅黑", 9), fg=COLOR_TEXT,
                 width=14, anchor=tk.W).pack(side=tk.LEFT)
        tk.Spinbox(row_sp4, from_=1, to=100, textvariable=self._risk_sp_target_var,
                   width=6, font=("Consolas", 9),
                   relief=tk.SUNKEN, bd=1).pack(side=tk.LEFT, padx=(2, 4))
        tk.Label(row_sp4, text="%  选 target 模式时生效", bg=COLOR_CARD_BG,
                 font=("微软雅黑", 8), fg=COLOR_TEXT_SECONDARY).pack(side=tk.LEFT)

        # ── 按钮区域 ──
        btn_row = tk.Frame(win, bg=COLOR_CARD_BG)
        btn_row.pack(fill=tk.X, padx=15, pady=(10, 12))

        def _save_risk_config():
            """保存风控配置到 self 变量"""
            # 止损
            self._risk_sl_fixed_ratio = self._risk_sl_fixed_var.get() / 100.0
            self._risk_sl_atr_enabled = self._risk_sl_atr_enabled_var.get()
            self._risk_sl_atr_multiplier = self._risk_sl_atr_var.get()

            # 止盈模式
            self._risk_sp_mode = self._risk_sp_mode_var.get()

            # 分级止盈档位
            self._risk_sp_graded_levels = [
                (self._risk_sp_l1_pct_var.get() / 100.0, self._risk_sp_l1_ratio_var.get() / 100.0),
                (self._risk_sp_l2_pct_var.get() / 100.0, self._risk_sp_l2_ratio_var.get() / 100.0),
                (self._risk_sp_l3_pct_var.get() / 100.0, self._risk_sp_l3_ratio_var.get() / 100.0),
            ]

            # 目标价止盈
            self._risk_sp_target_price_pct = self._risk_sp_target_var.get() / 100.0

            # 时间止损
            self._risk_ts_enabled = self._risk_ts_enabled_var.get()
            self._risk_ts_max_bars = self._risk_ts_max_bars_var.get()

            # 黑天鹅
            if hasattr(self, '_risk_bs_enabled_var'):
                self._risk_bs_enabled = self._risk_bs_enabled_var.get()

            # 更新状态标签
            self._update_risk_status()

            win.destroy()

        tk.Button(btn_row, text="✅ 保存", command=_save_risk_config,
                  bg=COLOR_SUCCESS, fg="white",
                  font=("微软雅黑", 10, "bold"),
                  relief=tk.FLAT, bd=0, cursor="hand2",
                  padx=20, pady=6).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(btn_row, text="❌ 取消", command=win.destroy,
                  bg="#e8eaed", fg=COLOR_TEXT,
                  font=("微软雅黑", 10),
                  relief=tk.FLAT, bd=0, cursor="hand2",
                  padx=20, pady=6).pack(side=tk.LEFT)

    def _update_risk_status(self) -> None:
        """更新状态栏中的风控配置摘要"""
        mode_text = "分级" if self._risk_sp_mode == "graded" else "目标价"
        atr_text = f"+ATR{self._risk_sl_atr_multiplier:.1f}倍" if self._risk_sl_atr_enabled else ""
        ts_text = f" 持股≤{self._risk_ts_max_bars}天" if self._risk_ts_enabled else ""
        bs_text = "" if getattr(self, '_risk_bs_enabled', True) else " 黑天鹅关"
        status = f"止盈:{mode_text} 止损:{self._risk_sl_fixed_ratio:.0%}{atr_text}{ts_text}{bs_text}"
        self._risk_status_var.set(status)

    # ═══════════════════════════════════════════
    #  数据加载配置
    # ═══════════════════════════════════════════

    def load_data(self, code: str) -> None:
        """外部设置股票代码"""
        self._code_entry.delete(0, tk.END)
        self._code_entry.insert(0, code)
