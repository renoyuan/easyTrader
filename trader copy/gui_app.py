"""
easyTrader 股票评分 GUI 界面
=============================
支持巴菲特评分与格雷厄姆评分双体系，
提供结构化结果展示与多股票管理。
"""
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import pandas as pd
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from trader.scorer.buffett import BuffettScorer
from trader.scorer.graham import GrahamScorer


# ──────────────────────────────────────────────
#  主题配色
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

        # 核心数据
        self.symbol: str | None = None
        self.buffett = BuffettScorer()

        # 历史记录
        self.history: list[dict] = []

        # 构建界面
        self._build_widgets()

        # 初始提示
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
            header, text="📊  easyTrader 价值评分系统",
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

        self._create_styled_button(
            btn_frame, "📥  输入股票代码",
            self.input_code, COLOR_PRIMARY
        ).pack(fill=tk.X, pady=4)

        self._create_styled_button(
            btn_frame, "🧑‍💼  巴菲特评分",
            self.run_buffett_score, COLOR_SUCCESS
        ).pack(fill=tk.X, pady=4)

        self._create_styled_button(
            btn_frame, "📐  格雷厄姆评分",
            self.run_graham_score, "#9334e6"
        ).pack(fill=tk.X, pady=4)

        # 分隔线
        ttk.Separator(btn_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

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

        # scrollbar
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
            status_bar, text="v1.0 | 数据来源: akshare",
            bg="#e8eaed", fg=COLOR_TEXT_SECONDARY,
            font=("微软雅黑", 8)
        ).pack(side=tk.LEFT, padx=12)

    @staticmethod
    def _create_styled_button(
        parent: tk.Frame, text: str,
        command, color: str
    ) -> tk.Button:
        """创建统一样式的按钮"""
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

    def _clear_tree(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _add_history(self, code: str, system: str, score: int, rating: str) -> None:
        self.history_tree.insert(
            "", 0, values=(code, system, f"{score}/100", rating)
        )

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
            self.stock_label.config(text=f"当前股票: {code}")
            self._set_status(f"已选择股票 {code}")
            self._info(f"\n{'='*50}\n📌 已选择股票: {code}\n{'='*50}\n")
        else:
            messagebox.showerror("输入错误", "请输入 6 位数字股票代码！")
            self._set_status("输入格式错误", is_ok=False)

    # ==========================================
    #  巴菲特评分
    # ==========================================
    def run_buffett_score(self) -> None:
        if not self._check_symbol():
            return

        self._before_run("巴菲特价值评分")
        try:
            res = self.buffett.score(self.symbol)
            if not res:
                self._info("❌ 评分失败：无财报数据，请确认已下载该股票数据")
                self._set_status("评分失败", is_ok=False)
                return

            # --- 文本输出 ---
            self._append_buffett_result(res)

            # --- 表格输出 ---
            self._clear_tree()
            self.tree.insert("", tk.END, values=(
                "🧑‍💼 巴菲特评分", f"{res['score']}/100", res["rating"]
            ))
            self.tree.insert("", tk.END, values=(
                "   ├ 质地趋势分", f"{res['base']}/80", res["trend_label"]
            ))
            self.tree.insert("", tk.END, values=(
                "   ├ 估值评分", f"{res['val_score']}/20", res["val_label"]
            ))
            for k, v in res["indicators"].items():
                if pd.isna(v):
                    continue
                label_map = {
                    "ROE": "净资产收益率(ROE)",
                    "净利润率": "净利润率",
                    "资产负债率": "资产负债率",
                    "经营现金流/净利润": "经营现金流/净利润",
                    "净利润增长率": "净利润增长率",
                }
                self.tree.insert("", tk.END, values=(
                    f"   ├ {label_map.get(k, k)}", f"{v:.2%}", ""
                ))

            self._set_status(f"巴菲特评分完成: {res['score']}/100")
            self._add_history(self.symbol, "巴菲特", res["score"], res["rating"])
            self.notebook.select(0)

        except Exception as e:
            self._handle_error("巴菲特评分", e)

    # ==========================================
    #  格雷厄姆评分
    # ==========================================
    def run_graham_score(self) -> None:
        if not self._check_symbol():
            return

        self._before_run("格雷厄姆价值评分")
        try:
            scorer = GrahamScorer()
            res = scorer.score(self.symbol)
            if not res:
                self._info("❌ 评分失败：数据不足或无法计算")
                self._set_status("评分失败", is_ok=False)
                return

            # --- 文本输出 ---
            self._append_graham_result(res)

            # --- 表格输出 ---
            self._clear_tree()
            self.tree.insert("", tk.END, values=(
                "📐 格雷厄姆评分", f"{res['score']}/100", res["rating"]
            ))
            pe_text = f"{res['pe']:.2f}" if res.get("pe") is not None else "N/A"
            pb_text = f"{res['pb']:.2f}" if res.get("pb") is not None else "N/A"
            self.tree.insert("", tk.END, values=("   ├ PE(TTM)", pe_text, ""))
            self.tree.insert("", tk.END, values=("   ├ PB", pb_text, ""))

            # 评分解释
            if res["score"] >= 80:
                explanation = "🔥 极度低估"
            elif res["score"] >= 60:
                explanation = "✅ 价值区间"
            elif res["score"] >= 40:
                explanation = "⚠️ 普通估值"
            else:
                explanation = "❌ 高估或质量不足"
            self.tree.insert("", tk.END, values=("   ├ 估值判断", "", explanation))

            self._set_status(f"格雷厄姆评分完成: {res['score']}/100")
            self._add_history(self.symbol, "格雷厄姆", res["score"], res["rating"])
            self.notebook.select(0)

        except Exception as e:
            self._handle_error("格雷厄姆评分", e)

    # ==========================================
    #  辅助方法
    # ==========================================
    def _check_symbol(self) -> bool:
        if not self.symbol:
            messagebox.showwarning("提示", "请先点击「输入股票代码」")
            self._set_status("请先输入股票代码", is_ok=False)
            return False
        return True

    def _before_run(self, title: str) -> None:
        self._set_status(f"⏳ {title}中...")
        self._info(f"\n{'='*50}")
        self._info(f"📊  {title} ...")
        self._info(f"{'='*50}")
        self.root.update()

    def _handle_error(self, context: str, error: Exception) -> None:
        msg = str(error)
        self._info(f"❌ {context} 异常: {msg}")
        self._set_status(f"{context} 失败", is_ok=False)
        messagebox.showerror("评分异常", msg)

    def _append_buffett_result(self, res: dict) -> None:
        self._info(f"\n股票代码: {res['code']}")
        self._info(f"🧑‍💼 巴菲特评分")
        self._info(f"  ├ 质地趋势分: {res['base']} / 80")
        self._info(f"  ├ 估值评分:   {res['val_score']} / 20")
        self._info(f"  └ 综合总分:   {res['score']} / 100")
        self._info(f"\n趋势状态: {res['trend_label']}")
        self._info(f"估值状态: {res['val_label']}")
        self._info(f"投资评级: {res['rating']}")
        self._info(f"{'─'*45}")
        for k, v in res["indicators"].items():
            if pd.isna(v):
                continue
            self._info(f"{k:<20} {v:.2%}")
        self._info(f"{'='*50}\n")

    def _append_graham_result(self, res: dict) -> None:
        self._info(f"\n股票代码: {res['code']}")
        self._info(f"📐 格雷厄姆评分")
        self._info(f"  └ 综合总分: {res['score']} / 100")
        self._info(f"\n投资评级: {res['rating']}")
        self._info(f"{'─'*45}")
        if res.get("pe") is not None:
            self._info(f"PE(TTM):     {res['pe']:.2f}")
        else:
            self._info(f"PE(TTM):     N/A")
        if res.get("pb") is not None:
            self._info(f"PB:          {res['pb']:.2f}")
        else:
            self._info(f"PB:          N/A")
        if res["score"] >= 80:
            self._info("🔥 极度低估（典型格雷厄姆机会）")
        elif res["score"] >= 60:
            self._info("✅ 价值区间（可关注）")
        elif res["score"] >= 40:
            self._info("⚠️ 普通估值（无明显机会）")
        else:
            self._info("❌ 高估或质量不足")
        self._info(f"{'='*50}\n")

    def clear_output(self) -> None:
        self.text.delete(1.0, tk.END)
        self._clear_tree()
        self._set_status("已清空")


def main() -> None:
    root = tk.Tk()
    app = EasyTraderGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()