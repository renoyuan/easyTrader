#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME: easyTrader
# CREATE_TIME: 2026-05-25
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# note:  

#!/usr/bin/env python
"""
方老哥综合评分模型
===================
融合方新侠（中线锁仓/重仓龙头）和赵老哥（首板突破/筹码结构）的风格，
基于分时线（逐笔成交）筹码分析 + 日线量价分析。

核心思想：
  1. 分时线筹码分布 → 判断筹码集中度、获利盘比例、主力方向
  2. 日线量价趋势  → 判断动量、突破形态、换手健康度
  3. 两者结合 → 给出适合"重仓锁仓+首板突破"综合风格的评分

满分 100 分，分两大维度：
  - 筹码结构分（0~60 分）：基于分时线数据的筹码分析
  - 量价趋势分（0~40 分）：基于日线数据的量价分析
"""

import sys
import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from trader.processor.feature import StockFeatureProcessor
from trader.data.statement import StatementDownload
from trader.data.intraday_storage import IntradayStorage


class FangLaogeScorer:
    """
    方老哥筹码+量价综合评分
    ========================
    风格：中线锁仓（方新侠）+ 首板突破（赵老哥）
    """

    def __init__(self, data_service=None):
        self.data_service = data_service or StatementDownload()
        self.proc = StockFeatureProcessor()

    # ═══════════════════════════════════════════════
    #  第一部分：分时线筹码分析（0~60 分）
    # ═══════════════════════════════════════════════

    def _get_intraday_data(self, code: str, target_date: str = None) -> pd.DataFrame:
        """
        获取指定日期分时逐笔成交数据
        优先级：本地库 > 新浪接口（拉取后自动入库）
        如果 target_date 为 None，则自动从今天往前回溯最近交易日
        返回字段: ticktime, price, volume, kind (U=买盘, D=卖盘, E=集合竞价)
        """
        import akshare as ak

        # 判断市场标识
        if code.startswith("6"):
            symbol = f"sh{code}"
        elif code.startswith("0") or code.startswith("3"):
            symbol = f"sz{code}"
        else:
            return pd.DataFrame()

        def _fetch_from_sina_and_save(_code: str, _symbol: str, _date: str) -> pd.DataFrame:
            """从新浪拉取并自动入库"""
            try:
                df = ak.stock_intraday_sina(symbol=_symbol, date=_date)
                if df is None or df.empty:
                    return pd.DataFrame()
                # 过滤集合竞价
                if 'kind' in df.columns:
                    df = df[df['kind'].isin(['U', 'D'])].copy()
                if df.empty:
                    return pd.DataFrame()
                # 自动入库
                saved = IntradayStorage.save_intraday(_code, df, _date)
                if saved:
                    print(f"  [fanglaoge] 分时数据已入库: {_code} {_date}, {saved} 条")
                return df
            except Exception as e:
                print(f"  [fanglaoge] 新浪分时拉取失败 {_date}: {e}")
                return pd.DataFrame()

        today = datetime.now()

        if target_date is None:
            # 未指定日期：从今天往前回溯，查本地 → 拉取
            for i in range(10):
                check_date = today - timedelta(days=i)
                if check_date.weekday() >= 5:
                    continue
                date_str = check_date.strftime("%Y%m%d")

                # 1. 先查本地
                local_df = IntradayStorage.load_intraday(code, date_str)
                if not local_df.empty:
                    print(f"  [fanglaoge] 命中本地分时库: {code} {date_str}")
                    return local_df

                # 2. 本地无，拉取
                df = _fetch_from_sina_and_save(code, symbol, date_str)
                if not df.empty:
                    return df
            return pd.DataFrame()
        else:
            # 指定日期
            local_df = IntradayStorage.load_intraday(code, target_date)
            if not local_df.empty:
                print(f"  [fanglaoge] 命中本地分时库: {code} {target_date}")
                return local_df
            return _fetch_from_sina_and_save(code, symbol, target_date)

    def _calc_chip_distribution(self, df: pd.DataFrame) -> dict:
        """
        基于分时逐笔数据计算筹码分布
        返回各维度指标
        """
        if df.empty or len(df) < 50:
            return {
                "chip_density": 0,      # 筹码集中度
                "profit_ratio": 0,       # 获利盘比例
                "buy_sell_ratio": 0,     # 买卖比
                "big_order_ratio": 0,    # 大单占比
                "big_buy_sell_ratio": 0, # 大单买卖比
                "valid": False
            }

        total_vol = df['volume'].sum()

        # ── 1. 筹码密度（按价格区间汇聚） ──
        # 每 0.05 元一档（针对茅台这类高价股）
        # 对低价股自适应调整：档位数量控制在 30~100 档
        price_range = df['price'].max() - df['price'].min()
        if price_range <= 0:
            return {"valid": False}

        # 自动计算合理的分档数（30~100 档）
        num_bins = min(max(int(price_range * 20), 30), 100)
        df['price_bin'] = pd.cut(df['price'], bins=num_bins, labels=False)

        # 按档汇聚
        chip_groups = df.groupby('price_bin').agg({
            'volume': 'sum',
            'kind': lambda x: (x == 'U').sum()  # 买盘笔数
        }).sort_index()
        chip_groups['vol_pct'] = chip_groups['volume'] / total_vol * 100

        # ── 2. 筹码集中度 ──
        # TOP5 最密集区间的成交量占比
        top5_vol = chip_groups.nlargest(5, 'volume')['volume'].sum()
        chip_density = top5_vol / total_vol if total_vol > 0 else 0

        # ── 3. 获利盘比例 ──
        # 当前收盘价 ≈ 最后一条数据的价格
        current_price = df['price'].iloc[-1]
        # 先算出每个档位对应的中位数价格
        # 用 price_bin 的平均价格近似
        bin_edges = pd.cut(df['price'], bins=num_bins, retbins=True)[1]
        below_vol = 0
        for i, row in chip_groups.iterrows():
            bin_center = (bin_edges[i] + bin_edges[i + 1]) / 2
            if bin_center <= current_price:
                below_vol += row['volume']

        profit_ratio = below_vol / total_vol if total_vol > 0 else 0

        # ── 4. 买卖盘力量 ──
        buy_vol = df[df['kind'] == 'U']['volume'].sum()
        sell_vol = df[df['kind'] == 'D']['volume'].sum()
        buy_sell_ratio = buy_vol / sell_vol if sell_vol > 0 else 0

        # ── 5. 大单分析（>= 400 手 = 40000 股） ──
        big_deals = df[df['volume'] >= 40000]
        big_vol = big_deals['volume'].sum()
        big_order_ratio = big_vol / total_vol if total_vol > 0 else 0
        big_buy = big_deals[big_deals['kind'] == 'U']['volume'].sum()
        big_sell = big_deals[big_deals['kind'] == 'D']['volume'].sum()
        big_buy_sell_ratio = big_buy / big_sell if big_sell > 0 else 0

        # ── 6. 分时段行为 ──
        # 早盘（09:30~10:30）资金占比，尾盘（14:30~15:00）资金占比
        morning = df[df['ticktime'] < '10:30:00']['volume'].sum()
        close_session = df[df['ticktime'] >= '14:30:00']['volume'].sum()
        morning_ratio = morning / total_vol if total_vol > 0 else 0
        tail_ratio = close_session / total_vol if total_vol > 0 else 0

        return {
            "chip_density": chip_density,
            "profit_ratio": profit_ratio,
            "buy_sell_ratio": buy_sell_ratio,
            "big_order_ratio": big_order_ratio,
            "big_buy_sell_ratio": big_buy_sell_ratio,
            "morning_ratio": morning_ratio,
            "tail_ratio": tail_ratio,
            "total_vol": total_vol,
            "valid": True
        }

    def _score_chip_structure(self, chip: dict) -> dict:
        """
        筹码结构评分（0~60 分）
        """
        if not chip.get("valid"):
            return {"score": 0, "detail": {}, "label": "数据不足"}

        score = 0
        detail = {}

        # ── 维度1：筹码集中度（0~20 分） ──
        # 集中度高 → 可能有主力控盘（方新侠风格：喜欢筹码集中）
        # 集中度适中 → 换手健康，有参与机会（赵老哥风格：有量有行情）
        # 太分散 → 散户行情
        cd = chip["chip_density"]
        if cd > 0.4:
            score += 20
            detail["筹码集中度"] = f"{cd:.1%} → 20分（高度集中，主力控盘）"
        elif cd > 0.25:
            score += 15
            detail["筹码集中度"] = f"{cd:.1%} → 15分（适中集中，有主力）"
        elif cd > 0.15:
            score += 8
            detail["筹码集中度"] = f"{cd:.1%} → 8分（略分散）"
        else:
            score += 2
            detail["筹码集中度"] = f"{cd:.1%} → 2分（高度分散，散户行情）"

        # ── 维度2：获利盘安全度（0~15 分） ──
        # 获利比例 30%~60% 最佳：既有安全垫，抛压又不大
        # 获利比例 > 80%：抛压大，容易回调
        # 获利比例 < 20%：套牢重，突破需要很大资金
        pr = chip["profit_ratio"]
        if 0.3 <= pr <= 0.6:
            score += 15
            detail["获利盘比例"] = f"{pr:.1%} → 15分（最佳区间）"
        elif 0.6 < pr <= 0.8:
            score += 10
            detail["获利盘比例"] = f"{pr:.1%} → 10分（获利偏多，略谨慎）"
        elif 0.2 <= pr < 0.3:
            score += 10
            detail["获利盘比例"] = f"{pr:.1%} → 10分（获利偏少，但安全）"
        elif pr > 0.8:
            score += 3
            detail["获利盘比例"] = f"{pr:.1%} → 3分（获利过多，抛压大）"
        else:
            score += 2
            detail["获利盘比例"] = f"{pr:.1%} → 2分（深度套牢区）"

        # ── 维度3：主力资金方向（0~15 分） ──
        # 买卖比 > 1.2：主动买盘占优
        # 大单买卖比 > 1.5：主力明显做多
        bsr = chip["buy_sell_ratio"]
        bbsr = chip["big_buy_sell_ratio"]

        # 综合买卖比和大单买卖比
        if bsr > 1.2 and bbsr > 1.5:
            score += 15
            detail["主力资金"] = f"买卖比{bsr:.2f}，大单比{bbsr:.2f} → 15分（主力强势做多）"
        elif bsr > 1.1 and bbsr > 1.2:
            score += 12
            detail["主力资金"] = f"买卖比{bsr:.2f}，大单比{bbsr:.2f} → 12分（主力做多）"
        elif bsr > 0.9:
            score += 8
            detail["主力资金"] = f"买卖比{bsr:.2f} → 8分（资金均衡）"
        elif bsr > 0.7:
            score += 4
            detail["主力资金"] = f"买卖比{bsr:.2f} → 4分（卖方略强）"
        else:
            score += 1
            detail["主力资金"] = f"买卖比{bsr:.2f} → 1分（卖方主导，出货嫌疑）"

        # ── 维度4：大单活跃度（0~10 分） ──
        # 有大单参与但不是全部大单（真主力建仓 vs 纯散户行情）
        bor = chip["big_order_ratio"]
        if 0.15 <= bor <= 0.5:
            score += 10
            detail["大单活跃度"] = f"大单占比{bor:.1%} → 10分（有主力参与）"
        elif bor > 0.5:
            score += 5
            detail["大单活跃度"] = f"大单占比{bor:.1%} → 5分（大单过多，可能是对倒）"
        elif bor > 0.05:
            score += 5
            detail["大单活跃度"] = f"大单占比{bor:.1%} → 5分（少量大单）"
        else:
            score += 1
            detail["大单活跃度"] = f"大单占比{bor:.1%} → 1分（无明显大单）"

        # ── 综合标签 ──
        if score >= 45:
            label = "🔥 筹码结构优秀（主力锁仓+资金做多）"
        elif score >= 35:
            label = "✅ 筹码结构良好（适合参与）"
        elif score >= 20:
            label = "⚖️ 筹码结构一般（观望）"
        else:
            label = "❌ 筹码结构差（回避）"

        return {"score": min(score, 60), "detail": detail, "label": label}

    # ═══════════════════════════════════════════════
    #  第二部分：日线量价趋势分析（0~40 分）
    # ═══════════════════════════════════════════════



    def _get_kline_data(self, code: str) -> pd.DataFrame:
        """获取日K线数据，近250个交易日"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365)
            kline = self.data_service.get_kline_df(
                code,
                start=start_date.strftime("%Y%m%d"),
                end=end_date.strftime("%Y%m%d")
            )
            if kline.empty:
                return pd.DataFrame()
            return kline
        except Exception as e:
            print(f"  [fanglaoge] K线数据获取失败: {e}")
            return pd.DataFrame()


    def _calc_multi_day_chip(self, code: str) -> dict:
        """
        基于近 5 日的分时线数据累加，估算多日筹码分布
        比单日数据更准确反映筹码集中度
        """
        all_chip_data = []

        # 获取最近 5 个交易日的日期
        today = datetime.now()
        for i in range(10):
            check_date = today - timedelta(days=i)
            # 跳过周末
            if check_date.weekday() >= 5:
                continue
            date_str = check_date.strftime("%Y%m%d")

            try:
                day_df = self._get_intraday_data(code, target_date=date_str)
                if not day_df.empty:
                    day_df = day_df.copy()
                    day_df['date'] = date_str
                    all_chip_data.append(day_df)
            except Exception:
                continue

            if len(all_chip_data) >= 5:
                break

        if len(all_chip_data) < 3:
            # 如果多日数据不足，退回单日
            return None

        # 合并多日数据
        merged = pd.concat(all_chip_data, ignore_index=True)
        return self._calc_chip_distribution(merged)

    def _score_trend(self, kline: pd.DataFrame, chip_multi: dict = None) -> dict:
        """
        日线量价趋势评分（0~40 分）
        """
        if kline.empty or len(kline) < 20:
            return {"score": 0, "detail": {}, "label": "K线数据不足"}

        score = 0
        detail = {}

        # 提取收盘价和成交量
        if 'close' in kline.columns:
            close = kline['close']
            volume = kline['volume']
        else:
            # 兼容不同列名
            close = kline.iloc[:, 3] if kline.shape[1] > 3 else kline.iloc[:, 1]
            volume = kline.iloc[:, 4] if kline.shape[1] > 4 else kline.iloc[:, 2]

        close = pd.to_numeric(close, errors='coerce').dropna()
        volume = pd.to_numeric(volume, errors='coerce').dropna()

        if len(close) < 20:
            return {"score": 0, "detail": {}, "label": "K线数据不足"}

        # ── 维度1：价格动量（0~15 分） ──
        # 短中长三个时间维度的动量
        mom_5 = (close.iloc[-1] / close.iloc[-5] - 1) if len(close) >= 5 else 0
        mom_10 = (close.iloc[-1] / close.iloc[-10] - 1) if len(close) >= 10 else 0
        mom_20 = (close.iloc[-1] / close.iloc[-20] - 1) if len(close) >= 20 else 0

        # 综合动量评分：短期冲劲 + 中期趋势
        # 赵老哥风格：5日涨幅 > 8% 是首板爆发信号
        # 方新侠风格：20日涨幅 > 15% 是趋势确认
        if mom_5 > 0.08 and mom_20 > 0.15:
            score += 15
            detail["价格动量"] = f"5日{mom_5:.1%}，20日{mom_20:.1%} → 15分（强势突破）"
        elif mom_5 > 0.05 and mom_20 > 0.10:
            score += 12
            detail["价格动量"] = f"5日{mom_5:.1%}，20日{mom_20:.1%} → 12分（趋势良好）"
        elif mom_10 > 0.03:
            score += 8
            detail["价格动量"] = f"10日{mom_10:.1%} → 8分（温和上涨）"
        elif mom_5 < -0.05:
            score += 2
            detail["价格动量"] = f"5日{mom_5:.1%} → 2分（短期下跌）"
        else:
            score += 5
            detail["价格动量"] = f"10日{mom_10:.1%} → 5分（横盘震荡）"

        # ── 维度2：成交量健康度（0~10 分） ──
        # 量价配合：上涨放量、下跌缩量
        # 换手率适中：不过热不冷清
        vol_5_avg = volume.iloc[-5:].mean()
        vol_20_avg = volume.iloc[-20:].mean()
        vol_ratio = vol_5_avg / vol_20_avg if vol_20_avg > 0 else 0

        # 短期放量但不异常
        if 1.2 <= vol_ratio <= 3.0:
            score += 10
            detail["成交量"] = f"量比{vol_ratio:.2f} → 10分（温和放量）"
        elif 1.0 <= vol_ratio < 1.2:
            score += 7
            detail["成交量"] = f"量比{vol_ratio:.2f} → 7分（量能平稳）"
        elif vol_ratio > 3.0:
            score += 3
            detail["成交量"] = f"量比{vol_ratio:.2f} → 3分（异常放量，警惕出货）"
        else:
            score += 3
            detail["成交量"] = f"量比{vol_ratio:.2f} → 3分（缩量，关注）"

        # ── 维度3：突破形态（0~10 分） ──
        # 赵老哥核心：是否突破关键阻力位
        # 简单判断：当前价是否在近60日高位附近
        recent_high = close.iloc[-60:].max() if len(close) >= 60 else close.max()
        current = close.iloc[-1]
        high_ratio = current / recent_high

        if high_ratio >= 0.98:
            score += 10
            detail["突破形态"] = f"近60日高位{high_ratio:.1%} → 10分（即将突破/已突破）"
        elif high_ratio >= 0.9:
            score += 6
            detail["突破形态"] = f"近60日高位{high_ratio:.1%} → 6分（接近阻力位）"
        elif high_ratio >= 0.8:
            score += 3
            detail["突破形态"] = f"近60日高位{high_ratio:.1%} → 3分（中部震荡）"
        else:
            score += 1
            detail["突破形态"] = f"近60日高位{high_ratio:.1%} → 1分（低位盘整）"

        # ── 维度4：趋势稳定性（0~5 分） ──
        # 均线多头排列 → 趋势健康
        if len(close) >= 60:
            ma5 = close.iloc[-5:].mean()
            ma20 = close.iloc[-20:].mean()
            ma60 = close.iloc[-60:].mean()
            if ma5 > ma20 > ma60:
                score += 5
                detail["趋势形态"] = "均线5>20>60 → 5分（多头排列）"
            elif ma5 > ma20 or ma20 > ma60:
                score += 3
                detail["趋势形态"] = "均线部分多头 → 3分（趋势改善中）"
            else:
                score += 1
                detail["趋势形态"] = "均线空头 → 1分（下跌趋势）"
        else:
            score += 2

        # ── 综合标签 ──
        if score >= 30:
            label = "🔥 强势突破（量价配合佳）"
        elif score >= 20:
            label = "✅ 趋势良好（可参与）"
        elif score >= 10:
            label = "⚖️ 震荡观望"
        else:
            label = "❌ 趋势向下（回避）"

        return {"score": min(score, 40), "detail": detail, "label": label}

    # ═══════════════════════════════════════════════
    #  综合评分
    # ═══════════════════════════════════════════════

    def score(self, code: str) -> dict:
        """
        方老哥综合评分入口
        """
        print(f"[fanglaoge] 开始评分: {code}")

        # ── 第一步：获取分时线数据，计算筹码分布 ──
        print(f"[fanglaoge] 获取分时线数据...")

        # 优先使用多日筹码数据（更准确）
        chip_multi = self._calc_multi_day_chip(code)
        if chip_multi and chip_multi.get("valid"):
            chip_result = chip_multi
            chip_source = "多日（近5日）"
        else:
            # 回退单日
            intraday = self._get_intraday_data(code)
            chip_result = self._calc_chip_distribution(intraday)
            chip_source = "单日"

        print(f"[fanglaoge] 筹码数据来源: {chip_source}")

        chip_score = self._score_chip_structure(chip_result)
        print(f"[fanglaoge] 筹码得分: {chip_score['score']}/60, {chip_score['label']}")

        # ── 第二步：获取日 K 线数据，计算量价趋势 ──
        print(f"[fanglaoge] 获取日K线数据...")
        kline = self._get_kline_data(code)
        trend_score = self._score_trend(kline, chip_multi)
        print(f"[fanglaoge] 趋势得分: {trend_score['score']}/40, {trend_score['label']}")

        # ── 第三步：综合 ──
        total = min(chip_score["score"] + trend_score["score"], 100)

        # 综合评级
        if total >= 80:
            rating = "🔥 方老哥极力推荐（龙头锁仓+突破确认）"
        elif total >= 65:
            rating = "✅ 方老哥推荐（筹码趋势双优）"
        elif total >= 50:
            rating = "⚖️ 观望（等待信号明朗）"
        elif total >= 35:
            rating = "⚠️ 谨慎（筹码或趋势走弱）"
        else:
            rating = "❌ 回避（结构趋势均差）"

        # 风格标签
        style_tags = []
        if chip_score["score"] >= 35:
            if chip_result.get("chip_density", 0) > 0.3 and chip_result.get("big_buy_sell_ratio", 0) > 1.2:
                style_tags.append("锁仓")
            if chip_result.get("profit_ratio", 0) > 0.4 and chip_result.get("profit_ratio", 0) < 0.8:
                style_tags.append("攻守兼备")
        if trend_score["score"] >= 25:
            style_tags.append("趋势突破")
        style_tag = "+".join(style_tags) if style_tags else "待观察"

        # 获取股票名称
        stock_name = self.proc.get_stock_name(code)

        # 组装详细指标
        chip_detail = chip_result if chip_result.get("valid") else {}

        return {
            "code": code,
            "name": stock_name,
            "score": total,
            "rating": rating,
            "style_tag": style_tag,
            "sub_scores": {
                "chip_score": chip_score["score"],
                "chip_label": chip_score["label"],
                "trend_score": trend_score["score"],
                "trend_label": trend_score["label"],
            },
            "chip_detail": chip_score["detail"],
            "trend_detail": trend_score["detail"],
            "chip_raw": {
                "chip_density": chip_detail.get("chip_density"),
                "profit_ratio": chip_detail.get("profit_ratio"),
                "buy_sell_ratio": chip_detail.get("buy_sell_ratio"),
                "big_order_ratio": chip_detail.get("big_order_ratio"),
                "big_buy_sell_ratio": chip_detail.get("big_buy_sell_ratio"),
                "morning_ratio": chip_detail.get("morning_ratio"),
                "tail_ratio": chip_detail.get("tail_ratio"),
            },
            "chip_source": chip_source,
        }

    def print_score(self, r: dict):
        """打印评分结果"""
        if r is None:
            print("评分失败")
            return

        print(f"\n==============================================")
        print(f"  方老哥综合评分")
        print(f"  {r['code']} {r['name']}")
        print(f"==============================================")
        print(f"  综合得分: {r['score']}/100")
        print(f"  风格标签: {r['style_tag']}")
        print(f"  综合评级: {r['rating']}")
        print(f"------------------------------------------------")
        print(f"  【筹码结构】{r['sub_scores']['chip_score']}/60")
        print(f"  {r['sub_scores']['chip_label']}")
        for k, v in r.get("chip_detail", {}).items():
            print(f"    ├ {v}")
        print(f"------------------------------------------------")
        print(f"  【量价趋势】{r['sub_scores']['trend_score']}/40")
        print(f"  {r['sub_scores']['trend_label']}")
        for k, v in r.get("trend_detail", {}).items():
            print(f"    ├ {v}")
        print(f"------------------------------------------------")
        print(f"  筹码原始数据:")
        raw = r.get("chip_raw", {})
        if raw.get("chip_density") is not None:
            print(f"    筹码集中度: {raw['chip_density']:.1%}")
            print(f"    获利盘比例: {raw['profit_ratio']:.1%}")
            print(f"    买卖比: {raw['buy_sell_ratio']:.2f}")
            print(f"    大单占比: {raw['big_order_ratio']:.1%}")
            print(f"    大单买卖比: {raw['big_buy_sell_ratio']:.2f}")
            print(f"    早盘资金占比: {raw['morning_ratio']:.1%}")
            print(f"    尾盘资金占比: {raw['tail_ratio']:.1%}")
        else:
            print("    数据不足（非交易时段或数据获取失败）")
        print(f"  数据来源: {r.get('chip_source', 'N/A')}")
        print(f"==============================================\n")


if __name__ == "__main__":
    s = FangLaogeScorer()
    code = input("请输入股票代码: ").strip()
    res = s.score(code)
    s.print_score(res)
