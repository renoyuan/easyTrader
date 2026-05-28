"""
股神评分面板
=============
将巴菲特、格雷厄姆、徐翔合并为一个下拉选择框，
选择评分体系后点击「开始评分」执行对应策略。
"""
import tkinter as tk
from tkinter import messagebox, ttk
import pandas as pd

from trader.scorer.buffett import BuffettScorer
from trader.scorer.graham import GrahamScorer
from trader.scorer.xuxiang import XuXiangScorer
from trader.scorer.renoyuan import RenoyuanScorer
from trader.scorer.xubin import XuBinScorer
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

