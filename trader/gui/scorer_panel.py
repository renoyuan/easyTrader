"""
股神评分面板
=============
将巴菲特、格雷厄姆、徐翔合并为一个下拉选择框，
选择评分体系后点击「开始评分」执行对应策略。
新增：全市场批量评分扫描功能
"""
import tkinter as tk
from tkinter import messagebox, ttk, simpledialog
import pandas as pd
import threading

from trader.scorer.buffett import BuffettScorer
from trader.scorer.graham import GrahamScorer
from trader.scorer.xuxiang import XuXiangScorer
from trader.scorer.renoyuan import RenoyuanScorer
from trader.scorer.xubin import XuBinScorer
from trader.scorer.market_scanner import MarketScanner, format_top_results
from trader.ai import DeepSeekClient


# ── 评分体系注册表 ──
SCORER_REGISTRY = {
    "巴菲特价值评分": {
        "icon": "🧑‍💼",
        "scorer_class": BuffettScorer,
        "color": "#34a853",
        "method": "score",
    },
    "格雷厄姆价值评分": {
        "icon": "📐",
        "scorer_class": GrahamScorer,
        "color": "#9334e6",
        "method": "score",
    },
    "徐翔趋势评分": {
        "icon": "🔥",
        "scorer_class": XuXiangScorer,
        "color": "#e67e22",
        "method": "score",
    },
    "renoyuan核心评分": {
        "icon": "🏦",
        "scorer_class": RenoyuanScorer,
        "color": "#0f9d58",
        "method": "score",
    },
    "xubin财报排雷评分": {
        "icon": "🚨",
        "scorer_class": XuBinScorer,
        "color": "#e74c3c",
        "method": "score",
    },
}


