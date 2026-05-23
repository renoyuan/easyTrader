import akshare as ak
import pandas as pd
import time
import orm
from orm import SessionLocal, StockBasic, init_db

# ======================
# 获取全A股股票映射表
# ======================
def get_all_stocks():
    df = ak.stock_info_a_code_name()

    def get_market(code):
        if code.startswith(("60", "68")):
            return "SH"
        elif code.startswith(("00", "30")):
            return "SZ"
        elif code.startswith(("8", "9")):
            return "BJ"
        else:
            return "OTHER"

    df["market"] = df["code"].apply(get_market)
    return df.to_dict("records")

# ======================
# 股票基础信息入库（已修复）
# ======================
def save_stock_basic(data_list):
    print("data_list" , data_list)
    db = SessionLocal()
    try:
        db.query(StockBasic).delete()
        db.commit()

        objects = []
        for item in data_list:
            obj = StockBasic(
                code=item["code"],
                name=item["name"],
                market=item["market"],
                list_status="L",
                industry=""
            )
            objects.append(obj)

        db.bulk_save_objects(objects)
        db.commit()
        print(f"✅ 成功写入 {len(data_list)} 只股票映射表")
    except Exception as e:
        print("❌ 入库失败", e)
        db.rollback()
    finally:
        db.close()

# ======================
# 下载日线 + 自动重试（解决网络错误）
# ======================
def get_akshare_daily(symbol: str, start: str, end: str, retry=3) -> pd.DataFrame:
    for i in range(retry):
        try:
            if symbol.startswith('6'):
                code = f'sh{symbol}'
            else:
                code = f'sz{symbol}'

            df = ak.stock_zh_a_hist(
                symbol=code,
                period='daily',
                start_date=start,
                end_date=end,
                adjust=''
            )

            if not df.empty:
                df.rename(columns={
                    '日期': 'Date', '开盘': 'Open', '收盘': 'Close',
                    '最高': 'High', '最低': 'Low', '成交量': 'Volume'
                }, inplace=True)
                df['Date'] = pd.to_datetime(df['Date'])
            return df

        except Exception as e:
            print(f"⚠️  {symbol} 下载失败，重试 {i+1}/{retry}")
            time.sleep(2)
    print(f"❌ {symbol} 下载失败，已跳过")
    return pd.DataFrame()

def get_akshare_daily(symbol: str, start: str, end: str, retry=3) -> pd.DataFrame:
    for i in range(retry):
        try:
            if symbol.startswith('6'):
                code = f'sh{symbol}'
            else:
                code = f'sz{symbol}'

            df = ak.stock_zh_a_hist(
                symbol=code,
                period='daily',
                start_date=start,
                end_date=end,
                adjust=''
            )

            if not df.empty:
                df.rename(columns={
                    '日期': 'date',
                    '开盘': 'open',
                    '收盘': 'close',
                    '最高': 'high',
                    '最低': 'low',
                    '成交量': 'volume',
                    '成交额': 'amount',
                    '振幅': 'amplitude',
                    '涨跌幅': 'pct_chg',
                    '涨跌额': 'change',
                    '换手率': 'turnover_rate'
                }, inplace=True)
                df['date'] = pd.to_datetime(df['date'])
            return df

        except Exception as e:
            print(f"⚠️ {symbol} 下载失败，重试 {i+1}/{retry}")
            time.sleep(2)
    print(f"❌ {symbol} 下载失败，已跳过")
    return pd.DataFrame()

def save_daily_to_db(code: str, df: pd.DataFrame):
    if df.empty:
        print(f"ℹ️ {code} 无数据，无需入库")
        return

    # 动态创建表（你的 orm 函数）
    StockKline = create_stock_table_class(code)
    StockKline.__table__.create(bind=engine, checkfirst=True)

    db = SessionLocal()
    try:
        # ==============================================
        # ✅ 关键：查出该股票已存在的所有日期，只插入新数据
        # ==============================================
        exist_dates = {
            x[0] for x in 
            db.query(StockKline.date).filter(StockKline.ts_code == code).all()
        }

        insert_count = 0
        for _, row in df.iterrows():
            current_date = row["date"]

            # 如果日期已存在 → 跳过
            if current_date in exist_dates:
                continue

            # 不存在 → 插入
            obj = StockKline(
                date=current_date,
                ts_code=code,
                open=row["open"],
                close=row["close"],
                high=row["high"],
                low=row["low"],
                volume=row["volume"],
                amount=row.get("amount"),
                amplitude=row.get("amplitude"),
                pct_chg=row.get("pct_chg"),
                change=row.get("change"),
                turnover_rate=row.get("turnover_rate")
            )
            db.add(obj)
            insert_count += 1

        db.commit()
        print(f"✅ {code} 入库完成 → 新增 {insert_count} 条数据")

    except Exception as e:
        print(f"❌ {code} 入库失败：{str(e)}")
        db.rollback()
    finally:
        db.close()
        
# ======================
# 主程序
# ======================
if __name__ == "__main__":
    # 1. 初始化数据库
    init_db()

    # 2. 获取并入库 全A股股票映射表
    # stock_list = get_all_stocks()
    # save_stock_basic(stock_list)

    # 3. 下载测试（不会再报网络错）
    # df = get_akshare_daily('600519', '20230101', '20231231')
    # print("\n📊 下载结果：")
    # print(df.head())