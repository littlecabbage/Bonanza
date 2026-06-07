---
name: collect-market-news
description: 采集市场新闻数据。获取财经快讯、政策新闻、行业动态等新闻信息。输出 market-news.json。
allowed-tools: Bash(opencli:*)
---

# 市场新闻采集

采集财经快讯、政策新闻、行业动态等市场相关新闻。

## 输入参数

```json
{
  "eastmoney_kuaixun": true,
  "output_file": ".bonanza/runs/<run-id>/market-news.json"
}
```

所有选项默认启用。

## 采集流程

### 1. 东方财富快讯

调用 `opencli eastmoney kuaixun` 获取：
- 实时财经快讯
- 重要公告
- 市场动态

## 错误处理

- 单个数据源失败：标记 `partial`，继续其他数据源
- 所有数据源失败：标记 `failed`
- 内容为空：正常记录，标记 `complete`

## 输出格式

遵循 `market-news.schema.json` 契约。

## 依赖

- `opencli` CLI 工具
- 东方财富新闻接口

## 禁止事项

- 不分析新闻影响
- 不评估重要性
- 不预测市场反应
