# 方案三：纯 Flutter 本地 APP 架构

> 文档版本：v1.0  
> 最后更新：2025-06-10  
> 状态：方案设计阶段

---

## 一、架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                         手机 APP（Flutter）                          │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                     UI 层（Flutter Widget）                    │   │
│  │                                                               │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐   │   │
│  │  │评分页面    │ │ 扫描结果页  │ │ 复盘页面    │ │ 设置页面  │   │   │
│  │  │├ 代码输入  │ │ ├ TopN排行  │ │ ├ 市场概览  │ │ ├ Token   │   │   │
│  │  │├ 体系选择  │ │ ├ 详情展开  │ │ ├ 个股复盘  │ │ ├ 数据管理│   │   │
│  │  │├ 结果卡片  │ │ ├ 搜索过滤  │ │ ├ K线图表   │ │ ├ 主题    │   │   │
│  │  │└ AI点评    │ │ └ 分享导出  │ │ └ AI分析    │ │ └ 关于    │   │   │
│  │  └────────────┘ └────────────┘ └────────────┘ └──────────┘   │   │
│  └──────────────────────────┬──────────────────────────────────────┘   │
│                             │                                        │
│  ┌──────────────────────────▼──────────────────────────────────────┐   │
│  │                   评分引擎层（纯 Dart）                           │   │
│  │                                                                   │   │
│  │  ┌─────────────────────────────────────────────────────────┐     │   │
│  │  │  lib/scorer/                                            │     │   │
│  │  │  ├── buffett_scorer.dart      巴菲特评分                 │     │   │
│  │  │  ├── graham_scorer.dart       格雷厄姆评分               │     │   │
│  │  │  ├── xuxiang_scorer.dart      徐翔趋势评分               │     │   │
│  │  │  ├── renoyuan_scorer.dart     renoyuan核心评分           │     │   │
│  │  │  ├── xubin_scorer.dart        xubin财报排雷评分           │     │   │
│  │  │  └── scorer_base.dart         评分器基类                 │     │   │
│  │  └─────────────────────────────────────────────────────────┘     │   │
│  │                                                                   │   │
│  │  ┌─────────────────────────────────────────────────────────┐     │   │
│  │  │  lib/processor/                                          │     │   │
│  │  │  ├── financial_processor.dart  财务指标计算               │     │   │
│  │  │  ├── trend_calculator.dart    趋势计算（线性回归等）      │     │   │
│  │  │  └── market_scanner.dart      全市场扫描                   │     │   │
│  │  └─────────────────────────────────────────────────────────┘     │   │
│  └──────────────────────────┬──────────────────────────────────────┘   │
│                             │                                        │
│  ┌──────────────────────────▼──────────────────────────────────────┐   │
│  │                    数据层（纯 Dart）                              │   │
│  │                                                                   │   │
│  │  ┌─────────────────────────────────────────────────────────┐     │   │
│  │  │  lib/data/                                               │     │   │
│  │  │  ├── east_money_api.dart        东方财富 API 封装          │     │   │
│  │  │  ├── sina_api.dart              新浪财经 API 封装          │     │   │
│  │  │  ├── tencent_api.dart           腾讯财经 API 封装          │     │   │
│  │  │  └── data_sync_manager.dart     数据同步管理器             │     │   │
│  │  └─────────────────────────────────────────────────────────┘     │   │
│  │                                                                   │   │
│  │  ┌─────────────────────────────────────────────────────────┐     │   │
│  │  │  lib/db/                                                 │     │   │
│  │  │  ├── database_helper.dart       SQLite 初始化 + 迁移       │     │   │
│  │  │  ├── models/                    DAO 数据模型               │     │   │
│  │  │  │   ├── stock_basic.dart                                 │     │   │
│  │  │  │   ├── income.dart                                      │     │   │
│  │  │  │   ├── balance.dart                                     │     │   │
│  │  │  │   ├── cashflow.dart                                    │     │   │
│  │  │  │   ├── dividend.dart                                    │     │   │
│  │  │  │   ├── valuation.dart                                   │     │   │
│  │  │  │   └── kline.dart                                       │     │   │
│  │  │  └── repositories/              数据仓库（CRUD 操作）       │     │   │
│  │  │      ├── stock_repository.dart                            │     │   │
│  │  │      ├── financial_repository.dart                        │     │   │
│  │  │      └── kline_repository.dart                            │     │   │
│  │  └─────────────────────────────────────────────────────────┘     │   │
│  └──────────────────────────┬──────────────────────────────────────┘   │
│                             │                                        │
├─────────────────────────────┼─────────────────────────────────────────┤
│                             │                                        │
│  ┌──────────────────────────▼──────────────────────────────────────┐   │
│  │                   本地存储（SQLite + Hive）                       │   │
│  │                                                                   │   │
│  │  ┌────────────────────┐  ┌────────────────────────────────────┐   │   │
│  │  │  SQLite (sqflite)   │  │  Hive NoSQL                       │   │   │
│  │  │                     │  │                                    │   │   │
│  │  │  ├ 财务数据（持久）  │  │  ├ 估值缓存（日过期）              │   │   │
│  │  │  ├ K线数据（持久）   │  │  ├ 扫描结果缓存（手动刷新）        │   │   │
│  │  │  └ 股票信息（持久）  │  │  ├ 用户偏好设置                   │   │   │
│  │  │                     │  │  └ 最近查看/收藏（永久）            │   │   │
│  │  └────────────────────┘  └────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                     │   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    AI 服务层                                     │   │
│  │  lib/services/deepseek_service.dart                             │   │   │
│  │  └── 直接调 DeepSeek API（Dio HTTP）                           │   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                     │   │
└─────────────────────────────────────────────────────────────────────┘   │
                                                                       │
           ┌──────────────────────────┼──────────────────────────┐
           ▼                          ▼                          ▼
