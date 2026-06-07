# 投资研究工作流参考

## 技能依赖关系

```text
collect-market-overview ──┐
collect-blogger-updates ──┤
collect-market-sentiment ──┼──→ extract-investment-entities ──→ fetch-stock-quotes
collect-capital-movements ─┤                                         │
collect-market-news ───────┘                                         ↓
                                                              analyze-investment-signals
                                                                         │
                                                                         ↓
                                                              build-investment-scenarios (可选)
                                                                         │
                                                                         ↓
                                                              render-investment-report
```

## 技能列表

| 技能 | 类型 | 必需 | 输出文件 |
|------|------|------|----------|
| `collect-market-overview` | 采集 | 是 | `market-overview.json` |
| `collect-blogger-updates` | 采集 | 否 | `blogger-updates.json` |
| `collect-market-sentiment` | 采集 | 否 | `market-sentiment.json` |
| `collect-capital-movements` | 采集 | 否 | `capital-movements.json` |
| `collect-market-news` | 采集 | 否 | `market-news.json` |
| `extract-investment-entities` | 处理 | 是 | `investment-entities.json` |
| `fetch-stock-quotes` | 查询 | 是 | `stock-quotes.json` |
| `analyze-investment-signals` | 分析 | 是 | `investment-signals.json` |
| `build-investment-scenarios` | 分析 | 否 | `investment-scenarios.json` |
| `render-investment-report` | 输出 | 是 | `investment-report.html` |

## 最小完整流程

最简报告只需要：

1. `collect-market-overview` → 市场基础数据
2. `extract-investment-entities` → 实体识别
3. `fetch-stock-quotes` → 行情查询
4. `analyze-investment-signals` → 信号分析
5. `render-investment-report` → HTML 渲染

## 数据新鲜度策略

- 数据生成时间超过 4 小时视为过期
- 过期数据需要重新采集
- 检查 `workflow-state.json` 中的 `generated_at` 字段
- 时区格式：`2026-06-07T10:00:00+08:00`

## 单点任务示例

### 查询板块排行

用户：「查询今日 A 股板块排行」

直接调用 `collect-market-overview`，参数 `sectors=true`，不创建运行目录。

### 查询股票行情

用户：「查询 000725 和 300476 的行情」

直接调用 `fetch-stock-quotes`，参数 `stocks=["000725", "300476"]`。

### 识别股票实体

用户：「从这些博主动态中识别股票」

直接调用 `extract-investment-entities`，输入文本或 JSON 文件。

### 渲染现有数据

用户：「把 .bonanza/runs/2026-06-07-001/ 下的 JSON 渲染为 HTML」

直接调用 `render-investment-report`，指定输入目录。

## 错误处理

### 部分失败

如果某个采集技能失败，继续执行其他步骤。在 `workflow-state.json` 中记录失败原因。

### 数据缺失

分析技能需要至少 1 个有效数据源。如果所有采集都失败，提示用户重新采集。

### 渲染失败

检查所有必需文件是否存在，JSON 格式是否正确。
