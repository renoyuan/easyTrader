"""
股神复盘 GUI 面板
==================
市场复盘 + 个股复盘
"""
import tkinter as tk
from tkinter import ttk, messagebox
import traceback
from datetime import datetime, timedelta

from trader.reviewer import MarketReviewer, StockReviewer
from trader.ai import DeepSeekClient


class ReviewerPanel:
    """股神复盘面板"""

    def __init__(self, status_callback, info_callback,
                 tree_callback, notebook_select_callback) -> None:
        self._set_status = status_callback
        self._info = info_callback
        self._update_tree = tree_callback
        self._select_tab = notebook_select_callback

        self.market = MarketReviewer()
        self.stock = StockReviewer()

    # ──────────────────────────
    #  市场复盘
    # ──────────────────────────
    def run_market_review(self) -> None:
        """执行市场复盘"""
        self._set_status("⏳ 市场复盘中...", True)
        self._info(f"\n{'='*50}")
        self._info("📊  市场复盘")
        self._info(f"{'='*50}")
        print(f"\n📊 市场复盘 ...")

        # 1. 市场情绪指标
        self._info("\n🔹 市场情绪指标")
        try:
            indices = self.market.get_index_summary()
            if indices:
                for name, data in indices.items():
                    if "count" in data:
                        extra = ""
                        if "avg_pct" in data and data["avg_pct"]:
                            extra += f"  均涨幅: {data['avg_pct']:.2f}%"
                        if "max_days" in data and data["max_days"]:
                            extra += f"  最长时间: {data['max_days']}天"
                        self._info(f"  📊 {name}: {data['count']}只{extra}")
                    else:
                        self._info(f"  📊 {name}: {data}")
            else:
                self._info("  ⚠️ 未获取到情绪指标")
        except Exception as e:
            self._info(f"  ❌ 获取指数失败: {e}")
            traceback.print_exc()

        # 2. 周度统计
        self._info("\n🔹 近5日市场统计")
        try:
            weekly = self.market.get_weekly_summary()
            stats = weekly.get("个股统计", {})
            if stats:
                self._info(f"  ✅ 上涨: {stats.get('上涨家数', 'N/A')} 家")
                self._info(f"  ❌ 下跌: {stats.get('下跌家数', 'N/A')} 家")
                self._info(f"  🚀 涨停: {stats.get('涨停', 'N/A')} 家")
                self._info(f"  💥 跌停: {stats.get('跌停', 'N/A')} 家")
        except Exception as e:
            self._info(f"  ❌ 获取周度统计失败: {e}")

        # 3. 涨跌 Top10
        self._info("\n🔹 涨跌幅 Top 10")
        try:
            tops = self.market.get_top_stocks()
            for group in ("主板", "科创创业"):
                self._info(f"\n  ── {group} ──")
                data = tops.get(group, {})
                up_list = data.get("涨幅榜", [])
                down_list = data.get("跌幅榜", [])
                if up_list:
                    self._info("  📈 涨幅前10:")
                    for i, s in enumerate(up_list, 1):
                        name = s.get('name', '')
                        code = s.get('code', '')
                        pct = s.get('pct_chg', 0)
                        price = s.get('price', 0)
                        self._info(f"    {i:>2}. {name}({code})  {pct:+.2f}%"
                                   + (f"  ¥{s.get('price', '')}" if s.get('price') else ""))
                if down_list:
                    self._info("  📉 跌幅前10:")
                    for i, s in enumerate(down_list, 1):
                        name = s.get('name', '')
                        code = s.get('code', '')
                        pct = s.get('pct_chg', 0)
                        price = s.get('price', 0)
                        self._info(f"    {i:>2}. {name}({code})  {pct:+.2f}%"
                                   + (f"  ¥{s.get('price', '')}" if s.get('price') else ""))
        except Exception as e:
            self._info(f"  ❌ 获取涨跌榜失败: {e}")

        # 填充摘要表格
        tree_rows = []
        if indices:
            for name, data in indices.items():
                if "count" in data:
                    tree_rows.append((f"📊 {name}", str(data['count']), ""))
        if stats:
            for k, v in stats.items():
                tree_rows.append((f"  {k}", str(v), ""))
        self._update_tree(tree_rows)

        self._info(f"\n{'='*50}\n")
        self._set_status("市场复盘完成", True)
        self._select_tab(0)

    # ──────────────────────────
    #  个股复盘
    # ──────────────────────────
    def run_stock_review(self, symbol: str) -> None:
        """执行个股复盘"""
        if not symbol:
            messagebox.showwarning("提示", "请先输入股票代码")
            return

        self._set_status(f"⏳ 个股复盘 {symbol}...", True)
        self._info(f"\n{'='*50}")
        self._info(f"📊  个股复盘")
        self._info(f"{'='*50}")
        print(f"\n📊 个股复盘 {symbol} ...")

        try:
            data = self.stock.get_stock_review(symbol)
            if not data or not data.get("periods"):
                self._info("❌ 未获取到数据，请确认股票代码正确")
                self._set_status("复盘失败", False)
                return

            name = data.get("name", "")
            end_date = data.get("统计截止", "")

            # 基础标识
            self._info(f"  标的：{symbol}  {name}")
            self._info(f"  统计截止：{end_date}")

            # 各区间涨跌
            self._info(f"\n🔹 区间涨跌表现")
            tree_rows = [
                (f"📊 个股复盘", f"{symbol} {name}", ""),
                ("统计截止", end_date, ""),
            ]
            for period_name in ("昨日", "近一周", "近两月", "近六月", "近一年"):
                p = data["periods"].get(period_name)
                if not p:
                    continue

                if period_name == "昨日":
                    # 昨日直接展示完整交易日的开盘/收盘/最高/最低
                    date = p.get('日期', '')
                    o = p.get('开盘', '-')
                    c = p.get('收盘', '-')
                    h = p.get('最高', '-')
                    l = p.get('最低', '-')
                    pct = p.get('涨跌幅%', 0)
                    icon = "📈" if pct > 0 else "📉" if pct < 0 else "➖"
                    self._info(f"  {icon} {date}  开盘{o} 收盘{c} 高{h} 低{l}  {pct:+.2f}%")
                    tree_rows.append((f"  {date}", f"{pct:+.2f}%", f"开{o} 收{c} 高{h} 低{l}"))
                else:
                    pct = p.get("涨跌幅%", 0)
                    icon = "📈" if pct > 0 else "📉" if pct < 0 else "➖"
                    self._info(f"  {icon} {period_name}: {pct:+.2f}%  "
                               f"始 {p.get('起始价', '-')} → 终 {p.get('最新价', '-')}  "
                               f"高 {p.get('最高', '-')} 低 {p.get('最低', '-')}")
                    tree_rows.append((
                        f"  {period_name}",
                        f"{pct:+.2f}%",
                        f"始{p.get('起始价','-')}→终{p.get('最新价','-')}"
                    ))

            # 关键财报数据
            fin = data.get("financial", {})
            if fin:
                self._info(f"\n🔹 关键财报数据")
                for k, v in fin.items():
                    if v is not None:
                        self._info(f"  {k}: {v}")
                        tree_rows.append((f"  {k}", str(v), ""))

            # ── AI 分析 ──
            self._info(f"\n{'='*50}")
            self._info("🤖 DeepSeekAI 分析")
            self._info(f"{'='*50}")
            try:
                ai = DeepSeekClient()
                if ai.is_ready:
                    analysis = ai.analyze_stock_review(data)
                    self._info(f"\n{analysis}\n")
                else:
                    self._info("  ⚠️ DeepSeek API Key 未配置，跳过 AI 分析\n请在左侧操作面板 → 系统设置 → 配置 DeepSeek Key")
                              
            except Exception as e:
                self._info(f"  ⚠️ AI 分析异常: {e}")

            self._update_tree(tree_rows)

            self._info(f"\n{'='*50}\n")
            self._set_status(f"个股复盘完成: {symbol}", True)
            self._select_tab(0)

        except Exception as e:
            self._info(f"❌ 个股复盘异常: {e}")
            traceback.print_exc()
            self._set_status("个股复盘失败", False)
