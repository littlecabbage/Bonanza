---
name: build-investment-scenarios
description: 可选情景推演。构建看多/中性/看空三情景。不产生个性化仓位。输出 investment-scenarios.json。
allowed-tools: Bash(python3:*)
---

# 投资情景推演

根据投资信号文件，构建三种市场情景（看多、中性、看空），辅助投资决策。

## 工作流程

1. **输入解析**：读取 investment-signals.json
2. **情景构建**：基于信号分析结果生成三种情景
3. **条件约束**：根据缺失数据调整输出内容
4. **输出结构化**：生成符合 schema 的 JSON 输出

## 输入

- `investment-signals.json`：分析信号结果文件路径（必需）
- `--timeframe`：时间范围（必需）
- `--risk-tolerance`：风险承受能力（可选）

## 输出

生成 `investment-scenarios.json`，符合 `schemas/investment-scenarios.schema.json`。

## 约束

- 不产生个性化仓位
- 缺少行情不生成价格区间