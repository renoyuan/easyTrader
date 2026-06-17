#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME: easyTrader
# CREATE_TIME: 2026-05-25
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# note:  

"""
分时线逐笔成交数据本地存储
===========================
- 写入：方老哥评分器拉取分时线后自动入库
- 读取：优先查本地，命中直接返回
- 过期：当日数据 1 小时后失效（盘中可刷新）
"""
import pandas as pd
from datetime import datetime, timedelta

from trader.db.orm import SessionLocal, IntradayTick


class IntradayStorage:
    """分时线逐笔成交本地存储"""

    # ── 写入 ──

    @staticmethod
    def save_intraday(code: str, df: pd.DataFrame, trade_date: str) -> int:
        """
        将分时逐笔数据入库（幂等，覆盖写入）
        :param code:        股票代码
        :param df:          分时DataFrame，需包含 ticktime, price, volume, kind, prev_price
        :param trade_date:  交易日期 YYYYMMDD
        :return:            写入条数
        """
        if df.empty:
            return 0

        with SessionLocal() as session:
            # 先删该股票该日旧数据（避免重复）
            deleted = session.query(IntradayTick).filter(
                IntradayTick.code == code,
                IntradayTick.trade_date == trade_date
            ).delete()
            session.commit()

            objects = []
            for _, row in df.iterrows():
                obj = IntradayTick(
                    code=code,
                    trade_date=trade_date,
                    ticktime=str(row.get("ticktime", "")),
                    price=float(row.get("price", 0)),
                    volume=int(float(row.get("volume", 0))),
                    kind=str(row.get("kind", "U")),
                    prev_price=float(row.get("prev_price", 0)) if "prev_price" in row else None,
                )
                objects.append(obj)

            # 分批写入（每批 5000 条）
            batch_size = 5000
            for i in range(0, len(objects), batch_size):
                session.bulk_save_objects(objects[i:i + batch_size])
            session.commit()

        return len(objects)

    # ── 读取 ──

    @staticmethod
    def load_intraday(code: str, trade_date: str) -> pd.DataFrame:
        """
        从本地库加载分时逐笔数据
        :param code:        股票代码
        :param trade_date:  交易日期 YYYYMMDD
        :return:            DataFrame，字段同新浪接口
        """
        with SessionLocal() as session:
            rows = session.query(IntradayTick).filter(
                IntradayTick.code == code,
                IntradayTick.trade_date == trade_date
            ).order_by(IntradayTick.ticktime).all()

        if not rows:
            return pd.DataFrame()

        records = []
        for r in rows:
            records.append({
                "ticktime": r.ticktime,
                "price": r.price,
                "volume": r.volume,
                "kind": r.kind,
                "prev_price": r.prev_price,
            })

        df = pd.DataFrame(records)
        return df

    # ── 查询是否有本地数据 ──

    @staticmethod
    def has_intraday(code: str, trade_date: str) -> bool:
        """检查本地是否已有该日分时数据"""
        with SessionLocal() as session:
            count = session.query(IntradayTick).filter(
                IntradayTick.code == code,
                IntradayTick.trade_date == trade_date
            ).count()
        return count > 0

    # ── 清理 ──

    @staticmethod
    def clean_old_data(days: int = 30):
        """清理指定天数前的分时数据"""
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        with SessionLocal() as session:
            deleted = session.query(IntradayTick).filter(
                IntradayTick.trade_date < cutoff
            ).delete()
            session.commit()
        print(f"[intraday_storage] 清理 {deleted} 条 {days} 天前的分时数据")
        return deleted