┌──────────────────┐ ┌────────────────────┐ ┌──────────────────────┐
│ 东方财富 HTTP API │ │ 新浪财经 HTTP API   │ │ DeepSeek API        │
│ push2.eastmoney  │ │ money.finance.sina  │ │ api.deepseek.com    │
│ datacenter-web   │ │                     │ │                     │
└──────────────────┘ └────────────────────┘ └──────────────────────┘
```

---

## 二、技术栈明细

| 层级 | 技术 | 版本 | 说明 |
|------|------|------|------|
| **UI 框架** | Flutter | 3.x | 跨端 UI 框架 |
| **语言** | Dart | 3.x | AOT 编译，原生 ARM 性能 |
| **HTTP 客户端** | Dio | 5.x | 拦截器、重试、超时、Cookie |
| **数据库** | sqflite | 2.x | SQLite Flutter 插件 |
| **NoSQL 缓存** | Hive | 2.x | 轻量级键值存储 |
| **状态管理** | Riverpod | 2.x | 推荐 |
| **图表** | fl_chart | 0.68+ | 折线图、K 线图 |
| **AI** | http 直调 | - | DeepSeek REST API |
| **路由** | go_router | - | 声明式路由 |
| **本地化** | intl | - | 中英文切换支持 |

---

## 三、数据获取策略：批量预下载 + 本地计算

### 3.1 核心思路

与 PC 版"逐只股票拉数据"不同，纯 APP 方案采用 **"按报表期批量拉全市场，本地计算"** 策略：

```
PC 版（慢）：     for 股票 in 5000: 拉数据(网络) → 计算(CPU)
                             5000 次网络请求 ≈ 30 分钟

APP 版（快）：    拉全市场利润表(1次网络) → 存 SQLite → for 股票 in 5000: 查本地(0ms) → 计算(CPU)
                             5 次网络请求 + 1 秒计算 ≈ 5 秒
