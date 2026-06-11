# 方案二：后端 API + Flutter 跨端 APP 架构

> 文档版本：v1.0  
> 最后更新：2025-06-10  
> 状态：方案设计阶段

---

## 一、架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                      云服务器（阿里云/腾讯云）                        │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                   Docker 容器                                  │   │
│  │                                                               │   │
│  │  ┌─────────────────────┐   ┌─────────────────────────────┐   │   │
│  │  │  FastAPI 服务        │   │  Celery 异步任务队列          │   │   │
│  │  │                     │   │                              │   │   │
│  │  │  GET /api/score     │   │  ├── 全市场扫描 Task          │   │   │
│  │  │  POST /api/scan     │   │  ├── 数据同步 Task            │   │   │
│  │  │  GET /api/data      │   │  └── 批量评分 Task            │   │   │
│  │  │  POST /api/ai       │   │                              │   │   │
│  │  └─────────┬───────────┘   └──────────┬──────────────────┘   │   │
│  │            │                           │                      │   │
│  │            ▼                           ▼                      │   │
│  │  ┌─────────────────────────────────────────────────────────┐   │   │
│  │  │           Python 评分引擎（核心逻辑复用）                    │   │   │
│  │  │                                                         │   │   │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │   │   │
│  │  │  │ Buffett  │ │ Graham   │ │ XuXiang  │ │ Renoyuan │   │   │   │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │   │   │
│  │  │  ┌──────────┐ ┌──────────────────┐ ┌────────────────┐ │   │   │
│  │  │  │ XuBin    │ │ StockFeatureProc │ │ MarketScanner  │ │   │   │
│  │  │  └──────────┘ └──────────────────┘ └────────────────┘ │   │   │
│  │  └───────────────────────┬─────────────────────────────────┘   │   │
│  │                          │                                      │   │
│  │  ┌───────────────────────▼─────────────────────────────────┐   │   │
│  │  │  数据库（MySQL 或 SQLite）                                │   │   │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐ │   │   │
│  │  │  │ income   │ │ balance  │ │ cashflow │ │ valuation  │ │   │   │
│  │  │  ├──────────┤ ├──────────┤ ├──────────┤ ├────────────┤ │   │   │
│  │  │  │ stock_   │ │ dividend │ │ kline    │ │ financial_ │ │   │   │
│  │  │  │ basic    │ │          │ │          │ │ indicator  │ │   │   │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └────────────┘ │   │   │
│  │  └─────────────────────────────────────────────────────────┘   │   │
│  │                                                               │   │
│  │  ┌─────────────────────────────────────────────────────────┐   │   │
│  │  │  定时任务（APScheduler，每天 18:00 执行）                  │   │   │
│  │  │  ├── 同步全市场财务数据（季度报告期）                       │   │   │
│  │  │  ├── 同步全市场估值数据（每日）                            │   │   │
│  │  │  ├── 全市场扫描并缓存结果                                  │   │   │
│  │  │  └── 清除过期缓存                                        │   │   │
│  │  └─────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────┘   │   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  外部数据源                                                   │   │   │
│  │  ├── 东方财富 HTTP API（同现有 akshare 封装）                  │   │   │
│  │  └── 新浪财经 HTTP API                                        │   │   │
│  └─────────────────────────────────────────────────────────────┘   │   │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTPS / WebSocket
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         手机 APP（Flutter）                          │
│                                                                     │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────┐  │
│  │ 评分页面      │ │ 扫描结果页面  │ │ 复盘页面      │ │ 设置页面  │  │
│  │              │ │              │ │              │ │          │  │
│  │ ├ 股票代码输入 │ │ ├ TopN排名   │ │ ├ 市场概览    │ │ ├ Token  │  │
│  │ ├ 体系选择    │ │ ├ 详情展开   │ │ ├ 个股复盘    │ │ ├ 主题    │  │
│  │ ├ 结果展示    │ │ ├ 搜索过滤   │ │ ├ AI分析     │ │ ├ 缓存    │  │
│  │ └ K线图表     │ │ └ 分享      │ │ └ 历史对比    │ │ └ 关于    │  │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────┘  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  本地缓存层（Hive / Isar NoSQL）                             │   │
│  │  ├── 最近查看股票列表                                         │   │
│  │  ├── 收藏股票列表                                             │   │
│  │  ├── 历史扫描结果                                             │   │
│  │  └── 用户偏好设置                                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  网络服务层                                                   │   │
│  │  ├── API Service（Dio HTTP 客户端）                           │   │
│  │  ├── WebSocket（实时扫描进度推送）                             │   │
│  │  └── 离线队列（网络恢复后自动重试）                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、技术栈明细

