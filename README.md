# 📊 easyTrader · 价值评分系统

> 一个基于 Python 的 A 股量化分析系统，集成多维度评分体系、相对估值模型、市场复盘和图形化操作界面。
>
> 版本：2026.06.12 · 数据来源：东方财富 / 申万指数 (akshare)

---

## 快速开始

### 环境要求
- Python 3.11+
- MySQL 5.7+ **（推荐）** 或 SQLite

### 安装依赖
`ash
pip install -r requirements.txt
`

### 初始化行业数据
`python
from trader.valuation.industry import download_sw_industry
download_sw_industry()
`

### 启动 GUI
`ash
python trader/gui_app.py
`

### 代码示例
`python
from trader.valuation.engine import quick_valuate
result = quick_valuate("600519")
print(result["_summary"]["verdict"])
`

---

## 功能总览

### 评分体系（6 种）
| 评分体系 | 核心理念 | 适用场景 |
|---------|---------|---------|
| 巴菲特价值评分 | ROE、财务质地、合理PE | 长期价值投资 |
| 格雷厄姆评分 | 安全边际、低PE/PB、高流动性 | 寻找低估价值股 |
| 徐翔趋势评分 | 价格动量、成交量放大、突破新高 | 短线/波段交易 |
| Renoyuan 核心评分 | 综合财务+增长+估值+股息 | 综合型选股 |
| 方老哥筹码趋势评分 | 筹码集中度、主力资金、突破形态 | 中线锁仓/首板博弈 |
| 徐彬财务安全评分 | 资产负债结构、现金流覆盖 | 财务风控 |

### 估值分析
| 方法 | 公式 | 依赖数据 |
|-----|------|---------|
| PE估值法 | 行业合理PE x EPS | 行业PE区间、EPS |
| PB估值法 | 行业合理PB x BVPS | 行业PB区间、每股净资产 |
| PS估值法 | 行业PS x 营收/总股本 | 营收、总股本 |
| PEG估值法 | 合理PE=增长率(PEG=1) | EPS、净利润增长率 |

### 项目结构
`
easyTrader/
├── trader/
│   ├── version.py               # 版本号
│   ├── config.py                 # 配置
│   ├── db/                       # ORM模型
│   ├── valuation/                # 估值模块(行业/相对估值/引擎)
│   ├── scorer/                   # 评分模块(6种评分体系)
│   ├── reviewer/                 # 复盘模块
│   ├── gui/                      # 图形界面(5个面板)
│   └── gui_app.py                # GUI入口
├── README.md
└── config.json
`

### 配置
`json
{
  "tushare_token": "",
  "deepseek_token": "",
  "db": {
    "type": "mysql",
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "",
    "database": "easytrader"
  }
}
`

### 数据来源
| 数据 | 来源 |
|------|------|
| 财务数据 | 东方财富(akshare) |
| K线行情 | 东方财富(akshare) |
| 估值数据 | 东方财富(akshare) |
| 行业数据 | 申万指数(akshare) |

Apache License 2.0

> renoyuan@foxmail.com | github.com/renoyuan/easyTrader