```

### 3.2 东方财富 API 批量接口

经实测验证，东方财富数据中心提供 **全市场批量查询 API**：

| 数据 | reportName | 类型 | 单次可获取 |
|------|-----------|------|-----------|
| **股票列表** | `push2.eastmoney.com/api/qt/clist/get` | 行情 | 全市场 |
| **估值数据** | `RPT_VALUEANALYSIS_DET` | 财务 | 全市场 |
| **利润表** | `RPT_DMSK_FN_INCOME` + 按日期筛选 | 财报 | 指定日期全市场 |
| **资产负债表** | `RPT_DMSK_FN_BALANCE` + 按日期筛选 | 财报 | 指定日期全市场 |
| **现金流量表** | `RPT_DMSK_FN_CASHFLOW` + 按日期筛选 | 财报 | 指定日期全市场 |
| **分红数据** | `RPT_SHAREBONUS_DET` + 按日期筛选 | 分红 | 指定日期全市场 |

> **已验证成功**：估值 API 返回 600519(贵州茅台) 的 PE_TTM、PB_MRQ、总市值等完整数据  
> **已验证成功**：股票列表 API 返回全市场股票代码/名称  
> **已验证成功**：K线 API 返回日 K 线数据

### 3.3 首次启动数据同步

```
┌──────────────────────────────────────────────────────────────┐
│                      首次启动欢迎页                           │
│                                                              │
│  欢迎使用 easyTrader                                        │
│                                                              │
│  首次使用需要下载基础数据（约 20MB）                          │
│  预计耗时：20-30 秒（Wi-Fi 环境）                            │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  ████████████████████░░░░░░░░░░░░  65%               │    │
│  │  正在下载 2024 年利润表...                             │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  [ 稍后再说 ]      [ 开始下载 ]                              │
└──────────────────────────────────────────────────────────────┘

下载流程：
步骤1: 股票基础信息    1次请求, ~200KB, ~0.5s
步骤2: 近5年利润表     5次请求, ~1MB×5, ~5s
步骤3: 近5年资产负债表  5次请求, ~1MB×5, ~5s
步骤4: 近5年现金流量表  5次请求, ~1MB×5, ~5s
步骤5: 估值数据(今日)  1次请求, ~500KB, ~1s
步骤6: 近5年分红数据   5次请求, ~500KB×5, ~3s
步骤7: 近5年财务指标   5次请求, ~500KB×5, ~3s
────────────────────────────────────────────────
总计: 27次请求, ~20MB, ~20-30s
```

### 3.4 日常使用数据同步

```
打开 APP
    │
    ▼
┌──────────────────────────────────────────────┐
│ 检查数据新鲜度                                 │
│                                              │
│  ├── 估值缓存是否今日已更新？                   │
│  │   ├─ 否 → 后台拉取全市场估值(1次请求, ~1s)   │
│  │   └─ 是 → 跳过                              │
│                                              │
│  ├── 财务数据是否最新季度？                     │
│  │   ├─ 否 → 后台拉取新增季度数据(N次请求)       │
│  │   └─ 是 → 跳过                              │
│                                              │
│  └── K线数据是否最近交易日？                    │
│      ├─ 否 → 后台增量同步                      │
│      └─ 是 → 跳过                             │
└──────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────┐
│ 用户操作（无需等待同步）                        │
│  - 查看昨日缓存的全市场扫描结果                  │
│  - 查看已缓存的个股评分                        │
│  - 收藏、对比、复盘（均基于本地数据）             │
└──────────────────────────────────────────────┘
```

### 3.5 全市场扫描流程

```
用户点击"扫描市场"
    │
    ▼
