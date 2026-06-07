---
name: analyze-investment-signals
description: 综合信号分析。从多维度数据提取投资信号，生成证据驱动分析。输出 investment-signals.json。
allowed-tools: Bash(python3:*)
---
# 综合信号分析
输入: 市场概览、行情、资金、博主、情绪、新闻等 JSON 文件路径
输出: investment-signals.json

## 工作流程

1. **输入收集**：读取各采集技能输出的 JSON 文件
2. **维度分析**：从价格、资金、情绪、事件四个维度提取信号
3. **证据聚合**：每个维度整理支持性证据和反对性证据
4. **置信度评估**：基于数据覆盖率和信号一致性计算置信度
5. **输出结构化**：生成符合 schema 的 JSON 输出

## 输入格式

```bash
python3 analyze_signals.py <overview.json> [quotes.json] [capital.json] [blogger.json] [sentiment.json] [news.json] [output.json]
```

各参数为可选 JSON 文件路径，程序自动检测并读取可用文件。最后一个参数为输出文件路径。

## 输出格式

生成 `investment-signals.json`，符合 `investment-signals.schema.json`：

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-06-07T16:00:00+08:00",
  "status": "complete",
  "source": {
    "skill": "analyze-investment-signals",
    "commands": ["python3 analyze_signals.py overview.json quotes.json"]
  },
  "coverage": {
    "requested": 6,
    "succeeded": 4,
    "failed": 2
  },
  "errors": [],
  "data": {
    "dimensions": [
      {
        "name": "price",
        "supporting_evidence": [...],
        "opposing_evidence": [...],
        "missing_data": [...],
        "conclusion": "..."
      }
    ],
    "confidence": "medium",
    "失效条件": [...],
    "coverage_rate": 0.75
  }
}
```

## 错误处理

- 文件不存在或格式错误：标记为 failed，不中断其他维度
- 所有文件无法读取：返回 failed 状态
- 部分维度无数据：coverage_rate 降低，confidence 相应下调

## 依赖

- Python 3.8+

## 限制

- 不输出强烈买入建议
- 不给个性化仓位
- 不承诺收益