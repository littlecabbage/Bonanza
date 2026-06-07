---
name: extract-investment-entities
description: 从文本或JSON数据中提取投资实体（股票、基金、行业、概念等）。支持从博主动态、新闻、讨论等多种来源识别实体。输出 investment-entities.json。
---

# 投资实体识别

从文本数据中识别投资相关的实体，包括股票代码、公司名称、行业板块、概念主题等。

## 工作流程

1. **输入解析**：接受纯文本或JSON格式的采集数据
2. **实体识别**：使用规则库和参考数据匹配实体
3. **实体标准化**：将识别的实体映射到标准代码
4. **输出结构化**：生成符合 schema 的 JSON 输出

## 输入格式

### 纯文本输入

```
文本内容，包含股票名称、行业、概念等
```

### JSON 输入

```json
{
  "source": "blogger-updates",
  "data": {
    "bloggers": [
      {
        "username": "...",
        "tweets": [
          {"text": "..."}
        ]
      }
    ]
  }
}
```

## 识别规则

### 股票识别

- 匹配 `references/stock-codes.json` 中的股票名称和代码
- 支持中文名称、股票代码、拼音缩写
- 支持 A 股、港股、美股

### 行业识别

- 匹配常见行业关键词
- 映射到申万行业分类

### 概念识别

- 匹配热点概念、政策主题
- 映射到东方财富概念板块

## 输出格式

生成 `investment-entities.json`，符合 `schemas/investment-entities.schema.json`：

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-06-07T14:00:00+08:00",
  "status": "complete",
  "source": {
    "skill": "extract-investment-entities",
    "commands": []
  },
  "coverage": {
    "requested": 1,
    "succeeded": 1,
    "failed": 0
  },
  "errors": [],
  "data": {
    "entities": [
      {
        "name": "腾讯控股",
        "code": "0700",
        "type": "stock",
        "market": "hk",
        "confidence": 0.95,
        "mentions": 3
      }
    ]
  }
}
```

## 参考数据

- `references/stock-codes.json`：股票代码映射表
- 内置行业关键词库
- 内置概念关键词库

## 错误处理

- 无法识别的实体：跳过，不报错
- 多个匹配：选择置信度最高的
- 数据格式错误：返回 failed 状态

## 依赖

- Python 3.8+
- `references/stock-codes.json`