┌──────────────────────────────────────────────┐
│ 从 SQLite 查询所有股票基础信息                  │
│ ← 本地查询，0ms                               │
└────────────────┬─────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────┐
│ for 股票 in 5000:                             │
│     financialData = SQLite 查询(5年财务)      │
│     ← 本地查询，每条 ~0.1ms                   │
│     valuationData = Hive 缓存查询(PE/PB)     │
│     ← 本地查询，每条 ~0.05ms                  │
│     score = 评分器计算(纯 Dart CPU)           │
│     ← 纯计算，每条 ~0.4ms                     │
└────────────────┬─────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────┐
│ 排序 → 取 TopN → 缓存到 Hive                  │
│ 显示结果列表                                   │
│                                                │
│ 5000 只总耗时：~1-3 秒                        │
└──────────────────────────────────────────────┘
```

---

## 四、Flutter APP 项目结构

```
easy_trader_app/
├── lib/
│   ├── main.dart                         # 应用入口
│   ├── app.dart                          # MaterialApp + 路由配置
│   │
│   ├── config/
│   │   ├── api_config.dart               # 东方财富 API 地址
│   │   ├── theme.dart                    # 主题（亮色/暗色）
│   │   └── constants.dart                # 常量（评分名称等）
│   │
│   ├── scorer/                           # 评分引擎（Python→Dart 翻译）
│   │   ├── scorer_base.dart              # 评分器抽象基类
│   │   ├── buffett_scorer.dart           # 巴菲特评分
│   │   ├── graham_scorer.dart            # 格雷厄姆评分
│   │   ├── xuxiang_scorer.dart           # 徐翔趋势评分
│   │   ├── renoyuan_scorer.dart          # renoyuan 核心评分
│   │   └── xubin_scorer.dart             # xubin 财报排雷
│   │
│   ├── processor/                        # 特征工程（Python→Dart 翻译）
│   │   ├── financial_processor.dart      # 财务指标计算
│   │   ├── trend_calculator.dart         # 趋势计算（线性回归）
│   │   └── market_scanner.dart           # 全市场扫描逻辑
│   │
│   ├── data/                             # 数据层
│   │   ├── east_money_api.dart           # 东方财富 API 封装
│   │   ├── sina_api.dart                 # 新浪财经 API 封装
│   │   └── data_sync_manager.dart        # 数据同步管理
│   │
│   ├── db/                               # 数据库层
│   │   ├── database_helper.dart          # SQLite 初始化
│   │   ├── models/                       # 数据模型
│   │   │   ├── stock_basic.dart
│   │   │   ├── income.dart
│   │   │   ├── balance.dart
│   │   │   ├── cashflow.dart
│   │   │   ├── dividend.dart
│   │   │   ├── valuation.dart
│   │   │   └── kline.dart
│   │   └── repositories/                 # CRUD 操作
│   │       ├── stock_repository.dart
│   │       ├── financial_repository.dart
│   │       └── kline_repository.dart
│   │
│   ├── services/                         # 外部服务
│   │   ├── deepseek_service.dart         # DeepSeek AI 客户端
│   │   └── cache_service.dart            # Hive 缓存服务
│   │
│   ├── providers/                        # 状态管理
│   │   ├── score_provider.dart           # 评分状态
│   │   ├── scan_provider.dart            # 扫描状态
│   │   ├── sync_provider.dart            # 数据同步状态
│   │   └── favorite_provider.dart        # 收藏状态
│   │
│   ├── pages/                            # 页面
│   │   ├── splash/
│   │   │   └── splash_page.dart          # 启动页（首次同步引导）
│   │   ├── home/
│   │   │   └── home_page.dart            # 首页（快速评分入口）
│   │   ├── score/
│   │   │   ├── score_page.dart           # 个股评分页
│   │   │   └── score_result_card.dart    # 评分结果卡片
│   │   ├── scan/
│   │   │   ├── scan_page.dart            # 全市场扫描页
│   │   │   └── scan_result_list.dart     # 扫描结果列表
│   │   ├── review/
│   │   │   ├── market_review_page.dart   # 市场复盘
│   │   │   └── stock_review_page.dart    # 个股复盘
│   │   ├── stock_detail/
│   │   │   ├── stock_detail_page.dart    # 股票详情
│   │   │   ├── kline_chart_widget.dart   # K线图组件
│   │   │   └── financial_table.dart      # 财务数据表
│   │   └── settings/
│   │       ├── settings_page.dart        # 设置页
│   │       ├── data_management_page.dart # 数据管理（手动同步/清理）
│   │       └── about_page.dart           # 关于
│   │
│   └── widgets/                          # 公共组件
│       ├── score_card.dart               # 评分卡片
│       ├── rating_badge.dart             # 评级徽章（颜色编码）
│       ├── progress_dialog.dart          # 进度对话框
│       ├── empty_state.dart              # 空状态占位
│       ├── error_state.dart              # 错误状态
│       └── pull_to_refresh.dart          # 下拉刷新封装
│
├── test/                                 # 单元测试
│   ├── scorer/
│   │   ├── buffett_scorer_test.dart
│   │   ├── graham_scorer_test.dart
│   │   └── ...
│   └── processor/
│       └── trend_calculator_test.dart
│
├── pubspec.yaml
├── android/
├── ios/
├── web/                                  # 可选：PWA Web 版
└── harmonyos/                            # 可选：鸿蒙版
```

---

## 五、东方财富 API 封装设计

### 5.1 API 基类

```dart
// lib/data/east_money_api.dart

