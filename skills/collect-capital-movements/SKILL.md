---
name: collect-capital-movements
description: 采集资金异动数据。获取龙虎榜、大宗交易、主力资金流向等资金动向信息。输出 capital-movements.json。
allowed-tools: Bash(opencli:*)
---

# 资金异动采集

采集龙虎榜、大宗交易、主力资金流向等资金异动数据。

## 输入参数

```json
{
  "longhu_bang": true,
  "main_fund_flow": true,
  "output_file": ".bonanza/runs/<run-id>/capital-movements.json"
}
```

所有选项默认启用。

## 采集流程

### 1. 龙虎榜

调用 `opencli eastmoney longhu` 获取：
- 涨跌幅异常股票
- 机构和游资买卖情况
- 上榜原因

### 2. 主力资金流向

调用 `opencli eastmoney money-flow` 获取：
- 板块资金净流入/流出
- 个股主力资金动向

## 错误处理

- 单个数据源失败：标记 `partial`，继续其他数据源
- 所有数据源失败：标记 `failed`
- 数据为空：正常记录，标记 `complete`

## 输出格式

遵循 `capital-movements.schema.json` 契约。

## 依赖

- `opencli` CLI 工具
- 东方财富数据接口

## 禁止事项

- 不分析资金趋势
- 不判断主力意图
- 不预测资金流向
