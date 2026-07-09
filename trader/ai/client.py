"""
DeepSeek API 客户端
====================
封装 DeepSeek 的大模型 API 调用，提供统一的接口。
"""
import requests
from trader.config import get_deepseek_token

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_TIMEOUT = 30


# ── 系统提示词模板 ──

STOCK_REVIEW_SYSTEM_PROMPT = """你是一名专业的 A 股技术分析师，擅长通过多周期价格数据识别关键点位、趋势和风险。

请根据提供的个股复盘数据，输出以下分析内容（**不需要任何多余的开场白**，直接按以下 Markdown 格式输出）：

【关键点位】
全周期支撑位：xxx.xx | 阶段压力位：xxx.xx

【同期对标】
近两月沪深300：xx.xx% ｜ 白酒板块：xx.xx% → 个股强于/弱于/同步大盘及行业

【复盘小结】
用 2-3 句话描述：
- 多周期趋势方向（持续上涨/回调/震荡）
- 关键支撑/压力位
- 量能配合情况
- 操作建议（注意控制风险/可逢低关注/趋势向好适合持有等）
"""


# ── 回测分析提示词 ──

BACKTEST_ANALYSIS_SYSTEM_PROMPT = """你是一名专业的 A 股量化策略分析师，擅长解读回测结果。

请根据提供的回测数据，输出以下分析内容（**不需要任何多余的开场白**，直接按以下 Markdown 格式输出）：

【策略表现概览】
- 总收益率 / 年化收益率：xx%
- 最大回撤：xx%
- 夏普比率：xx
- 盈亏比：xx
- 胜率：xx%
- 交易次数：xx 次

【盈利特征分析】
- 平均每笔盈利/亏损金额
- 主要盈利来源（哪类信号/哪段行情）
- 主要亏损原因（止损出局/趋势反转/震荡磨损）

【策略优势】
- 策略表现最好的地方（哪些市场环境下表现好）

【策略风险】
- 策略最脆弱的地方（哪些市场环境下表现差）
- 最大回撤发生的时段和原因

【优化建议】
- 针对信号、风控、过滤等方面的具体改进建议
"""

# ── 市场复盘分析提示词 ──

MARKET_REVIEW_SYSTEM_PROMPT = """你是一名专业的 A 股市场分析师，擅长解读市场整体表现。

请根据提供的市场复盘数据，输出以下分析内容（**不需要任何多余的开场白**，直接按以下 Markdown 格式输出）：

【市场概况】
- 四大指数表现总览（上证、深证、创业板、科创板）
- 今日/近周/近三月涨跌趋势判断

【市场情绪】
- 涨跌家数比
- 涨停/跌停数量
- 整体赚钱效应

【热点方向】
- 涨幅前列板块/个股特征
- 跌幅前列板块/个股特征
- 当前市场主线风格（大盘/小盘、价值/成长）

【风险提示】
- 近期需要警惕的风险因素
- 成交量或市场广度等异常信号
"""

# ── 行业复盘分析提示词 ──

INDUSTRY_REVIEW_SYSTEM_PROMPT = """你是一名专业的 A 股行业分析师，擅长解读行业轮动数据。

请根据提供的行业复盘数据，输出以下分析内容（**不需要任何多余的开场白**，直接按以下 Markdown 格式输出）：

【行业格局总览】
- A 股主要行业分布总览
- 市值前 5 大行业

【行业轮动分析】
- 昨日涨幅领先 vs 落后行业
- 近一月涨幅领先 vs 落后行业
- 近一年涨幅领先 vs 落后行业
- 是否存在明显的行业轮动规律

【焦点行业点评】
- 对当前最热 / 最冷的 2-3 个行业做简要分析
- 这些行业的驱动因素（政策/周期/事件驱动）

【配置建议】
- 当前环境下值得关注的方向
- 需要回避的行业
"""

# ── 评分分析提示词 ──