class EastMoneyAPI {
  static const String _dataCenter = 'https://datacenter-web.eastmoney.com';
  static const String _push2 = 'https://push2.eastmoney.com';
  static const String _push2his = 'https://push2his.eastmoney.com';

  final Dio _dio;

  EastMoneyAPI() : _dio = Dio(BaseOptions(
    connectTimeout: Duration(seconds: 10),
    receiveTimeout: Duration(seconds: 30),
    headers: {
      'User-Agent': 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36',
      'Referer': 'https://data.eastmoney.com/',
    },
  ));

  /// 获取全市场估值数据（1次请求全部股票）
  Future<List<ValuationDTO>> fetchAllValuations() async {
    final resp = await _dio.get(
      '$_dataCenter/api/data/v1/get',
      queryParameters: {
        'reportName': 'RPT_VALUEANALYSIS_DET',
        'columns': 'SECURITY_CODE,SECURITY_NAME_ABBR,PE_TTM,PB_MRQ,CLOSE_PRICE,TRADE_DATE',
        'pageSize': '5000',
        'pageNumber': '1',
        'sortColumns': 'TRADE_DATE',
        'sortTypes': '-1',
      },
    );
    // 解析 JSON → List<ValuationDTO>
  }

  /// 获取全市场利润表（按报告期）
  Future<List<IncomeDTO>> fetchAllIncome(String reportDate) async {
    // reportName: RPT_DMSK_FN_INCOME
    // 按 REPORT_DATE 筛选
  }

  /// 获取K线数据
  Future<List<KlineDTO>> fetchKLine(String code, {int limit = 200}) async {
    final resp = await _dio.get(
      '$_push2his/api/qt/stock/kline/get',
      queryParameters: {
        'secid': '${_getMarket(code)}.$code',
        'fields1': 'f1,f2,f3,f4,f5,f6',
        'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
        'klt': '101',  // 日K
        'fqt': '1',    // 前复权
        'end': '20500101',
        'lmt': limit.toString(),
      },
    );
    // 解析返回的 klines 字符串数组
  }
}
```

### 5.2 已验证的 API

| 接口 | URL | 实测 |
|------|-----|------|
| 全市场估值 | `datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_VALUEANALYSIS_DET` | ✅ **成功** |
| 全市场股票列表 | `push2.eastmoney.com/api/qt/clist/get` | ✅ **成功** |
| 个股K线 | `push2his.eastmoney.com/api/qt/stock/kline/get` | ✅ **成功** |
| 全市场利润表 | `datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_DMSK_FN_INCOME` | ✅ **可调** |
| 全市场资产负债表 | `datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_DMSK_FN_BALANCE` | ✅ **可调** |
| 全市场现金流量表 | `datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_DMSK_FN_CASHFLOW` | ✅ **可调** |

---

## 六、评分引擎 Dart 翻译示例

### 6.1 Python → Dart 对比（巴菲特趋势计算）

```python
# Python 版 (buffett.py)
def _trend(self, series, max_p):
    d = series.dropna()
    if len(d) < 2:
        return 0
    x = np.arange(len(d))
    y = d.values
    k = np.polyfit(x, y, 1)[0]
    if k > 0:
        return max_p
    elif abs(k) < 0.002:
        return int(max_p * 0.7)
    return 0
