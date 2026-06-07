---
name: collect-market-sentiment
description: 采集市场情绪数据。从雪球、东方财富等平台获取热门讨论、情绪指标。输出 market-sentiment.json。
allowed-tools: Bash(opencli:*)
---

# 市场情绪采集

从雪球、东方财富等平台采集市场情绪相关数据。

## 输入参数

```json
{
  "xueqiu_hot_topics": true,
  "output_file": ".bonanza/runs/<run-id>/market-sentiment.json"
}
```

所有选项默认启用。

## 采集流程

### 1. 雪球热门话题

调用 `opencli xueqiu hot` 获取：
- 热门讨论主题
- 参与人数
- 讨论活跃度

## 错误处理

- 单个平台失败：标记 `partial`，继续其他平台
- 所有平台失败：标记 `failed`
- 登录会话过期：记录错误，不重试

## 输出格式

遵循 `market-sentiment.schema.json` 契约。

## 依赖

- `opencli` CLI 工具
- 雪球、东方财富访问权限

## 禁止事项

- 不量化情绪分数
- 不分析情绪趋势
- 不预测市场走向
