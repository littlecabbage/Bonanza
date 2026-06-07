---
name: render-investment-report
description: 确定性 HTML 渲染。将 JSON 产物渲染为深色主题 HTML 报告。输出 investment-report.html。
allowed-tools: Bash(python3:*)
---

# 投资报告渲染

将采集和分析阶段生成的 JSON 产物渲染为深色主题的确定性 HTML 投资报告。

## 产物文件

- `investment-report.html`: 最终渲染的 HTML 报告

## 依赖

- Python 3.8+
- `assets/report-template.html`: HTML 渲染模板
- 输入 JSON 文件（market-overview.json, investment-signals.json, investment-scenarios.json）

## CSS 类命名

- `.advice-strong-buy`: 强烈买入建议（红色）
- `.advice-buy`: 买入建议（黄色）
- `.advice-hold`: 持有建议（灰色）
- `.advice-sell`: 卖出建议（绿色）
- `.badge-market-a`: A 股市场徽标（红色）
- `.badge-market-us`: 美股市场徽标（蓝色）
- `.badge-market-hk`: 港股市场徽标（绿色）