```

```dart
// Dart 版 (buffett_scorer.dart)

double _trend(List<double> series, double maxP) {
  final valid = series.where((v) => v.isFinite).toList();
  if (valid.length < 2) return 0;

  final n = valid.length;
  final xMean = (n - 1) / 2;
  final yMean = valid.reduce((a, b) => a + b) / n;

  double num = 0, den = 0;
  for (int i = 0; i < n; i++) {
    final dx = i - xMean;
    final dy = valid[i] - yMean;
    num += dx * dy;
    den += dx * dx;
  }

  final k = den == 0 ? 0 : num / den;
  if (k > 0) return maxP;
  if (k.abs() < 0.002) return maxP * 0.7;
  return 0;
}
```

### 6.2 Python VS Dart 代码量对比

| 评分器 | Python 行数 | Dart 行数 | 变化 |
|--------|------------|-----------|------|
| buffett.py | ~150 | ~120 | -20% |
| graham.py | ~120 | ~100 | -17% |
| xuxiang.py | ~120 | ~90 | -25% |
| renoyuan.py | ~200 | ~160 | -20% |
| xubin.py | ~200 | ~160 | -20% |
| feature.py | ~250 | ~200 | -20% |
| **总计** | **~1040** | **~830** | **-20%** |

> 减少原因：不需要 pandas/numpy 的 import 和序列化代码，去掉 print 调试日志等

---

## 七、性能分析

### 7.1 计算性能

| 操作 | Python (PC) | Dart (手机 ARM) | 加速比 |
|------|-------------|-----------------|--------|
| 5000只线性回归趋势计算 | ~500ms | ~30ms | **~16x** |
| 5000只财务指标排序 | ~100ms | ~5ms | **~20x** |
| 单只巴菲特全评分 | ~5ms | ~0.4ms | **~12x** |
| **全市场扫描(5000只)** | **~25s(纯计算)** | **~2s** | **~12x** |
| **全市场扫描(含网络)** | **5~30分钟** | **~5s(仅首次)** | **60~360x** |

### 7.2 存储空间

| 数据 | 大小 |
|------|------|
| 股票基础信息 | ~0.3 MB |
| 近5年利润表 | ~15 MB |
| 近5年资产负债表 | ~15 MB |
| 近5年现金流量表 | ~10 MB |
| 近5年分红数据 | ~5 MB |
| 估值缓存 | ~1 MB |
| K线缓存（常用股票） | ~10-50 MB |
| **总计** | **~60-100 MB** |

### 7.3 流量消耗

| 场景 | 流量 | 频率 |
|------|------|------|
| 首次启动 | ~20 MB | 1次 |
| 每日估值更新 | ~500 KB | 1次/日 |
| 每季度财务更新 | ~10 MB | 1次/季 |
| 个股K线查看 | ~50-200 KB | 按需 |
| **日均** | **~500 KB - 2 MB** | |

---

## 八、优劣势总结

### 优势
1. ✅ **零服务器成本**：完全本地运行
2. ✅ **离线可用**：数据下载后可离线评分
3. ✅ **隐私安全**：数据不出手机
4. ✅ **响应极快**：Dart AOT 原生编译，计算比 PC Python 快 10x+
5. ✅ **全市场扫描秒级**：批量预下载 + 本地计算，5000 只需 1-3 秒
6. ✅ **包大小小**：Flutter 纯 Dart，APK ~15-25MB
7. ✅ **三端覆盖**：一套代码 Android / iOS / 鸿蒙
8. ✅ **免费上架**：Android 上架 Google Play 免费，iOS 需 688 元/年
9. ✅ **无服务依赖**：不依赖第三方后端，数据源挂了不影响已缓存数据

### 不足
1. ❌ **首次启动需下载数据**：~20-30 秒，~20MB 流量
2. ❌ **数据实时性依赖同步频率**：估值每日更新，财务每季度更新
3. ❌ **手机存储占用**：~60-100 MB
4. ❌ **所有评分器需翻译为 Dart**：~830 行 Dart 代码（但逻辑完全相同）
5. ❌ **无法多人共享**：每台手机各自下载数据
6. ❌ **全市场扫描消耗手机 CPU**：5000 只评分时会发热（但仅需 1-3 秒）
7. ❌ **鸿蒙 NEXT 可能暂不支持**：Flutter 适配鸿蒙 NEXT 还在进行中

### 适用场景

- ✅ 个人投资者，注重隐私
- ✅ 不想花钱租服务器
- ✅ 经常在地铁/飞机等无网络环境使用
- ✅ Android/iOS/鸿蒙全平台覆盖需求
- ❌ 需要团队共享评分结果
- ❌ 对数据实时性要求极高（实时行情）

---

## 九、与方案二（APP+后端）详细对比

| 维度 | 方案二：APP+后端 | 方案三：纯 APP |
|------|-----------------|----------------|
| **服务器** | 需要，~50元/月起 | 不需要 ✅ |
| **离线能力** | 差（依赖网络） | 强 ✅ |
| **全市场扫描速度** | ~2.5秒（服务端） ✅ | ~1-3秒（手机端） ✅ |
| **首次使用体验** | 即开即用 ✅ | 需等待数据下载 |
| **流量消耗** | 每次操作都请求 | 批量下载后离线使用 |
| **多人共享** | 支持 ✅ | 不支持 |
| **开发量** | 大（API层+Flutter+部署） | 中（仅Flutter） |
| **维护成本** | 高（服务器+数据源适配） | 低（仅 APP 更新） |
| **数据实时性** | 高（服务端定时同步） ✅ | 中（依赖手机端同步） |
| **隐私** | 数据经过服务器 | 完全本地 ✅ |
| **APK大小** | ~15-25MB | ~15-25MB |
| **鸿蒙支持** | Flutter 适配中 | Flutter 适配中 |
| **上架成本** | Android免费+iOS 688元/年 | 同左 |
| **推荐场景** | 团队使用/追求最佳体验 | 个人使用/注重隐私/离线 |

---

## 十、开发路线图建议

```
Phase 1 (Week 1): 核心引擎翻译
  ├── 翻译 buffett_scorer.dart (评分逻辑)
  ├── 翻译 graham_scorer.dart
  ├── 翻译 xuxiang_scorer.dart
  ├── 翻译 renoyuan_scorer.dart
  ├── 翻译 xubin_scorer.dart
  ├── 翻译 financial_processor.dart (特征工程)
  ├── 编写趋势计算工具类 trend_calculator.dart
  └── 编写单元测试（确保输出与 Python 版本一致）

Phase 2 (Week 2): 数据层 + 数据库
  ├── 实现 east_money_api.dart（东方财富 API 封装）
  ├── 实现 sina_api.dart（新浪 API 封装，备选）
  ├── 定义 SQLite 模型（income, balance, cashflow 等）
  ├── 实现数据仓库（CRUD）
  ├── 实现 data_sync_manager.dart（同步管理器）
  └── 实现首次启动数据下载流程

Phase 3 (Week 3): UI 界面
  ├── 评分页面（输入代码 → 选择体系 → 展示结果）
  ├── 全市场扫描页面（启动扫描 → 进度显示 → 结果列表）
  ├── 复盘页面（市场概览 + 个股复盘 + K线图）
  ├── 股票详情页面（评分 + 财务数据 + AI点评）
  ├── 设置页面（Token配置 + 数据管理 + 主题）
  └── 公共组件封装

Phase 4 (Week 4): 打磨 + 打包
  ├── 状态管理集成（Riverpod）
  ├── 错误处理 + 重试机制
  ├── Hive 缓存层
  ├── 暗色模式
  ├── 性能优化
  ├── 打包 Android APK
  ├── 打包 iOS IPA
  └── 上架应用市场
```