class ScorerPanel:
    """股神评分面板——下拉选择评分体系 + 执行"""

    def __init__(self, status_callback, info_callback,
                 tree_callback, history_callback, notebook_select_callback) -> None:
        """
        :param status_callback:     (msg, is_ok) → 更新状态栏
        :param info_callback:       (msg) → 文本区追加内容
        :param tree_callback:       (rows: list[tuple]) → 刷新评分摘要表格
        :param history_callback:    (code, system, score, rating) → 添加历史记录
        :param notebook_select_callback: (index) → 切换到指定标签页
        """
        self._set_status = status_callback
        self._info = info_callback
        self._update_tree = tree_callback
        self._add_history = history_callback
        self._select_tab = notebook_select_callback

        self.symbol: str | None = None
        self._cached_scorer = {}  # 缓存评分器实例
        self._current_system = list(SCORER_REGISTRY.keys())[0]

    def build_selector(self, parent: tk.Frame) -> None:
        """由主窗口在按钮组内部创建下拉选择控件"""
        selector_frame = tk.Frame(parent, bg="#ffffff")
        selector_frame.pack(fill=tk.X, pady=(2, 2))

        # 美化标签
        lbl = tk.Label(
            selector_frame, text="选择评分体系",
            bg="#ffffff", fg="#5f6368",
            font=("微软雅黑", 9)
        )
        lbl.pack(anchor=tk.W, pady=(2, 1))

        # 自定义 ComboBox 样式
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Score.TCombobox",
            fieldbackground="#f5f5f5",
            background="#ffffff",
            foreground="#202124",
            arrowcolor="#1a73e8",
            font=("微软雅黑", 10),
            padding=3,
        )
        style.map(
            "Score.TCombobox",
            fieldbackground=[("readonly", "#f0f2f5")],
            foreground=[("readonly", "#202124")],
        )

                # 带图标的下拉选项
        display_names = [
            "🧑‍💼  巴菲特价值评分",
            "📐  格雷厄姆价值评分",
            "🔥  徐翔趋势评分",
            "🏦  renoyuan核心评分",
            "🚨  xubin财报排雷评分",
        ]
        self._combo = ttk.Combobox(
            selector_frame,
            values=display_names,
            state="readonly",
            style="Score.TCombobox",
            width=20,
        )
        self._combo.current(0)
        self._combo.pack(fill=tk.X, pady=(0, 4))
        self._combo.bind("<<ComboboxSelected>>", self._on_select)

        # 存一份真实名称映射
        self._display_to_real = {
            "🧑‍💼  巴菲特价值评分": "巴菲特价值评分",
            "📐  格雷厄姆价值评分": "格雷厄姆价值评分",
            "🔥  徐翔趋势评分": "徐翔趋势评分",
            "🏦  renoyuan核心评分": "renoyuan核心评分",
            "🚨  xubin财报排雷评分": "xubin财报排雷评分",
        }

    def _on_select(self, event=None) -> None:
        display = self._combo.get()
        self._current_system = self._display_to_real.get(display, display)

    def _get_system(self) -> str:
        """获取当前选中的真实评分体系名称"""
        display = self._combo.get()
        return self._display_to_real.get(display, display)

    # ────────────────────────────────
    #  统一评分入口
    # ────────────────────────────────
    def run_scoring(self) -> None:
        """执行当前选中的评分体系"""
        system = self._get_system()
        info = SCORER_REGISTRY.get(system)
        if not info:
            messagebox.showerror("错误", f"未找到评分体系: {system}")
            return

        if not self._check_symbol():
            return

        icon = info["icon"]
        self._before_run(f"{icon} {system}")

        # 获取或缓存评分器
        if system not in self._cached_scorer:
            scorer_cls = info["scorer_class"]
            self._cached_scorer[system] = scorer_cls()
        scorer = self._cached_scorer[system]

        try:
            res = scorer.score(self.symbol)
            if not res:
                self._info("❌ 评分失败：数据不足，请确认已下载该股票数据")
                self._set_status("评分失败", False)
                return

            # 输出结果
            dispatch_map = {
                "巴菲特价值评分": (self._append_buffett_result, self._fill_tree_buffett,
                                "巴菲特价值投资评分体系：基于 ROE、净利润率、负债率、现金流等财务质地和估值分位综合打分",
                                lambda r: f"质地趋势分：{r['base']}/80  估值分：{r['val_score']}/20\n综合总分：{r['score']}/100\n趋势状态：{r['trend_label']}  估值状态：{r['val_label']}\n投资评级：{r['rating']}"),
                "格雷厄姆价值评分": (self._append_graham_result, self._fill_tree_graham,
                                "格雷厄姆价值投资评分体系：核心逻辑是低估值（PE/PB低）、财务稳定、高安全边际",
                                lambda r: f"综合总分：{r['score']}/100\nPE(TTM)：{r['pe']}\nPB：{r['pb']}\n投资评级：{r['rating']}"),
                "徐翔趋势评分": (self._append_xuxiang_result, self._fill_tree_xuxiang,
                            "徐翔趋势交易评分体系：基于动量、成交量放大、连续上涨、突破新高、波动率等短期交易因子",
                            lambda r: f"综合总分：{r['score']}/100\n10日动量：{r.get('momentum','N/A')}%\n交易评级：{r['rating']}"),
                                "renoyuan核心评分": (self._append_renoyuan_result, self._fill_tree_renoyuan,
                                "renoyuan 核心评分体系：以股息率为最高权重，结合 ROE 稳定性、经营现金流持续性、低波动、低负债和合理估值的红利低波策略",
                                lambda r: f"综合总分：{r['score']}/100\n股息率：{r['indicators'].get('股息率','N/A')}\nROE：{r['indicators'].get('ROE','N/A')}\n可信度：{r.get('confidence','N/A')}\n投资评级：{r['rating']}"),
                "xubin财报排雷评分": (self._append_xubin_result, self._fill_tree_xubin,
                                "xubin 财报排雷评分体系：基于利润含金量、收入真实性、毛利率合理性、存货健康度、负债风险等因子进行财务造假风险筛查",
                                lambda r: f"综合总分：{r['score']}/100\n风险评级：{r['rating']}\n可信度：{r.get('confidence','N/A')}\n是否高危：{r.get('high_risk','N/A')}"),
            }
            append_fn, tree_fn, system_intro, summary_fn = dispatch_map.get(system, (None, None, "", None))
            if append_fn:
                append_fn(res)
            if tree_fn:
                tree_fn(res)

                        # ── AI 点评（先出评分结果，再问是否继续） ──
            self._info(f"\n{'─'*45}")
            self._info("🤖 是否需要 DeepSeekAI 第三方点评？")
            self._info(f"{'─'*45}")
            try:
                ai = DeepSeekClient()
                if not ai.is_ready:
                    self._info("  ⚠️ DeepSeek API Key 未配置，跳过 AI 点评\n"
                               "    请在左侧操作面板 → 设置 DeepSeek Key")
                else:
                    do_ai = messagebox.askyesno(
                        "AI 点评",
                        f"当前 {system} 评分已完成，是否调用 DeepSeekAI 进行第三方点评？\n\n"
                        f"评分结果：{res['score']}/100\n评级：{res['rating']}",
                        icon='question'
                    )
                    if do_ai:
                        summary = summary_fn(res) if summary_fn else f"总分: {res['score']}/100"
                        self._info("  调用 DeepSeekAI 进行点评...")
                        analysis = ai.analyze_scorer_result(system, system_intro, summary)
                        self._info(f"\n{analysis}\n")
                    else:
                        self._info("  跳过 AI 点评\n")
            except Exception as e:
                self._info(f"  ⚠️ AI 点评异常: {e}")

            # 短名称用于历史记录
            short_name = system.replace("价值评分", "").replace("趋势评分", "")
            self._set_status(f"{system}完成: {res['score']}/100", True)
            self._add_history(self.symbol, short_name, res["score"], res["rating"])
            self._select_tab(0)

        except Exception as e:
            self._handle_error(system, e)

    # ────────────────────────────────
    #  内部方法
    # ────────────────────────────────
    def _check_symbol(self) -> bool:
        if not self.symbol:
            messagebox.showwarning("提示", "请先点击「输入股票代码」")
            self._set_status("请先输入股票代码", False)
            return False
        return True

    def _before_run(self, title: str) -> None:
        self._set_status(f"⏳ {title}中...", True)
        self._info(f"\n{'='*50}")
        self._info(f"📊  {title} ...")
        self._info(f"{'='*50}")

    def _handle_error(self, context: str, error: Exception) -> None:
        msg = str(error)
        import traceback
        traceback.print_exc()
        self._info(f"❌ {context} 异常: {msg}")
        self._set_status(f"{context} 失败", False)
        messagebox.showerror("评分异常", msg)

    # ────────────────────────────────
    #  文本输出
    # ────────────────────────────────
    def _append_buffett_result(self, res: dict) -> None:
        full_name = f"{res['code']} {res.get('name', '')}"
        self._info(f"\n股票: {full_name}")
        self._info(f"🧑‍💼 巴菲特评分")
        self._info(f"  ├ 质地趋势分: {res['base']} / 80")
        self._info(f"  ├ 估值评分:   {res['val_score']} / 20")
        self._info(f"  └ 综合总分:   {res['score']} / 100")
        self._info(f"\n趋势状态: {res['trend_label']}")
        self._info(f"估值状态: {res['val_label']}")
        self._info(f"投资评级: {res['rating']}")
        self._info(f"{'─'*45}")
        # 定义：哪些是比率（小数），哪些是倍数/次数
        ratio_keys = {'ROE', '净利润率', '资产负债率', '经营现金流/净利润', '净利润增长率',
                      '毛利率', '销售净利率', '流动比率', '速动比率'}
        turnover_keys = {'存货周转率', '应收账款周转率', '总资产周转率'}
        for k, v in res["indicators"].items():
            if pd.isna(v):
                continue
            if k in ratio_keys:
                self._info(f"{k:<20} {v:.2%}")
            elif k in turnover_keys:
                self._info(f"{k:<20} {v:.2f} 次")
            else:
                # 金额或其他数值
                if abs(v) > 1e8:
                    self._info(f"{k:<20} {v:.2e} 元")
                else:
                    self._info(f"{k:<20} {v:.4f}")
        self._info(f"{'='*50}\n")

    def _append_graham_result(self, res: dict) -> None:
        full_name = f"{res['code']} {res.get('name', '')}"
        self._info(f"\n股票: {full_name}")
        self._info(f"📐 格雷厄姆评分")
        self._info(f"  └ 综合总分: {res['score']} / 100")
        self._info(f"\n投资评级: {res['rating']}")
        self._info(f"{'─'*45}")
        pe_txt = f"{res['pe']:.2f}" if res.get("pe") is not None else "N/A"
        pb_txt = f"{res['pb']:.2f}" if res.get("pb") is not None else "N/A"
        self._info(f"PE(TTM):     {pe_txt}")
        self._info(f"PB:          {pb_txt}")
        score = res["score"]
        if score >= 80:
            self._info("🔥 极度低估（典型格雷厄姆机会）")
        elif score >= 60:
            self._info("✅ 价值区间（可关注）")
        elif score >= 40:
            self._info("⚠️ 普通估值（无明显机会）")
        else:
            self._info("❌ 高估或质量不足")
        self._info(f"{'='*50}\n")

    def _append_xuxiang_result(self, res: dict) -> None:
        full_name = f"{res['code']} {res.get('name', '')}"
        self._info(f"\n股票: {full_name}")
        self._info(f"🔥 徐翔趋势评分")
        self._info(f"  └ 综合总分: {res['score']} / 100")
        if res.get("momentum") is not None:
            self._info(f"\n10日动量:   {res['momentum']}%")
        self._info(f"\n交易评级: {res['rating']}")
        self._info(f"{'─'*45}")
        score = res["score"]
        if score >= 80:
            self._info("🔥 强势龙头（可参与短期交易）")
        elif score >= 60:
            self._info("⚡ 中等趋势（观察为主）")
        elif score >= 40:
            self._info("⚠️ 弱势震荡（不建议参与）")
        else:
            self._info("❌ 无交易价值（回避）")
        self._info(f"{'='*50}\n")
    
    # ── renoyuan 核心评分 ──

    def _append_renoyuan_result(self, res: dict) -> None:
        full_name = f"{res['code']} {res.get('name', '')}"
        self._info(f"\n股票: {full_name}")
        self._info(f"🏦 renoyuan 核心评分")
        self._info(f"  └ 综合总分: {res['score']} / 100")
        self._info(f"\n投资评级: {res['rating']}")
        self._info(f"评分可信度: {res.get('confidence', 'N/A')}")
        if res.get("warnings"):
            self._info(f"⚠️ 数据警告:")
            for w in res["warnings"]:
                self._info(f"   - {w}")
        self._info(f"{'─'*45}")
        for k, v in res["indicators"].items():
            if v is None or pd.isna(v):
                continue
            if "率" in k or "ROE" in k or "波动" in k or "稳定性" in k:
                self._info(f"{k:<20} {v:.2%}")
            else:
                self._info(f"{k:<20} {v:.2f}")
        self._info(f"{'='*50}\n")

    # ── xubin 财报排雷评分 ──

    def _append_xubin_result(self, res: dict) -> None:
        full_name = f"{res['code']} {res.get('name', '')}"
        self._info(f"\n股票: {full_name}")
        self._info(f"🚨 xubin 财报排雷评分")
        self._info(f"  └ 综合总分: {res['score']} / 100")
        self._info(f"\n风险评级: {res['rating']}")
        self._info(f"评分可信度: {res.get('confidence', 'N/A')}")
        if res.get("high_risk"):
            self._info(f"🚨 高危预警：此公司财务存在严重风险！")
        if res.get("warnings"):
            self._info(f"⚠️ 风险警告:")
            for w in res["warnings"]:
                self._info(f"   - {w}")
        self._info(f"{'─'*45}")
        for k, v in res["indicators"].items():
            if v is None or pd.isna(v):
                continue
            if "率" in k or "毛利率" in k:
                self._info(f"{k:<28} {v:.2%}")
            elif "含金量" in k:
                self._info(f"{k:<28} {v:.2f}")
            else:
                self._info(f"{k:<28} {v:.2f}")
        self._info(f"{'='*50}\n")

    def _fill_tree_xubin(self, res: dict) -> None:
        score = res["score"]
        confidence = res.get("confidence", "")
        high_risk = res.get("high_risk", False)
        rating = "🚨 高危" if high_risk else res["rating"]
        rows = [
            ("🚨 xubin财报排雷", f"{score}/100", rating),
            ("   ├ 可信度", confidence, ""),
        ]
        for k, v in res["indicators"].items():
            if v is None or pd.isna(v):
                continue
            label = k[:18]  # 截断过长字段名
            if "率" in k or "毛利率" in k:
                rows.append((f"   ├ {label}", f"{v:.2%}", ""))
            elif "含金量" in k:
                rows.append((f"   ├ {label}", f"{v:.2f}", ""))
            else:
                rows.append((f"   ├ {label}", f"{v:.2f}", ""))
        self._update_tree(rows)

    def _fill_tree_renoyuan(self, res: dict) -> None:
        score = res["score"]
        dy = res["indicators"].get("股息率", None)
        roe = res["indicators"].get("ROE", None)
        confidence = res.get("confidence", "")
        dy_txt = f"{dy:.2f}%" if dy is not None else "N/A"
        roe_txt = f"{roe:.2%}" if roe is not None else "N/A"
        self._update_tree([
            ("🏦 renoyuan核心评分", f"{score}/100", res["rating"]),
            ("   ├ 股息率", dy_txt, ""),
            ("   ├ ROE", roe_txt, ""),
            ("   ├ 可信度", confidence, ""),
        ])

    # ────────────────────────────────
    #  表格填充
    # ────────────────────────────────
    def _fill_tree_buffett(self, res: dict) -> None:
        rows = [
            ("🧑‍💼 巴菲特评分", f"{res['score']}/100", res["rating"]),
            ("   ├ 质地趋势分", f"{res['base']}/80", res["trend_label"]),
            ("   ├ 估值评分", f"{res['val_score']}/20", res["val_label"]),
        ]
        ratio_keys = {'ROE', '净利润率', '资产负债率', '经营现金流/净利润', '净利润增长率',
                      '毛利率', '销售净利率', '流动比率', '速动比率'}
        turnover_keys = {'存货周转率', '应收账款周转率', '总资产周转率'}
        for k, v in res["indicators"].items():
            if pd.isna(v):
                continue
            label_map = {
                "ROE": "净资产收益率(ROE)", "净利润率": "净利润率",
                "资产负债率": "资产负债率", "经营现金流/净利润": "经营现金流/净利润",
                "净利润增长率": "净利润增长率",
            }
            label = label_map.get(k, k)
            if k in ratio_keys:
                rows.append((f"   ├ {label}", f"{v:.2%}", ""))
            elif k in turnover_keys:
                rows.append((f"   ├ {label}", f"{v:.2f} 次", ""))
            else:
                rows.append((f"   ├ {label}", f"{v:.4f}", ""))
        self._update_tree(rows)

    def _fill_tree_graham(self, res: dict) -> None:
        pe = f"{res['pe']:.2f}" if res.get("pe") is not None else "N/A"
        pb = f"{res['pb']:.2f}" if res.get("pb") is not None else "N/A"
        score = res["score"]
        explanation = "🔥 极度低估" if score >= 80 else "✅ 价值区间" if score >= 60 else "⚠️ 普通估值" if score >= 40 else "❌ 高估"
        self._update_tree([
            ("📐 格雷厄姆评分", f"{score}/100", res["rating"]),
            ("   ├ PE(TTM)", pe, ""), ("   ├ PB", pb, ""),
            ("   ├ 估值判断", "", explanation),
        ])

    def _fill_tree_xuxiang(self, res: dict) -> None:
        momentum = f"{res['momentum']}%" if res.get("momentum") is not None else "N/A"
        score = res["score"]
        explanation = "🔥 强势龙头" if score >= 80 else "⚡ 中等趋势" if score >= 60 else "⚠️ 弱势震荡" if score >= 40 else "❌ 无交易价值"
        self._update_tree([
            ("🔥 徐翔趋势评分", f"{score}/100", res["rating"]),
            ("   ├ 10日动量", momentum, ""),
            ("   ├ 趋势判断", "", explanation),
        ])

    # ════════════════════════════════════════
    #  全市场批量评分扫描
    # ════════════════════════════════════════
    def run_market_scan(self, parent_root: tk.Tk) -> None:
        """
        打开全市场评分扫描对话框
        :param parent_root: 主窗口 root，用于创建进度弹窗
        """
        system = self._get_system()
        info = SCORER_REGISTRY.get(system)
        if not info:
            messagebox.showerror("错误", f"未找到评分体系: {system}")
            return

                # ── 弹出选择对话框（多选框 + 自定义股票输入 + 确认按钮） ──
        dialog = MarketScanDialog(parent_root, system)
        parent_root.wait_window(dialog.top)

        if not dialog.result:
            return

        markets = dialog.result.get("markets")  # list of market codes or None
        custom_codes = dialog.result.get("custom_codes")  # list of stock codes or None
        top_n = dialog.result["top_n"]

        # ── 创建进度条窗口 ──
        progress_win = tk.Toplevel(parent_root)
        progress_win.title(f"🔍 扫描中 - {system}")
        progress_win.geometry("520x240")
        progress_win.configure(bg="#ffffff")
        progress_win.resizable(False, False)
        progress_win.transient(parent_root)
        progress_win.grab_set()

        # 居中
        progress_win.update_idletasks()
        x = parent_root.winfo_x() + (parent_root.winfo_width() - 520) // 2
        y = parent_root.winfo_y() + (parent_root.winfo_height() - 200) // 2
        progress_win.geometry(f"+{x}+{y}")

        # 标题
        if custom_codes:
            label_text = f"🔍 {system} - 自定义 {len(custom_codes)} 只股票"
        else:
            market_label = "全市场" if "ALL" in markets else "+".join(markets)
            label_text = f"🔍 {system} - {market_label}"

        # 进度标签
        progress_label = tk.Label(
            progress_win,
            text="初始化...",
            font=("微软雅黑", 10),
            bg="#ffffff", fg="#5f6368",
            wraplength=480
        )
        progress_label.pack(pady=(4, 8))

        # 进度条
        progress_bar = ttk.Progressbar(
            progress_win,
            orient=tk.HORIZONTAL,
            length=460,
            mode='determinate'
        )
        progress_bar.pack(pady=4)

        # 状态标签
        status_label = tk.Label(
            progress_win,
            text="",
            font=("微软雅黑", 9),
            bg="#ffffff", fg="#ea4335"
        )
        status_label.pack(pady=(4, 8))

        # 停止按钮
        stop_btn = tk.Button(
            progress_win,
            text="⏹ 停止扫描",
            command=None,  # 稍后设置
            bg="#ea4335", fg="white",
            font=("微软雅黑", 10, "bold"),
            relief=tk.FLAT, bd=0,
            cursor="hand2",
            padx=16, pady=4
        )
        stop_btn.pack(pady=4)

        # ── 启动扫描线程 ──
        scanner = MarketScanner()

        def on_stop():
            scanner.stop()
            stop_btn.config(text="正在停止...", state=tk.DISABLED)

        stop_btn.config(command=on_stop)

        def update_progress(current, total, stock_name):
            progress_bar["value"] = current
            progress_bar["maximum"] = total
            pct = current / total * 100 if total > 0 else 0
            progress_label.config(
                text=f"正在扫描: {stock_name}\n进度: {current}/{total} ({pct:.1f}%)"
            )
            progress_win.update()

        def log_msg(msg):
            self._info(msg)
            status_label.config(text=msg[-60:] if len(msg) > 60 else msg)
            progress_win.update()

        def on_result(results):
            progress_win.destroy()
            if results:
                # 输出 TOP 结果到文本区
                formatted = format_top_results(results, system)
                self._info(formatted)

                # 填充表格
                tree_rows = []
                for i, r in enumerate(results, 1):
                    code = r.get("code", "")
                    name = r.get("name", "")
                    score = r.get("score", 0)
                    rating = r.get("rating", "")
                    medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
                    tree_rows.append((f"{medal} {name}({code})", f"{score}/100", rating))
                self._update_tree(tree_rows)

                # 添加历史
                for r in results[:3]:
                    self._add_history(
                        f"{r.get('code','')} ({r.get('name','')})",
                        system,
                        r.get("score", 0),
                        r.get("rating", "")
                    )

                self._set_status(f"🏆 扫描完成, TOP{len(results)}", True)
                self._select_tab(0)
            else:
                self._info("❌ 扫描完成，但未获取到有效评分结果")
            self._set_status("扫描完成，无结果", False)

        def scan_thread():
            try:
                if custom_codes:
                    scanner.scan_custom(
                        codes=custom_codes,
                        scorer_name=system,
                        top_n=top_n,
                        progress_callback=update_progress,
                        result_callback=on_result,
                        log_callback=log_msg,
                    )
                else:
                    scanner.scan(
                        markets=markets,
                        scorer_name=system,
                        top_n=top_n,
                        progress_callback=update_progress,
                        result_callback=on_result,
                        log_callback=log_msg,
                    )
            except Exception as e:
                import traceback
                err_msg = str(e)
                traceback.print_exc()
                progress_win.after(0, lambda em=err_msg: (
                    progress_win.destroy(),
                    self._info(f"❌ 扫描异常: {em}"),
                    self._set_status("扫描异常", False)
                ))

        t = threading.Thread(target=scan_thread, daemon=True)
        t.start()


