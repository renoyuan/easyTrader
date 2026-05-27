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

    # ── 内部工具 ──

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