### 2.1 后端

| 组件 | 技术 | 说明 |
|------|------|------|
| **API 框架** | FastAPI | Python 异步 Web 框架，自动生成 OpenAPI 文档 |
| **异步任务** | Celery + Redis | 全市场扫描等耗时任务异步执行 |
| **定时任务** | APScheduler | 每日自动同步数据 + 全市场扫描 |
| **ORM** | SQLAlchemy | 现有代码复用 |
| **数据库** | MySQL 8.0 或 SQLite | MySQL 适合多人，SQLite 适合单人 |
| **缓存** | Redis | 任务队列 + 临时缓存 |
| **部署** | Docker + Docker Compose | 一键部署 |
| **反向代理** | Nginx | 域名 + SSL + 负载均衡 |
| **监控** | Prometheus + Grafana | 可选 |

### 2.2 前端（Flutter APP）

| 组件 | 技术 | 说明 |
|------|------|------|
| **UI 框架** | Flutter 3.x | Dart 语言，跨端编译 |
| **状态管理** | Riverpod / Provider | 推荐 Riverpod |
| **HTTP 客户端** | Dio | 拦截器、重试、超时配置 |
| **WebSocket** | web_socket_channel | 扫描进度实时推送 |
| **本地缓存** | Hive / Isar | 轻量级 NoSQL |
| **图表** | fl_chart / syncfusion | K 线图、柱状图 |
| **推送** | Firebase / 华为推送 | 扫描完成通知 |

---

## 三、API 设计

