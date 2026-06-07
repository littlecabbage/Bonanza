---
name: guide-investment-workflow
description: 投资研究工作流导航和状态管理。当用户开始新任务、继续已有任务、或查询单点任务时调用。检查运行目录、数据新鲜度、已完成步骤，并推荐下一步行动。
---

# 投资研究工作流导航

判断用户请求类型并引导到合适的技能。

## 请求分类

**新任务**：用户首次表达目标，无运行目录或数据。  
**继续任务**：已有运行目录，需要检查完成状态和数据新鲜度。  
**单点任务**：用户明确指定单一操作（如"查询行情"），不创建完整报告流程。

## 运行目录结构

```text
.bonanza/runs/<YYYY-MM-DD>-<run-id>/
├── workflow-state.json
├── blogger-updates.json
├── market-overview.json
├── market-sentiment.json
├── capital-movements.json
├── market-news.json
├── investment-entities.json
├── stock-quotes.json
├── investment-signals.json
├── investment-scenarios.json
└── investment-report.html
```

## 状态检查

运行 `scripts/inspect_run.py` 检查运行目录：

```bash
python3 scripts/inspect_run.py .bonanza/runs/<run-id>
```

输出包含：
- `completed_steps`：已完成的技能列表
- `available_products`：可用的 JSON 文件
- `data_freshness`：各文件生成时间
- `recommended_next_steps`：推荐的下一步（最多 3 个）

## 下一步推荐格式

每个推荐项包含：

```json
{
  "skill": "collect-market-overview",
  "reason": "市场概览是所有分析的基础",
  "expected_output": "market-overview.json"
}
```

## 单点任务处理

以下请求直接进入对应技能，不创建运行目录：

- "查询今日板块排行" → `collect-market-overview`
- "获取这三个博主动态" → `collect-blogger-updates`
- "查询 000725 行情" → `fetch-stock-quotes`
- "从文本识别股票" → `extract-investment-entities`
- "把 JSON 渲染为 HTML" → `render-investment-report`

## 完整报告流程

新任务推荐流程：

1. `collect-market-overview` — 市场基础数据
2. `collect-blogger-updates` — 博主观点（可选）
3. `collect-market-sentiment` — 市场情绪
4. `collect-capital-movements` — 资金异动
5. `collect-market-news` — 财经快讯
6. `extract-investment-entities` — 实体识别
7. `fetch-stock-quotes` — 行情查询
8. `analyze-investment-signals` — 信号分析
9. `build-investment-scenarios` — 情景推演（可选）
10. `render-investment-report` — HTML 渲染

每轮只执行一个技能，完成后由 agent 展示结果并请求用户确认下一步。

## 数据新鲜度

数据超过 4 小时视为过期，需要重新采集。检查 `workflow-state.json` 中的 `generated_at` 字段。

## 禁止事项

- 不执行任何市场数据采集。
- 不分析投资信号。
- 不渲染报告。
- 不自动执行完整流程。
- 不创建新的工作流引擎或数据库。

## 输出格式

导航技能返回结构化 JSON：

```json
{
  "task_type": "new | continue | single",
  "current_state": {
    "completed_steps": [],
    "available_products": {},
    "data_freshness": {}
  },
  "recommended_next": [
    {
      "skill": "collect-market-overview",
      "reason": "市场概览是分析基础",
      "expected_output": "market-overview.json"
    }
  ],
  "single_skill_direct": null
}
```
