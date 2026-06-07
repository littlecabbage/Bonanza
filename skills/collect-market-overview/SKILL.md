---
name: collect-market-overview
description: 采集市场概览数据。获取大盘指数、板块排行、热股列表等基础市场数据。输出 market-overview.json。
allowed-tools: Bash(opencli:*)
---

# 市场概览采集

采集大盘指数、板块表现、热门股票等市场基础数据。

## 输入参数

```json
{
  "indices": true,
  "sectors": true,
  "hot_stocks": true,
  "output_file": ".bonanza/runs/<run-id>/market-overview.json"
}
```

所有选项默认启用。

## 采集流程

### 1. 大盘指数

调用 `opencli eastmoney index-board` 获取：
- 上证指数 (000001)
- 深证成指 (399001)
- 创业板指 (399006)
- 科创 50 (000688)

### 2. 板块排行

调用 `opencli eastmoney sectors` 获取：
- 涨幅前 20 板块
- 板块名称、涨幅、成交额

### 3. 热门股票

调用 `opencli eastmoney hot-rank` 获取：
- 市场关注度最高的股票
- 按热度排序

## 错误处理

- 单个数据源失败：标记 `partial`，继续其他数据源
- 所有数据源失败：标记 `failed`
- 网络超时：记录错误，不重试

## 输出格式

遵循 `market-overview.schema.json` 契约。

## 依赖

- `opencli` CLI 工具
- 东方财富数据接口

## 禁止事项

- 不分析市场趋势
- 不推荐股票
- 不预测走势
