## 与GUI界面

### AI分析（trader/ai_model.py）

示例：使用线性回归模型预测股票收盘价。

```python
from trader.ai_model import StockAIModel
import pandas as pd
df = pd.read_csv('data.csv')
model = StockAIModel()
model.train(df, ["open", "high", "low"], "close")
preds = model.predict(df, ["open", "high", "low"])
print(preds)
```

### GUI界面（trader/gui_app.py）

直接运行即可启动图形界面，支持加载CSV数据并进行AI分析：

```bash
python trader/gui_app.py
```

---

easyTraser trader for python
python==3.13.3

# easyTraser

easyTraser 是一个基于 Python 的股票分析项目，支持收益率对比、形态分析、走势分析，并计划集成 AI 智能分析与可视化 GUI 页面。

## 环境要求

- Python >= 3.13.3

## 功能规划

1. **收益率对比**：对不同股票或策略的历史收益率进行对比分析。
2. **形态分析**：对股票K线形态、技术指标等进行分析。
3. **走势分析**：对股票历史走势进行统计与可视化。
4. **AI分析**：利用机器学习/深度学习模型对股票进行预测或分类，辅助投资决策。
5. **GUI页面**：提供图形化界面，方便用户交互、查看分析结果。

## 推荐项目结构

```
trader/
	__init__.py
	data.py         # 数据获取与处理
	stock_any.py    # 技术指标与策略实现
	ai_model.py     # AI模型训练与预测
	gui_app.py      # 图形界面主程序
	demo.py         # 主程序示例
```

## 依赖安装

建议使用 pip 安装相关依赖：

```bash
pip install -r requiments.txt
```

## 未来计划

- 支持更多AI模型与特征工程
- 丰富GUI交互体验
- 增加回测与实盘接口

---

欢迎贡献代码与建议！

pyinstaller -F --name "股神分析系统" --collect-all numpy trader/gui\_app.py