```
┌─────────────────────────────────────────────────────────────────┐
│                    REST API 接口清单                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [评分]                                                          │
│  POST /api/v1/score/{code}                                      │
│    Body: { "system": "buffett" }                                 │
│    Response: { "code": 0, "data": { score, rating, ... } }      │
│                                                                  │
│  [全市场扫描 - 异步]                                              │
│  POST /api/v1/scan                                               │
│    Body: { "markets": ["SH","SZ"], "system": "buffett", "top":10}│
│    Response: { "code": 0, "data": { "task_id": "xxx" } }        │
│                                                                  │
│  GET /api/v1/scan/{task_id}                                      │
│    Response: { "code": 0, "data": { "status": "running",        │
│                "progress": "50%", "results": [...] } }           │
│                                                                  │
│  GET /api/v1/scan/latest                                        │
│    Response: 最近一次缓存的扫描结果                                │
│                                                                  │
│  [复盘]                                                          │
│  POST /api/v1/review/stock                                       │
│    Body: { "code": "600519" }                                    │
│    Response: { K线数据 + 财务指标 + AI分析 }                      │
│                                                                  │
│  GET /api/v1/review/market                                      │
│    Response: { 上涨/下跌统计, 板块分布 }                           │
│                                                                  │
│  [数据]                                                          │
│  GET /api/v1/data/kline/{code}?start=...&end=...                │
│  GET /api/v1/data/financial/{code}?years=5                      │
│  GET /api/v1/data/valuation/{code}                               │
│                                                                  │
│  [AI]                                                            │
│  POST /api/v1/ai/comment                                         │
│    Body: { "system": "buffett", "result": {...} }               │
│    Response: { "comment": "AI 点评文本" }                         │
│                                                                  │
│  [用户]（如需用户系统）                                            │
│  POST /api/v1/user/register                                      │
│  POST /api/v1/user/login                                        │
│  GET /api/v1/user/favorites                                     │
│  POST /api/v1/user/favorites/{code}                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 四、后端代码改造方案

### 4.1 新增文件清单

```
trader/
├── api/                          # NEW: API 层
│   ├── __init__.py
│   ├── main.py                   # FastAPI 应用入口
│   ├── config.py                 # API 配置（端口、密钥等）
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── scorer.py             # 评分相关接口
│   │   ├── scanner.py            # 全市场扫描接口
│   │   ├── reviewer.py           # 复盘接口
│   │   ├── data.py               # 数据查询接口
│   │   └── ai.py                 # AI 分析接口
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py            # Pydantic 请求/响应模型
│   │
│   └── tasks/
│       ├── __init__.py
│       ├── celery_app.py         # Celery 配置
│       ├── scan_task.py          # 全市场扫描异步任务
│       └── sync_task.py          # 数据同步定时任务
│
├── Dockerfile                    # NEW
├── docker-compose.yml            # NEW
└── requirements-api.txt          # NEW: 新增 fastapi, uvicorn, celery, redis
```

### 4.2 现有代码改动量

| 文件 | 改动类型 | 改动说明 |
|------|----------|----------|
| `trader/scorer/*.py` | **无需改动** ✅ | 评分逻辑完全复用 |
| `trader/processor/feature.py` | **无需改动** ✅ | 特征工程完全复用 |
| `trader/data/statement.py` | **无需改动** ✅ | 数据层完全复用 |
| `trader/db/orm.py` | **无需改动** ✅ | ORM 完全复用 |
| `trader/gui/*.py` | **废弃** | 不再需要 Tkinter 界面 |
| **新增 `trader/api/`** | **新增 ~500 行** | API 路由 + 模型 + 任务 |

### 4.3 核心 API 代码示例

```python
# trader/api/main.py
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from trader.scorer.buffett import BuffettScorer
from trader.scorer.market_scanner import MarketScanner

app = FastAPI(title="easyTrader API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"])

# 评分器缓存（避免重复创建）
_scorers = {}

@app.post("/api/v1/score/{code}")
async def score_stock(code: str, system: str = "buffett"):
    scorer_cls = SCORER_MAP[system]
    if system not in _scorers:
        _scorers[system] = scorer_cls()
    result = _scorers[system].score(code)
    return {"code": 0, "data": result}

@app.post("/api/v1/scan")
async def start_scan(markets: list[str], system: str, top_n: int = 10):
    task_id = str(uuid.uuid4())
    # 异步执行
    celery_app.send_task("run_scan", args=[task_id, markets, system, top_n])
    return {"code": 0, "data": {"task_id": task_id}}
```

---

## 五、前端 Flutter APP 结构

```
easy_trader_app/
├── lib/
│   ├── main.dart                     # 入口
│   ├── app.dart                      # MaterialApp 配置
│   │
│   ├── config/
│   │   ├── api_config.dart           # API 地址 & 超时
│   │   ├── theme.dart                # 主题（深色/浅色模式）
│   │   └── constants.dart            # 常量
│   │
│   ├── models/
│   │   ├── score_result.dart         # 评分结果
│   │   ├── scan_result.dart          # 扫描结果
│   │   ├── stock_info.dart           # 股票基础信息
│   │   ├── kline_data.dart           # K线数据
│   │   └── financial_data.dart       # 财务数据
│   │
│   ├── services/
│   │   ├── api_service.dart          # Dio HTTP 封装
│   │   ├── websocket_service.dart    # WebSocket 进度推送
│   │   ├── cache_service.dart        # Hive 本地缓存
│   │   └── notification_service.dart # 推送通知
│   │
│   ├── providers/
│   │   ├── score_provider.dart       # 评分状态
│   │   ├── scan_provider.dart        # 扫描状态
│   │   └── favorite_provider.dart    # 收藏状态
│   │
│   ├── pages/
│   │   ├── home/
│   │   │   └── home_page.dart        # 首页（推荐/收藏）
│   │   ├── score/
│   │   │   ├── score_page.dart       # 评分页
│   │   │   └── score_result_card.dart # 评分结果卡片
│   │   ├── scan/
│   │   │   ├── scan_page.dart        # 扫描页
│   │   │   ├── scan_progress.dart    # 进度条组件
│   │   │   └── scan_result_list.dart # 结果列表
│   │   ├── review/
│   │   │   ├── market_review_page.dart  # 市场复盘
│   │   │   ├── stock_review_page.dart   # 个股复盘
│   │   │   └── ai_analysis_section.dart # AI分析区
│   │   ├── stock_detail/
│   │   │   ├── stock_detail_page.dart   # 股票详情
│   │   │   ├── kline_chart.dart         # K线图
│   │   │   └── financial_table.dart     # 财务数据表
│   │   └── settings/
│   │       ├── settings_page.dart       # 设置页
│   │       ├── token_config.dart        # Token 配置
│   │       └── about_page.dart          # 关于
│   │
│   └── widgets/
│       ├── score_card.dart              # 评分卡片
│       ├── rating_badge.dart            # 评级徽章
│       ├── progress_dialog.dart         # 进度对话框
│       └── empty_state.dart             # 空状态占位
│
├── pubspec.yaml
├── android/
├── ios/
└── web/                         # 可选：同时支持浏览器
```

---

## 六、部署方案

### 6.1 服务器最低配置

| 配置项 | 最低 | 推荐 |
|--------|------|------|
| CPU | 2 核 | 4 核 |
| 内存 | 4 GB | 8 GB |
| 硬盘 | 40 GB SSD | 80 GB SSD |
| 带宽 | 5 Mbps | 10 Mbps |
| 月费 | ~50-80 元 | ~100-150 元 |

### 6.2 Docker Compose 部署

```yaml
# docker-compose.yml
version: "3.8"
services:
  api:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      - redis
      - db
    environment:
      - DATABASE_URL=mysql+pymysql://user:pass@db/easytrader

  celery-worker:
    build: .
    command: celery -A trader.api.tasks.celery_app worker --loglevel=info
    depends_on:
      - redis
      - db

  redis:
    image: redis:7-alpine

  db:
    image: mysql:8.0
    environment:
      MYSQL_DATABASE: easytrader
      MYSQL_USER: user
      MYSQL_PASSWORD: pass
    volumes:
      - mysql_data:/var/lib/mysql

volumes:
  mysql_data:
```

---

## 七、数据同步策略

### 7.1 定时任务（APScheduler）

| 任务 | 频率 | 说明 |
|------|------|------|
| 同步估值数据 | 每日 18:00 | 拉取全市场 PE/PB/市值 |
| 同步财务数据 | 季报后次日 | 拉取利润表/资产负债表/现金流量表 |
| 全市场扫描 | 每日 18:30 | 各评分体系扫描并缓存 Top100 |
| 清除过期缓存 | 每日 02:00 | 清理 7 天前的临时扫描结果 |

### 7.2 用户首次使用体验

```
打开 APP
    │
    ▼
┌────────────────────┐
│ 加载本地缓存        │
│ ← 空（首次使用）    │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ 请求 /api/v1/scan/ │
│ latest             │
│ ← 返回昨日扫描结果  │
│  （秒级响应）       │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ 展示 TopN 排行榜    │
│ 用户可直接查看评分   │
└────────────────────┘
```

**用户无需等待**——扫描结果已经在服务器上每天定时跑好了。

---

## 八、性能分析

### 8.1 响应时间

| 操作 | 耗时 | 说明 |
|------|------|------|
| 个股评分 | **< 1s** | 服务器本地计算，仅查数据库无网络 |
| 查看缓存扫描结果 | **< 0.5s** | 直接返回已缓存的 TopN |
| 发起新扫描 | **瞬间** | 异步执行，返回 task_id |
| 查询扫描进度 | **实时** | WebSocket 推送进度 |
| 个股复盘 | **< 2s** | 需拉取 K 线数据 |

### 8.2 全市场扫描实际耗时（服务器端）

```
服务器 4核8G MySQL：
  扫描 5000 只 × 巴菲特评分
  数据库查询：~0.5s（批量 IN 查询）
  纯计算：~2s（5000 × 每个 0.4ms）
  总计：~2.5s

  对比 PC 现有架构：5~30 分钟 → 2.5 秒
  加速比：120x ~ 720x
```

---

## 九、优劣势总结

### 优势
1. ✅ **移动端覆盖**：Android / iOS / 鸿蒙一套代码
2. ✅ **全市场扫描极快**：2.5 秒（服务器端批量计算）
3. ✅ **无需本地下载数据**：服务器每日自动同步
4. ✅ **多人共用**：一台服务器全家使用
5. ✅ **核心代码零修改**：Python 评分引擎完全复用
6. ✅ **APK 包极小**：Flutter 纯 Dart，~15-25MB
7. ✅ **原生性能**：Dart AOT 编译，比 Python 快 10x
8. ✅ **可扩展**：可加用户系统、推送、收藏、社区功能

### 不足
1. ❌ **需要服务器**：最低 ~50 元/月
2. ❌ **需要网络**：离线不可用（个股评分可考虑本地缓存部分数据）
3. ❌ **开发量较大**：后端 API 层 + Flutter 前端约 2-3 周
4. ❌ **App Store 上架费**：Apple 开发者账号 688 元/年
5. ❌ **维护成本**：服务器运维 + 数据源变更适配

### 适用场景

- ✅ 个人投资者，想随时随地用手机看评分
- ✅ 团队成员共享一套评分系统
- ✅ 追求最佳性能和体验
- ❌ 不想花服务器钱
- ❌ 需要完全离线使用
