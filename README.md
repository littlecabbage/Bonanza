# Bonanza

**模块化投资研究 Skill 集合** — 由 Agent 编排、单点 Skill 执行的多步投资分析工具。

> money loves me

## 架构

```text
用户提出目标 → Agent 判断场景、维护状态
        ↓
  Agent 选择 Skill → 单点 Skill 返回结构化产物
        ↓
  Agent 验收结果 → 推荐下一步
```

每个 Skill 只完成一个明确任务，Agent 每轮默认只调用一个 Skill。

## Skill 清单

| Skill | 职责 | 状态 |
|-------|------|------|
| `guide-investment-workflow` | 流程导航与状态管理 | ✅ 已创建 |
| `collect-blogger-updates` | 博主动态采集 | ✅ 已创建 |
| `collect-market-overview` | 市场概览采集 | ✅ 已创建 |
| `collect-market-sentiment` | 市场情绪采集 | ✅ 已创建 |
| `collect-capital-movements` | 资金异动采集 | ✅ 已创建 |
| `collect-market-news` | 财经快讯采集 | ✅ 已创建 |
| `extract-investment-entities` | 投资实体识别 | ✅ 已创建 |
| `fetch-stock-quotes` | 行情查询 | ✅ 已创建 |
| `analyze-investment-signals` | 综合信号分析 | 🔲 待建 |
| `build-investment-scenarios` | 可选情景推演 | 🔲 待建 |
| `render-investment-report` | 确定性 HTML 渲染 | 🔲 待建 |

## 运行目录结构

所有产物写入 `.bonanza/runs/<YYYY-MM-DD>-<run-id>/`：

```text
.bonanza/runs/<YYYY-MM-DD>-<run-id>/
├── workflow-state.json        ← 流程状态
├── blogger-updates.json       ← 博主动态
├── market-overview.json       ← 市场概览
├── market-sentiment.json      ← 市场情绪
├── capital-movements.json     ← 资金异动
├── market-news.json           ← 财经快讯
├── investment-entities.json   ← 投资实体
├── stock-quotes.json          ← 行情数据
├── investment-signals.json    ← 综合信号
├── investment-scenarios.json  ← 情景推演
└── investment-report.html     ← 最终报告
```

## 数据契约

所有 JSON 产物遵循统一顶层契约：

```json
{
  "schema_version": "1.0",
  "generated_at": "<ISO 8601 with timezone>",
  "status": "complete | partial | failed",
  "source": { "skill": "<skill-name>", "commands": [] },
  "coverage": { "requested": 0, "succeeded": 0, "failed": 0 },
  "errors": [],
  "data": {}
}
```

JSON Schema 定义位于 `schemas/` 目录，每个 Skill 对应一个 schema 文件。

## 验证命令

```bash
# 仓库级测试
python3 -m unittest discover -s tests -v

# 仓库结构验证
python3 scripts/validate_repository.py

# 单个 Skill 验证
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/<skill-name>
```