class MarketScanDialog:
    """全市场评分扫描参数选择对话框（多选框 + 自定义股票输入 + 确定/取消按钮）"""

    def __init__(self, parent: tk.Tk, system: str):
        self.result = None
        self.top = tk.Toplevel(parent)
        self.top.title("📊 全市场评分扫描")
        self.top.geometry("520x560")
        self.top.configure(bg="#ffffff")
        self.top.resizable(False, False)
        self.top.transient(parent)
        self.top.grab_set()

        # 居中
        self.top.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 520) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 560) // 2
        self.top.geometry(f"+{x}+{y}")

        # ── 标题 ──
        tk.Label(
            self.top,
            text="📊 全市场批量评分扫描",
            font=("微软雅黑", 14, "bold"),
            bg="#ffffff", fg="#202124"
        ).pack(pady=(16, 4))

        tk.Label(
            self.top,
            text=f"评分体系: {system}",
            font=("微软雅黑", 10),
            bg="#ffffff", fg="#5f6368"
        ).pack(pady=(0, 6))

        # ══════════════════════════════════════
        #  模式一：按市场扫描
        # ══════════════════════════════════════
        tk.Label(
            self.top,
            text="━━━ 方式一：按市场扫描 ━━━",
            font=("微软雅黑", 9, "bold"),
            bg="#ffffff", fg="#5f6368"
        ).pack(fill=tk.X, padx=20, pady=(2, 2))

        # 多选框变量
        self.var_all = tk.BooleanVar(value=True)  # 默认全市场
        self.var_sh = tk.BooleanVar(value=False)
        self.var_sz = tk.BooleanVar(value=False)
        self.var_cyb = tk.BooleanVar(value=False)
        self.var_kcb = tk.BooleanVar(value=False)
        self.var_bj = tk.BooleanVar(value=False)

        # 多选框容器
        cb_frame = tk.Frame(self.top, bg="#ffffff")
        cb_frame.pack(fill=tk.X, padx=20)

        # "全市场" 特殊：选中则禁用其他选项
        self.cb_all = tk.Checkbutton(
            cb_frame, text="☑ 全市场（沪市+深市+创业板+科创板）",
            variable=self.var_all,
            font=("微软雅黑", 10),
            bg="#ffffff", fg="#1a73e8",
            selectcolor="#ffffff",
            activebackground="#ffffff",
            anchor=tk.W,
            command=self._on_all_toggle,
        )
        self.cb_all.pack(fill=tk.X, pady=1)

        ttk.Separator(cb_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=2)

        # 各市场多选框（保存引用以便禁用/启用）
        self.cb_sh = self._create_checkbtn(cb_frame, "沪市主板（60/68开头）", self.var_sh, self._on_market_toggle)
        self.cb_sz = self._create_checkbtn(cb_frame, "深市主板（00开头）", self.var_sz, self._on_market_toggle)
        self.cb_cyb = self._create_checkbtn(cb_frame, "创业板（300开头）", self.var_cyb, self._on_market_toggle)
        self.cb_kcb = self._create_checkbtn(cb_frame, "科创板（688开头）", self.var_kcb, self._on_market_toggle)
        self.cb_bj = self._create_checkbtn(cb_frame, "北交所（8/9开头 - 数据不全慎选）", self.var_bj, self._on_market_toggle)

        # 初始状态：全市场勾选，禁用子市场
        self._set_sub_state(tk.DISABLED)

        # ══════════════════════════════════════
        #  模式二：自定义股票代码
        # ══════════════════════════════════════
        tk.Label(
            self.top,
            text="━━━ 方式二：自定义股票代码（输入后优先使用） ━━━",
            font=("微软雅黑", 9, "bold"),
            bg="#ffffff", fg="#5f6368"
        ).pack(fill=tk.X, padx=20, pady=(6, 2))

        hint_frame = tk.Frame(self.top, bg="#ffffff")
        hint_frame.pack(fill=tk.X, padx=20)

        tk.Label(
            hint_frame,
            text="输入 6 位股票代码，多个用逗号/空格/换行分隔",
            font=("微软雅黑", 8),
            bg="#ffffff", fg="#9e9e9e"
        ).pack(anchor=tk.W)

        # 文本输入框（带滚动条）
        text_frame = tk.Frame(self.top, bg="#ffffff")
        text_frame.pack(fill=tk.X, padx=20, pady=(2, 4))

        self.custom_text = tk.Text(
            text_frame,
            font=("Consolas", 10),
            height=3,
            relief=tk.SOLID, bd=1,
            padx=6, pady=4,
            wrap=tk.WORD,
        )
        self.custom_text.pack(fill=tk.X)

        # ══════════════════════════════════════
        #  TOP N 选择
        # ══════════════════════════════════════
        top_frame2 = tk.Frame(self.top, bg="#ffffff")
        top_frame2.pack(pady=6)

        tk.Label(
            top_frame2, text="输出前几名：",
            font=("微软雅黑", 10, "bold"),
            bg="#ffffff", fg="#202124"
        ).pack(side=tk.LEFT, padx=(0, 10))

        self.top_n_var = tk.IntVar(value=5)
        for n in [3, 5, 10, 20]:
            tk.Radiobutton(
                top_frame2, text=f"Top {n}", value=n,
                variable=self.top_n_var,
                font=("微软雅黑", 10),
                bg="#ffffff", selectcolor="#ffffff",
                indicatoron=True
            ).pack(side=tk.LEFT, padx=(0, 6))

        # ── 提示 ──
        tk.Label(
            self.top,
            text="⚠️ 全市场扫描可能需要 5~30 分钟，自定义扫描更快",
            font=("微软雅黑", 9),
            bg="#fff3e0", fg="#e65100",
            justify=tk.CENTER,
            padx=12, pady=6
        ).pack(fill=tk.X, padx=30, pady=(2, 6))

        # ── 确定按钮 ──
        btn_frame = tk.Frame(self.top, bg="#ffffff")
        btn_frame.pack(pady=6)

        tk.Button(
            btn_frame, text="✅ 确定开始扫描",
            command=self._confirm,
            bg="#1a73e8", fg="white",
            font=("微软雅黑", 11, "bold"),
            relief=tk.FLAT, bd=0,
            cursor="hand2",
            padx=20, pady=6
        ).pack(side=tk.LEFT, padx=6)

        tk.Button(
            btn_frame, text="取消",
            command=self._cancel,
            bg="#9e9e9e", fg="white",
            font=("微软雅黑", 10, "bold"),
            relief=tk.FLAT, bd=0,
            cursor="hand2",
            padx=16, pady=6
        ).pack(side=tk.LEFT, padx=6)

    def _create_checkbtn(self, parent, text, var, command):
        cb = tk.Checkbutton(
            parent, text=text,
            variable=var,
            font=("微软雅黑", 9),
            bg="#ffffff", fg="#202124",
            selectcolor="#ffffff",
            activebackground="#ffffff",
            anchor=tk.W,
            command=command,
        )
        cb.pack(fill=tk.X, pady=1)
        return cb

    def _set_sub_state(self, state):
        """设置所有子市场 Checkbutton 的状态"""
        for cb in [self.cb_sh, self.cb_sz, self.cb_cyb, self.cb_kcb, self.cb_bj]:
            cb.config(state=state)

    def _on_all_toggle(self):
        """全市场勾选时，禁用子市场；取消全市场时启用"""
        if self.var_all.get():
            self._set_sub_state(tk.DISABLED)
            for var in [self.var_sh, self.var_sz, self.var_cyb, self.var_kcb, self.var_bj]:
                var.set(False)
        else:
            self._set_sub_state(tk.NORMAL)

    def _on_market_toggle(self):
        """任一子市场勾选时，取消全市场"""
        if self.var_sh.get() or self.var_sz.get() or self.var_cyb.get() or self.var_kcb.get() or self.var_bj.get():
            self.var_all.set(False)
            self._set_sub_state(tk.NORMAL)
        else:
            # 全都没选时，自动勾回全市场
            self.var_all.set(True)
            self._set_sub_state(tk.DISABLED)

    def _parse_custom_codes(self) -> list:
        """从文本框中提取股票代码列表"""
        raw = self.custom_text.get("1.0", tk.END).strip()
        if not raw:
            return []

        # 用逗号、空格、换行分隔
        import re
        codes = re.split(r'[,，\s\n]+', raw)
        # 过滤出 6 位数字代码
        valid = [c.strip() for c in codes if c.strip().isdigit() and len(c.strip()) == 6]
        return valid

    def _confirm(self):
        """确定开始扫描"""
        # 优先检查自定义股票代码
        custom_codes = self._parse_custom_codes()
        if custom_codes:
            self.result = {
                "markets": None,
                "custom_codes": custom_codes,
                "top_n": self.top_n_var.get(),
            }
            self.top.destroy()
            return

        # 否则走市场选择
        markets = []
        if self.var_all.get():
            markets = ["ALL"]
        else:
            if self.var_sh.get():
                markets.append("SH")
            if self.var_sz.get():
                markets.append("SZ_MAIN")
            if self.var_cyb.get():
                markets.append("CYB")
            if self.var_kcb.get():
                markets.append("KCB")
            if self.var_bj.get():
                markets.append("BJ")

            if not markets:
                messagebox.showwarning("提示", "请至少选择一个市场，或输入自定义股票代码")
                return

        self.result = {
            "markets": markets,
            "custom_codes": None,
            "top_n": self.top_n_var.get(),
        }
        self.top.destroy()

    def _cancel(self):
        self.result = None
        self.top.destroy()