SCORE_COMMENT_SYSTEM_PROMPT = """你是一名专业的 A 股投资策略评论员，正在对某评分体系的评价结果进行"第三方点评"。

评分体系简介：
{system_intro}

评分结果：
{score_result}

请以客观、专业的口吻，对上述评分结果进行点评分析（**不需要任何开场白**，直接输出）：

【评分体系观点】
用 1-2 句话总结该评分体系的核心逻辑和结论。

【我的评价】
- 该评分体系的合理之处（它抓住了哪些关键因素？）
- 可能的局限性（它忽略/未能反映哪些风险？）
- 综合建议（在当前市场环境下，如何看待这个评分结果？）
"""


class DeepSeekClient:
    """DeepSeek API 客户端"""

    def __init__(self, token: str = None, model: str = DEFAULT_MODEL):
        """
        :param token: DeepSeek API Key，不传则从配置读取
        :param model: 模型名称，默认 deepseek-chat
        """
        self.token = token or get_deepseek_token()
        self.model = model

    @property
    def is_ready(self) -> bool:
        """检查是否已配置 API Key"""
        return bool(self.token)

    def chat(self, system_prompt: str, user_prompt: str,
             temperature: float = 0.3, max_tokens: int = 1024,
             timeout: int = None) -> str:
        """
        调用 DeepSeek 对话 API

        :param system_prompt: 系统提示词（角色设定）
        :param user_prompt: 用户提示词（具体数据）
        :param temperature: 生成温度，0-1，越低越确定
        :param max_tokens: 最大生成 token 数
        :param timeout: 超时秒数，默认 DEFAULT_TIMEOUT
        :return: 模型回复文本
        :raises ValueError: API Key 未设置
        :raises ConnectionError: 网络/API 异常
        """
        if not self.is_ready:
            raise ValueError("DeepSeek API Key 未设置，请在设置页面配置")

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        to = timeout or DEFAULT_TIMEOUT
        try:
            resp = requests.post(
                DEEPSEEK_API_URL, headers=headers, json=payload, timeout=to
            )
            resp.raise_for_status()
            result = resp.json()
        except requests.exceptions.Timeout:
            raise ConnectionError(f"DeepSeek API 请求超时（{to}s）")
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"DeepSeek API 连接失败: {e}")
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            detail = e.response.text[:200] if e.response is not None else ""
            raise ConnectionError(f"DeepSeek API HTTP {status}: {detail}")

        choices = result.get("choices", [])
        if not choices:
            raise RuntimeError(f"DeepSeek API 返回异常: {result}")

        content = choices[0].get("message", {}).get("content", "").strip()
        return content

    # ── 快捷方法 ──

    def analyze_stock_review(self, review_data: dict) -> str:
        """
        对个股复盘数据进行 AI 技术分析

        :param review_data: StockReviewer.get_stock_review() 返回的字典
        :return: 分析结论文本（Markdown 格式）
        """
        user_prompt = self._build_review_prompt(review_data)
        return self.chat(STOCK_REVIEW_SYSTEM_PROMPT, user_prompt)

    def analyze_backtest_result(self, code: str, scorer_name: str,
                                  stats, trades_df) -> str:
        """
        对回测结果进行 AI 分析点评

        :param code: 股票代码
        :param scorer_name: 评分体系名称
        :param stats: PerformanceStats 对象
        :param trades_df: 交易记录 DataFrame
        :return: AI 分析文本
        """
        user_prompt = self._build_backtest_prompt(code, scorer_name, stats, trades_df)
        return self.chat(BACKTEST_ANALYSIS_SYSTEM_PROMPT, user_prompt)

    def analyze_market_review(self, indices: dict, sentiment: dict,
                               top_stocks: dict) -> str:
        """
        对市场复盘数据进行 AI 分析

        :param indices: get_index_performance() 返回值
        :param sentiment: get_market_sentiment() 返回值
        :param top_stocks: get_top_stocks() 返回值
        :return: AI 分析文本
        """
        user_prompt = self._build_market_review_prompt(indices, sentiment, top_stocks)
        return self.chat(MARKET_REVIEW_SYSTEM_PROMPT, user_prompt)

    def analyze_industry_review(self, review_result: dict) -> str:
        """
        对行业复盘数据进行 AI 分析

        :param review_result: IndustryReviewer.full_review() 返回值
        :return: AI 分析文本
        """
        user_prompt = self._build_industry_review_prompt(review_result)
        return self.chat(INDUSTRY_REVIEW_SYSTEM_PROMPT, user_prompt)

    # ── 内部工具 ──

    def analyze_scorer_result(self, system_name: str, system_intro: str,
                               score_result: str) -> str:
        """
        对评分体系的评价结果进行第三方 AI 点评

        :param system_name: 评分体系名称（如"巴菲特价值评分"）
        :param system_intro: 评分体系简介（核心逻辑）
        :param score_result: 评分结果的文本描述（关键指标数值）
        :return: AI 点评文本
        """
        user_prompt = f"""评分体系：{system_name}

评分体系简介：
{system_intro}

评分结果：
{score_result}

请以上述数据为准，进行第三方点评。"""
        return self.chat(SCORE_COMMENT_SYSTEM_PROMPT, user_prompt)

    @staticmethod
    def _build_backtest_prompt(code: str, scorer_name: str,
                                stats, trades_df) -> str:
        """构建回测分析的提示词"""
        lines = [
            f"## 回测数据",
            f"股票：{code}",
            f"评分体系：{scorer_name}",
            "",
            "【回测绩效指标】",
        ]

        # 从 stats 中提取关键指标
        try:
            total_return = getattr(stats, 'total_return', None) or \
                           (getattr(stats, 'total_return_pct', None))
            lines.append(f"总收益率: {total_return:+.2%}" if total_return is not None else "总收益率: N/A")
        except Exception:
            lines.append("总收益率: N/A")

        for attr, label in [
            ('annual_return', '年化收益率'),
            ('max_drawdown', '最大回撤'),
            ('sharpe_ratio', '夏普比率'),
            ('profit_loss_ratio', '盈亏比'),
            ('win_rate', '胜率'),
            ('total_trades', '交易次数'),
            ('avg_profit', '平均每笔盈利'),
            ('avg_loss', '平均每笔亏损'),
            ('profit_factor', '盈亏系数'),
        ]:
            try:
                val = getattr(stats, attr, None)
                lines.append(f"{label}: {val}")
            except Exception:
                pass

        lines.append("")
        lines.append("【交易记录摘要】")
        try:
            if trades_df is not None and len(trades_df) > 0:
                lines.append(f"共 {len(trades_df)} 笔交易")
                wins = trades_df[trades_df.get('is_win', False)] if 'is_win' in trades_df.columns else None
                if wins is not None:
                    lines.append(f"盈利交易: {len(wins)} 笔")
                # 前5笔交易
                lines.append("")
                lines.append("最近交易记录（前10笔）：")
                for i, (_, row) in enumerate(trades_df.head(10).iterrows()):
                    entry_date = row.get('entry_date', row.get('buy_date', ''))
                    exit_date = row.get('exit_date', row.get('sell_date', ''))
                    pnl = row.get('pnl', row.get('profit', ''))
                    pnl_pct = row.get('pnl_pct', row.get('profit_pct', ''))
                    exit_reason = row.get('exit_reason', '')
                    lines.append(
                        f"  {i+1}. {entry_date}~{exit_date} "
                        f"盈亏:{pnl} ({pnl_pct}) "
                        f"原因:{exit_reason}"
                    )
            else:
                lines.append("无交易记录")
        except Exception:
            lines.append("交易记录展示异常")

        return "\n".join(lines)

    @staticmethod
    def _build_market_review_prompt(indices: dict, sentiment: dict,
                                     top_stocks: dict) -> str:
        """构建市场复盘分析的提示词"""
        lines = [
            "## 市场复盘数据",
            "",
            "【四大指数表现】",
        ]

        if indices:
            for name, data in indices.items():
                today = data.get("today", "N/A")
                week = data.get("week_1", "N/A")
                month3 = data.get("month_3", "N/A")
                vol_today = data.get("volume_today", "N/A")
                vol_avg = data.get("volume_avg_3m", "N/A")
                lines.append(
                    f"{name}: 今日{today:+.2f}% "
                    f"近周{week:+.2f}% "
                    f"近3月{month3:+.2f}% "
                    f"成交{vol_today}亿(均{vol_avg}亿)"
                )
        else:
            lines.append("（数据获取失败）")

        lines.append("")
        lines.append("【市场情绪】")
        if sentiment:
            for name, data in sentiment.items():
                if isinstance(data, dict):
                    detail = "; ".join(f"{k}:{v}" for k, v in data.items())
                    lines.append(f"{name}: {detail}")
                else:
                    lines.append(f"{name}: {data}")
        else:
            lines.append("（数据获取失败）")

        lines.append("")
        lines.append("【涨跌 TOP 板块】")
        if top_stocks:
            for group, data in top_stocks.items():
                up = data.get("涨幅榜", [])[:3]
                down = data.get("跌幅榜", [])[:3]
                lines.append(f"\n{group}:")
                if up:
                    lines.append("  涨幅: " + " | ".join(
                        [f"{s.get('name','')}({s.get('pct_chg',0):+.2f}%)" for s in up]
                    ))
                if down:
                    lines.append("  跌幅: " + " | ".join(
                        [f"{s.get('name','')}({s.get('pct_chg',0):+.2f}%)" for s in down]
                    ))
        else:
            lines.append("（数据获取失败）")

        return "\n".join(lines)

    @staticmethod
    def _build_industry_review_prompt(review_result: dict) -> str:
        """构建行业复盘分析的提示词"""
        lines = [
            "## 行业复盘数据",
            "",
            f"统计日期: {review_result.get('统计日期', 'N/A')}",
            f"行业总数: {review_result.get('行业总数', 'N/A')}",
            f"A股总市值: {review_result.get('A股总市值(亿)', 'N/A')}亿",
            "",
        ]

        # 市值排名 TOP5
        top5_mv = review_result.get("市值排名TOP5", [])
        if top5_mv:
            lines.append("【市值排名 TOP5】")
            for item in top5_mv:
                lines.append(
                    f"  #{item['rank']} {item['board_name']}: "
                    f"{item['total_mv']:.2f}亿 "
                    f"(A股占比{item['mv_ratio']:.2f}%)"
                )
        else:
            lines.append("【市值排名 TOP5】（数据不可用）")

        # 热度排名
        hot = review_result.get("热度排名", {})
        for period in ["昨日", "近一月", "近一年"]:
            pd = hot.get(period, {})
            up = pd.get("涨幅TOP5", [])
            down = pd.get("跌幅TOP5", [])
            if up or down:
                lines.append(f"\n【{period} 涨跌幅排名】")
                if up:
                    lines.append("  涨幅: " + " | ".join(
                        [f"#{u['rank']} {u['board_name']}({u['change_pct']:+.2f}%)" for u in up]
                    ))
                if down:
                    lines.append("  跌幅: " + " | ".join(
                        [f"#{d['rank']} {d['board_name']}({d['change_pct']:+.2f}%)" for d in down]
                    ))

        return "\n".join(lines)

    @staticmethod
    def _build_review_prompt(data: dict) -> str:
        """构建个股复盘的提示词"""
        symbol = data.get("code", "")
        name = data.get("name", "")
        periods = data.get("periods", {})
        end_date = data.get("统计截止", "")
        financial = data.get("financial", {})

        lines = [
            f"## 个股复盘数据",
            f"股票：{symbol} {name}",
            f"统计截止：{end_date}",
            "",
        ]

        # 昨日
        yd = periods.get("昨日", {})
        if yd:
            lines.append(
                f"【昨日】开盘{yd.get('开盘','-')} "
                f"收盘{yd.get('收盘','-')} "
                f"最高{yd.get('最高','-')} 最低{yd.get('最低','-')} "
                f"涨跌幅{yd.get('涨跌幅%',0):+.2f}%"
            )

        # 多周期
        for pname, label in [("近一周", "近一周"), ("近两月", "近两月"),
                              ("近六月", "近六月"), ("近一年", "近一年")]:
            p = periods.get(pname)
            if p:
                lines.append(
                    f"【{label}】起始价{p.get('起始价','-')} "
                    f"最新价{p.get('最新价','-')} "
                    f"最高{p.get('最高','-')} 最低{p.get('最低','-')} "
                    f"涨跌幅{p.get('涨跌幅%',0):+.2f}%"
                )

        # 财务
        if financial:
            lines.append("")
            lines.append("【财务数据】")
            for k, v in financial.items():
                if v is not None:
                    lines.append(f"{k}: {v}")

        return "\n".join(lines)
