---
name: collect-blogger-updates
description: 采集财经博主动态数据。从博主列表获取最新推文、观点和股票提及。输出 blogger-updates.json。
allowed-tools: Bash(opencli:*)
---

# 博主动态采集

从配置的博主列表中采集最新推文和观点。

## 输入参数

```json
{
  "bloggers": ["博主1", "博主2"],
  "tweets_per_blogger": 5,
  "output_file": ".bonanza/runs/<run-id>/blogger-updates.json"
}
```

默认值：
- `tweets_per_blogger`: 5
- `output_file`: 自动生成

## 采集流程

1. 读取博主列表配置
2. 对每个博主调用 `opencli twitter tweets`
3. 提取推文内容、发布时间、提及股票
4. 写入 `blogger-updates.json`

## 错误处理

- 单个博主采集失败：标记 `partial`，继续其他博主
- 所有博主失败：标记 `failed`
- 浏览器会话过期：记录错误，不重试

## 输出格式

遵循 `schemas/blogger-updates.schema.json` 契约。

## 依赖

- `opencli` CLI 工具
- Twitter/X 访问权限
- 博主列表配置

## 禁止事项

- 不分析推文内容
- 不提取投资信号
- 不推荐下一步行动
